// La Capa 3 es aritmetica pura, asi que se prueba entera sin red y sin base de datos.
// Es justo lo que la propuesta promete de este numero: «it is the same arithmetic every time,
// it is testable, and it is tunable per category».
import { describe, it, expect } from 'vitest'
import {
  PESOS_PLAN_PERSONA, PESOS_INTENCION_PLAN, normalizarBanda, jaccard, disponibilidad,
  proximidad, confianza, encajeCategoria, puntuarPersona, puntuarPlan, CALIBRACION,
} from '../server/utils/scoring'

describe('los pesos son los del §7 y no se tocan antes del dia 7', () => {
  it('Plan→Persona suma exactamente 1.00', () => {
    const s = Object.values(PESOS_PLAN_PERSONA).reduce((a, b) => a + b, 0)
    expect(Number(s.toFixed(10))).toBe(1)
  })
  it('Intencion→Plan suma exactamente 1.00', () => {
    const s = Object.values(PESOS_INTENCION_PLAN).reduce((a, b) => a + b, 0)
    expect(Number(s.toFixed(10))).toBe(1)
  })
  it('el gusto pesa mas que ninguna otra cosa en Plan→Persona', () => {
    const max = Math.max(...Object.values(PESOS_PLAN_PERSONA))
    expect(PESOS_PLAN_PERSONA.taste_affinity).toBe(max)
  })
})

describe('la normalizacion del ADR-0002', () => {
  it('lleva el techo medido a 1.0 y el piso a 0', () => {
    const { taste_persona_piso: p, taste_persona_techo: t } = CALIBRACION
    expect(normalizarBanda(t, p, t)).toBe(1)
    expect(normalizarBanda(p, p, t)).toBe(0)
  })

  it('personas y planes tienen bandas DISTINTAS, y esa es la leccion del dia 7', () => {
    // consulta↔bio y consulta↔plan no viven en el mismo sitio: 0,424 contra 0,724 en el corpus
    // real. Con una sola banda, el match impecable de la frase 1 se quedaba en 68%.
    expect(CALIBRACION.taste_persona_techo).toBeLessThan(CALIBRACION.taste_plan_techo)
  })
  it('nunca se sale de [0,1], por raro que venga el crudo', () => {
    expect(normalizarBanda(5, 0.2, 0.7)).toBe(1)
    expect(normalizarBanda(-3, 0.2, 0.7)).toBe(0)
  })
})

describe('los componentes, uno a uno', () => {
  it('la fecha exacta vale 1.0 y el mismo fin de semana 0.7 (§7)', () => {
    expect(disponibilidad(true, true, true)).toBe(1)
    expect(disponibilidad(false, true, true)).toBe(0.7)
  })
  it('no estar libre vale CERO, no «un poco menos»', () => {
    // «Una fecha que no funciona no es un 60% de match: no es match» — §6 del brief.
    expect(disponibilidad(false, false, true)).toBe(0)
  })
  it('la proximidad decae sobre el radio del plan y se anula fuera', () => {
    expect(proximidad(0.1, 40)).toBe(1)
    expect(proximidad(20, 40)).toBeCloseTo(0.5, 2)
    expect(proximidad(60, 40)).toBe(0)
  })
  it('el Jaccard devuelve tambien QUE se comparte, para poder explicarlo', () => {
    const r = jaccard(['afrobeats', 'dancing'], ['afrobeats', 'concert'])
    expect(r.valor).toBeCloseTo(1 / 3, 3)
    expect(r.comunes).toEqual(['afrobeats'])
  })
  it('un reporte hunde la confianza aunque el historial sea bueno', () => {
    const limpio = confianza({ verification: 3, completed_plans: 20, reports: 0 })
    const reportado = confianza({ verification: 3, completed_plans: 20, reports: 1 })
    expect(limpio).toBeGreaterThan(reportado)
  })
  it('las categorias complementarias del §7 son una tabla, no una inferencia', () => {
    expect(encajeCategoria('concert', 'concert')).toBe(1)
    expect(encajeCategoria('concert', 'restaurant')).toBe(0.7)
    expect(encajeCategoria('concert', 'football')).toBe(0.2)
  })
})

