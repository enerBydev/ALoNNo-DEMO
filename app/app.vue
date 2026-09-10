<script setup lang="ts">
// La UI del §10, deliberadamente minima: Helder dijo que el diseno no tiene que ser sofisticado
// y que le interesa «la calidad e inteligencia del emparejamiento». Un textarea, sus frases, y
// resultados que se puedan auditar.
//
// **NO HAY SELECTOR DE MODO.** El sistema deduce el arquetipo (§2.4). Pedirle al usuario que
// elija ES un filtro, y Helder dijo textual que no quiere filtros.
import frases from '../db/frases.json'

type Componente = {
  nombre: string; etiqueta_de: string; etiqueta_en: string
  crudo: number; valor: number; peso: number; puntos: number; detalle?: string
}
type Resultado = {
  tipo: 'PERSONA' | 'PLAN'; id: string; titulo: string; subtitulo: string; idioma: string
  ciudad: string | null; km: number | null; porcentaje: number; explicacion: string | null
  componentes: Componente[]; motivo_descarte: string | null; cuando: string | null; plazas: number | null
}
type Respuesta = {
  consulta: string; degradado: boolean; intencion: any; ventana: any
  resultados: Resultado[]; descartados: Resultado[]; totales: any; tiempos: any; tokens: any
}

const T = {
  de: {
    titulo: 'Wer passt zu meinem Plan?',
    entrada: 'Schreib einen Satz. Keine Filter.',
    buscar: 'Suchen', buscando: 'Sucht…',
    ejemplos: 'Deine zehn Sätze — zum Anklicken',
    entendido: 'So habe ich das verstanden',
    resultados: 'Ergebnisse', descartados: 'Aussortiert — und warum',
    desglose: 'Woher kommt die Zahl?', componente: 'Komponente', valor: 'Wert', punkte: 'Punkte',
    nadie: 'Nichts gefunden.', libre: 'frei', plaza: 'Platz frei', plazas: 'Plätze frei', sinPlaza: 'ausgebucht',
    arquetipos: {
      plan_seeks_person: 'Du hast einen Plan und suchst jemanden',
      plan_seeks_plan: 'Du hast einen Plan und suchst einen passenden Plan',
      intent_seeks_any: 'Du suchst etwas zu tun — und jemanden dafür',
      standing_interest: 'Du suchst Leute mit demselben Interesse, ohne festes Datum',
    } as Record<string, string>,
  },
  en: {
    titulo: 'This is my plan. Who fits?',
    entrada: 'Write one sentence. No filters.',
    buscar: 'Search', buscando: 'Searching…',
    ejemplos: 'Your ten sentences — click any of them',
    entendido: 'This is how I understood it',
    resultados: 'Results', descartados: 'Ruled out — and why',
    desglose: 'Where does the number come from?', componente: 'Component', valor: 'Value', punkte: 'Points',
    nadie: 'Nothing found.', libre: 'free', plaza: 'seat free', plazas: 'seats free', sinPlaza: 'full',
    arquetipos: {
      plan_seeks_person: 'You have a plan and you are looking for a person',
      plan_seeks_plan: 'You have a plan and you are looking for a matching plan',
      intent_seeks_any: 'You are looking for something to do — and someone to do it with',
      standing_interest: 'You are looking for people with the same interest, no fixed date',
    } as Record<string, string>,
  },
}

const idioma = ref<'de' | 'en'>('en')
const t = computed(() => T[idioma.value])
const consulta = ref('')
const cargando = ref(false)
const error = ref<string | null>(null)
const datos = ref<Respuesta | null>(null)
const abierto = ref<Record<string, boolean>>({})
const verDescartados = ref(false)

async function buscar(frase?: string) {
  const q = (frase ?? consulta.value).trim()
  if (!q || cargando.value) return
  consulta.value = q
  cargando.value = true
  error.value = null
  try {
    datos.value = await $fetch<Respuesta>('/api/buscar', { query: { q } })
    abierto.value = {}
    verDescartados.value = false
  } catch (e: any) {
    error.value = e?.statusMessage || e?.message || 'no se pudo buscar'
    datos.value = null
  } finally {
    cargando.value = false
  }
}

const fecha = (iso: string | null) =>
  iso ? new Date(iso).toLocaleDateString(idioma.value === 'de' ? 'de-DE' : 'en-GB',
    { weekday: 'short', day: 'numeric', month: 'short' }) : null
</script>

