// CAPA 0 — comprension de la frase. Una sola llamada al LLM por busqueda (§6 del brief).
//
// DOS DECISIONES DE DISENO QUE VALE LA PENA CONOCER:
//
// 1. **El modelo no escribe fechas.** Devuelve una EXPRESION de un conjunto cerrado
//    (`manana`, `este_finde`, `proximo_mes`...) y el codigo la resuelve contra el reloj del
//    servidor. Es el plan B que el §12 del brief propone para el riesgo «el parser falla con
//    fechas relativas en aleman», y ademas evita que invente un 2026-02-30.
//
// 2. **`has_concrete_event` y `user_has_booking` son dos preguntas distintas** (ADR-0003).
//    El brief las mezclaba en una, y por eso la frase 6 —el momento estrella— fallaba por
//    diseno: hay un concierto de Coldplay identificable (evento concreto: SI) pero quien
//    escribe no tiene entrada (reserva propia: NO). La regla de mezcla se ata a la segunda.

export type Arquetipo = 'plan_seeks_person' | 'plan_seeks_plan' | 'intent_seeks_any' | 'standing_interest'

export type Expresion =
  | 'hoy' | 'manana' | 'este_finde' | 'este_sabado' | 'este_domingo'
  | 'viernes_noche' | 'esta_semana' | 'proximo_mes' | 'mes_nombrado' | 'sin_fecha'

export interface Intencion {
  archetype: Arquetipo
  archetype_secundario: Arquetipo | null
  has_concrete_event: boolean
  user_has_booking: boolean
  subject_specificity: 'named' | 'genre' | 'open'
  language: 'de' | 'en'
  category: string | null
  /** La frase va de moverse en coche: ofrecer o buscar plaza. `pickando.docx`. */
  trayecto: boolean
  /** Adonde va, tal y como lo escribio: puede ser un barrio, no solo una ciudad. */
  hacia: string | null
  subject: string | null
  city: string | null
  dest_city: string | null
  fecha: { expresion: Expresion; mes: string | null }
  seats_open: number | null
  must_match: string[]
  nice_to_have: string[]
  pace: string | null
  budget_band: string | null
  confidence: number
  unparsed: string[]
  /** Lo que dijo el modelo antes de que el arbol del §9-A decidiera. Se ense~na cuando difieren. */
  archetype_modelo?: Arquetipo
}

export interface Ventana {
  // La etiqueta la LEE EL USUARIO: va en su idioma, no en el del codigo. Se escapo un «el mes
  // que viene» en espanol dentro de una interfaz en ingles, y se veia en la primera pantalla.
  desde: string | null   // ISO date
  hasta: string | null
  etiqueta: string       // lo que se le ense~na al usuario en el panel «asi lo entendi»
  exacta: boolean        // true si el filtro duro debe exigir la fecha
}

