<script setup lang="ts">
// SEO por defecto: la seccion K de la propuesta vende que las paginas publicas son un canal de
// captacion, y eso empieza por que el HTML llegue hecho y con sus etiquetas.
useSeoMeta({
  title: 'ALoNNo — this is my plan, who fits?',
  description: 'Write one sentence. ALoNNo understands it, finds people and plans that fit, '
    + 'and explains every match with a number you can check.',
  ogTitle: 'ALoNNo — this is my plan, who fits?',
  ogDescription: 'Natural-language matching for plans and people. Demo with synthetic data.',
})
</script>

<template>
  <NuxtLayout>
    <NuxtPage />
  </NuxtLayout>
</template>

<style>@import '~/assets/css/base.css';</style>
