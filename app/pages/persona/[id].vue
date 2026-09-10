<script setup lang="ts">
const ruta = useRoute()
const { data, error } = await useFetch<any>(`/api/persona/${ruta.params.id}`)
const p = computed(() => data.value?.persona)
useSeoMeta({ title: () => p.value ? `${p.value.display_name} — ALoNNo` : 'Profile' })
const fecha = (i: string) => new Date(i).toLocaleDateString('en-GB',
  { day: 'numeric', month: 'short' })
</script>

<template>
  <div class="contenedor estrecho">
    <p v-if="error" class="tarjeta">That profile does not exist.</p>
    <template v-else-if="p">
      <NuxtLink to="/buscar" class="minusculo tenue" style="text-decoration:none">← back to search</NuxtLink>
      <header class="cabecera">
        <span class="avatar">{{ p.display_name.charAt(0) }}</span>
        <div>
          <h1>{{ p.display_name }}</h1>
          <p class="tenue">
            {{ p.city }}<template v-if="p.age"> · {{ p.age }}</template>
            · speaks {{ (p.languages || []).join(', ').toUpperCase() }}
            <template v-if="p.verification >= 2"> · ✓ verified</template>
          </p>
        </div>
      </header>

      <p class="bio">{{ p.bio }}</p>

      <div class="tags">
        <span v-for="a in p.top_artists || []" :key="a" class="etiqueta">🎵 {{ a }}</span>
        <span v-for="t in p.top_teams || []" :key="t" class="etiqueta">⚽ {{ t }}</span>
        <span v-for="c in p.cuisines || []" :key="c" class="etiqueta">🍽 {{ c }}</span>
        <span v-for="i in p.interests || []" :key="i" class="etiqueta gris">
          {{ i.replace(/_/g, ' ') }}
        </span>
      </div>

      <div class="rejilla dos" style="margin-top:1.2rem">
        <div class="tarjeta">
          <h3>Style</h3>
          <p class="pequeno tenue">
            pace: {{ p.pace || '—' }} · budget: {{ p.budget_band || '—' }}<br>
            prefers: {{ (p.group_pref || '—').replace(/_/g, ' ') }}
          </p>
        </div>
        <div class="tarjeta">
          <h3>Track record</h3>
          <p class="pequeno tenue">
            {{ p.completed_plans }} plans completed · verification {{ p.verification }}/3
          </p>
        </div>
      </div>

      <template v-if="data.planes.length">
        <h2 style="margin-top:1.6rem">Plans they organise</h2>
        <NuxtLink v-for="pl in data.planes" :key="pl.id" :to="`/plan/${pl.id}`" class="tarjeta plan">
          <div>
            <b>{{ pl.title }}</b>
            <p class="minusculo tenue">
              {{ pl.dest_city }} · {{ fecha(pl.starts_at) }} · {{ pl.seats_open }} free
            </p>
          </div>
          <span class="etiqueta gris">{{ pl.category.replace('_', ' ') }}</span>
        </NuxtLink>
      </template>

      <template v-if="data.apuntada.length">
        <h2 style="margin-top:1.4rem">Interested in</h2>
        <NuxtLink v-for="pl in data.apuntada" :key="pl.id" :to="`/plan/${pl.id}`" class="tarjeta plan">
          <b>{{ pl.title }}</b>
          <span class="minusculo tenue">{{ fecha(pl.starts_at) }}</span>
        </NuxtLink>
      </template>
    </template>
  </div>
</template>

<style scoped>
.cabecera { display: flex; gap: 1rem; align-items: center; margin: .8rem 0 1rem; }
.avatar { width: 58px; height: 58px; border-radius: 50%; background: var(--acento); color: #fff;
  display: grid; place-items: center; font-size: 1.5rem; font-weight: 700; flex: none; }
.bio { margin-bottom: 1rem; }
.tags { display: flex; flex-wrap: wrap; gap: .3rem; }
.plan { display: flex; justify-content: space-between; align-items: center; gap: 1rem;
  text-decoration: none; margin-bottom: .5rem; }
.plan:hover { border-color: var(--acento); }
</style>