export const SISTEMA_PARSER = `Eres el analizador de intenciones de ALoNNo, un producto que conecta a personas
que quieren hacer planes juntas. Recibes UNA frase en aleman o en ingles y devuelves SOLO un
objeto JSON. Nada de texto alrededor, nada de explicaciones.

## Los cuatro arquetipos

- "plan_seeks_person": quien escribe YA TIENE un plan o una reserva y busca a alguien que le
  acompane.
- "plan_seeks_plan": tiene un plan y busca OTRO PLAN o a alguien con un plan parecido, tipicamente
  un viaje en las mismas fechas.
- "intent_seeks_any": quiere hacer algo, tiene una ventana de tiempo, pero NO tiene nada
  reservado ni ninguna entrada.
- "standing_interest": un interes continuo, SIN ninguna fecha. "Busco gente a la que le guste X".

## Las dos banderas que mas se confunden

- "has_concrete_event": ¿existe un evento identificable en el mundo? Un concierto de un grupo
  con nombre, un partido concreto, una reserva. NO depende de quien escribe.
- "user_has_booking": ¿lo tiene YA quien escribe? Una entrada, una mesa reservada, un viaje
  pagado. Si dice "no tengo entrada todavia", "quiero ir", "me gustaria", es FALSE.

Ejemplo que hay que acertar: "I want to go to a Coldplay concert next month. I do not have a
ticket yet" -> has_concrete_event: true (el concierto existe), user_has_booking: false (el no
tiene entrada), archetype: "intent_seeks_any".

## Fechas: NO ESCRIBAS NINGUNA FECHA

Devuelve solo una expresion de esta lista cerrada, y el sistema la resuelve:
"hoy", "manana", "este_finde", "este_sabado", "este_domingo", "viernes_noche", "esta_semana",
"proximo_mes", "mes_nombrado", "sin_fecha".
Si la frase nombra un mes ("in October", "im Oktober"), usa "mes_nombrado" y pon el mes en
ingles y en minusculas en el campo "mes".
Si no hay ninguna referencia temporal, usa "sin_fecha".

## Ciudades y destino

"city" es donde esta o busca quien escribe. "dest_city" solo se rellena cuando el plan OCURRE en
otro sitio (un viaje): "Ich habe eine Reise nach Barcelona gebucht" -> city: null o la suya,
dest_city: "Barcelona".
Usa siempre la grafia sin dieresis: Dusseldorf, Koln, Munchen.

## Resto de campos

- "category": uno de concert, football, weekend_trip, holiday, restaurant, activity, commute,
  errands, nightlife, gym. null si la frase no lo dice ("algo espontaneo" -> null).
  Las cuatro ultimas son MOTIVOS DE VIAJE EN COCHE: "commute" es ir o volver del trabajo,
  "errands" recados o compras, "nightlife" salir de noche, "gym" entrenar.
- "trayecto": true si la frase va de MOVERSE EN COCHE — ofrecer o buscar plaza, una ruta, una
  hora de salida, un sitio al que llegar. "Ich fahre morgen um 8 nach Mitte, zwei Plaetze frei"
  -> true. "Ich habe ein Ticket fuer Burna Boy" -> false: eso es un plan, no un viaje.
- "hacia": el sitio AL QUE SE VA cuando es un trayecto, tal y como lo escribe la persona —
  puede ser un barrio ("Mitte", "Ehrenfeld"), no solo una ciudad. null si no lo dice.
  OJO: "dest_city" es SOLO una ciudad. Un barrio va en "hacia", nunca en "dest_city".
- "subject_specificity": "named" si nombra un artista, equipo o sitio concreto; "genre" si solo
  dice el estilo (techno, afrobeats); "open" si no dice nada.
- "must_match" / "nice_to_have": etiquetas cortas en ingles, snake_case. **Maximo 3 en total
  entre las dos listas**: cada token que escribes es tiempo que el usuario espera mirando una
  pantalla, y tres etiquetas ya discriminan.
- "confidence": 0..1. Si dudas entre dos arquetipos, pon el segundo en "archetype_secundario".
- "unparsed": trozos de la frase que no supiste colocar. Deja la lista VACIA salvo que de
  verdad haya algo que no encajaba en ningun campo.

Devuelve exactamente estas claves: archetype, archetype_secundario, has_concrete_event,
user_has_booking, subject_specificity, language, category, subject, city, dest_city,
fecha {expresion, mes}, seats_open, must_match, nice_to_have, pace, budget_band, confidence,
unparsed, trayecto, hacia.`

// Las seis primeras son planes; las cuatro ultimas, motivos de viaje en coche. Conviven en la
// misma columna a proposito: el motor no distingue «plan» de «trayecto», y por eso el mismo
// motor sirve a los dos productos del hilo de Workana (docs/conocimiento/07-pickando-vs-alonno.md).
const CATEGORIAS = ['concert', 'football', 'weekend_trip', 'holiday', 'restaurant', 'activity',
  'commute', 'errands', 'nightlife', 'gym']
const CATEGORIAS_DE_COCHE = ['commute', 'errands', 'nightlife', 'gym']
const ARQUETIPOS: Arquetipo[] = ['plan_seeks_person', 'plan_seeks_plan', 'intent_seeks_any', 'standing_interest']
const MESES = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august',
  'september', 'october', 'november', 'december']

/** Normaliza lo que devuelva el modelo. Nunca confiamos en que respete el contrato al 100%:
 *  la demo tiene que seguir en pie aunque el modelo se invente una categoria. */
