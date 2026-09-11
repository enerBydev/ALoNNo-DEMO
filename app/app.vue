<script setup lang="ts">
// SEO por defecto: la seccion K de la propuesta vende que las paginas publicas son un canal de
// captacion, y eso empieza por que el HTML llegue hecho y con sus etiquetas.
useSeoMeta({
  title: 'ALoNNo — find the driver going your way',
  description: 'Say it in one sentence, in German or English. ALoNNo reads it, finds the drivers '
    + 'whose route passes near you, and explains every match with a number you can check.',
  ogTitle: 'ALoNNo — find the driver going your way',
  ogDescription: 'Natural-language ride matching. Demo with synthetic data.',
})
</script>

<template>
  <!-- `UApp` es obligatorio en Nuxt UI 4: es lo que monta el contenedor de los toasts, los
       modales y los tooltips. Sin el, `useToast()` no pinta nada y no da error. -->
  <UApp>
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
  </UApp>
</template>

<style>@import '~/assets/css/base.css';</style>
