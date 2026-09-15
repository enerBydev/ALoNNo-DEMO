import { CIUDADES, BARRIOS } from './lugares'
import { claveDeLugar, variantesDeLugar } from './alias'

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
  const buscar = (t: string | null): [number, number] | null => {
    if (!t) return null
    // «Munich», «Koeln», «Neukölln»: exonimos, grafias sin umlaut y con umlaut, todas al catalogo.
    for (const k of variantesDeLugar(t)) {
      if (CIUDADES[k]) return CIUDADES[k]
      const b = BARRIOS[k]
      if (b) return [b[0], b[1]]
    }
    // «Koln-Ehrenfeld», «Berlin Mitte»: la persona escribe las dos mitades. Primero la clave
    // compuesta del catalogo, luego un BARRIO entre los trozos —es lo mas preciso—, y la ciudad al
    // final: «Berlin-Neukölln» centraba en Berlin, a 4,75 km de Neukölln (revision del lote 5).
    const trozos = claveDeLugar(t).split(/[\s,/]+/).filter(Boolean)
    if (trozos.length > 1) {
      for (const compuesta of [trozos.join('/'), [...trozos].reverse().join('/')]) {
        const b = BARRIOS[compuesta]
        if (b) return [b[0], b[1]]
      }
      for (const trozo of trozos) for (const k of variantesDeLugar(trozo)) {
        const bb = BARRIOS[k]
        if (bb) return [bb[0], bb[1]]
      }
      for (const trozo of trozos) for (const k of variantesDeLugar(trozo)) if (CIUDADES[k]) return CIUDADES[k]
    }
    return null
  }

  return buscar(lugar) ?? buscar(respaldo)
}

/** El barrio mas cercano a un punto [lon, lat], con nombre de pantalla («Neukolln»), o null si
 *  el punto no cae a menos de ~2,5 km de ninguno. El origen de un viaje no es columna —solo lo es
 *  su punto— y la tarjeta decia «Berlin → Mitte» para un viaje que sale de Neukolln: el barrio
 *  esta en el titulo en dos de tres plantillas, y en la tercera no esta en ningun sitio. Contra el
 *  catalogo generado el resultado es determinista, que es lo que exige el brief §9. */
export function barrioDe(punto: [number, number] | null): string | null {
  if (!punto) return null
  const [lon, lat] = punto
  const kx = Math.cos((lat * Math.PI) / 180)
  let mejor: string | null = null
  let d2 = Infinity
  for (const [clave, [blon, blat]] of Object.entries(BARRIOS)) {
    const dx = (blon - lon) * kx
    const dy = blat - lat
    const d = dx * dx + dy * dy
    if (d < d2) {
      d2 = d
      mejor = clave
    }
  }
  // 0,0225 grados ≈ 2,5 km: mas lejos que eso ya no es «ese barrio», es la ciudad.
  if (mejor == null || Math.sqrt(d2) > 0.0225) return null
  const nombre = mejor.includes('/') ? mejor.slice(mejor.indexOf('/') + 1) : mejor
  return nombre.replace(/(^|[\s-])(\p{L})/gu, (m) => m.toUpperCase())
}

/** La ciudad a la que pertenece un barrio, si se reconoce. Sirve para decir «Kreuzberg, Berlin»
 *  en la pantalla sin que el usuario tenga que escribir las dos cosas. */
export function ciudadDe(lugar: string | null): string | null {
  if (!lugar) return null
  for (const k of variantesDeLugar(lugar)) {
    if (CIUDADES[k]) return k
    if (BARRIOS[k]) return BARRIOS[k][2]
  }
  // Compuesto: el barrio dice la ciudad con mas precision que el trozo que suene a ciudad.
  const trozos = claveDeLugar(lugar).split(/[\s,/]+/).filter(Boolean)
  if (trozos.length > 1) {
    for (const trozo of trozos) for (const k of variantesDeLugar(trozo)) if (BARRIOS[k]) return BARRIOS[k][2]
    for (const trozo of trozos) for (const k of variantesDeLugar(trozo)) if (CIUDADES[k]) return k
  }
  return null
}