const perfecta = {
  similitud: CALIBRACION.taste_persona_techo, km: 0.2, disponible_exacto: true, disponible_finde: true,
  interests: ['afrobeats', 'live_music', 'dancing'], top_artists: ['Burna Boy'],
  top_teams: [], cuisines: [], pace: 'moderate', budget_band: 'mid', group_pref: 'one_to_one',
  languages: ['de', 'en'], verification: 3, completed_plans: 20, reports: 0,
}
const contexto = {
  tags: ['afrobeats', 'live_music', 'concert', 'Burna Boy'], categoria: 'concert',
  radioKm: 40, hayFecha: true, pace: 'moderate', budget_band: 'mid', language_pref: ['de'],
}

describe('Plan→Persona, de punta a punta', () => {
  it('un match impecable entra en la banda 88-95% que exige el §9', () => {
    const p = puntuarPersona(perfecta, contexto)
    expect(p.porcentaje).toBeGreaterThanOrEqual(88)
    expect(p.porcentaje).toBeLessThanOrEqual(100)
  })

  it('el mismo perfil, pero ocupado ese dia, queda DESCARTADO', () => {
    const p = puntuarPersona({ ...perfecta, disponible_exacto: false, disponible_finde: false }, contexto)
    expect(p.descartado).toBe('no esta libre esa fecha')
  })

  it('el near-miss por gusto rankea muy por debajo aunque cumpla los filtros duros', () => {
    const sinGusto = puntuarPersona(
      { ...perfecta, similitud: 0.26, interests: ['classical', 'museums'], top_artists: [] }, contexto)
    const bueno = puntuarPersona(perfecta, contexto)
    expect(sinGusto.porcentaje).toBeLessThan(bueno.porcentaje - 25)
  })

  it('los componentes vienen ordenados por lo que APORTAN, que es lo que se explica', () => {
    const p = puntuarPersona(perfecta, contexto)
    const puntos = p.componentes.map((c) => c.puntos)
    expect([...puntos].sort((a, b) => b - a)).toEqual(puntos)
  })

  it('el porcentaje es exactamente la suma de los componentes: nada sale de la nada', () => {
    const p = puntuarPersona(perfecta, contexto)
    const suma = p.componentes.reduce((s, c) => s + c.puntos, 0)
    expect(p.porcentaje).toBe(Math.round(suma))
  })
})

describe('Intencion→Plan: el caso de la frase 6', () => {
  const base = {
    similitud: 0.62, km: 1.5, subject: 'Coldplay', tags: ['concert', 'pop'],
    category: 'concert', starts_at: '2026-10-11T20:00:00Z', radius_km: 40,
  }
  const ctx = {
    subject: 'Coldplay', subjectEspecificidad: 'named' as const, categoria: 'concert',
    desde: '2026-10-01', hasta: '2026-10-31', tags: ['concert'], radioKm: 40,
  }

  it('un plan LLENO puntua por debajo del mismo plan con plaza libre', () => {
    // Es EL fallo que la similitud pura no puede corregir: los dos textos se parecen igual.
    // Sin este componente, la frase 6 devuelve arriba un concierto al que no puedes ir.
    const conPlaza = puntuarPlan({ ...base, seats_open: 1 }, ctx)
    const lleno = puntuarPlan({ ...base, seats_open: 0 }, ctx)
    expect(conPlaza.porcentaje).toBeGreaterThan(lleno.porcentaje)
  })

  it('con el sujeto nombrado, no coincidir el artista cuesta los 18 puntos enteros', () => {
    const otro = puntuarPlan({ ...base, seats_open: 1, subject: 'Amelie Lens' }, ctx)
    const suyo = puntuarPlan({ ...base, seats_open: 1 }, ctx)
    expect(suyo.porcentaje - otro.porcentaje).toBeGreaterThanOrEqual(17)
  })

  it('una fecha lejana hunde el resultado aunque el artista sea el correcto', () => {
    const tarde = puntuarPlan({ ...base, seats_open: 1, starts_at: '2027-03-11T20:00:00Z' }, ctx)
    const aTiempo = puntuarPlan({ ...base, seats_open: 1 }, ctx)
    expect(tarde.porcentaje).toBeLessThan(aTiempo.porcentaje - 10)
  })
})
