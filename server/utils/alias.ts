// EXONIMOS Y GRAFIAS → LA CLAVE DEL CATALOGO GENERADO (`lugares.ts`).
//
// La Capa 0 escribe en el idioma de la frase: «Cologne», «Munich». `normalizar()` solo quitaba
// diacriticos, asi que «Cologne» no casaba con «koln» y la frase 2 del cliente devolvia CERO planes
// aunque el seed tenia cuatro; «Munich» no estaba en CIUDADES y `centroDe()` caia a Berlin sin
// avisar (frase 4). Lo midio la aceptacion de la v10 (15-sep-2026, bloqueante B1): el alias solo
// existia en el parser de reglas, el camino que casi nunca corre.
const ALIAS: Record<string, string> = {
  munich: 'munchen', muenchen: 'munchen',
  cologne: 'koln', koeln: 'koln',
  duesseldorf: 'dusseldorf',
  'frankfurt am main': 'frankfurt', 'frankfurt/main': 'frankfurt', 'frankfurt a. m.': 'frankfurt',
  lisbon: 'lissabon', lisboa: 'lissabon',
  vienna: 'wien',
  ruegen: 'rugen',
}
const NOMBRE: Record<string, string> = {
  munchen: 'Munchen', koln: 'Koln', dusseldorf: 'Dusseldorf', frankfurt: 'Frankfurt',
  lissabon: 'Lissabon', wien: 'Wien', rugen: 'Rugen',
}

/** «Köln», «Koeln», «Straße» → «koln», «koeln», «strasse»: sin diacriticos, sin ß, en minusculas. */
export function claveDeLugar(t: string): string {
  return t.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/ß/g, 'ss')
    .toLowerCase().replace(/-/g, ' ').replace(/\s+/g, ' ').trim()
}

/** Las formas en las que puede estar escrito un lugar, de la mas literal a la mas plegada:
 *  la clave tal cual, su alias, la clave con ae/oe/ue plegados, y el alias de esa. */
export function variantesDeLugar(t: string): string[] {
  const base = claveDeLugar(t)
  const plegada = base.replace(/ae/g, 'a').replace(/oe/g, 'o').replace(/ue/g, 'u')
  return [...new Set([base, ALIAS[base], plegada, ALIAS[plegada]].filter((x): x is string => Boolean(x)))]
}

/** El nombre de pantalla cuando el texto es un exonimo conocido («Munich» → «Munchen»); si no,
 *  el texto tal cual, que ya vale como clave. */
export function canonizarLugar(t: string): string {
  const base = claveDeLugar(t)
  const plegada = base.replace(/ae/g, 'a').replace(/oe/g, 'o').replace(/ue/g, 'u')
  const k = ALIAS[base] ?? ALIAS[plegada]
  return k ? (NOMBRE[k] ?? k) : t
}
