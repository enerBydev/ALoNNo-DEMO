// CAPA 4 — la explicacion. Una llamada al LLM, y solo sobre lo que se va a ense~nar.
//
// **EL MODELO ESCRIBE LA ORACION; NUNCA ESCRIBE EL NUMERO** (regla 6 y seccion D de la
// propuesta). Aqui se ve literalmente: al modelo se le pasan los componentes YA CALCULADOS con
// sus puntos, y se le pide prosa. Si se inventa una cifra, se detecta — la comprobacion esta
// abajo y borra cualquier numero que no venga del scoring.
//
// Se explica el top 5, no los 50 candidatos: «bounded by results rendered, not by candidates
// evaluated», que es el control 3 de la seccion E.
import { chatJson, type Uso } from './ia'
import type { Componente } from './scoring'

export interface ParaExplicar {
  id: string
  titulo: string
  porcentaje: number
  componentes: Componente[]
}

const SISTEMA = `Escribes una frase corta por cada resultado de un buscador de planes sociales.

Recibes, por resultado, los TRES componentes que mas aportan a su puntuacion, con sus puntos ya
calculados. Tu trabajo es convertirlos en una frase natural que explique POR QUE encaja.

REGLAS:
- Una sola frase por resultado. Maximo 22 palabras.
- **No escribas ningun numero, ni porcentajes, ni puntos.** El sistema los pone despues.
- Nombra los hechos concretos que te dan (el artista compartido, los kilometros, el dia), no
  generalidades. Mal: "tiene gustos parecidos". Bien: "Burna Boy esta en el top de los dos".
- **El idioma es una orden, no una sugerencia.** Se te dice al principio y al final del mensaje.
  Si te piden aleman, escribe ALEMAN. Si te piden ingles, escribe INGLES. Nunca espanol.
- No inventes nada que no este en los componentes. Si el detalle dice "libre ese dia", NO
  escribas "manana" ni "hoy": no sabes que dia es. Usa exactamente lo que se te da.

Devuelve un JSON con esta forma exacta: {"explicaciones": [{"id": "<id>", "frase": "<texto>"}]}`

/** Un numero en la frase seria el modelo escribiendo el numero. Se quita. */
export function limpiarNumeros(frase: string): string {
  return frase
    .replace(/\b\d+([.,]\d+)?\s*%/g, '')
    .replace(/\+\s*\d+([.,]\d+)?/g, '')
    .replace(/\s{2,}/g, ' ')
    .trim()
}

export async function explicar(
  env: Record<string, string | undefined>,
  items: ParaExplicar[],
  idioma: 'de' | 'en',
): Promise<{ frases: Record<string, string>; uso: Uso }> {
  if (!items.length) return { frases: {}, uso: { tokens_entrada: 0, tokens_salida: 0, ms: 0 } }

  // EL NOMBRE DEL IDIOMA VA EN INGLES. Medido: con «aleman»/«ingles» el modelo respondia en
  // ESPANOL — leia la palabra como el idioma en el que se le hablaba, no como el que se le pedia.
  const nombre = idioma === 'de' ? 'German' : 'English'
  const cuerpo = items.map((i) => ({
    id: i.id,
    titulo: i.titulo,
    porque: i.componentes.slice(0, 3).map((c) => ({
      que: idioma === 'de' ? c.etiqueta_de : c.etiqueta_en,
      detalle: c.detalle ?? null,
      aporta: Math.round(c.puntos),
    })),
  }))

  const { json, uso } = await chatJson(
    env,
    SISTEMA,
    `Write every sentence in ${nombre}. Not in any other language.\n\n`
    + `${JSON.stringify(cuerpo, null, 1)}\n\n`
    + `Remember: every "frase" must be written in ${nombre}.`,
    120 * items.length + 200,
  )

  const frases: Record<string, string> = {}
  for (const e of json?.explicaciones ?? []) {
    if (typeof e?.id === 'string' && typeof e?.frase === 'string') {
      frases[e.id] = limpiarNumeros(e.frase)
    }
  }
  return { frases, uso }
}
