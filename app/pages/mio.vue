<script setup lang="ts">
// FLUJO 3 · lo mio: los viajes que ofrezco, las plazas que pedi, y quien pidio plaza en los mios.
// El vocabulario es el del coche compartido (re-verificacion #54): «plan», «organise» e
// «interested» eran del producto anterior y la barra ya decia «My rides».
definePageMeta({ middleware: 'sesion' })
useSeoMeta({ title: 'My rides — Match Engine demo' })
const { data, pending } = await useFetch<any>('/api/mio')
const fecha = (i: string) => new Date(i).toLocaleDateString('en-GB',
  { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'Europe/Berlin' })
</script>

<template>
  <div class="contenedor estrecho">
    <h1>My rides</h1>
    <p v-if="pending" class="tenue"><span class="cargando" /> loading…</p>

    <template v-else-if="data">
      <h2 style="margin-top:1.4rem">Rides I offer</h2>
      <p v-if="!data.planes.length" class="tarjeta tenue pequeno">
        None yet. <NuxtLink to="/crear">Offer a ride</NuxtLink> and it becomes findable the moment you publish.
      </p>
      <NuxtLink v-for="p in data.planes" :key="p.id" :to="`/plan/${p.id}`" class="tarjeta fila">
        <div>
          <b>{{ p.title }}</b>
          <p class="minusculo tenue">{{ p.dest_city }} · {{ fecha(p.starts_at) }}</p>
        </div>
        <span class="etiqueta">{{ p.seats_open }} {{ p.seats_open === 1 ? 'seat' : 'seats' }} free</span>
      </NuxtLink>

      <h2 style="margin-top:1.6rem">Seats I asked for</h2>
      <p v-if="!data.apuntado.length" class="tarjeta tenue pequeno">
        Nothing yet. <NuxtLink to="/">Find a ride</NuxtLink> and tap <b>Request a seat</b>.
      </p>
      <NuxtLink v-for="p in data.apuntado" :key="p.id" :to="`/plan/${p.id}`" class="tarjeta fila">
        <div>
          <b>{{ p.title }}</b>
          <p class="minusculo tenue">{{ p.dest_city }} · {{ fecha(p.starts_at) }}</p>
        </div>
        <span class="etiqueta gris">waiting</span>
      </NuxtLink>

      <h2 style="margin-top:1.6rem">Requests on my rides</h2>
      <p v-if="!data.interesados.length" class="tarjeta tenue pequeno">
        Nobody yet. Requests show up here as soon as someone asks for a seat.
      </p>
      <NuxtLink v-for="i in data.interesados" :key="i.persona?.id + i.plan?.id"
                :to="`/persona/${i.persona?.id}`" class="tarjeta fila">
        <div>
          <b>{{ i.persona?.display_name }}</b>
          <p class="minusculo tenue">asked for a seat on “{{ i.plan?.title }}”</p>
        </div>
        <span class="etiqueta verde">new</span>
      </NuxtLink>
    </template>
  </div>
</template>

<style scoped>
.fila { display: flex; justify-content: space-between; align-items: center; gap: 1rem;
  text-decoration: none; margin-bottom: .5rem; }
.fila:hover { border-color: var(--accion); }
</style>
