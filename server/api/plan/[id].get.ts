// Un plan, con su dueno y quien se ha apuntado. Se sirve con SSR para que la pagina sea
// indexable: la seccion K de la propuesta vende que cada plan publico es un canal de captacion,
// y eso solo funciona si el HTML llega hecho.
import { tabla, sesionDe } from '../../utils/sesion'

export default defineEventHandler(async (event) => {
  const id = getRouterParam(event, 'id')!
  const [plan] = await tabla<any>(event,
    `plans?id=eq.${id}&select=*,perfil:profiles!plans_owner_id_fkey(id,display_name,city,bio,bio_lang,interests,top_artists,verification,completed_plans)`)
  if (!plan) throw createError({ statusCode: 404, statusMessage: 'ese plan no existe' })

  const apuntados = await tabla<any>(event,
    `intereses?plan_id=eq.${id}&select=creado,persona:profiles(id,display_name,city,bio_lang,interests)`)

  const yo = sesionDe(event)
  return {
    plan,
    apuntados: apuntados.map((a) => a.persona),
    yo_apuntado: Boolean(yo && apuntados.some((a) => a.persona?.id === yo.id)),
    soy_el_dueno: Boolean(yo && plan.owner_id === yo.id),
  }
})