export function normalizar(bruto: any): Intencion {
  const enumerado = <T,>(v: any, permitidos: readonly T[], defecto: T): T =>
    permitidos.includes(v) ? (v as T) : defecto
  const lista = (v: any): string[] =>
    Array.isArray(v) ? v.filter((x) => typeof x === 'string').slice(0, 8) : []
  const ciudad = (v: any): string | null => {
    if (typeof v !== 'string' || !v.trim()) return null
    return v.normalize('NFD').replace(/[̀-ͯ]/g, '').trim()
  }
  const exp = bruto?.fecha?.expresion ?? bruto?.date?.expresion ?? 'sin_fecha'
  const intencion: Intencion = {
    archetype: enumerado(bruto?.archetype, ARQUETIPOS, 'intent_seeks_any'),
    archetype_secundario: ARQUETIPOS.includes(bruto?.archetype_secundario)
      ? bruto.archetype_secundario : null,
    has_concrete_event: Boolean(bruto?.has_concrete_event),
    user_has_booking: Boolean(bruto?.user_has_booking),
    subject_specificity: enumerado(bruto?.subject_specificity, ['named', 'genre', 'open'] as const, 'open'),
    language: bruto?.language === 'de' ? 'de' : 'en',
    category: CATEGORIAS.includes(bruto?.category) ? bruto.category : null,
    subject: typeof bruto?.subject === 'string' && bruto.subject.trim() ? bruto.subject.trim() : null,
    city: ciudad(bruto?.city),
    dest_city: ciudad(bruto?.dest_city),
    fecha: {
      expresion: enumerado(exp, ['hoy', 'manana', 'este_finde', 'este_sabado', 'este_domingo',
        'viernes_noche', 'esta_semana', 'proximo_mes', 'mes_nombrado', 'sin_fecha'] as const, 'sin_fecha'),
      mes: MESES.includes(String(bruto?.fecha?.mes ?? '').toLowerCase())
        ? String(bruto.fecha.mes).toLowerCase() : null,
    },
    seats_open: Number.isFinite(bruto?.seats_open) ? Number(bruto.seats_open) : null,
    // Una categoria de coche implica trayecto aunque el modelo no marque la bandera: el codigo
    // aplica el arbol, el modelo solo extrae hechos (la regla que sostiene toda la Capa 0).
    trayecto: Boolean(bruto?.trayecto) || CATEGORIAS_DE_COCHE.includes(bruto?.category),
    hacia: typeof bruto?.hacia === 'string' && bruto.hacia.trim() ? bruto.hacia.trim() : null,
    must_match: lista(bruto?.must_match),
    nice_to_have: lista(bruto?.nice_to_have),
    pace: ['relaxed', 'moderate', 'intense'].includes(bruto?.pace) ? bruto.pace : null,
    budget_band: ['low', 'mid', 'high'].includes(bruto?.budget_band) ? bruto.budget_band : null,
    confidence: Number.isFinite(bruto?.confidence) ? Math.min(1, Math.max(0, Number(bruto.confidence))) : 0.5,
    unparsed: lista(bruto?.unparsed),
  }
  intencion.archetype_modelo = intencion.archetype
  intencion.archetype = decidirArquetipo(intencion)
  return intencion
}

/** EL ARQUETIPO LO DECIDE EL CODIGO, NO EL MODELO.
 *
 * Medido el 10-sep-2026: el modelo acierta los HECHOS —«¿tiene entrada?» → `user_has_booking:
 * false`, correcto— y falla la TAXONOMIA: etiquetaba la frase 6 como `plan_seeks_person` cuando
 * el arbol del §9-A dice `intent_seeks_any`. Y la frase 6 es, segun el brief, el momento estrella
 * de la demo: si se clasifica como plan concreto, devuelve gente parecida a quien pregunta y
 * NUNCA a quien tiene la entrada de sobra. El brief avisa dos veces de este fallo.
 *
 * Pedirle mejor la taxonomia es pelear con el prompt para siempre. El arbol del §9-A es
 * determinista en cuanto tienes las dos banderas, asi que se aplica aqui — donde se puede
 * probar. Es el mismo criterio que con las fechas: el modelo dice QUE dice la frase, el codigo
 * decide QUE se hace con eso.
 *
 * Se conserva lo que dijo el modelo en `archetype_modelo` para poder ense~nar la discrepancia. */
