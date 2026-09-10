// EL FRENO DE PRESUPUESTO. Protege lo unico que hay que proteger: el credito de IA.
//
// La demo es una URL PUBLICA con una clave de IA detras. Sin freno, un bucle de `curl` la deja
// sin credito antes del 16 y Helder abre un link muerto.
//
// ── POR QUE ESTE FRENO Y NO UNO POR IP, que es lo que la seccion J dice ──────────────────────
//
// Se intentaron los dos caminos obvios y ninguno funciona aqui. Medido el 10-sep-2026:
//
//  1. **El binding nativo `ratelimits`.** Se declaro, el Worker lo recibio (`ratelimit · FRENO`
//     en sus bindings) y el codigo lo veia. `limit()` devolvia `{success: true}` SIEMPRE, hasta
//     con un limite de 3 peticiones por 10 segundos y diez seguidas.
//  2. **Contar por IP en KV.** El contador se vio subir (2/12, 3/12… en una cabecera de
//     diagnostico) pero nunca alcanzaba el limite: **las lecturas de KV son de consistencia
//     eventual** y cada colo puede servir un valor viejo. KV no es un contador.
//
// Lo correcto para contar por IP es un Durable Object, y eso es trabajo del proyecto pagado, no
// de una demo con seis dias por delante. **Asi que se protege el presupuesto en vez de la IP**:
// un contador DIARIO con un umbral alto, donde la imprecision de KV da igual porque no se
// decide sobre una peticion sino sobre quinientas.
//
// Lo que esto NO hace, y se dice: no impide que una sola persona haga cien busquedas. Impide que
// alguien gaste el credito entero. Para una demo de siete dias, ese es el riesgo real.
const TECHO_DIARIO = 400   // busquedas nuevas al dia; las cacheadas no cuentan porque no gastan

export default defineEventHandler(async (event) => {
  if (!getRequestURL(event).pathname.startsWith('/api/buscar')) return

  const kv = (event.context as Record<string, any>).cloudflare?.env?.CACHE
  if (!kv) return   // en local no hay binding: no se frena lo que no se puede medir

  const dia = new Date().toISOString().slice(0, 10)
  const clave = `gasto:${dia}`
  const gastado = Number((await kv.get(clave)) ?? 0)

  if (gastado >= TECHO_DIARIO) {
    throw createError({
      statusCode: 429,
      statusMessage: 'This demo has reached its daily AI budget. The ten example sentences still '
        + 'work — they are cached. Fresh searches resume tomorrow.',
    })
  }
  await kv.put(clave, String(gastado + 1), { expirationTtl: 60 * 60 * 48 })
})
