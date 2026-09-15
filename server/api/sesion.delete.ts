export default defineEventHandler((event) => {
  deleteCookie(event, 'match_engine_sesion', { path: '/' })
  return { sesion: null }
})
