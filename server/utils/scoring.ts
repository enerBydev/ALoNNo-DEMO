// CAPA 3 — el scoring. Aritmetica determinista, y la fuente del porcentaje que ve el usuario.
//
// **EL MODELO ESCRIBE LA ORACION; NUNCA ESCRIBE EL NUMERO** (regla 6 del proyecto, y la frase
// exacta de la seccion D de la propuesta). Todo lo que hay en este fichero es aritmetica: la
// misma entrada da el mismo numero siempre, se puede probar, y se puede explicar componente a
// componente. Un LLM no puede hacer ninguna de las tres cosas.
//
// LOS PESOS SON LOS DEL §7 Y NO SE TOCAN ANTES DEL DIA 7 (regla 7). Lo que si se declara aqui
// —y no estaba definido en ninguna parte— es COMO cada componente se convierte en un numero de
// 0 a 1. Ver ADR-0002: con las formulas tal cual, un match impecable daba ~72% y el brief exige
// la banda 88-95%, porque los componentes crudos no llegan a 1.0 en la practica. La similitud
// coseno de dos textos del mismo tema ronda 0,65-0,70, no 1,0; y el Jaccard penaliza tener
// intereses de mas.
//
// LOS PISOS Y TECHOS SON LO QUE SE CALIBRA EL DIA 7. Los pesos, no.

export interface Componente {
  nombre: string
  etiqueta_de: string
  etiqueta_en: string
  crudo: number
  valor: number      // normalizado a [0,1]
  peso: number
  puntos: number     // peso * valor * 100 — lo que aporta al porcentaje final
  detalle?: string
}

export interface Puntuacion {
  porcentaje: number
  componentes: Componente[]
  descartado: string | null   // si no es null, es un near-miss: por que quedo fuera
}

/** Los siete pesos del §7 para Plan→Persona. Suman 1.00. */
export const PESOS_PLAN_PERSONA = {
  taste_affinity: 0.30,
  explicit_overlap: 0.20,
  availability: 0.15,
  proximity: 0.15,
  style_fit: 0.10,
  reciprocity: 0.07,
  trust: 0.03,
} as const

/** Los pesos del §7 para Intencion→Planes. */
export const PESOS_INTENCION_PLAN = {
  intent_similarity: 0.34,
  subject_match: 0.18,
  date_fit: 0.16,
  location: 0.14,
  seats_available: 0.10,
  owner_affinity: 0.05,
  trust: 0.03,
} as const

/** LA CALIBRACION. Estos numeros son el objeto del dia 7, y por eso viven juntos y con su
 *  razon al lado. Cambiar uno cambia la ESCALA; cambiar un peso cambia las PRIORIDADES. */
export const CALIBRACION = {
  // Medido sobre el corpus real el 10-sep-2026: dos textos sin relacion rondan 0,28 de coseno
  // y un match tematico fuerte llega a ~0,68. Sin normalizar, el mejor resultado posible
  // aportaria 0,68 × 30 = 20,4 puntos de los 30 que el peso promete.
  taste_piso: 0.24,
  taste_techo: 0.68,
  // El Jaccard de dos personas con cinco intereses cada una y tres compartidos es 0,43. Exigir
  // 1,0 seria exigir que dos personas sean identicas, que no es lo que mide «comparten gusto».
  overlap_techo: 0.45,
  // La proximidad se mide contra el radio que el PROPIO plan declara (§7), no contra un numero
  // fijo: un concierto tiene radio 40 km y un viaje, otro.
  proximidad_suelo_km: 0.3,
} as const

const clamp01 = (x: number) => Math.min(1, Math.max(0, x))

/** La normalizacion del ADR-0002: piso y techo declarados, resultado en [0,1]. */
export function normalizarBanda(crudo: number, piso: number, techo: number): number {
  if (techo <= piso) return clamp01(crudo)
  return clamp01((crudo - piso) / (techo - piso))
}

