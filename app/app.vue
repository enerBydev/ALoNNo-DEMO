<script setup lang="ts">
// DEMO: el dia 1 solo demuestra que el deploy responde. La UI real es el dia 6 (brief §10).
const { data: salud } = await useFetch('/api/salud')
</script>

<template>
  <main>
    <h1>ALoNNo — matching demo</h1>
    <p>Say what you are planning. The system figures out the rest.</p>
    <p class="pie">
      DEMO · synthetic data · no real personal data ·
      backend: {{ salud?.estado ?? 'unknown' }}
    </p>
  </main>
</template>

<style>
:root { color-scheme: light dark; }
body { margin: 0; font: 16px/1.5 system-ui, sans-serif; }
main { max-width: 42rem; margin: 4rem auto; padding: 0 1.5rem; }
h1 { font-size: 1.6rem; margin-bottom: .25rem; }
.pie { margin-top: 3rem; font-size: .8rem; opacity: .6; }
</style>