<template>
  <main>
    <header>
      <h1>{{ t.titulo }}</h1>
      <div class="idiomas">
        <button :class="{ on: idioma === 'de' }" @click="idioma = 'de'">DE</button>
        <button :class="{ on: idioma === 'en' }" @click="idioma = 'en'">EN</button>
      </div>
    </header>

    <!-- Un textarea, y nada mas. Sin toggle de modo: el sistema deduce el arquetipo. -->
    <form @submit.prevent="buscar()">
      <textarea v-model="consulta" :placeholder="t.entrada" rows="3" @keydown.meta.enter="buscar()" />
      <button type="submit" :disabled="cargando || !consulta.trim()">
        {{ cargando ? t.buscando : t.buscar }}
      </button>
    </form>

    <!-- Las 10 frases de Helder, VERBATIM y clicables (regla 4). Que reconozca las suyas. -->
    <section class="ejemplos">
      <h2>{{ t.ejemplos }}</h2>
      <ul>
        <li v-for="f in frases" :key="f.escenario">
          <button @click="buscar(f.frase_de_helder)" :disabled="cargando">
            <span class="bandera">{{ /[äöüßÄÖÜ]|^Ich|^Meine/.test(f.frase_de_helder) ? 'DE' : 'EN' }}</span>
            {{ f.frase_de_helder }}
          </button>
        </li>
      </ul>
    </section>

    <p v-if="error" class="error">{{ error }}</p>

    <template v-if="datos">
      <!-- El panel «asi lo entendi»: la respuesta de producto a «no quiero llenar 20 filtros».
           El usuario no configura: corrige. -->
      <section class="entendido">
        <h2>{{ t.entendido }}</h2>
        <p class="arquetipo">{{ t.arquetipos[datos.intencion.archetype] ?? datos.intencion.archetype }}</p>
        <dl>
          <template v-if="datos.intencion.city"><dt>Stadt / City</dt><dd>{{ datos.intencion.city }}</dd></template>
          <template v-if="datos.intencion.dest_city"><dt>Ziel / Destination</dt><dd>{{ datos.intencion.dest_city }}</dd></template>
          <template v-if="datos.intencion.category"><dt>Art / Category</dt><dd>{{ datos.intencion.category }}</dd></template>
          <template v-if="datos.intencion.subject"><dt>Thema / Subject</dt><dd>{{ datos.intencion.subject }}</dd></template>
          <dt>Wann / When</dt><dd>{{ datos.ventana.etiqueta }}</dd>
        </dl>
        <p v-if="datos.degradado" class="aviso">
          The language model did not answer: this reading comes from fallback rules, so it is
          rougher than usual.
        </p>
      </section>

      <section>
        <h2>{{ t.resultados }} <small>{{ datos.totales.mostrados }}/{{ datos.totales.candidatos }}</small></h2>
        <p v-if="!datos.resultados.length">{{ t.nadie }}</p>
        <article v-for="r in datos.resultados" :key="r.id">
          <div class="cabeza">
            <!-- Etiquetado por tipo: en los arquetipos 3 y 4 la lista viene mezclada a proposito -->
            <span class="tipo" :class="r.tipo.toLowerCase()">{{ r.tipo }}</span>
            <span class="pct">{{ r.porcentaje }}%</span>
            <h3>{{ r.titulo }}</h3>
            <span class="meta">
              <span class="lang">{{ r.idioma.toUpperCase() }}</span>
              <template v-if="r.ciudad"> · {{ r.ciudad }}</template>
              <template v-if="r.km !== null"> · {{ r.km.toFixed(1) }} km</template>
              <template v-if="r.cuando"> · {{ fecha(r.cuando) }}</template>
              <template v-if="r.plazas !== null">
                · {{ r.plazas > 0 ? `${r.plazas} ${r.plazas === 1 ? t.plaza : t.plazas}` : t.sinPlaza }}
              </template>
            </span>
          </div>
          <p class="explicacion" v-if="r.explicacion">{{ r.explicacion }}</p>
          <p class="sub">{{ r.subtitulo }}</p>

          <!-- El desglose completo: es lo que hace verificable el numero, y lo que la propuesta
               prometio por escrito. -->
          <button class="mas" @click="abierto[r.id] = !abierto[r.id]">
            {{ abierto[r.id] ? '−' : '+' }} {{ t.desglose }}
          </button>
          <table v-if="abierto[r.id]">
            <thead><tr><th>{{ t.componente }}</th><th>{{ t.valor }}</th><th>×</th><th>{{ t.punkte }}</th></tr></thead>
            <tbody>
              <tr v-for="c in r.componentes" :key="c.nombre">
                <td>
                  {{ idioma === 'de' ? c.etiqueta_de : c.etiqueta_en }}
                  <small v-if="c.detalle">{{ c.detalle }}</small>
                </td>
                <td>{{ c.valor.toFixed(2) }}</td>
                <td>{{ c.peso.toFixed(2) }}</td>
                <td><b>+{{ Math.round(c.puntos) }}</b></td>
              </tr>
            </tbody>
            <tfoot><tr><td colspan="3">=</td><td><b>{{ r.porcentaje }}%</b></td></tr></tfoot>
          </table>
        </article>
      </section>

      <!-- «Ver descartados»: los near-miss prueban que el ranking discrimina, no solo que
           devuelve filas. -->
      <section v-if="datos.descartados.length">
        <button class="mas" @click="verDescartados = !verDescartados">
          {{ verDescartados ? '−' : '+' }} {{ t.descartados }} ({{ datos.totales.descartados }})
        </button>
        <ul v-if="verDescartados" class="descartados">
          <li v-for="r in datos.descartados" :key="r.id">
            <b>{{ r.porcentaje }}%</b> {{ r.titulo }} — <i>{{ r.motivo_descarte }}</i>
          </li>
        </ul>
      </section>

      <!-- El desglose por capa, no un numero suelto: ense~na DONDE se va el tiempo, que es el
           argumento de costes de la propuesta hecho visible. -->
      <p class="tiempos">
        {{ datos.tiempos.total }} ms —
        LLM {{ datos.tiempos.capa_0_llm + datos.tiempos.capa_4_llm }} ·
        embedding {{ datos.tiempos.embedding }} ·
        Postgres {{ datos.tiempos.capa_1_2_postgres }} ·
        scoring &lt;1
      </p>
    </template>

    <footer>DEMO · synthetic data · no real personal data · enerBydev</footer>
  </main>
