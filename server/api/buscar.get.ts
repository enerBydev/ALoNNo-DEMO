// El endpoint de busqueda: orquesta las capas 0, 1 y 2 del §6.
//
// **Es un GET a proposito.** La frase va en la URL y no en el cuerpo porque
// `defineCachedEventHandler` de Nitro construye la clave de cache con la URL: con un POST, dos
// frases distintas comparten entrada de cache y la segunda recibe la respuesta de la primera.
// Medido el 10-sep-2026. Ademas, asi una busqueda es enlazable.
import { embeberConsulta, chatJson, type Uso } from '../utils/ia'
import { SISTEMA_PARSER, normalizar, resolverVentana, type Intencion } from '../utils/parser'
import { rpc, centroDe, type Persona, type Plan } from '../utils/bd'

export default defineEventHandler(async (event) => {
  const t0 = Date.now()
  const q = String((getQuery(event).q ?? '')).trim()
  if (!q) throw createError({ statusCode: 400, statusMessage: 'falta ?q=<frase>' })
  if (q.length > 500) throw createError({ statusCode: 400, statusMessage: 'frase demasiado larga' })

  const env = {
    ...process.env,
    ...((event.context as Record<string, any>).cloudflare?.env ?? {}),
  } as Record<string, string | undefined>

  // ── CAPA 0 · comprension. Una sola llamada al LLM por busqueda.
  const { json, uso: usoParser } = await chatJson(env, SISTEMA_PARSER, q)
  const intencion: Intencion = normalizar(json)
  const ventana = resolverVentana(intencion)

  // ── CAPA 1 + 2 · filtros duros y recuperacion, las dos dentro de Postgres.
  const { vector, uso: usoEmbed } = await embeberConsulta(env, q)
  const vec = `[${vector.map((x) => x.toFixed(6)).join(',')}]`
  const idioma = intencion.language === 'de' ? 'german' : 'english'
  const centro = centroDe(intencion.city)

  const comunes = {
    q_vector: vec,
    q_texto: q,
    q_idioma: idioma,
    q_lon: centro?.[0] ?? null,
    q_lat: centro?.[1] ?? null,
    q_radio_km: 40,
    q_desde: ventana.desde,
    q_hasta: ventana.hasta,
  }

  const [personas, planes] = await Promise.all([
    rpc<Persona>(env, 'buscar_personas', {
      ...comunes, q_exacta: ventana.exacta, q_excluir: null, q_limite: 50,
    }),
    rpc<Plan>(env, 'buscar_planes', {
      ...comunes,
      q_categoria: intencion.category,
      // Si la frase nombra un destino de viaje, manda el destino y no el radio de origen.
      q_dest_city: intencion.dest_city,
      q_excluir: null,
      q_limite: 50,
    }),
  ])

  const uso = (...us: Uso[]): Uso => ({
    tokens_entrada: us.reduce((s, u) => s + u.tokens_entrada, 0),
    tokens_salida: us.reduce((s, u) => s + u.tokens_salida, 0),
    ms: us.reduce((s, u) => s + u.ms, 0),
  })

  return {
    consulta: q,
    // El panel «asi lo entendi» del §10: el usuario no configura, corrige.
    intencion,
    ventana,
    candidatos: { personas: personas.filas.length, planes: planes.filas.length },
    personas: personas.filas.slice(0, 20),
    planes: planes.filas.slice(0, 20),
    // El desglose por capa, no un numero suelto: es la seccion E de la propuesta hecha visible.
    tiempos: {
      capa_0_llm: usoParser.ms,
      embedding: usoEmbed.ms,
      capa_1_2_postgres: Math.max(personas.ms, planes.ms),
      total: Date.now() - t0,
    },
    tokens: uso(usoParser, usoEmbed),
  }
})
