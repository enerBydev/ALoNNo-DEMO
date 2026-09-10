<script setup lang="ts">
// FLUJO 3 · lo mio: mis planes, a que me apunte, y quien se apunto a los mios.
definePageMeta({ middleware: 'sesion' })
useSeoMeta({ title: 'Mine — ALoNNo demo' })
const { data, pending } = await useFetch<any>('/api/mio')
const fecha = (i: string) => new Date(i).toLocaleDateString('en-GB',
  { weekday: 'short', day: 'numeric', month: 'short' })
</script>

<template>
  <div class="contenedor estrecho">
    <h1>Mine</h1>
    <p v-if="pending" class="tenue"><span class="cargando" /> loading…</p>

    <template v-else-if="data">
      <h2 style="margin-top:1.4rem">Plans I organise</h2>
      <p v-if="!data.planes.length" class="tarjeta tenue pequeno">
        None yet. <NuxtLink to="/crear">Post one</NuxtLink> and watch it become searchable.
      </p>
      <NuxtLink v-for="p in data.planes" :key="p.id" :to="`/plan/${p.id}`" class="tarjeta fila">
        <div>
          <b>{{ p.title }}</b>
          <p class="minusculo tenue">{{ p.dest_city }} · {{ fecha(p.starts_at) }}</p>
        </div>
        <span class="etiqueta">{{ p.seats_open }} free</span>
      </NuxtLink>

      <h2 style="margin-top:1.6rem">I am interested in</h2>
      <p v-if="!data.apuntado.length" class="tarjeta tenue pequeno">
        Nothing yet. Search and tap <b>I'm interested</b> on any plan.
      </p>
      <NuxtLink v-for="p in data.apuntado" :key="p.id" :to="`/plan/${p.id}`" class="tarjeta fila">
        <div>
          <b>{{ p.title }}</b>
          <p class="minusculo tenue">{{ p.dest_city }} · {{ fecha(p.starts_at) }}</p>
        </div>
        <span class="etiqueta gris">waiting</span>
      </NuxtLink>

      <h2 style="margin-top:1.6rem">Interested in my plans</h2>
      <p v-if="!data.interesados.length" class="tarjeta tenue pequeno">
        Nobody yet.
      </p>
      <NuxtLink v-for="i in data.interesados" :key="i.persona?.id + i.plan?.id"
                :to="`/persona/${i.persona?.id}`" class="tarjeta fila">
        <div>
          <b>{{ i.persona?.display_name }}</b>
          <p class="minusculo tenue">wants to join “{{ i.plan?.title }}”</p>
        </div>
        <span class="etiqueta verde">new</span>
      </NuxtLink>
    </template>
  </div>
</template>

<style scoped>
.fila { display: flex; justify-content: space-between; align-items: center; gap: 1rem;
  text-decoration: none; margin-bottom: .5rem; }
.fila:hover { border-color: var(--acento); }
</style>
