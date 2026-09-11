// El respaldo por reglas TIENE que entender un trayecto, porque es lo que sostiene la demo
// cuando el proveedor de IA tarda mas de 11 s — y el 11-sep-2026 lo hizo en 3 de 7 busquedas
// seguidas. Sin esto devolvia `city: null` y `trayecto: false`: sin centro geografico no hay
// radio de 2 km, y a un berlines se le contestaba con coches de Dusseldorf.
import { describe, expect, it } from 'vitest'
import { parsearSinModelo } from '../server/utils/parser'

describe('el respaldo lee un trayecto sin tocar el modelo', () => {
  it('«von X nach Y» da origen y destino', () => {
    const i = parsearSinModelo('Ich fahre morgen um 8 von Neukolln nach Mitte, zwei Plaetze frei')
    expect(i.trayecto).toBe(true)
    expect(i.city).toBe('neukolln')
    expect(i.hacia).toBe('mitte')
    expect(i.fecha.expresion).toBe('manana')
    expect(i.language).toBe('de')
  })

  it('«from X to Y» tambien, en ingles', () => {
    const i = parsearSinModelo('I drive from Ehrenfeld to Altstadt every weekday morning')
    expect(i.trayecto).toBe(true)
    expect(i.city).toBe('ehrenfeld')
    expect(i.hacia).toBe('altstadt')
    expect(i.language).toBe('en')
  })

  it('«Richtung Y» sin origen da destino y marca trayecto', () => {
    const i = parsearSinModelo('Suche Mitfahrgelegenheit morgen frueh Richtung Mitte')
    expect(i.trayecto).toBe(true)
    expect(i.hacia).toBe('mitte')
  })

  it('una frase de coche sin destino sigue siendo un trayecto', () => {
    const i = parsearSinModelo('Noch zwei Plaetze frei im Auto')
    expect(i.trayecto).toBe(true)
  })

  it('una frase de plan social NO se marca como trayecto', () => {
    const i = parsearSinModelo(
      'Ich habe noch ein Ticket fuer Burna Boy in Duesseldorf am Samstag. Mein Freund kann nicht mehr.')
    expect(i.trayecto).toBe(false)
    expect(i.city).toBe('Dusseldorf')
    expect(i.user_has_booking).toBe(true)
  })

  it('«to» dentro de otra frase no inventa un destino absurdo', () => {
    const i = parsearSinModelo('I want to go to a Coldplay concert next month')
    // «go to a coldplay concert» no es un barrio; lo que importa es que no rompa ni marque
    // trayecto por una preposicion suelta.
    expect(i.trayecto).toBe(false)
  })
})