</template>

<style>
:root { color-scheme: light dark; --linea: #8883; --tenue: #8888; }
* { box-sizing: border-box; }
body { margin: 0; font: 15px/1.55 system-ui, -apple-system, sans-serif; }
main { max-width: 46rem; margin: 0 auto; padding: 2rem 1.25rem 4rem; }
header { display: flex; align-items: baseline; justify-content: space-between; gap: 1rem; }
h1 { font-size: 1.5rem; margin: 0 0 1.25rem; }
h2 { font-size: .82rem; text-transform: uppercase; letter-spacing: .07em; color: var(--tenue);
     margin: 2rem 0 .6rem; font-weight: 600; }
h2 small { text-transform: none; letter-spacing: 0; font-weight: 400; }
h3 { margin: 0; font-size: 1rem; flex: 1 1 100%; order: 3; }
.idiomas button { border: 1px solid var(--linea); background: none; color: inherit;
  padding: .2rem .5rem; cursor: pointer; font: inherit; font-size: .8rem; }
.idiomas button.on { background: currentColor; color: Canvas; }
form { display: flex; gap: .5rem; align-items: flex-start; }
textarea { flex: 1; font: inherit; padding: .7rem; border: 1px solid var(--linea);
  background: none; color: inherit; border-radius: 3px; resize: vertical; }
form > button { padding: .7rem 1.1rem; font: inherit; cursor: pointer; border: 1px solid currentColor;
  background: currentColor; color: Canvas; border-radius: 3px; }
form > button:disabled { opacity: .45; cursor: default; }
.ejemplos ul { list-style: none; margin: 0; padding: 0; display: grid; gap: .3rem; }
.ejemplos button { text-align: left; width: 100%; font: inherit; font-size: .84rem;
  background: none; border: 1px solid var(--linea); border-radius: 3px; color: inherit;
  padding: .45rem .6rem; cursor: pointer; }
.ejemplos button:hover:not(:disabled) { border-color: currentColor; }
.bandera { font-size: .68rem; border: 1px solid var(--linea); padding: 0 .25rem;
  margin-right: .45rem; opacity: .75; }
.entendido { border: 1px solid var(--linea); border-radius: 3px; padding: .8rem 1rem; }
.entendido h2 { margin-top: 0; }
.arquetipo { margin: 0 0 .5rem; font-weight: 600; }
dl { display: grid; grid-template-columns: auto 1fr; gap: .15rem .8rem; margin: 0; font-size: .87rem; }
dt { color: var(--tenue); } dd { margin: 0; }
article { border-top: 1px solid var(--linea); padding: .85rem 0; }
.cabeza { display: flex; flex-wrap: wrap; align-items: baseline; gap: .5rem; }
.tipo { font-size: .64rem; letter-spacing: .06em; border: 1px solid var(--linea); padding: 0 .3rem; }
.tipo.plan { background: CanvasText; color: Canvas; border-color: CanvasText; }
.pct { font-size: 1.45rem; font-weight: 700; font-variant-numeric: tabular-nums; }
.meta { font-size: .78rem; color: var(--tenue); flex: 1 1 100%; order: 4; }
.lang { border: 1px solid var(--linea); padding: 0 .22rem; font-size: .68rem; }
.explicacion { margin: .5rem 0 .2rem; }
.sub { margin: .2rem 0 .5rem; font-size: .85rem; color: var(--tenue); }
.mas { background: none; border: none; color: inherit; opacity: .7; cursor: pointer;
  font: inherit; font-size: .8rem; padding: .2rem 0; text-decoration: underline; }
table { width: 100%; border-collapse: collapse; font-size: .8rem; margin-top: .4rem; }
th, td { text-align: right; padding: .2rem .35rem; border-bottom: 1px solid var(--linea); }
th:first-child, td:first-child { text-align: left; }
td small { display: block; color: var(--tenue); font-size: .72rem; }
tfoot td { border: none; font-size: .95rem; }
.descartados { list-style: none; padding: 0; font-size: .85rem; }
.descartados li { padding: .2rem 0; color: var(--tenue); }
.tiempos { font-size: .76rem; color: var(--tenue); font-variant-numeric: tabular-nums;
  border-top: 1px solid var(--linea); padding-top: .6rem; margin-top: 1.5rem; }
.aviso { font-size: .82rem; border-left: 2px solid currentColor; padding-left: .6rem; opacity: .8; }
.error { color: #c33; }
footer { margin-top: 2.5rem; font-size: .74rem; color: var(--tenue); }
</style>
