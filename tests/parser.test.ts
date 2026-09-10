// El arbol de decision del §9-A, probado sobre las diez frases de Helder.
//
// No llama al modelo: prueba la parte DETERMINISTA — que es justo la que se le quito al modelo
// porque la fallaba. Corre sin red, dentro de `just ci`.
import { describe, it, expect } from 'vitest'
import { decidirArquetipo, resolverVentana, normalizar, type Intencion } from '../server/utils/parser'

const base = (extra: Partial<Intencion>): Intencion => normalizar({
  archetype: 'intent_seeks_any', has_concrete_event: false, user_has_booking: false,
  subject_specificity: 'open', language: 'en', category: null, subject: null,
  city: null, dest_city: null, fecha: { expresion: 'sin_fecha', mes: null },
  confidence: 0.9, ...extra,
})

describe('el arbol de decision del §9-A', () => {
  it('frase 1: tiene entrada y busca compania -> plan_seeks_person', () => {
    expect(decidirArquetipo(base({ user_has_booking: true, has_concrete_event: true, city: 'Dusseldorf' })))
      .toBe('plan_seeks_person')
  })

  it('frase 6: hay concierto pero NO tiene entrada -> intent_seeks_any', () => {
    // El caso que el brief avisa dos veces y que el modelo fallaba: el evento existe
    // (has_concrete_event) pero quien escribe no lo tiene (user_has_booking). Si esto se
    // clasifica como plan concreto, la demo pierde su momento estrella.
    expect(decidirArquetipo(base({
      user_has_booking: false, has_concrete_event: true,
      city: 'Dusseldorf', fecha: { expresion: 'proximo_mes', mes: null },
    }))).toBe('intent_seeks_any')
  })

  it('frase 7: viaje reservado a otra ciudad -> plan_seeks_plan', () => {
    expect(decidirArquetipo(base({ user_has_booking: true, dest_city: 'Barcelona' })))
      .toBe('plan_seeks_plan')
  })

  it('frase 9: sin reserva y SIN fecha -> standing_interest', () => {
    expect(decidirArquetipo(base({ user_has_booking: false, city: 'Koln' })))
      .toBe('standing_interest')
  })
})

describe('las fechas se resuelven en codigo, nunca las escribe el modelo', () => {
  // Jueves 10 de septiembre de 2026, el dia en que se escribio esto.
  const jueves = new Date('2026-09-10T12:00:00Z')

  it('«am Samstag» cae en sabado', () => {
    const v = resolverVentana(base({ fecha: { expresion: 'este_sabado', mes: null } }), jueves)
    expect(v.desde).toBe('2026-09-12')
    expect(new Date(v.desde!).getUTCDay()).toBe(6)
    expect(v.exacta).toBe(true)
  })

  it('«morgen» es el dia siguiente y es una fecha EXACTA', () => {
    const v = resolverVentana(base({ fecha: { expresion: 'manana', mes: null } }), jueves)
    expect(v.desde).toBe('2026-09-11')
    expect(v.exacta).toBe(true)
  })

  it('«this weekend» cubre sabado y domingo, y no es exacta', () => {
    const v = resolverVentana(base({ fecha: { expresion: 'este_finde', mes: null } }), jueves)
    expect(v.desde).toBe('2026-09-12')
    expect(v.hasta).toBe('2026-09-13')
    expect(v.exacta).toBe(false)
  })

  it('«in October» abarca el mes entero', () => {
    const v = resolverVentana(base({ fecha: { expresion: 'mes_nombrado', mes: 'october' } }), jueves)
    expect(v.desde).toBe('2026-10-01')
    expect(v.hasta).toBe('2026-10-31')
  })

  it('sin fecha no hay ventana: un interes permanente no se filtra por tiempo', () => {
    const v = resolverVentana(base({}), jueves)
    expect(v.desde).toBeNull()
  })
})
