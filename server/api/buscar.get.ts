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
  // EL PRESUPUESTO DE LA PETICION ENTERA. Sin esto, cada capa tenia su techo y nadie miraba la
  // suma: 15 s de Capa 0 + 9 s de Capa 4 son 24 s, y el navegador no sabe si eso es una espera o
  // una averia. Con presupuesto, la Capa 4 —que es prosa, la unica capa que el cliente NO
  // necesita para decidir— cobra lo que sobre y se salta si no sobra nada.
  const PRESUPUESTO_MS = 20_000
  const q = String(getQuery(event).q ?? '').trim()
  if (!q) throw createError({ statusCode: 400, statusMessage: 'falta ?q=<frase>' })
  if (q.length > 500) throw createError({ statusCode: 400, statusMessage: 'frase demasiado larga' })
  // DE DONDE SALE QUIEN PREGUNTA. `pickando.docx` lo pide con nombre propio —«Pickup location:
  // automatically allows you to find a driver based on a passenger's location»— y sin esto una
  // frase como «Ich suche eine Mitfahrgelegenheit nach Mitte» no tiene centro: devuelve coches
  // de Dusseldorf a alguien de Berlin. La ciudad de la frase SIEMPRE gana; esto es el respaldo.
  // Va por la URL y no por la cookie a proposito: la clave de cache se construye con la URL, y
  // dos ciudades distintas tienen que ser dos entradas distintas.
  const ciudadDeQuienPregunta = String(getQuery(event).ciudad ?? '').trim() || null

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
  let motivoDegradado: string | null = null
  try {
    // TIEMPO MAXIMO PARA LA CAPA 0. Medido: el mismo modelo y la misma frase tardan entre 3,9 s
    // y 91 s segun la cola del proveedor. Una demo que se mira en vivo no puede quedarse noventa
    // segundos en blanco: pasado el limite se usa el parser de reglas, que da un resultado peor
    // pero inmediato. Y se declara.
    // Un poco por encima del techo del proveedor (11 s), para que el que corte sea el de dentro
    // —que puede reintentar— y no este, que solo sabe rendirse.
    const LIMITE_MS = 15_000
    const r = await Promise.race([
      chatJson(env, SISTEMA_PARSER, q),
      new Promise<never>((_, rechaza) =>
        setTimeout(() => rechaza(new Error('capa 0: se agoto el tiempo')), LIMITE_MS)),
    ])
    intencion = normalizar(r.json)
    usoParser = r.uso
  } catch (e: any) {
    intencion = parsearSinModelo(q)
    degradado = true
    // EL WORKER TENIA LA OBSERVABILIDAD ENCENDIDA AL 100 % Y NO EMITIA NI UNA LINEA. Se descubrio
    // el 11-sep-2026 auditando una averia real: `wrangler tail` devolvia `logs: []`,
    // `exceptions: []` y `outcome: "canceled"` — todo lo que se pagaba por guardar estaba vacio,
    // porque nadie escribia nada. Un `catch` mudo convierte un fallo del proveedor en «la demo
    // va rara», que es lo que no se puede diagnosticar despues.
    motivoDegradado = String(e?.statusMessage ?? e?.message ?? e).slice(0, 200)
    console.warn(`[capa-0] degradada: ${motivoDegradado} · frase=${JSON.stringify(q.slice(0, 80))}`)
  }
  // Una expresion temporal explicita en la frase gana sobre el silencio del modelo.
  intencion = reforzarFecha(intencion, q)
  const ventana = resolverVentana(intencion)

  // ── CAPA 1 + 2 · filtros duros y recuperacion, las dos dentro de Postgres.
  const { vector, uso: usoEmbed } = await embeberConsulta(env, q)
  const vec = `[${vector.map((x) => x.toFixed(6)).join(',')}]`
  const centro = centroDe(intencion.city, ciudadDeQuienPregunta)
  const comunes = {
    q_vector: vec,
    q_texto: q,
    q_idioma: intencion.language === 'de' ? 'german' : 'english',
    q_lon: centro?.[0] ?? null,
    q_lat: centro?.[1] ?? null,
    // EL NUMERO DEL DOCX. «Passenger: tracking within 1-2 km of all drivers driving on the
    // same route»: quien busca coche no quiere uno a 40 km, quiere el que le pasa por delante.
    // Un plan social sigue emparejando a 40 — son dos radios porque son dos productos, y el
    // motor los atiende con la misma consulta.
    q_radio_km: intencion.trayecto ? 2 : 40,
    q_desde: ventana.desde,
    q_hasta: ventana.hasta,
  }
  const [resPersonas, resPlanes] = await Promise.all([
    rpc<Persona>(env, 'buscar_personas', { ...comunes, q_exacta: ventana.exacta, q_excluir: null, q_limite: 50 }),
    rpc<Plan>(env, 'buscar_planes', {
      ...comunes,
      // LA CATEGORIA NO FILTRA UN TRAYECTO. A quien quiere llegar a Mitte a las ocho le da
      // exactamente igual si el conductor va al trabajo, al gimnasio o a hacer la compra: lo
      // que comparte es la carretera, no el motivo. Filtrando por `commute` se caian los otros
      // tres motivos y una busqueda real pasaba de 4 viajes a 1.
      q_categoria: intencion.trayecto ? null : intencion.category,
      q_dest_city: intencion.dest_city,
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
      radioKm: intencion.trayecto ? 2 : 40,
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
      // En un trayecto, «el sujeto» es ADONDE VAS. La Capa 0 lo saca en `hacia` —que puede ser
      // un barrio— y sin esto el componente «es justo eso» se quedaba en 0,6 neutro aunque el
      // viaje fuera exactamente a Mitte, que es lo unico que habias pedido.
      subject: intencion.subject ?? (intencion.trayecto ? intencion.hacia : null),
      subjectEspecificidad: intencion.trayecto && intencion.hacia && !intencion.subject
        ? 'named' : intencion.subject_specificity,
      // Ni filtra ni descarta: el motivo del viaje no es asunto del pasajero. Con `commute`
      // puesto, dos viajes que pasaban a 300 m se marcaban «otra categoria» y desaparecian.
      categoria: intencion.trayecto ? null : intencion.category,
      desde: ventana.desde,
      hasta: ventana.hasta,
      tags: tagsConsulta,
      radioKm: intencion.trayecto ? 2 : 40,
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

  // DOS LISTAS, NO UNA MEZCLADA. Y esto no es un gusto: la version anterior ordenaba por
  // `orden` —el porcentaje ya multiplicado por MEZCLA— y ense~naba el porcentaje SIN
  // multiplicar. Medido el 11-sep-2026: la lista salia 91·72·71·69·63·60·54·54·**86**·46, con
  // un 86 % nueve posiciones por debajo de dos 54 %.
  //
  // Por dentro es defendible (un concierto no le sirve a quien YA tiene la entrada). Por fuera
  // solo se lee de una manera: *el numero que me ense~nas no es el que usas* — y eso destruye a
  // la vez el desglose, la confianza y los primeros diez segundos.
  //
  // Con dos listas cada una ordenada por SU numero, la contradiccion no puede existir: el
  // multiplicador decide QUE LISTA VA PRIMERO, que es para lo que sirve de verdad. Y de paso la
  // pantalla explica sola que son dos cosas distintas, que es lo que el cliente dijo no entender.
  const porSuNumero = (a: Fila, b: Fila) => b.puntuacion.porcentaje - a.puntuacion.porcentaje
  const vivosPersonas = todos.filter((f) => f.tipo === 'PERSONA' && !f.puntuacion.descartado).sort(porSuNumero)
  const vivosPlanes = todos.filter((f) => f.tipo === 'PLAN' && !f.puntuacion.descartado).sort(porSuNumero)
  const vivos = [...vivosPersonas, ...vivosPlanes].sort((a, b) => b.orden - a.orden)
  const descartados = todos.filter((f) => f.puntuacion.descartado).sort(porSuNumero)

  const mandaElViaje = empuje('PLAN') >= empuje('PERSONA')

  // ── CAPA 4 · explicacion, solo del top que se ense~na. Se reparte entre las DOS listas: si se
  // explicara el top 5 global, la lista secundaria se quedaria siempre sin una sola frase.
  const paraExplicar: ParaExplicar[] = [
    ...(mandaElViaje ? vivosPlanes : vivosPersonas).slice(0, 3),
    ...(mandaElViaje ? vivosPersonas : vivosPlanes).slice(0, TOP_EXPLICADO - 3),
  ].map((f) => ({
    id: f.id,
    titulo: f.tipo === 'PLAN' ? (f as any).title : (f as any).display_name,
    porcentaje: f.puntuacion.porcentaje,
    componentes: f.puntuacion.componentes,
  }))
  let frases: Record<string, string> = {}
  let usoExplicacion: Uso = { tokens_entrada: 0, tokens_salida: 0, ms: 0 }
  try {
    // LA CAPA 4 TAMBIEN NECESITA UN TECHO. La Capa 0 tenia su `Promise.race` desde el principio
    // y esta no: medido el 11-sep-2026, una busqueda tardo 82 s en total con las capas 0-3
    // sumando 10 — los otros 70 eran esta llamada colgada, esperando a un proveedor que no
    // respondia. Una demo que se ense~na en vivo no puede tener una rama sin techo.
    const restante = PRESUPUESTO_MS - (Date.now() - t0)
    // Menos de 2,5 s no da ni para empezar: mejor entregar el numero y su desglose —que es lo
    // que hay que poder defender— que hacer esperar por una frase que no va a llegar.
    if (restante < 2_500) throw new Error(`sin presupuesto: quedaban ${restante} ms`)
    const TECHO_EXPLICACION_MS = Math.min(restante, 9_000)
    const r = await Promise.race([
      explicar(env, paraExplicar, intencion.language),
      new Promise<never>((_, rechaza) =>
        setTimeout(() => rechaza(new Error('capa 4: se agoto el tiempo')), TECHO_EXPLICACION_MS)),
    ])
    frases = r.frases
    usoExplicacion = r.uso
  } catch (e: any) {
    // La explicacion es prosa: si el proveedor falla, la demo sigue ense~nando el numero y su
    // desglose, que es lo que de verdad hay que poder defender.
    frases = {}
    console.warn(`[capa-4] sin explicacion: ${String(e?.statusMessage ?? e?.message ?? e).slice(0, 200)}`)
  }

  const salida = (f: Fila) => ({
    tipo: f.tipo,
    id: f.id,
    titulo: f.tipo === 'PLAN' ? (f as any).title : (f as any).display_name,
    subtitulo: f.tipo === 'PLAN' ? (f as any).description : (f as any).bio,
    idioma: f.tipo === 'PLAN' ? (f as any).desc_lang : (f as any).bio_lang,
    ciudad: f.tipo === 'PLAN' ? (f as any).dest_city : (f as any).city,
    km: f.km == null ? null : Math.round(Number(f.km) * 10) / 10,
    porcentaje: f.puntuacion.porcentaje,
    explicacion: frases[f.id] ?? null,
    componentes: f.puntuacion.componentes,
    motivo_descarte: f.puntuacion.descartado,
    cuando: f.tipo === 'PLAN' ? (f as any).starts_at : null,
    plazas: f.tipo === 'PLAN' ? (f as any).seats_open : null,
    // ── el viaje, cuando lo hay ───────────────────────────────────────────────────────────
    // `ruta` es null en un plan al que se llega en avion (Barcelona): ahi la tarjeta ense~na
    // un plan, no un trayecto. Es la misma fila, y la UI decide como se lee.
    viaje: f.tipo === 'PLAN' && (f as any).distancia_km != null
      ? {
          desde: (f as any).origin_city,
          hasta: (f as any).venue ?? (f as any).dest_city,
          via: (f as any).via ?? [],
          km: Number((f as any).distancia_km),
          // La tarifa es una multiplicacion, no un servicio: el docx pide «price calculated
          // per km» con min y max configurables, y eso es exactamente lo que se ense~na.
          precio_km: Number((f as any).precio_por_km),
          precio_total: Math.round(Number((f as any).distancia_km) * Number((f as any).precio_por_km) * 100) / 100,
          recurrente: (f as any).recurrente ?? null,
          // A cuanto pasa de ti la RUTA, que casi nunca es a cuanto esta el destino.
          // Redondeado aqui y no en la plantilla: «pasa a 0,76445526829 km de ti» llego a salir
          // en una respuesta real, y un numero con once decimales delata que nadie lo miro.
          km_de_tu_ruta: (f as any).km_ruta != null ? Math.round(Number((f as any).km_ruta) * 10) / 10 : null,
        }
      : null,
    conductor: f.tipo === 'PLAN' && (f as any).conductor
      ? {
          nombre: (f as any).conductor,
          coche: (f as any).conductor_coche ?? null,
          nota: (f as any).conductor_nota != null ? Number((f as any).conductor_nota) : null,
          notas: Number((f as any).conductor_notas ?? 0),
          verificado: Number((f as any).conductor_verificado ?? 0),
          viajes: Number((f as any).conductor_viajes ?? 0),
        }
      : null,
  })

  const suma = (...us: Uso[]): Uso => ({
    tokens_entrada: us.reduce((s, u) => s + u.tokens_entrada, 0),
    tokens_salida: us.reduce((s, u) => s + u.tokens_salida, 0),
    ms: us.reduce((s, u) => s + u.ms, 0),
  })

  return {
    consulta: q,
    degradado,      // true = la Capa 0 no respondio y esto salio de reglas, no del modelo
    motivo_degradado: motivoDegradado,
    intencion,      // el panel «asi lo entendi» del §10: el usuario no configura, corrige
    ventana,
    // `listas` es lo que pinta la pantalla; `resultados` se conserva plano para las pruebas y
    // para cualquier cosa que solo quiera «lo mejor de todo».
    listas: (mandaElViaje
      ? [
          { clave: 'viajes' as const, titulo: intencion.trayecto ? 'Rides going your way' : 'Plans you could join', filas: vivosPlanes },
          { clave: 'personas' as const, titulo: intencion.trayecto ? 'Drivers who match you' : 'People who fit you', filas: vivosPersonas },
        ]
      : [
          { clave: 'personas' as const, titulo: intencion.trayecto ? 'Drivers who match you' : 'People who fit you', filas: vivosPersonas },
          { clave: 'viajes' as const, titulo: intencion.trayecto ? 'Rides going your way' : 'Plans you could join', filas: vivosPlanes },
        ]
    ).map((l) => ({ clave: l.clave, titulo: l.titulo, total: l.filas.length, resultados: l.filas.slice(0, 8).map(salida) })),
    resultados: vivos.slice(0, 12).map(salida),
    descartados: descartados.slice(0, 6).map(salida),
    totales: {
      candidatos: todos.length,
      personas: vivosPersonas.length,
      viajes: vivosPlanes.length,
      mostrados: Math.min(vivos.length, 12),
      descartados: descartados.length,
    },
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
  // `?fresco=1` salta la cache. Sirve para dos cosas y las dos hacen falta:
  //   * en desarrollo, para ver el cambio que acabas de escribir en vez del de hace media hora;
  //   * delante del cliente, para poder decir «y ahora sin cache» y ense~nar los tiempos REALES
  //     de cada capa. Una demo que solo sabe ense~nar 0,3 s cacheados no esta demostrando nada.
  // No entra en la clave a proposito: la respuesta fresca se guarda en la MISMA entrada, asi que
  // forzar una vez tambien refresca a los demas.
  shouldBypassCache: (event) => Boolean(getQuery(event).fresco),
  // LA VERSION VA EN LA CLAVE, Y HAY QUE SUBIRLA AL TOCAR CUALQUIER CAPA — no solo el scoring.
  // Paso el 10-sep-2026: se corrigio el parser para que la frase 8 detectara «this weekend», se
  // desplego, y las 10 frases seguian dando el resultado viejo porque salian de KV. Una cache
  // que no se invalida ense~na el trabajo de ayer y parece que el arreglo no funciono.
  getKey: (event) => {
    const q = String(getQuery(event).q ?? '').trim().toLowerCase()
    const ciudad = String(getQuery(event).ciudad ?? '').trim().toLowerCase()
    // La ciudad entra en la clave porque cambia el resultado: la misma frase desde Berlin y
    // desde Koln devuelve coches distintos. Olvidarla serviria el resultado del otro.
    return `v8:${ciudad}:${q}`
  },
})