export function decidirArquetipo(i: Intencion): Arquetipo {
  if (i.user_has_booking) {
    // Tiene algo reservado. ¿Busca compania para SU plan, o busca otro plan que coincida?
    // Lo segundo es el caso del viaje: «he reservado Barcelona, busco a quien vaya en esas fechas».
    return i.dest_city ? 'plan_seeks_plan' : 'plan_seeks_person'
  }
  // No tiene nada reservado: es una intencion. La distingue el tiempo, no el tema.
  return i.fecha.expresion === 'sin_fecha' ? 'standing_interest' : 'intent_seeks_any'
}

/** EL CODIGO CORRIGE AL MODELO TAMBIEN EN LAS FECHAS.
 *
 * Medido el 10-sep-2026 con la frase 8 de Helder —«I am in Berlin this weekend and would like to
 * do something spontaneous»—: el modelo devolvia `sin_fecha`, y con eso la frase se clasificaba
 * como `standing_interest` (un interes permanente) cuando es una intencion CON ventana. Se
 * perdia el filtro del fin de semana entero.
 *
 * Una expresion temporal explicita en la frase gana sobre el silencio del modelo. Al reves no:
 * si el modelo SI vio una fecha, se respeta — el sabe leer «am zweiten Oktoberwochenende» y
 * estas reglas no. */
export function reforzarFecha(i: Intencion, q: string): Intencion {
  if (i.fecha.expresion !== 'sin_fecha') return i
  const t = q.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
  const reglas: Array<[RegExp, Expresion]> = [
    [/\b(morgen|tomorrow)\b/, 'manana'],
    [/\b(heute|today|tonight|heute abend)\b/, 'hoy'],
    [/\b(samstag|saturday)\b/, 'este_sabado'],
    [/\b(sonntag|sunday)\b/, 'este_domingo'],
    [/\b(freitag|friday)\b/, 'viernes_noche'],
    [/\b(wochenende|weekend)\b/, 'este_finde'],
    [/\b(diese woche|this week)\b/, 'esta_semana'],
    [/\b(nachsten monat|next month|im monat)\b/, 'proximo_mes'],
  ]
  for (const [re, exp] of reglas) {
    if (re.test(t)) {
      // EL ARQUETIPO SE RECALCULA. `normalizar()` ya lo habia decidido con la fecha que dijo el
      // modelo; si aqui se cambia la fecha y no se vuelve a decidir, la correccion no llega a
      // ninguna parte. Paso el 10-sep-2026 con la frase 8: la fecha quedaba bien y el arquetipo
      // seguia siendo `standing_interest`. La prueba unitaria no lo cazo porque llamaba a las
      // dos funciones por separado, que es justo lo que el codigo real NO hace.
      const corregida = { ...i, fecha: { ...i.fecha, expresion: exp } }
      return { ...corregida, archetype: decidirArquetipo(corregida) }
    }
  }
  return i
}

const DIA = 86_400_000
const iso = (d: Date) => d.toISOString().slice(0, 10)

/** Resuelve la expresion contra el reloj del servidor. Aqui, y en ningun otro sitio, se
 *  convierte «este sabado» en una fecha. */
