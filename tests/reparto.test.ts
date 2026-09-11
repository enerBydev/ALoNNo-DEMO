// El fallo que trajo este test (11-sep-2026): la pantalla ense~naba 28+18+15+15+10+4+3 = 93
// junto a un total de 91. Cada componente se redondeaba por su cuenta. Ver
// docs/conocimiento/20-critica-uiux.md §1.3.
import { describe, expect, it } from 'vitest'
import { puntuarPersona, puntuarPlan } from '../server/utils/scoring'

const persona: any = {
  id: 'p1', display_name: 'Amara', city: 'Dusseldorf', bio: 'afrobeats every weekend',
  bio_lang: 'en', age: 27, interests: ['afrobeats', 'live_music', 'dancing'],
  top_artists: ['Burna Boy', 'Tems'], top_teams: [], cuisines: ['nigerian'],
  pace: 'moderate', budget_band: 'mid', group_pref: 'one_to_one', languages: ['en', 'de'],
  verification: 2, completed_plans: 6, reports: 0,
  km: 1.2, disponible_exacto: true, disponible_finde: true, similitud: 0.44, rrf: 0.03,
}

const plan: any = {
  id: 'v1', owner_id: 'p9', title: 'Neukolln → Mitte, 08:10', description: 'zwei Plaetze frei',
  desc_lang: 'de', category: 'commute', origin_city: 'Berlin', dest_city: 'Berlin',
  is_travel: false, venue: 'Mitte', subject: 'Mitte', tags: ['commute', 'rideshare'],
  starts_at: new Date(Date.now() + 3600e3).toISOString(),
  ends_at: new Date(Date.now() + 7200e3).toISOString(),
  seats_open: 2, radius_km: 2, budget_band: 'low', pace: 'relaxed', language_pref: ['de', 'en'],
  via: ['Kreuzberg'], distancia_km: 6.4, precio_por_km: 0.09, recurrente: 'weekdays',
  conductor: 'Lina', conductor_coche: 'Hyundai i30', conductor_nota: 4.6, conductor_notas: 14,
  conductor_verificado: 2, conductor_viajes: 14,
  km: 0.6, km_ruta: 0.6, similitud: 0.51, rrf: 0.03,
}

const contexto: any = {
  tags: ['commute', 'rideshare'], categoria: 'commute', radioKm: 2, hayFecha: true,
  fechaTexto: new Date().toISOString().slice(0, 10), pace: 'relaxed', budget_band: 'low',
  language_pref: ['de'],
}

describe('los enteros del desglose suman el porcentaje que se ense~na', () => {
  it('en una persona', () => {
    const p = puntuarPersona(persona, contexto)
    const suma = p.componentes.reduce((s, c) => s + c.puntos_enteros, 0)
    expect(suma).toBe(p.porcentaje)
  })

  it('en un viaje', () => {
    const p = puntuarPlan(plan, contexto)
    const suma = p.componentes.reduce((s, c) => s + c.puntos_enteros, 0)
    expect(suma).toBe(p.porcentaje)
  })

  it('ningun componente queda en negativo al repartir', () => {
    for (const p of [puntuarPersona(persona, contexto), puntuarPlan(plan, contexto)]) {
      for (const c of p.componentes) expect(c.puntos_enteros).toBeGreaterThanOrEqual(0)
    }
  })
})