/** Jaccard clasico. Es lo que el §7 pide para «tags/artistas/equipos/cocinas compartidos». */
export function jaccard(a: string[], b: string[]): { valor: number; comunes: string[] } {
  const A = new Set(a.map((x) => x.toLowerCase()))
  const B = new Set(b.map((x) => x.toLowerCase()))
  if (!A.size || !B.size) return { valor: 0, comunes: [] }
  const comunes = [...A].filter((x) => B.has(x))
  const union = new Set([...A, ...B])
  return { valor: comunes.length / union.size, comunes }
}

/** §7: exacta = 1.0 · mismo fin de semana = 0.7 · flexible = 0.4 · no disponible = 0. */
export function disponibilidad(exacto: boolean, finde: boolean, hayFecha: boolean): number {
  if (!hayFecha) return 0.6          // sin fecha en la consulta, la disponibilidad no discrimina
  if (exacto) return 1
  if (finde) return 0.7
  return 0
}

/** §7: decaimiento sobre el radio que declara el plan. Fuera del radio, cero. */
export function proximidad(km: number | null, radioKm: number): number {
  if (km === null || !Number.isFinite(km)) return 0.5   // sin dato, neutro
  if (km <= CALIBRACION.proximidad_suelo_km) return 1
  return clamp01(1 - km / Math.max(radioKm, 1))
}

/** §7 style_fit: pace + budget_band + group_pref + idioma comun. Cada eje aporta lo mismo. */
export function estilo(
  persona: { pace: string | null; budget_band: string | null; group_pref: string | null; languages: string[] },
  plan: { pace: string | null; budget_band: string | null; language_pref: string[] | null },
): { valor: number; detalle: string } {
  const ejes: Array<[string, boolean | null]> = [
    ['ritmo', plan.pace ? persona.pace === plan.pace : null],
    ['presupuesto', plan.budget_band ? persona.budget_band === plan.budget_band : null],
    ['idioma', plan.language_pref?.length
      ? persona.languages.some((l) => plan.language_pref!.includes(l))
      : null],
    // Un plan de dos no le va bien a quien solo quiere grupos, y al reves.
    ['formato', persona.group_pref ? persona.group_pref !== 'small_group' : null],
  ]
  const evaluables = ejes.filter(([, v]) => v !== null)
  if (!evaluables.length) return { valor: 0.5, detalle: 'sin datos de estilo' }
  const aciertos = evaluables.filter(([, v]) => v === true)
  return {
    valor: aciertos.length / evaluables.length,
    detalle: `${aciertos.length}/${evaluables.length}: ${aciertos.map(([n]) => n).join(', ') || 'ninguno'}`,
  }
}

/** §7 trust: verification/3 · log(1+completed_plans) · penalizacion por reports. */
export function confianza(p: { verification: number; completed_plans: number; reports: number }): number {
  const verificado = clamp01((p.verification ?? 0) / 3)
  const historial = clamp01(Math.log(1 + (p.completed_plans ?? 0)) / Math.log(21)) // 20 planes = 1.0
  const castigo = clamp01((p.reports ?? 0) * 0.5)
  return clamp01((verificado * 0.5 + historial * 0.5) - castigo)
}

/** Las categorias complementarias del §7. Tabla explicita: el brief dice que NO se infieren. */
const COMPLEMENTARIAS: Record<string, string[]> = {
  holiday: ['weekend_trip', 'restaurant'],
  weekend_trip: ['holiday', 'activity'],
  activity: ['weekend_trip'],
  concert: ['restaurant'],
  football: ['restaurant'],
  restaurant: ['concert', 'football', 'holiday'],
}

export function encajeCategoria(a: string | null, b: string | null): number {
  if (!a || !b) return 0.5
  if (a === b) return 1
  return COMPLEMENTARIAS[a]?.includes(b) ? 0.7 : 0.2
}

/** §7 reciprocity: ¿lo que esta persona declara querer encaja con este tipo de plan?
 *  Es lo que hace que la frase 6 encuentre a la persona de la frase 1. */