export function resolverVentana(i: Intencion, ahora = new Date()): Ventana {
  const hoy = new Date(Date.UTC(ahora.getUTCFullYear(), ahora.getUTCMonth(), ahora.getUTCDate()))
  const mas = (n: number) => new Date(hoy.getTime() + n * DIA)
  // 0 = domingo. Dias hasta el proximo <objetivo>, contando hoy como 0 solo si coincide.
  const hasta = (objetivo: number) => (objetivo - hoy.getUTCDay() + 7) % 7

  switch (i.fecha.expresion) {
    case 'hoy':
      return { desde: iso(hoy), hasta: iso(hoy), etiqueta: 'today', exacta: true }
    case 'manana':
      return { desde: iso(mas(1)), hasta: iso(mas(1)), etiqueta: 'tomorrow', exacta: true }
    case 'este_sabado': {
      const s = mas(hasta(6))
      return { desde: iso(s), hasta: iso(s), etiqueta: 'this Saturday', exacta: true }
    }
    case 'este_domingo': {
      const s = mas(hasta(0) === 0 ? 7 : hasta(0))
      return { desde: iso(s), hasta: iso(s), etiqueta: 'this Sunday', exacta: true }
    }
    case 'viernes_noche': {
      const v = mas(hasta(5))
      return { desde: iso(v), hasta: iso(v), etiqueta: 'Friday evening', exacta: true }
    }
    case 'este_finde': {
      const sab = mas(hasta(6))
      return { desde: iso(sab), hasta: iso(new Date(sab.getTime() + DIA)), etiqueta: 'this weekend', exacta: false }
    }
    case 'esta_semana':
      return { desde: iso(hoy), hasta: iso(mas(7)), etiqueta: 'this week', exacta: false }
    case 'proximo_mes':
      return { desde: iso(mas(21)), hasta: iso(mas(51)), etiqueta: 'next month', exacta: false }
    case 'mes_nombrado': {
      if (!i.fecha.mes) return { desde: iso(mas(21)), hasta: iso(mas(51)), etiqueta: 'next month', exacta: false }
      const idx = MESES.indexOf(i.fecha.mes)
      // El mes nombrado que viene: si ya paso este ano, el del ano que viene.
      let ano = hoy.getUTCFullYear()
      if (idx < hoy.getUTCMonth()) ano += 1
      const ini = new Date(Date.UTC(ano, idx, 1))
      const fin = new Date(Date.UTC(ano, idx + 1, 0))
      return { desde: iso(ini), hasta: iso(fin), etiqueta: `in ${i.fecha.mes}`, exacta: false }
    }
    default:
      return { desde: null, hasta: null, etiqueta: 'no fixed date', exacta: false }
  }
}


/** PARSER DE RESERVA: reglas, sin LLM.
 *
 * Si la Capa 0 falla —el proveedor esta caido, agoto el cupo, devuelve basura—, la demo NO puede
 * quedarse en blanco delante del cliente. Esto extrae lo minimo con expresiones regulares para
 * que las capas 1 y 2 sigan funcionando: la busqueda semantica no necesita el parser, solo la
 * frase. Se pierde el panel «asi lo entendi» afinado, no la busqueda.
 *
 * Se marca con `confidence: 0` para que la UI lo diga: es un modo degradado, no un resultado
 * normal, y la regla 8 prohibe disimularlo. */
