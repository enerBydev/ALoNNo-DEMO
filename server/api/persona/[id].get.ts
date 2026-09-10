// Un perfil, con los planes que organiza y aquellos a los que se apunto.
import { tabla } from '../../utils/sesion'

export default defineEventHandler(async (event) => {
  const id = getRouterParam(event, 'id')!
  const [persona] = await tabla<any>(event, `profiles?id=eq.${id}&select=*`)
  if (!persona) throw createError({ statusCode: 404, statusMessage: 'esa persona no existe' })
  const suyos = await tabla<any>(event,
    `plans?owner_id=eq.${id}&select=id,title,category,dest_city,starts_at,seats_open&order=starts_at.asc`)
  const apuntada = await tabla<any>(event,
    `intereses?persona_id=eq.${id}&select=plan:plans(id,title,category,dest_city,starts_at)`)
  // El embedding no sale de aqui: son 2048 numeros que nadie va a mirar y engordan la respuesta.
  delete persona.embedding
  delete persona.fts
  return { persona, planes: suyos, apuntada: apuntada.map((a) => a.plan).filter(Boolean) }
})
