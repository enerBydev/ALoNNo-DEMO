<script setup lang="ts">
defineProps<{ error: { statusCode: number; statusMessage?: string } }>()
</script>
<template>
  <div class="contenedor estrecho" style="padding-top:4rem;text-align:center">
    <h1>{{ error.statusCode }}</h1>
    <p class="tenue" style="margin:.6rem 0 1.4rem">{{ error.statusMessage || 'Something broke.' }}</p>
    <NuxtLink to="/" class="boton" @click="clearError">Back to the start</NuxtLink>
  </div>
</template>
<style>@import '~/assets/css/base.css';</style>