export function parsearSinModelo(q: string): Intencion {
  const t = q.toLowerCase()
  // «Düsseldorf» y «Duesseldorf» son la misma ciudad, y la segunda es como la escribe media
  // Alemania en un teclado que no es el suyo. Sin plegar los digrafos, la frase 1 de Helder
  // escrita «Duesseldorf» perdia la ciudad entera: `city: null`, sin centro y sin radio.
  const sinTildes = t.normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/ae/g, 'a').replace(/oe/g, 'o').replace(/ue/g, 'u').replace(/\u00df/g, 'ss')
  const aleman = /\b(ich|nicht|und|habe|suche|jemanden|moechte|mochte|wochenende|freund)\b/.test(sinTildes)

  const CIUDADES = ['berlin', 'dusseldorf', 'koln', 'frankfurt', 'munchen', 'munich', 'cologne', 'barcelona']
  const encontrada = CIUDADES.find((c) => sinTildes.includes(c)) ?? null
  let ciudad = encontrada
    ? { munich: 'Munchen', cologne: 'Koln' }[encontrada] ?? encontrada[0].toUpperCase() + encontrada.slice(1)
    : null

  // ── LOS TRAYECTOS, SIN MODELO ───────────────────────────────────────────────────────────
  //
  // Esto no es un adorno del respaldo: es lo que hace que la demo no dependa del proveedor.
  // Medido el 11-sep-2026, la Capa 0 se degrado en 3 de 7 busquedas seguidas —el proveedor
  // tardaba mas de 11 s— y el respaldo devolvia `city: null` y `trayecto: false`, o sea sin
  // centro geografico y sin radio de 2 km: a un berlines se le contestaba con coches de
  // Dusseldorf. Un respaldo que no entiende la frase mas comun del producto no es un respaldo.
  //
  // «von X nach Y», «from X to Y», «nach Y», «to Y», «Richtung Y», «towards Y». El nombre del
  // sitio se deja tal cual: `centroDe()` ya resuelve barrios y ciudades, y sin diacriticos.
  const DE_A = [
    /\bvon\s+([a-zaeoeuess.\- ]{3,28}?)\s+nach\s+([a-zaeoeuess.\- ]{3,28}?)(?=[,.;!?]|\s+(?:um|am|gegen|morgen|heute|mit|und|zwei|ein)\b|$)/,
    /\bfrom\s+([a-z.\- ]{3,28}?)\s+to\s+([a-z.\- ]{3,28}?)(?=[,.;!?]|\s+(?:at|on|around|tomorrow|today|with|and|every|each|most|in|for)\b|$)/,
  ]
  const SOLO_A = [
    /\b(?:nach|richtung)\s+([a-zaeoeuess.\- ]{3,28}?)(?=[,.;!?]|\s+(?:um|am|gegen|morgen|heute|mit|und|zwei|ein|fahren|faehrt)\b|$)/,
    /\b(?:to|towards|toward)\s+([a-z.\- ]{3,28}?)(?=[,.;!?]|\s+(?:at|on|around|tomorrow|today|with|and|every|each|most)\b|$)/,
  ]
  const limpiar = (x: string) => x.trim().replace(/\s+/g, ' ').replace(/[.,;]+$/, '')
  let desde: string | null = null
  let hacia: string | null = null
  for (const re of DE_A) {
    const m = sinTildes.match(re)
    if (m) { desde = limpiar(m[1]); hacia = limpiar(m[2]); break }
  }
  if (!hacia) {
    for (const re of SOLO_A) {
      const m = sinTildes.match(re)
      if (m) { hacia = limpiar(m[1]); break }
    }
  }
  // Las palabras que delatan un coche aunque la frase no diga ni origen ni destino.
  const hayCoche = /\b(mitfahr|mitfahrgelegenheit|fahre|faehrt|fahrt|fahren|platz frei|plaetze frei|plaetze|auto|beifahrer|pendel|rideshare|ride|lift|driving|drive|drives|car|seat|seats|carpool|commute)\b/
    .test(sinTildes)
  const trayecto = Boolean(hacia) || hayCoche
  // El origen manda sobre la ciudad suelta: «von Neukolln nach Mitte» centra en Neukolln, no en
  // el primer nombre de ciudad que aparezca en la frase.
  if (desde) ciudad = desde

  let expresion: Expresion = 'sin_fecha'
  if (/\b(morgen|tomorrow)\b/.test(sinTildes)) expresion = 'manana'
  else if (/\b(samstag|saturday)\b/.test(sinTildes)) expresion = 'este_sabado'
  else if (/\b(freitag|friday)\b/.test(sinTildes)) expresion = 'viernes_noche'
  else if (/\b(wochenende|weekend)\b/.test(sinTildes)) expresion = 'este_finde'
  else if (/\b(monat|month)\b/.test(sinTildes)) expresion = 'proximo_mes'

  // «No tengo entrada todavia» / «me gustaria ir» = no hay reserva propia.
  const sinReserva = /\b(no ticket|not have a ticket|kein ticket|keine karte|mochte|moechte|would like|want to)\b/
    .test(sinTildes)
  const conReserva = /\b(habe noch ein ticket|extra ticket|spare ticket|reserviert|booked|gebucht|have an extra)\b/
    .test(sinTildes)

  // Un trayecto de diario se pide para hoy o para ma~nana, no «alguna vez»: si la frase habla de
  // coche y no dice cuando, se asume hoy. Sin esto el filtro de fecha no acota nada y salen
  // viajes de dentro de tres semanas por delante del de las 08:10.
  if (trayecto && expresion === 'sin_fecha' && /\b(frueh|morgens|jetzt|gleich|now|early|morning)\b/.test(sinTildes)) {
    expresion = 'hoy'
  }

  return normalizar({
    archetype: 'intent_seeks_any',
    has_concrete_event: conReserva,
    user_has_booking: conReserva && !sinReserva,
    subject_specificity: hacia ? 'named' : 'open',
    language: aleman ? 'de' : 'en',
    category: trayecto ? 'commute' : null,
    subject: hacia,
    city: ciudad,
    dest_city: null,
    fecha: { expresion, mes: null },
    trayecto,
    hacia,
    must_match: [],
    nice_to_have: [],
    confidence: 0,
    unparsed: [trayecto
      ? 'la Capa 0 no respondio: el trayecto se leyo por reglas (origen, destino y hora)'
      : 'la Capa 0 no respondio: esto es un analisis de reserva por reglas'],
  })
}