export function reciprocidad(intereses: string[], tagsDelPlan: string[], categoria: string | null): number {
  const { valor } = jaccard(intereses, [...tagsDelPlan, categoria ?? ''])
  return clamp01(valor * 3)   // un solo interes compartido con el plan ya es una senal
}

function comp(
  nombre: string, de: string, en: string, crudo: number, valor: number, peso: number, detalle?: string,
): Componente {
  return { nombre, etiqueta_de: de, etiqueta_en: en, crudo, valor, peso, puntos: peso * valor * 100, detalle }
}

/** El score Plan→Persona del §7, con sus siete componentes. */
export function puntuarPersona(
  persona: {
    similitud: number; km: number | null; disponible_exacto: boolean; disponible_finde: boolean
    interests: string[]; top_artists: string[] | null; top_teams: string[] | null; cuisines: string[] | null
    pace: string | null; budget_band: string | null; group_pref: string | null; languages: string[]
    verification: number; completed_plans: number; reports: number
  },
  contexto: {
    tags: string[]; categoria: string | null; radioKm: number; hayFecha: boolean
    pace?: string | null; budget_band?: string | null; language_pref?: string[] | null
    /** La fecha concreta, para que la explicacion no tenga que adivinarla (y se la invente). */
    fechaTexto?: string | null
  },
): Puntuacion {
  const P = PESOS_PLAN_PERSONA
  const gustos = [
    ...(persona.interests ?? []), ...(persona.top_artists ?? []),
    ...(persona.top_teams ?? []), ...(persona.cuisines ?? []),
  ]
  const solape = jaccard(gustos, contexto.tags)
  const est = estilo(persona, {
    pace: contexto.pace ?? null,
    budget_band: contexto.budget_band ?? null,
    language_pref: contexto.language_pref ?? null,
  })
  const disp = disponibilidad(persona.disponible_exacto, persona.disponible_finde, contexto.hayFecha)
  const prox = proximidad(persona.km, contexto.radioKm)

  const componentes = [
    comp('taste_affinity', 'Gusto parecido', 'Shared taste',
      persona.similitud,
      normalizarBanda(persona.similitud, CALIBRACION.taste_piso, CALIBRACION.taste_techo),
      P.taste_affinity),
    comp('explicit_overlap', 'Intereses en comun', 'Interests in common',
      solape.valor, clamp01(solape.valor / CALIBRACION.overlap_techo), P.explicit_overlap,
      solape.comunes.slice(0, 4).join(', ')),
    comp('availability', 'Disponibilidad', 'Availability', disp, disp, P.availability,
      persona.disponible_exacto
        ? (contexto.fechaTexto ?? '')
        : persona.disponible_finde ? 'weekend' : '—'),
    comp('proximity', 'Cercania', 'Distance', persona.km ?? -1, prox, P.proximity,
      persona.km === null ? undefined : `${persona.km.toFixed(1)} km`),
    comp('style_fit', 'Estilo compatible', 'Style fit', est.valor, est.valor, P.style_fit, est.detalle),
    comp('reciprocity', 'Busca algo asi', 'Wants this kind of plan',
      reciprocidad(persona.interests ?? [], contexto.tags, contexto.categoria),
      reciprocidad(persona.interests ?? [], contexto.tags, contexto.categoria), P.reciprocity),
    comp('trust', 'Confianza', 'Trust', confianza(persona), confianza(persona), P.trust),
  ]

  // La fecha es filtro DURO (§6 capa 1): «una fecha que no funciona no es un 60% de match, no es
  // match». Si llego hasta aqui sin disponibilidad, se marca como descartado y no se rankea.
  const descartado = contexto.hayFecha && disp === 0 ? 'no esta libre esa fecha' : null

  return {
    porcentaje: Math.round(componentes.reduce((s, c) => s + c.puntos, 0)),
    componentes: componentes.sort((a, b) => b.puntos - a.puntos),
    descartado,
  }
}

