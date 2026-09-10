// Los perfiles entre los que se elige al entrar. Se ense~nan los de los escenarios plantados
// primero: entrar como Amara y buscar «Burna Boy» es la forma mas rapida de ver el producto.
export default defineCachedEventHandler(async (event) => {
  const env = { ...process.env, ...((event.context as any).cloudflare?.env ?? {}) }
  const url = env.SUPABASE_URL, clave = env.SUPABASE_SECRET_KEY
  const r = await fetch(
    `${url}/rest/v1/profiles?select=id,display_name,city,age,bio,bio_lang,interests,top_artists`
    + `&order=completed_plans.desc&limit=24`,
    { headers: { apikey: clave, Authorization: `Bearer ${clave}` } })
  if (!r.ok) throw createError({ statusCode: 502, statusMessage: 'no se pudieron leer los perfiles' })
  return { perfiles: await r.json() }
}, { maxAge: 300, name: 'perfiles', getKey: () => 'v1' })
