// El unico sitio que habla con Postgres. Llama a las funciones de `db/funciones.sql` por RPC:
// el SQL vive en la base, versionado, y el servidor solo pasa parametros.
//
// Se usa la clave de SERVIDOR (`secret`), que salta RLS por diseno. La clave publica no puede
// leer nada: las tres tablas estan cerradas con row-level security desde el incidente del 10 de
// septiembre. Ver incidentes/2026-09-10-rls-apagado.md.

export interface Persona {
  id: string; display_name: string; city: string; bio: string; bio_lang: string; age: number | null
  interests: string[]; top_artists: string[] | null; top_teams: string[] | null; cuisines: string[] | null
  pace: string | null; budget_band: string | null; group_pref: string | null; languages: string[]
  verification: number; completed_plans: number; reports: number
  km: number | null; disponible_exacto: boolean; disponible_finde: boolean
  similitud: number; rrf: number
}

export interface Plan {
  id: string; owner_id: string; title: string; description: string; desc_lang: string
  category: string; origin_city: string; dest_city: string; is_travel: boolean
  venue: string | null; subject: string | null; tags: string[]
  starts_at: string; ends_at: string; seats_open: number; radius_km: number
  budget_band: string | null; pace: string | null; language_pref: string[] | null
  km: number | null; similitud: number; rrf: number
}

function config(env: Record<string, string | undefined>) {
  const url = env.SUPABASE_URL
  const clave = env.SUPABASE_SECRET_KEY
  if (!url || !clave) throw createError({ statusCode: 503, statusMessage: 'sin credenciales de base de datos' })
  return { url, clave }
}

export async function rpc<T>(
  env: Record<string, string | undefined>,
  funcion: string,
  argumentos: Record<string, unknown>,
): Promise<{ filas: T[]; ms: number }> {
  const { url, clave } = config(env)
  const t0 = Date.now()
  const r = await fetch(`${url}/rest/v1/rpc/${funcion}`, {
    method: 'POST',
    headers: {
      apikey: clave,
      Authorization: `Bearer ${clave}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(argumentos),
  })
  if (!r.ok) {
    throw createError({ statusCode: 502, statusMessage: `${funcion}: ${r.status} ${(await r.text()).slice(0, 200)}` })
  }
  return { filas: (await r.json()) as T[], ms: Date.now() - t0 }
}

/** Centro de cada ciudad del cliente. Sirve para anclar el radio cuando la frase nombra una
 *  ciudad pero no un punto — que es siempre. */
export const CENTROS: Record<string, [number, number]> = {
  Berlin: [13.4050, 52.5200],
  Dusseldorf: [6.7763, 51.2277],
  Koln: [6.9603, 50.9375],
  Frankfurt: [8.6821, 50.1109],
  Munchen: [11.5820, 48.1351],
  Bonn: [7.0980, 50.7340],
  Leverkusen: [6.9800, 51.0300],
  Neuss: [6.6900, 51.2000],
  Barcelona: [2.1700, 41.3870],
}

/** «Dusseldorf», «Düsseldorf» y «dusseldorf» son la misma ciudad. */
export function centroDe(ciudad: string | null): [number, number] | null {
  if (!ciudad) return null
  const limpia = ciudad.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
  for (const [nombre, punto] of Object.entries(CENTROS)) {
    if (nombre.toLowerCase() === limpia) return punto
  }
  return null
}
