<script setup lang="ts">
// FLUJO 2 · «create a plan». Y de paso, la unica pantalla donde se VE la regla 5: el plan se
// embebe al escribirlo, una vez, y a partir de ahi aparece en las busquedas sin costar nada.
definePageMeta({ middleware: 'sesion' })
useSeoMeta({ title: 'Post a plan — ALoNNo demo' })

const { sesion } = useSesion()
const form = reactive({
  title: '', description: '', category: 'concert', dest_city: '', subject: '',
  dia_offset: 2, seats_open: 1,
})
const enviando = ref(false)
const hecho = ref<any>(null)
const error = ref<string | null>(null)

const CATEGORIAS = ['concert', 'football', 'weekend_trip', 'holiday', 'restaurant', 'activity']
const CIUDADES = ['Berlin', 'Dusseldorf', 'Koln', 'Frankfurt', 'Munchen', 'Barcelona']
const CUANDO = [
  { v: 0, t: 'today' }, { v: 1, t: 'tomorrow' }, { v: 2, t: 'in 2 days' },
  { v: 7, t: 'next week' }, { v: 30, t: 'next month' },
]

watchEffect(() => { if (sesion.value && !form.dest_city) form.dest_city = sesion.value.city })

async function publicar() {
  enviando.value = true; error.value = null
  try {
    hecho.value = await $fetch('/api/plan', { method: 'POST', body: { ...form } })
  } catch (e: any) {
    error.value = e?.data?.statusMessage || 'the plan could not be published'
  } finally { enviando.value = false }
}
</script>

<template>
  <div class="contenedor estrecho">
    <h1>Post a plan</h1>
    <p class="tenue" style="margin-top:.5rem">
      Write it the way you would tell a friend. It becomes searchable the moment you publish —
      and that is the whole point: <b>the embedding is computed now, not when someone searches</b>.
    </p>

    <div v-if="hecho" class="tarjeta ok">
      <h2>Published ✓</h2>
      <p class="pequeno">
        Embedded on write: a <b>{{ hecho.dimension }}-dimension</b> vector, computed once. Every
        search from now on finds it with an index lookup and no API call.
      </p>
      <div class="acciones">
        <NuxtLink :to="`/plan/${hecho.plan.id}`" class="boton">See your plan →</NuxtLink>
        <NuxtLink to="/buscar" class="boton fantasma">Search for it</NuxtLink>
      </div>
    </div>

    <form v-else class="formulario" @submit.prevent="publicar">
      <div>
        <label for="t">Title</label>
        <input id="t" v-model="form.title" required maxlength="90"
               placeholder="Burna Boy live — one spare ticket">
      </div>
      <div>
        <label for="d">What is it, in your words</label>
        <textarea id="d" v-model="form.description" rows="3" required maxlength="400"
                  placeholder="I have one seat left and I would rather not go alone…" />
      </div>
      <div class="rejilla dos">
        <div>
          <label for="c">Kind of plan</label>
          <select id="c" v-model="form.category">
            <option v-for="c in CATEGORIAS" :key="c" :value="c">{{ c.replace('_', ' ') }}</option>
          </select>
        </div>
        <div>
          <label for="ci">Where</label>
          <select id="ci" v-model="form.dest_city">
            <option v-for="c in CIUDADES" :key="c" :value="c">{{ c }}</option>
          </select>
        </div>
      </div>
      <div class="rejilla dos">
        <div>
          <label for="w">When</label>
          <select id="w" v-model.number="form.dia_offset">
            <option v-for="c in CUANDO" :key="c.v" :value="c.v">{{ c.t }}</option>
          </select>
        </div>
        <div>
          <label for="s">Seats open</label>
          <input id="s" v-model.number="form.seats_open" type="number" min="1" max="4">
        </div>
      </div>
      <div>
        <label for="su">Artist, team or cuisine <span class="tenue">(optional)</span></label>
        <input id="su" v-model="form.subject" maxlength="60" placeholder="Burna Boy">
      </div>

      <p v-if="error" class="error pequeno">{{ error }}</p>
      <button class="boton" :disabled="enviando">
        <span v-if="enviando" class="cargando" />
        {{ enviando ? 'Embedding and publishing…' : 'Publish plan' }}
      </button>
      <p class="minusculo tenue">
        Publishing runs one embedding call. Searching runs none.
      </p>
    </form>
  </div>
</template>

<style scoped>
.formulario { display: grid; gap: .9rem; margin-top: 1.3rem; }
.ok { margin-top: 1.3rem; border-color: var(--verde); background: var(--verde-suave); }
.acciones { display: flex; gap: .5rem; margin-top: .9rem; flex-wrap: wrap; }
.error { color: #dc2626; }
</style>
