// El seed es el criterio de aceptacion de la demo: si esta mal, no hay nada que ense~nar.
// Estas pruebas corren sin red y protegen las tres cosas que lo romperian en silencio.
import { describe, it, expect } from 'vitest'
import { readFileSync, existsSync } from 'node:fs'

const RUTA = new URL('../db/seed.json', import.meta.url)
const hay = existsSync(RUTA)
const seed = hay ? JSON.parse(readFileSync(RUTA, 'utf8')) : null

describe.skipIf(!hay)('db/seed.json', () => {
  it('no contiene NI UNA fecha literal', () => {
    // La regla 3 del proyecto y el §12 del brief: es «el bug mas probable de todo el proyecto».
    // Una fecha absoluta aqui caduca, y la frase de Helder que dependa de ella devuelve vacio
    // delante del cliente. El tiempo se expresa con desplazamientos; los materializa sembrar.py.
    const texto = JSON.stringify(seed)
    const fechas = texto.match(/\d{4}-\d{2}-\d{2}/g) ?? []
    expect(fechas).toEqual([])
  })

  it('cada plan y cada intent apunta a un perfil que existe', () => {
    const ids = new Set<string>(seed.perfiles.map((p: any) => p.id))
    const huerfanos = [...seed.planes, ...seed.intents]
      .filter((x: any) => !ids.has(x.owner_id))
      .map((x: any) => x.clave)
    expect(huerfanos).toEqual([])
  })

  it('no repite ninguna clave ni ningun id', () => {
    const filas = [...seed.perfiles, ...seed.planes, ...seed.intents]
    expect(new Set(filas.map((f: any) => f.clave)).size).toBe(filas.length)
    expect(new Set(filas.map((f: any) => f.id)).size).toBe(filas.length)
  })

  it('tiene el volumen que el §9 del brief pide', () => {
    expect(seed.perfiles.length).toBeGreaterThanOrEqual(240)
    expect(seed.planes.length).toBeGreaterThanOrEqual(180)
  })

  it('mezcla los idiomas a proposito: entre el 40% y el 70% en aleman', () => {
    // §8: sin corpus mezclado, el matching cross-lingua no tiene nada que demostrar.
    const de = seed.perfiles.filter((p: any) => p.bio_lang === 'de').length
    const proporcion = de / seed.perfiles.length
    expect(proporcion).toBeGreaterThan(0.4)
    expect(proporcion).toBeLessThan(0.7)
  })
})
