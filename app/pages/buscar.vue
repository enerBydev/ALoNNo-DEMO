<script setup lang="ts">
// FLUJO 1 · «find a person». El corazon de la demo.
import frases from '../../db/frases.json'
useSeoMeta({ title: 'Search — ALoNNo demo' })

const { sesion } = useSesion()
const ruta = useRoute()
const consulta = ref(String(ruta.query.q ?? ''))
const cargando = ref(false)
const error = ref<string | null>(null)
const datos = ref<any>(null)
const abierto = ref<Record<string, boolean>>({})
const verDescartados = ref(false)

const ARQUETIPOS: Record<string, string> = {
  plan_seeks_person: 'You have a plan and you are looking for a person',
  plan_seeks_plan: 'You have a plan and you are looking for a matching plan',
  intent_seeks_any: 'You are looking for something to do — and someone to do it with',
  standing_interest: 'You are looking for people with the same interest, no fixed date',
}

async function buscar(frase?: string) {
  const q = (frase ?? consulta.value).trim()
  if (!q || cargando.value) return
  consulta.value = q
  cargando.value = true; error.value = null
  // La busqueda queda en la URL: es enlazable y se puede recargar. Es lo que hace posible
  // ense~narla en una llamada sin volver a teclearla.
  navigateTo({ query: { q } }, { replace: true })
  try {
    datos.value = await $fetch('/api/buscar', { query: { q } })
    abierto.value = {}; verDescartados.value = false
  } catch (e: any) {
    error.value = e?.data?.statusMessage || e?.statusMessage || 'the search failed'
    datos.value = null
  } finally { cargando.value = false }
}
if (consulta.value) await buscar()

const fecha = (iso: string | null) => iso
  ? new Date(iso).toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })
  : null
const enlace = (r: any) => r.tipo === 'PLAN' ? `/plan/${r.id}` : `/persona/${r.id}`
</script>

<template>
  <div class="contenedor">
    <div class="cabecera">
      <h1>Say what you are planning</h1>
      <p class="tenue">No filters. One sentence, in German or English.</p>
    </div>

    <form class="buscador" @submit.prevent="buscar()">
      <textarea v-model="consulta" rows="2" placeholder="I have a spare ticket for…"
                @keydown.meta.enter="buscar()" @keydown.ctrl.enter="buscar()" />
      <button class="boton" :disabled="cargando || !consulta.trim()">
        <span v-if="cargando" class="cargando" />{{ cargando ? 'Searching…' : 'Search' }}
      </button>
    </form>

    <details class="ejemplos" :open="!datos">
      <summary class="pequeno">Helder's ten sentences — click any of them</summary>
      <ul>
        <li v-for="f in frases" :key="f.escenario">
          <button :disabled="cargando" @click="buscar(f.frase_de_helder)">
            <span class="etiqueta gris">{{ /[äöüßÄÖÜ]|^Ich|^Meine/.test(f.frase_de_helder) ? 'DE' : 'EN' }}</span>
            {{ f.frase_de_helder }}
          </button>
        </li>
      </ul>
    </details>

    <p v-if="error" class="tarjeta error">{{ error }}</p>

    <div v-if="cargando && !datos" class="tarjeta tenue esperando">
      <span class="cargando" /> Understanding the sentence, filtering, ranking…
    </div>

    <template v-if="datos">
      <!-- «Asi lo entendi»: el usuario no configura, corrige. -->
      <section class="tarjeta entendido">
        <div class="fila-titulo">
          <h2>{{ ARQUETIPOS[datos.intencion.archetype] ?? datos.intencion.archetype }}</h2>
          <span class="etiqueta">understood</span>
        </div>
        <div class="chips">
          <span v-if="datos.intencion.city" class="chip">📍 {{ datos.intencion.city }}</span>
          <span v-if="datos.intencion.dest_city" class="chip">✈️ {{ datos.intencion.dest_city }}</span>
          <span class="chip">🗓 {{ datos.ventana.etiqueta }}</span>
          <span v-if="datos.intencion.category" class="chip">{{ datos.intencion.category.replace('_', ' ') }}</span>
          <span v-if="datos.intencion.subject" class="chip">🎟 {{ datos.intencion.subject }}</span>
          <span class="chip">{{ datos.intencion.language.toUpperCase() }}</span>
        </div>
        <p v-if="datos.degradado" class="minusculo aviso">
          The language model did not answer in time, so this reading comes from fallback rules.
          Rougher than usual — and we say so instead of hiding it.
        </p>
      </section>

      <div class="fila-titulo" style="margin:1.6rem 0 .6rem">
        <h2>{{ datos.totales.mostrados }} of {{ datos.totales.candidatos }} candidates</h2>
        <span class="minusculo tenue">ranked by a number you can check</span>
      </div>

      <article v-for="r in datos.resultados" :key="r.id" class="tarjeta resultado">
        <div class="izq">
          <div class="puntuacion">{{ r.porcentaje }}<span class="pc">%</span></div>
          <div class="barra"><i :style="{ width: r.porcentaje + '%' }" /></div>
        </div>
        <div class="der">
          <div class="fila-titulo">
            <span class="etiqueta" :class="{ gris: r.tipo === 'PERSONA' }">{{ r.tipo }}</span>
            <NuxtLink :to="enlace(r)"><h3>{{ r.titulo }}</h3></NuxtLink>
            <span class="etiqueta gris">{{ r.idioma.toUpperCase() }}</span>
          </div>
          <p class="minusculo tenue meta">
            <template v-if="r.ciudad">{{ r.ciudad }}</template>
            <template v-if="r.km !== null"> · {{ r.km.toFixed(1) }} km</template>
            <template v-if="r.cuando"> · {{ fecha(r.cuando) }}</template>
            <template v-if="r.plazas !== null">
              · {{ r.plazas > 0 ? `${r.plazas} seat${r.plazas === 1 ? '' : 's'} free` : 'full' }}
            </template>
          </p>
          <p v-if="r.explicacion" class="explicacion">{{ r.explicacion }}</p>
          <p class="pequeno tenue recorte">{{ r.subtitulo }}</p>

          <button class="mas minusculo" @click="abierto[r.id] = !abierto[r.id]">
            {{ abierto[r.id] ? '−' : '+' }} Where does {{ r.porcentaje }}% come from?
          </button>
          <table v-if="abierto[r.id]" class="minusculo">
            <tr v-for="c in r.componentes" :key="c.nombre">
              <td>{{ c.etiqueta_en }}<em v-if="c.detalle"> · {{ c.detalle }}</em></td>
              <td class="n">{{ c.valor.toFixed(2) }}</td>
              <td class="n tenue">×{{ c.peso.toFixed(2) }}</td>
              <td class="n"><b>+{{ Math.round(c.puntos) }}</b></td>
            </tr>
            <tr class="suma"><td colspan="3">adds up to</td><td class="n"><b>{{ r.porcentaje }}%</b></td></tr>
          </table>
        </div>
      </article>

      <section v-if="datos.descartados.length" style="margin-top:1rem">
        <button class="mas pequeno" @click="verDescartados = !verDescartados">
          {{ verDescartados ? '−' : '+' }} Ruled out, and why ({{ datos.totales.descartados }})
        </button>
        <ul v-if="verDescartados" class="descartados pequeno tenue">
          <li v-for="r in datos.descartados" :key="r.id">
            <b>{{ r.porcentaje }}%</b> {{ r.titulo }} — <i>{{ r.motivo_descarte }}</i>
          </li>
        </ul>
      </section>

      <!-- Donde se va el tiempo. La seccion E de la propuesta, hecha visible. -->
      <p class="minusculo tenue tiempos">
        {{ datos.tiempos.total }} ms —
        <b>LLM {{ datos.tiempos.capa_0_llm + datos.tiempos.capa_4_llm }}</b> ·
        embedding {{ datos.tiempos.embedding }} ·
        Postgres {{ datos.tiempos.capa_1_2_postgres }} · scoring &lt;1.
        The expensive part is the model, and it only runs twice: once to read your sentence, once
        to phrase what you see.
      </p>
    </template>
  </div>
