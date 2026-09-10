/** La sesion, leida de la cookie. Un solo sitio, para que ninguna ruta la interprete a su manera. */
export interface Sesion { id: string; display_name: string; city: string }

export function sesionDe(event: any): Sesion | null {
  const crudo = getCookie(event, 'alonno_sesion')
  if (!crudo) return null
  try { return JSON.parse(crudo) as Sesion } catch { return null }
}

export function exigirSesion(event: any): Sesion {
  const s = sesionDe(event)
  if (!s) throw createError({ statusCode: 401, statusMessage: 'entra primero' })
  return s
}

export function entorno(event: any): Record<string, string | undefined> {
  return { ...process.env, ...((event.context as any).cloudflare?.env ?? {}) }
}

/** Lectura directa contra PostgREST con la clave de servidor. */
export async function tabla<T>(event: any, ruta: string): Promise<T[]> {
  const env = entorno(event)
  const r = await fetch(`${env.SUPABASE_URL}/rest/v1/${ruta}`, {
    headers: { apikey: env.SUPABASE_SECRET_KEY!, Authorization: `Bearer ${env.SUPABASE_SECRET_KEY}` },
  })
  if (!r.ok) throw createError({ statusCode: 502, statusMessage: `${ruta}: ${r.status}` })
  return (await r.json()) as T[]
}

export async function escribir(event: any, ruta: string, cuerpo: unknown, metodo = 'POST') {
  const env = entorno(event)
  const r = await fetch(`${env.SUPABASE_URL}/rest/v1/${ruta}`, {
    method: metodo,
    headers: {
      apikey: env.SUPABASE_SECRET_KEY!, Authorization: `Bearer ${env.SUPABASE_SECRET_KEY}`,
      'Content-Type': 'application/json', Prefer: 'return=representation',
    },
    body: JSON.stringify(cuerpo),
  })
  const texto = await r.text()
  if (!r.ok) throw createError({ statusCode: 502, statusMessage: `${ruta}: ${r.status} ${texto.slice(0, 160)}` })
  return texto ? JSON.parse(texto) : null
}
