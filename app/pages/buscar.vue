<script setup lang="ts">
// `/buscar` ya no existe como pantalla: la busqueda ES la portada desde el 11-sep-2026
// (docs/conocimiento/20-critica-uiux.md §6 — «el producto estaba a dos clics»).
//
// Se queda como redireccion en vez de borrarse porque la URL ya se ha ense~nado, y un enlace
// compartido que muere es peor que tres lineas de redireccion. Conserva `?q=`.
const ruta = useRoute()
await navigateTo({ path: '/', query: ruta.query }, { replace: true, redirectCode: 301 })
</script>

<template>
  <div />
</template>