/** El score Intencion→Plan del §7. Es el de la frase 6: el usuario NO tiene reserva y lo que
 *  necesita primero es A QUE IR, asi que las plazas libres pesan de verdad. */
export function puntuarPlan(
  plan: {
    similitud: number; km: number | null; seats_open: number; subject: string | null
    tags: string[]; category: string; starts_at: string; radius_km: number
  },
  contexto: {
    subject: string | null; subjectEspecificidad: 'named' | 'genre' | 'open'
    categoria: string | null; desde: string | null; hasta: string | null
    tags: string[]; radioKm: number
  },
): Puntuacion {
  const P = PESOS_INTENCION_PLAN

  // §7: si el sujeto viene con nombre propio, manda el solape LEXICO exacto — «Coldplay» es un
  // token, no un concepto. Si es un genero, manda lo semantico.
  let sujeto = 0.5
  if (contexto.subject && plan.subject) {
    const igual = plan.subject.toLowerCase().includes(contexto.subject.toLowerCase())
      || contexto.subject.toLowerCase().includes(plan.subject.toLowerCase())
    sujeto = contexto.subjectEspecificidad === 'named' ? (igual ? 1 : 0) : (igual ? 1 : 0.5)
  } else if (contexto.subjectEspecificidad === 'open') {
    sujeto = 0.6   // la frase 8 no nombra nada: el sujeto no puede penalizar
  }

  let fecha = 0.6   // sin ventana declarada, neutro (§7: «standing = 0.6 neutro»)
  if (contexto.desde) {
    const ini = new Date(contexto.desde).getTime()
    const fin = new Date(contexto.hasta ?? contexto.desde).getTime() + 86_400_000
    const cuando = new Date(plan.starts_at).getTime()
    if (cuando >= ini && cuando <= fin) fecha = 1
    else {
      const dias = Math.min(Math.abs(cuando - ini), Math.abs(cuando - fin)) / 86_400_000
      fecha = dias <= 3 ? 0.5 : dias <= 10 ? 0.2 : 0
    }
  }

  const componentes = [
    comp('intent_similarity', 'Encaja con lo que pides', 'Matches what you asked',
      plan.similitud,
      normalizarBanda(plan.similitud, CALIBRACION.taste_piso, CALIBRACION.taste_techo),
      P.intent_similarity),
    comp('subject_match', 'Es justo eso', 'Exactly that', sujeto, sujeto, P.subject_match,
      plan.subject ?? undefined),
    comp('date_fit', 'Cuadra la fecha', 'Date fits', fecha, fecha, P.date_fit,
      plan.starts_at.slice(0, 10)),
    comp('location', 'Donde quieres', 'Where you want',
      plan.km ?? -1, proximidad(plan.km, Math.max(contexto.radioKm, plan.radius_km)), P.location,
      plan.km === null ? undefined : `${plan.km.toFixed(1)} km`),
    // ESTE es el componente que ordena bien la frase 6: por similitud pura gana el plan LLENO,
    // porque su texto se parece igual. Un plan sin plazas no sirve para lo que pediste.
    comp('seats_available', 'Queda plaza', 'Seat available',
      plan.seats_open, plan.seats_open > 0 ? 1 : 0.2, P.seats_available,
      plan.seats_open > 0 ? `${plan.seats_open}` : '0'),
    comp('owner_affinity', 'Afinidad con quien lo organiza', 'Affinity with the organiser',
      0.5, 0.5, P.owner_affinity),
    comp('trust', 'Confianza', 'Trust', 0.6, 0.6, P.trust),
  ]

  return {
    porcentaje: Math.round(componentes.reduce((s, c) => s + c.puntos, 0)),
    componentes: componentes.sort((a, b) => b.puntos - a.puntos),
    descartado: encajeCategoria(contexto.categoria, plan.category) < 0.3 ? 'otra categoria' : null,
  }
}
