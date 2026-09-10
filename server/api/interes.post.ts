// FLUJO 3 · «agree to meet».
//
// Un interes es unidireccional: te apuntas a un plan. **Hay match mutuo cuando el dueno del
// plan tambien se apunta a uno tuyo** — y es entonces cuando, en el producto de verdad, se
// abriria el chat. La propuesta lo llama «interest & mutual match» y lo pone en el M3.
import { exigirSesion, escribir, tabla } from '../utils/sesion'

export default defineEventHandler(async (event) => {
  const yo = exigirSesion(event)
  const { plan_id, quitar } = await readBody<{ plan_id?: string; quitar?: boolean }>(event)
  if (!plan_id) throw createError({ statusCode: 400, statusMessage: 'falta plan_id' })

  const [plan] = await tabla<any>(event, `plans?id=eq.${plan_id}&select=id,owner_id,title,seats_open`)
  if (!plan) throw createError({ statusCode: 404, statusMessage: 'ese plan no existe' })
  if (plan.owner_id === yo.id) {
    throw createError({ statusCode: 400, statusMessage: 'es tu propio plan' })
  }

  if (quitar) {
    await escribir(event, `intereses?persona_id=eq.${yo.id}&plan_id=eq.${plan_id}`, {}, 'DELETE')
    return { apuntado: false, mutuo: false }
  }

  await escribir(event, 'intereses', { persona_id: yo.id, plan_id })

  // ¿El dueno de este plan se apunto a alguno mio? Eso es el match mutuo.
  const mios = await tabla<any>(event, `plans?owner_id=eq.${yo.id}&select=id`)
  let mutuo = false
  let plan_suyo = null
  if (mios.length) {
    const ids = mios.map((p) => p.id).join(',')
    const cruce = await tabla<any>(event,
      `intereses?persona_id=eq.${plan.owner_id}&plan_id=in.(${ids})&select=plan:plans(id,title)`)
    mutuo = cruce.length > 0
    plan_suyo = cruce[0]?.plan ?? null
  }
  return { apuntado: true, mutuo, plan_suyo, plan: { id: plan.id, title: plan.title } }
})
