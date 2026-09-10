// FLUJO 2 · «create a plan».
//
// **AQUI SE VE LA REGLA 5 EN VIVO**: el embedding se calcula AL ESCRIBIR, no al buscar. Es el
// argumento de coste que la propuesta le vendio al cliente (seccion E, control 1), y este
// endpoint es la unica forma de ense~narlo funcionando: publicas un plan, se embebe una vez, y
// a partir de ahi aparece en las busquedas sin costar ni una llamada mas.
import { exigirSesion, entorno, escribir, tabla } from '../utils/sesion'

const CATEGORIAS = ['concert', 'football', 'weekend_trip', 'holiday', 'restaurant', 'activity']
const CIUDADES: Record<string, [number, number]> = {
  Berlin: [13.4050, 52.5200], Dusseldorf: [6.7763, 51.2277], Koln: [6.9603, 50.9375],
  Frankfurt: [8.6821, 50.1109], Munchen: [11.5820, 48.1351], Barcelona: [2.1700, 41.3870],
}

export default defineEventHandler(async (event) => {
  const yo = exigirSesion(event)
  const b = await readBody<any>(event)

  const titulo = String(b?.title ?? '').trim()
  const descripcion = String(b?.description ?? '').trim()
  if (titulo.length < 4 || descripcion.length < 10) {
    throw createError({ statusCode: 400, statusMessage: 'el plan necesita un titulo y una descripcion' })
  }
  const categoria = CATEGORIAS.includes(b?.category) ? b.category : 'activity'
  const ciudad = CIUDADES[b?.dest_city] ? b.dest_city : yo.city
  const [lon, lat] = CIUDADES[ciudad] ?? CIUDADES.Berlin
  const dias = Math.min(60, Math.max(0, Number(b?.dia_offset ?? 2)))
  const idioma = /[äöüß]/i.test(descripcion) || b?.desc_lang === 'de' ? 'de' : 'en'

  // El texto que se embebe es el mismo que usa el sembrador: titulo, descripcion, sujeto,
  // etiquetas y categoria. Si divergieran, un plan creado a mano rankearia distinto que uno
  // sembrado, y la demo dejaria de ser comparable consigo misma.
  const etiquetas: string[] = Array.isArray(b?.tags)
    ? b.tags.filter((t: any) => typeof t === 'string').slice(0, 6) : [categoria]
  const texto = [titulo, descripcion, b?.subject ?? '', etiquetas.join(' '), categoria]
    .filter(Boolean).join(' · ')

  const env = entorno(event)
  const r = await fetch('https://integrate.api.nvidia.com/v1/embeddings', {
    method: 'POST',
    headers: { Authorization: `Bearer ${env.NVIDIA_API_KEY}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: 'nvidia/nemotron-3-embed-1b',
      input: [texto],
      input_type: 'passage',   // pasaje, no consulta: el modelo es asimetrico
      truncate: 'END', encoding_format: 'float',
    }),
  })
  if (!r.ok) throw createError({ statusCode: 502, statusMessage: 'no se pudo embeber el plan' })
  const emb = (await r.json()).data[0].embedding as number[]

  const [creado] = await escribir(event, 'plans', {
    id: crypto.randomUUID(),
    owner_id: yo.id,
    title: titulo,
    description: descripcion,
    desc_lang: idioma,
    category: categoria,
    origin_city: yo.city,
    dest_city: ciudad,
    is_travel: ciudad !== yo.city,
    geo: `SRID=4326;POINT(${lon} ${lat})`,
    origin_geo: `SRID=4326;POINT(${lon} ${lat})`,
    date_precision: 'exact',
    starts_at: new Date(Date.now() + dias * 86400000).toISOString(),
    ends_at: new Date(Date.now() + dias * 86400000 + 4 * 3600000).toISOString(),
    radius_km: 40,
    seats_open: Math.min(4, Math.max(1, Number(b?.seats_open ?? 1))),
    subject: b?.subject ?? null,
    tags: etiquetas,
    language_pref: [idioma],
    embedding: `[${emb.map((x) => x.toFixed(6)).join(',')}]`,
  })
  return { plan: creado, embebido_al_escribir: true, dimension: emb.length }
})