</template>

<style scoped>
.cabecera { margin-bottom: 1.1rem; }
.buscador { display: flex; gap: .6rem; align-items: stretch; }
.buscador textarea { resize: vertical; }
.buscador .boton { white-space: nowrap; }
.ejemplos { margin: .9rem 0 1.4rem; }
.ejemplos summary { cursor: pointer; color: var(--tenue); }
.ejemplos ul { list-style: none; margin: .7rem 0 0; padding: 0; display: grid; gap: .3rem; }
.ejemplos button { width: 100%; text-align: left; font: inherit; font-size: .85rem;
  background: var(--papel-2); border: 1px solid var(--linea); border-radius: 9px;
  padding: .5rem .65rem; cursor: pointer; color: inherit; display: flex; gap: .5rem;
  align-items: flex-start; }
.ejemplos button:hover:not(:disabled) { border-color: var(--acento); }
.ejemplos .etiqueta { flex: none; }
.esperando, .error { margin: 1rem 0; }
.error { border-color: #dc2626; color: #dc2626; }
.entendido { border-left: 3px solid var(--acento); }
.fila-titulo { display: flex; align-items: center; gap: .5rem; flex-wrap: wrap; }
.chips { display: flex; flex-wrap: wrap; gap: .35rem; margin-top: .6rem; }
.chip { font-size: .8rem; background: var(--papel); border: 1px solid var(--linea);
  border-radius: 20px; padding: .18rem .6rem; }
.aviso { margin-top: .6rem; color: var(--acento); }
.resultado { display: flex; gap: 1rem; margin-bottom: .7rem; }
.izq { width: 76px; flex: none; }
.pc { font-size: .95rem; font-weight: 600; }
.izq .barra { margin-top: .35rem; }
.der { min-width: 0; flex: 1; }
.der h3 { display: inline; }
.der a { text-decoration: none; }
.der a:hover h3 { color: var(--acento); }
.meta { margin: .25rem 0 .4rem; }
.explicacion { margin-bottom: .25rem; }
.recorte { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden; }
.mas { background: none; border: none; padding: .3rem 0 0; color: var(--tenue); cursor: pointer;
  font: inherit; text-decoration: underline; }
table { width: 100%; border-collapse: collapse; margin-top: .5rem; }
td { padding: .22rem .3rem; border-bottom: 1px solid var(--linea); }
td em { color: var(--tenue); font-style: normal; }
.n { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.suma td { border: none; padding-top: .4rem; }
.descartados { list-style: none; padding: .4rem 0 0; }
.tiempos { margin-top: 1.6rem; border-top: 1px solid var(--linea); padding-top: .7rem; }
</style>
