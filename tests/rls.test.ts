// La RLS probada como codigo. La seccion J de la propuesta lo promete literalmente:
// "Row-level security policies on user data, tested as code".
//
// Se salta si no hay credenciales en el entorno (en CI no las hay a proposito: son secretos del
// Worker). Saltarse un test y decirlo es honesto; darlo por pasado sin ejecutarlo, no.
import { describe, it, expect } from 'vitest'

const URL_BASE = process.env.SUPABASE_URL
const CLAVE_PUBLICA = process.env.SUPABASE_PUBLISHABLE_KEY

const perfil = {
  id: '00000000-0000-0000-0000-0000000000fd',
  display_name: 'prueba rls',
  city: 'Berlin',
  geo: 'POINT(13.4 52.5)',
  languages: ['de'],
  bio_lang: 'de',
  bio: 'prueba',
  interests: ['test'],
  availability: ['[2026-09-10,2026-09-11)'],
}

describe.skipIf(!URL_BASE || !CLAVE_PUBLICA)('RLS cierra la base al rol anonimo', () => {
  it('rechaza un INSERT con la clave publica', async () => {
    const r = await fetch(`${URL_BASE}/rest/v1/profiles`, {
      method: 'POST',
      headers: {
        apikey: CLAVE_PUBLICA!,
        Authorization: `Bearer ${CLAVE_PUBLICA!}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(perfil),
    })
    expect(r.ok).toBe(false)
    expect(await r.text()).toContain('row-level security')
  })

  it('no devuelve filas en un SELECT con la clave publica', async () => {
    const r = await fetch(`${URL_BASE}/rest/v1/profiles?select=id&limit=1`, {
      headers: { apikey: CLAVE_PUBLICA! },
    })
    expect(await r.json()).toEqual([])
  })
})
