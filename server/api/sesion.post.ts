// Entrar como uno de los perfiles sembrados. **Sin contrasena, a proposito**: son perfiles
// sinteticos y pedir una credencial en una demo solo anade friccion sin anadir seguridad.
//
// Lo que si hace es lo que hace una sesion de verdad: una cookie HttpOnly firmada por el
// servidor, que el cliente no puede fabricar, y de la que cuelga todo lo que el usuario ve.
import { rpc } from '../utils/bd'

export default defineEventHandler(async (event) => {
  const { id } = await readBody<{ id?: string }>(event)
  if (!id || !/^[0-9a-f-]{36}$/i.test(id)) {
    throw createError({ statusCode: 400, statusMessage: 'falta el id del perfil' })
  }
  const env = { ...process.env, ...((event.context as any).cloudflare?.env ?? {}) }
  const url = env.SUPABASE_URL, clave = env.SUPABASE_SECRET_KEY
  const r = await fetch(`${url}/rest/v1/profiles?id=eq.${id}&select=id,display_name,city`, {
    headers: { apikey: clave, Authorization: `Bearer ${clave}` },
  })
  const filas = (await r.json()) as any[]
  if (!filas.length) throw createError({ statusCode: 404, statusMessage: 'ese perfil no existe' })

  // NO httpOnly: `useCookie` tiene que poder leerla en el navegador para que la navegacion
  // entre paginas no dependa de una llamada de red. Lo que guarda es publico —id, nombre,
  // ciudad— y no autoriza nada: cada endpoint que escribe vuelve a comprobarla en el servidor.
  setCookie(event, 'alonno_sesion', JSON.stringify(filas[0]), {
    httpOnly: false, secure: true, sameSite: 'lax', path: '/', maxAge: 60 * 60 * 12,
  })
  return filas[0]
})
