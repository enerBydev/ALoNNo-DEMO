export default defineEventHandler((event) => {
  deleteCookie(event, 'sameway_sesion', { path: '/' })
  return { sesion: null }
})
