<script setup lang="ts">
// `/buscar` ya no existe como pantalla: la busqueda ES la portada desde el 11-sep-2026.
//
// Se queda como redireccion porque la URL ya se ha ense~nado, y un enlace compartido que muere
// es peor que tres lineas. Conserva `?q=`.
//
// Va como MIDDLEWARE DE RUTA y no como `navigateTo` en el setup: el `await navigateTo()` del
// setup funcionaba en SSR y fallaba en navegacion cliente —«Sign in» sin `volver` acababa en una
// pagina en blanco— (programa de UX, 15-sep-2026). Un middleware corre igual en las dos.
definePageMeta({
  middleware: [
    (to) => navigateTo({ path: '/', query: to.query }, { replace: true, redirectCode: 301 }),
  ],
})
</script>

<template>
  <div />
</template>
