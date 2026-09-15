// El arbol de decision del §9-A, probado sobre las diez frases del cliente.
//
// No llama al modelo: prueba la parte DETERMINISTA — que es justo la que se le quito al modelo
// porque la fallaba. Corre sin red, dentro de `just ci`.
import { describe, it, expect } from 'vitest'
import { decidirArquetipo, resolverVentana, normalizar, reforzarFecha, type Intencion } from '../server/utils/parser'

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


describe('el codigo corrige al modelo cuando la frase dice una fecha y el no la ve', () => {
  it('frase 8: «this weekend» convierte un interes permanente en una intencion con ventana', () => {
    // Medido con la frase 8 del cliente: el modelo devolvia `sin_fecha` y la frase acababa como
    // `standing_interest`, perdiendo el filtro del fin de semana entero.
    const mudo = base({ user_has_booking: false, city: 'Berlin' })
    expect(decidirArquetipo(mudo)).toBe('standing_interest')
    const corregida = reforzarFecha(mudo, 'I am in Berlin this weekend and would like to do something')
    expect(corregida.fecha.expresion).toBe('este_finde')
    // El arquetipo tiene que venir YA corregido en el objeto, sin que nadie lo recalcule fuera:
    // asi es como lo usa el endpoint, y llamar a las dos funciones por separado en la prueba
    // escondia el fallo.
    expect(corregida.archetype).toBe('intent_seeks_any')
  })

  it('«morgen» tambien, en aleman', () => {
    const r = reforzarFecha(base({}), 'Ich habe ein Extra-Ticket fuer morgen in Muenchen')
    expect(r.fecha.expresion).toBe('manana')
  })

  it('SI pisa al modelo cuando la frase lleva un marcador inequivoco (aceptacion v10, B3)', () => {
    // Hasta el 15-sep-2026 esto se respetaba al reves: «si el modelo dijo algo, se respeta». La
    // aceptacion de la v10 midio «tomorrow» leido como hoy y «am Montag» como el mes que viene,
    // congelados seis horas en cache. Un marcador en la frase es un hecho; lo del modelo, una lectura.
    const conFecha = base({ fecha: { expresion: 'proximo_mes', mes: null } })
    expect(reforzarFecha(conFecha, 'this weekend').fecha.expresion).toBe('este_finde')
    const hoy = base({ fecha: { expresion: 'hoy', mes: null } })
    expect(reforzarFecha(hoy, 'I have an extra ticket for Bayern in Munich tomorrow').fecha.expresion).toBe('manana')
  })

  it('lunes a jueves existen: «am Montag» es el lunes que viene, nunca hoy', () => {
    const r = reforzarFecha(base({ fecha: { expresion: 'proximo_mes', mes: null } }), 'Ich brauche eine Fahrt nach Westend am Montag')
    expect(r.fecha.expresion).toBe('este_lunes')
    const v = resolverVentana(r, new Date('2026-09-21T10:00:00Z')) // un lunes
    expect(v.desde).toBe('2026-09-28')
    expect(v.exacta).toBe(true)
  })

  it('un mes nombrado manda sobre el finde: «a weekend in Cologne in October» es octubre', () => {
    const r = reforzarFecha(base({ fecha: { expresion: 'este_finde', mes: null } }), 'I already booked a weekend in Cologne in October')
    expect(r.fecha).toEqual({ expresion: 'mes_nombrado', mes: 'october' })
    const de = reforzarFecha(base({}), 'Am Oktoberwochenende nach Koeln')
    expect(de.fecha.mes).toBe('october')
  })

  it('«jeden Morgen» es la ma~nana, no ma~nana', () => {
    expect(reforzarFecha(base({}), 'Ich fahre jeden Morgen nach Mitte').fecha.expresion).toBe('sin_fecha')
  })

  it('exonimos: «Munich» y «Cologne» llegan al catalogo como Munchen y Koln (aceptacion v10, B1)', () => {
    expect(base({ city: 'Munich' }).city).toBe('Munchen')
    expect(base({ dest_city: 'Cologne' }).dest_city).toBe('Koln')
    expect(base({ city: 'Koeln' }).city).toBe('Koln')
  })

  it('frase 9 sigue sin fecha: no hay ninguna expresion temporal que agarrar', () => {
    const r = reforzarFecha(base({}), 'Meine Freunde interessieren sich nicht fuer Afrobeats. Ich suche jemanden in Koeln')
    expect(r.fecha.expresion).toBe('sin_fecha')
    expect(decidirArquetipo(r)).toBe('standing_interest')
  })
})
