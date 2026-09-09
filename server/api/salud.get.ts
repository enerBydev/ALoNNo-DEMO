// Endpoint de salud. Helder pidio una URL de health en el proyecto anterior, y ademas es
// lo que permite decidir si un despliegue quedo bien sin abrir el navegador.
//
// Comprueba la BASE, no solo el proceso: un Worker vivo que no alcanza Postgres responde
// 200 igual, y eso es justo el fallo que hay que ver antes de que lo vea el cliente.
export default defineEventHandler(async (event) => {
  const env = {
    ...process.env,
    ...((event.context as Record<string, any>).cloudflare?.env ?? {}),
  } as Record<string, string | undefined>

  const url = env.SUPABASE_URL
  const key = env.SUPABASE_SECRET_KEY
  let bd = 'sin credencial'

  if (url && key) {
    try {
      const r = await fetch(`${url}/rest/v1/profiles?select=id&limit=1`, {
        headers: { apikey: key, Authorization: `Bearer ${key}` },
      })
      bd = r.ok ? 'ok' : `error ${r.status}`
    } catch (e) {
      bd = `inalcanzable: ${(e as Error).message}`
    }
  }

  return {
    estado: 'ok',
    servicio: 'alonno-demo',
    bd,
    region_bd: 'eu-central-1 (Frankfurt)',
    hora: new Date().toISOString(),
  }
})
