// DEMO: sonda de diagnostico. Pregunta al proveedor de IA si la credencial autoriza las dos
// operaciones que la demo necesita —chat (Capa 0 y 4) y embeddings— y devuelve SOLO el codigo
// de estado. Nunca el token, nunca el vector completo.
//
// Existe porque `GET /v1/models` responde 200 con claves que ya no valen: lo unico que prueba
// una credencial es ejecutar la inferencia que se va a usar.
const BASE = 'https://integrate.api.nvidia.com/v1'

async function sonda(url: string, key: string, cuerpo: unknown) {
  try {
    const r = await fetch(url, {
      method: 'POST',
      headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(cuerpo),
    })
    const texto = await r.text()
    return { http: r.status, ok: r.ok, detalle: r.ok ? null : texto.slice(0, 160) }
  } catch (e) {
    return { http: 0, ok: false, detalle: (e as Error).message.slice(0, 160) }
  }
}

export default defineEventHandler(async (event) => {
  const env = {
    ...process.env,
    ...((event.context as Record<string, any>).cloudflare?.env ?? {}),
  } as Record<string, string | undefined>

  const key = env.NVIDIA_API_KEY
  if (!key) return { proveedor: 'nvidia-nim', error: 'sin NVIDIA_API_KEY en el entorno' }

  const chat = await sonda(`${BASE}/chat/completions`, key, {
    model: 'nvidia/llama-3.1-nemotron-70b-instruct',
    messages: [{ role: 'user', content: 'Say OK' }],
    max_tokens: 5,
  })

  const emb = await sonda(`${BASE}/embeddings`, key, {
    model: 'nvidia/llama-3.2-nv-embedqa-1b-v1',
    input: ['Ich habe noch ein Ticket für Burna Boy in Düsseldorf am Samstag.'],
    input_type: 'query',
    encoding_format: 'float',
  })

  return { proveedor: 'nvidia-nim', chat, embeddings: emb }
})
