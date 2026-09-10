<script setup lang="ts">
// La pagina publica de un plan. **SSR con datos estructurados**: la seccion K de la propuesta
// vende que cada plan es una pagina que un buscador —o un asistente— puede leer y citar. Eso
// solo es cierto si el HTML llega hecho, que es justo lo que Nuxt da y lo que un cliente movil
// puro no puede dar.
const ruta = useRoute()
const { sesion } = useSesion()
const { data, error, refresh } = await useFetch<any>(`/api/plan/${ruta.params.id}`)

const p = computed(() => data.value?.plan)
const cuando = computed(() => p.value
  ? new Date(p.value.starts_at).toLocaleString('en-GB',
      { weekday: 'long', day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' })
  : '')

useSeoMeta({
  title: () => p.value ? `${p.value.title} — ALoNNo` : 'Plan — ALoNNo',
  description: () => p.value?.description ?? '',
})
// Datos estructurados de tipo Event: es lo que permite que un asistente cite este plan.
useHead(() => ({
  script: p.value ? [{
    type: 'application/ld+json',
    innerHTML: JSON.stringify({
      '@context': 'https://schema.org', '@type': 'Event',
      name: p.value.title, description: p.value.description,
      startDate: p.value.starts_at, endDate: p.value.ends_at,
      eventStatus: 'https://schema.org/EventScheduled',
      location: { '@type': 'Place', name: p.value.venue ?? p.value.dest_city,
                  address: { '@type': 'PostalAddress', addressLocality: p.value.dest_city } },
    }),
  }] : [],
}))

const enviando = ref(false)
const resultado = ref<any>(null)
async function apuntarse(quitar = false) {
  if (!sesion.value) return navigateTo(`/entrar?volver=/plan/${ruta.params.id}`)
  enviando.value = true
  try {
    resultado.value = await $fetch('/api/interes', {
      method: 'POST', body: { plan_id: ruta.params.id, quitar },
    })
    await refresh()
  } finally { enviando.value = false }
}
</script>

<template>
  <div class="contenedor estrecho">
    <p v-if="error" class="tarjeta">That plan does not exist.</p>

    <template v-else-if="p">
      <NuxtLink to="/buscar" class="volver minusculo tenue">← back to search</NuxtLink>

      <div class="fila-titulo">
        <span class="etiqueta">{{ p.category.replace('_', ' ') }}</span>
        <span v-if="p.is_travel" class="etiqueta gris">travel</span>
        <span class="etiqueta gris">{{ p.desc_lang.toUpperCase() }}</span>
      </div>
      <h1>{{ p.title }}</h1>
      <p class="cuando">🗓 {{ cuando }} · 📍 {{ p.venue || p.dest_city }}</p>
      <p class="descripcion">{{ p.description }}</p>

      <div class="tarjeta plazas">
        <div>
          <b>{{ p.seats_open }}</b> {{ p.seats_open === 1 ? 'seat' : 'seats' }} open
          <p class="minusculo tenue">
            {{ data.apuntados.length }} {{ data.apuntados.length === 1 ? 'person has' : 'people have' }}
            shown interest
          </p>
        </div>
        <button v-if="!data.soy_el_dueno" class="boton" :class="{ hecho: data.yo_apuntado }"
                :disabled="enviando" @click="apuntarse(data.yo_apuntado)">
          <span v-if="enviando" class="cargando" />
          {{ data.yo_apuntado ? "✓ You're in — tap to leave" : "I'm interested" }}
        </button>
        <span v-else class="etiqueta gris">your plan</span>
      </div>

      <div v-if="resultado?.mutuo" class="tarjeta mutuo">
        <b>🎉 Mutual match.</b>
        <p class="pequeno">
          {{ p.perfil.display_name }} is interested in your plan “{{ resultado.plan_suyo?.title }}”
          too. In the real product this is the moment the chat opens — the demo stops here on
          purpose: no chat, no notifications, no messaging.
        </p>
      </div>

      <h2 style="margin-top:1.8rem">Organised by</h2>
      <NuxtLink :to="`/persona/${p.perfil.id}`" class="tarjeta duenno">
        <span class="avatar">{{ p.perfil.display_name.charAt(0) }}</span>
        <div>
          <h3>{{ p.perfil.display_name }}</h3>
          <p class="minusculo tenue">
            {{ p.perfil.city }} · {{ p.perfil.completed_plans }} plans completed
            <template v-if="p.perfil.verification >= 2"> · ✓ verified</template>
          </p>
          <p class="pequeno tenue recorte">{{ p.perfil.bio }}</p>
        </div>
      </NuxtLink>

      <template v-if="data.apuntados.length">
        <h2 style="margin-top:1.6rem">Who has shown interest</h2>
        <div class="rejilla dos">
          <NuxtLink v-for="a in data.apuntados" :key="a.id" :to="`/persona/${a.id}`"
                    class="tarjeta apuntado">
            <span class="avatar pequeno">{{ a.display_name.charAt(0) }}</span>
            <div>
              <b>{{ a.display_name }}</b>
              <p class="minusculo tenue">{{ a.city }}</p>
            </div>
          </NuxtLink>
        </div>
      </template>
    </template>
  </div>
</template>

<style scoped>
.volver { display: inline-block; margin-bottom: .8rem; text-decoration: none; }
.fila-titulo { display: flex; gap: .4rem; margin-bottom: .5rem; }
.cuando { margin: .7rem 0; font-weight: 560; }
.descripcion { margin-bottom: 1.2rem; }
.plazas { display: flex; align-items: center; justify-content: space-between; gap: 1rem;
  flex-wrap: wrap; }
.mutuo { margin-top: .8rem; border-color: var(--verde); background: var(--verde-suave); }
.duenno, .apuntado { display: flex; gap: .7rem; align-items: center; text-decoration: none; }
.duenno:hover, .apuntado:hover { border-color: var(--acento); }
.avatar { width: 40px; height: 40px; border-radius: 50%; background: var(--acento); color: #fff;
  display: grid; place-items: center; font-weight: 700; flex: none; }
.avatar.pequeno { width: 30px; height: 30px; font-size: .85rem; }
.recorte { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden; margin-top: .2rem; }
</style>
