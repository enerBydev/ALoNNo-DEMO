// El unico sitio del proyecto que habla con el proveedor de IA.
//
// Dos decisiones que estan aqui y no se repiten en ningun otro fichero:
//
// 1. `input_type` en los embeddings. `nemotron-3-embed-1b` es ASIMETRICO: lo que se guarda es
//    un `passage` y lo que se busca es una `query`. Sin ese parametro el recall cae de 8/8 a 7/8
//    y el margen se hunde de +0.340 a +0.091 — y **no da ningun error**. Por eso la funcion no
//    acepta un valor por defecto: quien llama tiene que decir cual de los dos es.
//
// 2. `chat_template_kwargs: { thinking: false }`. El modelo de chat razona por defecto y factura
//    ese razonamiento. Es el control de coste mas caro de la seccion E de la propuesta.

export const MODELO_CHAT = 'nvidia/nemotron-3.5-lightning-30b-a3b'
export const MODELO_EMBED = 'nvidia/nemotron-3-embed-1b'
export const DIMENSION = 2048
const BASE = 'https://integrate.api.nvidia.com/v1'

export interface Uso {
  tokens_entrada: number
  tokens_salida: number
  ms: number
}

/** Un fallo puntual del proveedor no puede tumbar una busqueda delante del cliente.
 *  Medido el 10-sep-2026: dos de diez frases devolvieron 502 en una tanda, y la misma frase
 *  funciono al reintentarla. Dos intentos con espera corta cubren eso sin alargar la demo. */
async function conReintento(f: () => Promise<Response>, intentos = 3): Promise<Response> {
  let ultima: Response | null = null
  for (let i = 0; i < intentos; i++) {
    try {
      const r = await f()
      if (r.ok) return r
      ultima = r
      // 4xx que no sea 429 es culpa nuestra: reintentar no lo arregla.
      if (r.status < 500 && r.status !== 429) return r
    } catch (e) {
      if (i === intentos - 1) throw e
    }
    await new Promise((res) => setTimeout(res, 400 * (i + 1)))
  }
  return ultima as Response
}

function claveDe(env: Record<string, string | undefined>): string {
  const clave = env.NVIDIA_API_KEY
  if (!clave) throw createError({ statusCode: 503, statusMessage: 'sin credencial de IA' })
  return clave
}

/** Vector de una frase de busqueda. SIEMPRE `query`: lo contrario degrada sin avisar. */
export async function embeberConsulta(
  env: Record<string, string | undefined>,
  texto: string,
): Promise<{ vector: number[]; uso: Uso }> {
  const t0 = Date.now()
  const r = await conReintento(() => fetch(`${BASE}/embeddings`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${claveDe(env)}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: MODELO_EMBED,
      input: [texto],
      input_type: 'query',
      truncate: 'END',
      encoding_format: 'float',
    }),
  }))
  if (!r.ok) {
    throw createError({ statusCode: 502, statusMessage: `embeddings: ${r.status} ${(await r.text()).slice(0, 120)}` })
  }
  const d = (await r.json()) as any
  return {
    vector: d.data[0].embedding,
    uso: { tokens_entrada: d.usage?.prompt_tokens ?? 0, tokens_salida: 0, ms: Date.now() - t0 },
  }
}

/** Una respuesta del modelo de chat, en JSON. `temperature: 0` porque el §9 prohibe la
 *  aleatoriedad en tiempo de ejecucion: la misma frase tiene que dar el mismo arquetipo
 *  delante del cliente. */
export async function chatJson(
  env: Record<string, string | undefined>,
  sistema: string,
  usuario: string,
  maxTokens = 500,
): Promise<{ json: any; uso: Uso }> {
  const t0 = Date.now()
  const r = await conReintento(() => fetch(`${BASE}/chat/completions`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${claveDe(env)}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: MODELO_CHAT,
      messages: [
        { role: 'system', content: sistema },
        { role: 'user', content: usuario },
      ],
      temperature: 0,
      max_tokens: maxTokens,
      response_format: { type: 'json_object' },
      // El razonamiento se factura y aqui no aporta: la tarea es rellenar un formulario.
      chat_template_kwargs: { thinking: false },
    }),
  }))
  if (!r.ok) {
    throw createError({ statusCode: 502, statusMessage: `chat: ${r.status} ${(await r.text()).slice(0, 120)}` })
  }
  const d = (await r.json()) as any
  const crudo: string = d.choices?.[0]?.message?.content ?? ''
  const uso: Uso = {
    tokens_entrada: d.usage?.prompt_tokens ?? 0,
    tokens_salida: d.usage?.completion_tokens ?? 0,
    ms: Date.now() - t0,
  }
  return { json: extraerJson(crudo), uso }
}

/** El modelo a veces envuelve el JSON en ``` o lo precede de una frase. Se rescata en vez de
 *  fallar: una demo no puede caerse porque el modelo se puso conversador. */
export function extraerJson(crudo: string): any {
  const limpio = crudo.trim().replace(/^```(?:json)?/i, '').replace(/```$/, '').trim()
  try {
    return JSON.parse(limpio)
  } catch {
    const i = limpio.indexOf('{')
    const j = limpio.lastIndexOf('}')
    if (i >= 0 && j > i) return JSON.parse(limpio.slice(i, j + 1))
    throw createError({ statusCode: 502, statusMessage: 'el parser no devolvio JSON' })
  }
}
