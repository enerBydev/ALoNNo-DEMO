import { CIUDADES, BARRIOS } from './lugares'

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
  conduce: boolean; coche: string | null; plazas_coche: number | null
  nota: number | null; notas_conteo: number | null; desde_offset: number | null
  km: number | null; disponible_exacto: boolean; disponible_finde: boolean
  similitud: number; rrf: number
}

export interface Plan {
  id: string; owner_id: string; title: string; description: string; desc_lang: string
  category: string; origin_city: string; dest_city: string; is_travel: boolean
  venue: string | null; subject: string | null; tags: string[]
  starts_at: string; ends_at: string; seats_open: number; radius_km: number
  budget_band: string | null; pace: string | null; language_pref: string[] | null
  // El viaje. `distancia_km` es null cuando al plan no se llega en coche (un vuelo a Barcelona):
  // esa es la se~nal que usa la UI para ense~nar un plan en vez de un trayecto.
  via: string[] | null; distancia_km: number | null; precio_por_km: number | null
  recurrente: string | null
  // El conductor viaja con el viaje: sin esto, pintar una estrella costaria una consulta por fila.
  conductor: string | null; conductor_coche: string | null; conductor_nota: number | null
  conductor_notas: number | null; conductor_verificado: number | null; conductor_viajes: number | null
  ruta_geojson: string | null; origen_geojson: string | null; destino_geojson: string | null
  km: number | null; km_ruta: number | null; similitud: number; rrf: number
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

/** Donde esta un sitio, sea ciudad o barrio.
 *
 *  EL FALLO QUE LO CAMBIO (11-sep-2026): esto conocia NUEVE ciudades y nada mas, y la Capa 0
 *  devuelve lo que la persona escribe. «Ich fahre morgen von Neukolln nach Mitte» ponia
 *  `city: "Neukolln"`, aqui salia `null`, y **sin centro no hay filtro de radio**: a un berlines
 *  se le contestaba con coches de Dusseldorf. No fallaba: contestaba mal, que es peor.
 *
 *  Los 63 barrios salen generados de los mismos catalogos que siembran la base
 *  (`scripts/generar-lugares.py`), para que no haya dos verdades sobre donde esta Kreuzberg. */
export function centroDe(lugar: string | null, respaldo: string | null = null): [number, number] | null {
  const clave = (t: string) =>
    t.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/-/g, ' ').trim()

  const buscar = (t: string | null): [number, number] | null => {
    if (!t) return null
    const k = clave(t)
    if (CIUDADES[k]) return CIUDADES[k]
    const b = BARRIOS[k]
    if (b) return [b[0], b[1]]
    // «Koln-Ehrenfeld», «Berlin Mitte»: la persona escribe las dos mitades y las dos valen.
    for (const trozo of k.split(/[\s,/]+/).filter(Boolean)) {
      if (CIUDADES[trozo]) return CIUDADES[trozo]
      const bb = BARRIOS[trozo]
      if (bb) return [bb[0], bb[1]]
    }
    return null
  }

  return buscar(lugar) ?? buscar(respaldo)
}

/** La ciudad a la que pertenece un barrio, si se reconoce. Sirve para decir «Kreuzberg, Berlin»
 *  en la pantalla sin que el usuario tenga que escribir las dos cosas. */
export function ciudadDe(lugar: string | null): string | null {
  if (!lugar) return null
  const k = lugar.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/-/g, ' ').trim()
  if (CIUDADES[k]) return k
  return BARRIOS[k]?.[2] ?? null
}
