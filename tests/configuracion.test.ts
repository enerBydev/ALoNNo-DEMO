// EL BUILDER DE CLOUDFLARE Y EL DEVSHELL TIENEN QUE SER LA MISMA MÁQUINA.
//
// Workers Builds no lee el `flake.nix`: elige pnpm 10.11 y Node 24 salvo que el repo se lo
// diga. Medido el 5-sep-2026 conectando OnlyHouseMX/site — tres builds fallidos seguidos, y
// el primero moría con ERR_PNPM_LOCKFILE_CONFIG_MISMATCH porque el lock lo había escrito
// pnpm 11 y el builder traía el 10.
//
// `nuevo-proyecto.sh` escribe los dos valores LEYÉNDOLOS del devshell, así que nacen
// correctos. Esta prueba existe para el día después: cuando nixpkgs suba Node o pnpm, el
// flake cambia y estos ficheros no, y sin nadie mirando el builder vuelve a ser otra máquina.
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const RAIZ = resolve(import.meta.dirname, '..')

describe('el toolchain declarado es el del devshell', () => {
  it('.node-version es exactamente el Node que está corriendo', () => {
    expect(readFileSync(resolve(RAIZ, '.node-version'), 'utf8').trim()).toBe(process.versions.node)
  })

  it('packageManager es exactamente el pnpm del devshell', () => {
    // Si no coinciden, pnpm descarga OTRO en silencio y el lock deja de ser reproducible.
    const pnpm = execFileSync('pnpm', ['--version'], { encoding: 'utf8' }).trim()
    const pkg = JSON.parse(readFileSync(resolve(RAIZ, 'package.json'), 'utf8')) as { packageManager?: string }
    expect(pkg.packageManager).toBe(`pnpm@${pnpm}`)
  })
})
