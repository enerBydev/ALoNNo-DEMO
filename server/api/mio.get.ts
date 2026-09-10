// Lo mio: mis planes, a que me he apuntado, y quien se apunto a los mios.
import { exigirSesion, tabla } from '../utils/sesion'

export default defineEventHandler(async (event) => {
  const yo = exigirSesion(event)
  const mios = await tabla<any>(event,
    `plans?owner_id=eq.${yo.id}&select=id,title,category,dest_city,starts_at,seats_open&order=starts_at.asc`)
  const apuntado = await tabla<any>(event,
    `intereses?persona_id=eq.${yo.id}&select=creado,plan:plans(id,title,category,dest_city,starts_at,owner_id)`)
  let interesados: any[] = []
  if (mios.length) {
    interesados = await tabla<any>(event,
      `intereses?plan_id=in.(${mios.map((p) => p.id).join(',')})`
      + `&select=creado,plan:plans(id,title),persona:profiles(id,display_name,city,bio_lang)`)
  }
  return { yo, planes: mios, apuntado: apuntado.map((a) => a.plan).filter(Boolean), interesados }
})
