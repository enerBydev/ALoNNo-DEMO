// Protege las rutas que necesitan saber quien eres. Se declara por pagina con
// `definePageMeta({ middleware: 'sesion' })`, no globalmente: la busqueda tiene que poder
// probarse sin entrar, porque es lo primero que hara quien abra el link.
export default defineNuxtRouteMiddleware((a) => {
  const { sesion } = useSesion()
  if (!sesion.value) {
    return navigateTo(`/entrar?volver=${encodeURIComponent(a.fullPath)}`)
  }
})
