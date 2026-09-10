/** La sesion, compartida por toda la app.
 *
 *  **Se lee con `useCookie` y no con un `fetch`.** Es la unica forma que funciona igual en el
 *  servidor y en el cliente sin trucos: en SSR Nuxt lee la cabecera de la peticion, y en el
 *  navegador lee `document.cookie`. Un `$fetch` desde el servidor NO reenvia las cookies del
 *  visitante, y con `useRequestFetch` funciona en SSR pero el middleware seguia rebotando tras
 *  hidratar. Se vio recargando /crear con sesion valida: rebotaba a /entrar?volver=/crear.
 *
 *  **La cookie NO es httpOnly, a proposito.** Guarda un id publico, un nombre y una ciudad —lo
 *  mismo que ya sale en pantalla— y no autoriza nada por si misma: cada endpoint que escribe
 *  vuelve a comprobarla en el servidor. En el producto de verdad esto seria un token de sesion
 *  firmado y httpOnly; aqui es una demo declaradamente sin auth (regla 1), y hacerla httpOnly
 *  solo anadia una llamada de red por navegacion sin proteger nada.
 */
export interface Sesion { id: string; display_name: string; city: string }

export function useSesion() {
  const galleta = useCookie<Sesion | null>('alonno_sesion', {
    default: () => null,
    sameSite: 'lax',
    path: '/',
    maxAge: 60 * 60 * 12,
  })

  async function entrar(id: string) {
    galleta.value = await $fetch<Sesion>('/api/sesion', { method: 'POST', body: { id } })
    return galleta.value
  }
  async function salir() {
    await $fetch('/api/sesion', { method: 'DELETE' })
    galleta.value = null
  }
  // Se conserva por compatibilidad con el layout: ya no hace falta pedir nada.
  const cargar = async () => galleta.value

  return { sesion: galleta, cargar, entrar, salir }
}
