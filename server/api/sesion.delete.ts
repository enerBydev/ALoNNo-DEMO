export default defineEventHandler((event) => {
  deleteCookie(event, 'alonno_sesion', { path: '/' })
  return { sesion: null }
})
