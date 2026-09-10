// El endpoint de busqueda: orquesta las cinco capas del §6.
//
// **Es un GET a proposito.** La frase va en la URL y no en el cuerpo porque
// `defineCachedEventHandler` de Nitro construye la clave de cache con la URL: con un POST, dos
// frases distintas comparten entrada de cache y la segunda recibe la respuesta de la primera.
// Medido el 10-sep-2026. Ademas, asi una busqueda es enlazable.
import { embeberConsulta, chatJson, type Uso } from '../utils/ia'
import { SISTEMA_PARSER, normalizar, parsearSinModelo, reforzarFecha, resolverVentana, type Intencion } from '../utils/parser'
import { rpc, centroDe, type Persona, type Plan } from '../utils/bd'
import { puntuarPersona, puntuarPlan, type Puntuacion } from '../utils/scoring'
import { explicar, type ParaExplicar } from '../utils/explicar'

const TOP_EXPLICADO = 5

export default defineCachedEventHandler(async (event) => {
  const t0 = Date.now()
  const q = String(getQuery(event).q ?? '').trim()
  if (!q) throw createError({ statusCode: 400, statusMessage: 'falta ?q=<frase>' })
  if (q.length > 500) throw createError({ statusCode: 400, statusMessage: 'frase demasiado larga' })

  const env = {
    ...process.env,
    ...((event.context as Record<string, any>).cloudflare?.env ?? {}),
  } as Record<string, string | undefined>

  // ── CAPA 0 · comprension. Una sola llamada al LLM por busqueda.
  //
  // Si el proveedor falla, se cae al parser de reglas en vez de devolver un error: la busqueda
  // semantica no necesita el parser, solo la frase. Se pierde precision, no la demo — y la
  // respuesta lo declara con `confidence: 0`, porque la regla 8 prohibe disimular lo que no va.
  let intencion: Intencion
  let usoParser: Uso = { tokens_entrada: 0, tokens_salida: 0, ms: 0 }
  let degradado = false
  try {
    // TIEMPO MAXIMO PARA LA CAPA 0. Medido: el mismo modelo y la misma frase tardan entre 3,9 s
    // y 91 s segun la cola del proveedor. Una demo que se mira en vivo no puede quedarse noventa
    // segundos en blanco: pasado el limite se usa el parser de reglas, que da un resultado peor
    // pero inmediato. Y se declara.
    const LIMITE_MS = 12_000
    const r = await Promise.race([
      chatJson(env, SISTEMA_PARSER, q),
      new Promise<never>((_, rechaza) =>
        setTimeout(() => rechaza(new Error('capa 0: se agoto el tiempo')), LIMITE_MS)),
    ])
    intencion = normalizar(r.json)
    usoParser = r.uso
  } catch {
    intencion = parsearSinModelo(q)
    degradado = true
  }
  // Una expresion temporal explicita en la frase gana sobre el silencio del modelo.
  intencion = reforzarFecha(intencion, q)
  const ventana = resolverVentana(intencion)

  // ── CAPA 1 + 2 · filtros duros y recuperacion, las dos dentro de Postgres.
  const { vector, uso: usoEmbed } = await embeberConsulta(env, q)
  const vec = `[${vector.map((x) => x.toFixed(6)).join(',')}]`
  const centro = centroDe(intencion.city)
  const comunes = {
    q_vector: vec,
    q_texto: q,
    q_idioma: intencion.language === 'de' ? 'german' : 'english',
    q_lon: centro?.[0] ?? null,
    q_lat: centro?.[1] ?? null,
    q_radio_km: 40,
    q_desde: ventana.desde,
    q_hasta: ventana.hasta,
  }
  const [resPersonas, resPlanes] = await Promise.all([
    rpc<Persona>(env, 'buscar_personas', { ...comunes, q_exacta: ventana.exacta, q_excluir: null, q_limite: 50 }),
    rpc<Plan>(env, 'buscar_planes', {
      ...comunes, q_categoria: intencion.category, q_dest_city: intencion.dest_city,
      q_excluir: null, q_limite: 50,
    }),
  ])

  // ── CAPA 3 · scoring. Aritmetica, no opinion. Aqui nace el porcentaje.
  const tagsConsulta = [
    ...intencion.must_match, ...intencion.nice_to_have,
    intencion.subject ?? '', intencion.category ?? '',
  ].filter(Boolean)

  const personas = resPersonas.filas.map((p) => ({
    tipo: 'PERSONA' as const,
    ...p,
    puntuacion: puntuarPersona(p, {
      tags: tagsConsulta,
      categoria: intencion.category,
      radioKm: 40,
      hayFecha: Boolean(ventana.desde),
      fechaTexto: ventana.desde,
      pace: intencion.pace,
      budget_band: intencion.budget_band,
      language_pref: [intencion.language],
    }),
  }))

  const planes = resPlanes.filas.map((p) => ({
    tipo: 'PLAN' as const,
    ...p,
    puntuacion: puntuarPlan(p, {
      subject: intencion.subject,
      subjectEspecificidad: intencion.subject_specificity,
      categoria: intencion.category,
      desde: ventana.desde,
      hasta: ventana.hasta,
      tags: tagsConsulta,
      radioKm: 40,
    }),
  }))

  // LA REGLA DE MEZCLA del §7, atada a `user_has_booking` y no a `has_concrete_event` (ADR-0003).
  //
  // Cada arquetipo pide una cosa distinta, y el §9-A lo dice frase por frase:
  //   plan_seeks_person (1,2,4,5,10) -> «Personas en Dusseldorf con gusto afrobeats». Quien
  //     pregunta YA TIENE la entrada: ense~narle otro concierto igual no le sirve de nada.
  //   plan_seeks_plan (7)            -> «Planes de viaje a Barcelona en fechas solapadas».
  //   intent_seeks_any (3,6,8)       -> mezcla: primero A QUE IR, luego con quien.
  //   standing_interest (9)          -> «Personas en Colonia con gusto afrobeats», sin fecha.
  //
  // No es un filtro duro: los dos tipos siguen apareciendo y etiquetados, como pide el §10.4.
  // Lo que cambia es cual manda.
  const MEZCLA: Record<string, { PERSONA: number; PLAN: number }> = {
    plan_seeks_person: { PERSONA: 1.0, PLAN: 0.55 },
    plan_seeks_plan: { PERSONA: 0.6, PLAN: 1.0 },
    intent_seeks_any: { PERSONA: 0.95, PLAN: 1.05 },
    standing_interest: { PERSONA: 1.05, PLAN: 0.9 },
  }
  const empuje = (t: 'PERSONA' | 'PLAN') => MEZCLA[intencion.archetype]?.[t] ?? 1

  type Fila = (typeof personas[number] | typeof planes[number]) & { orden: number }
  const todos: Fila[] = [...personas, ...planes].map((f) => ({
    ...f, orden: f.puntuacion.porcentaje * empuje(f.tipo),
  }))

  const vivos = todos.filter((f) => !f.puntuacion.descartado).sort((a, b) => b.orden - a.orden)
  const descartados = todos.filter((f) => f.puntuacion.descartado)
    .sort((a, b) => b.puntuacion.porcentaje - a.puntuacion.porcentaje)

  // ── CAPA 4 · explicacion, solo del top que se ense~na.
  const paraExplicar: ParaExplicar[] = vivos.slice(0, TOP_EXPLICADO).map((f) => ({
    id: f.id,
    titulo: f.tipo === 'PLAN' ? (f as any).title : (f as any).display_name,
    porcentaje: f.puntuacion.porcentaje,
    componentes: f.puntuacion.componentes,
  }))
  let frases: Record<string, string> = {}
  let usoExplicacion: Uso = { tokens_entrada: 0, tokens_salida: 0, ms: 0 }
  try {
    const r = await explicar(env, paraExplicar, intencion.language)
    frases = r.frases
    usoExplicacion = r.uso
  } catch {
    // La explicacion es prosa: si el proveedor falla, la demo sigue ense~nando el numero y su
    // desglose, que es lo que de verdad hay que poder defender.
    frases = {}
  }

  const salida = (f: Fila) => ({
    tipo: f.tipo,
    id: f.id,
    titulo: f.tipo === 'PLAN' ? (f as any).title : (f as any).display_name,
    subtitulo: f.tipo === 'PLAN' ? (f as any).description : (f as any).bio,
    idioma: f.tipo === 'PLAN' ? (f as any).desc_lang : (f as any).bio_lang,
    ciudad: f.tipo === 'PLAN' ? (f as any).dest_city : (f as any).city,
    km: f.km,
    porcentaje: f.puntuacion.porcentaje,
    explicacion: frases[f.id] ?? null,
    componentes: f.puntuacion.componentes,
    motivo_descarte: f.puntuacion.descartado,
    cuando: f.tipo === 'PLAN' ? (f as any).starts_at : null,
    plazas: f.tipo === 'PLAN' ? (f as any).seats_open : null,
  })

  const suma = (...us: Uso[]): Uso => ({
    tokens_entrada: us.reduce((s, u) => s + u.tokens_entrada, 0),
    tokens_salida: us.reduce((s, u) => s + u.tokens_salida, 0),
    ms: us.reduce((s, u) => s + u.ms, 0),
  })

  return {
    consulta: q,
    degradado,      // true = la Capa 0 no respondio y esto salio de reglas, no del modelo
    intencion,      // el panel «asi lo entendi» del §10: el usuario no configura, corrige
    ventana,
    resultados: vivos.slice(0, 12).map(salida),
    descartados: descartados.slice(0, 6).map(salida),
    totales: { candidatos: todos.length, mostrados: Math.min(vivos.length, 12), descartados: descartados.length },
    // El desglose por capa, no un numero suelto: la seccion E de la propuesta hecha visible.
    tiempos: {
      capa_0_llm: usoParser.ms,
      embedding: usoEmbed.ms,
      capa_1_2_postgres: Math.max(resPersonas.ms, resPlanes.ms),
      capa_3_scoring_ms: 0,
      capa_4_llm: usoExplicacion.ms,
      total: Date.now() - t0,
    },
    tokens: suma(usoParser, usoEmbed, usoExplicacion),
  }
}, {
  // LA CACHE. La Capa 0 tarda entre 3,9 s y 15 s por variabilidad del proveedor, y las 10 frases
  // de Helder son clicables: se van a repetir. Cacheadas, la segunda vez cuestan una lectura de
  // KV y cero llamadas a la IA — que es ademas el control 4 de la seccion E de la propuesta.
  //
  // La clave la construye Nitro con la URL, y por eso este endpoint es un GET: con un POST el
  // cuerpo NO entra en la clave y dos frases distintas compartirian respuesta. Medido.
  maxAge: 60 * 60 * 6,
  swr: true,
  name: 'buscar',
  // LA VERSION VA EN LA CLAVE, Y HAY QUE SUBIRLA AL TOCAR CUALQUIER CAPA — no solo el scoring.
  // Paso el 10-sep-2026: se corrigio el parser para que la frase 8 detectara «this weekend», se
  // desplego, y las 10 frases seguian dando el resultado viejo porque salian de KV. Una cache
  // que no se invalida ense~na el trabajo de ayer y parece que el arreglo no funciono.
  getKey: (event) => `v6:${String(getQuery(event).q ?? '').trim().toLowerCase()}`,
})