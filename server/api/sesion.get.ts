// Quien es el usuario actual. El layout lo pregunta en cada carga para pintar la cabecera.
export default defineEventHandler((event) => {
  const crudo = getCookie(event, 'alonno_sesion')
  if (!crudo) return { sesion: null }
  try { return { sesion: JSON.parse(crudo) } } catch { return { sesion: null } }
})
