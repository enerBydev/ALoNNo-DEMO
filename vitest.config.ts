import { defineConfig } from 'vitest/config'

// EL FALLO QUE LO CAUSÓ (2026-08-19, calc-nuxt): vitest encontraba una SEGUNDA copia de
// la suite dentro de .direnv/flake-inputs/<hash>-source/ (donde nix-direnv materializa
// las entradas del flake) y la corría también. Hoy idénticas; en cuanto diverjan, el
// gate validaría código que no es el del repo. La exclusión por defecto de vitest no
// conoce .direnv.
export default defineConfig({
  test: {
    exclude: [
      '**/node_modules/**',
      '**/dist/**',
      '**/.direnv/**',
      '**/.nuxt/**',
      '**/.output/**',
    ],
  },
})
