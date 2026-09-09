// DEMO: sonda de diagnostico PARAMETRIZABLE. Existe para contestar «esta credencial autoriza
// esta operacion en este endpoint?» sin volver a desplegar por cada intento, y sin que el
// token pase nunca por una linea de ordenes.
//
//   /api/diagnostico-ia?op=models[&q=nemotron]
//   /api/diagnostico-ia?op=chat&model=nvidia/nemotron-3.5-lightning-30b-a3b
//   /api/diagnostico-ia?op=embeddings&model=nvidia/llama-3.2-nv-embedqa-1b-v1
//   ...&base=https://ai.api.nvidia.com/v1        (para probar otro endpoint)
//
// Devuelve codigos de estado y extractos. NUNCA el token, y del vector solo su longitud.
const BASE_POR_DEFECTO = 'https://integrate.api.nvidia.com/v1'

export default defineEventHandler(async (event) => {
  const env = {
    ...process.env,
    ...((event.context as Record<string, any>).cloudflare?.env ?? {}),
  } as Record<string, string | undefined>

  const key = env.NVIDIA_API_KEY
  if (!key) return { error: 'sin NVIDIA_API_KEY en el entorno' }

  const q = getQuery(event) as Record<string, string | undefined>
  const base = (q.base || BASE_POR_DEFECTO).replace(/\/$/, '')
  const op = q.op || 'chat'
  const model = q.model || 'nvidia/nemotron-3.5-lightning-30b-a3b'
  const cabeceras = { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' }

  try {
    if (op === 'models') {
      const r = await fetch(`${base}/models`, { headers: cabeceras })
      if (!r.ok) return { op, base, http: r.status, detalle: (await r.text()).slice(0, 200) }
      const d = (await r.json()) as { data?: Array<{ id: string }> }
      const ids = (d.data ?? []).map((m) => m.id)
      const filtro = q.q?.toLowerCase()
      return {
        op, base, http: r.status, total: ids.length,
        modelos: (filtro ? ids.filter((i) => i.toLowerCase().includes(filtro)) : ids).sort(),
      }
    }

    const ruta = op === 'embeddings' ? '/embeddings' : '/chat/completions'
    const cuerpo =
      op === 'embeddings'
        ? { model, input: ['Ich habe noch ein Ticket für Burna Boy.'], input_type: 'query', encoding_format: 'float' }
        : { model, messages: [{ role: 'user', content: 'Say OK' }], max_tokens: 8 }

    const r = await fetch(`${base}${ruta}`, { method: 'POST', headers: cabeceras, body: JSON.stringify(cuerpo) })
    const texto = await r.text()
    if (!r.ok) return { op, base, model, http: r.status, detalle: texto.slice(0, 220) }

    const d = JSON.parse(texto)
    return {
      op, base, model, http: r.status, ok: true,
      // Del embedding interesa la DIMENSION, que es lo que fija el esquema de la base.
      resultado:
        op === 'embeddings'
          ? { dimension: d?.data?.[0]?.embedding?.length ?? null }
          : { texto: d?.choices?.[0]?.message?.content?.slice(0, 80) ?? null },
    }
  } catch (e) {
    return { op, base, model, error: (e as Error).message.slice(0, 200) }
  }
})
