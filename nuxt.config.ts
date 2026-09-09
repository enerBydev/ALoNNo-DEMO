// Nuxt 4 + Nitro. El destino es Cloudflare Workers (decidido el dia 1).
export default defineNuxtConfig({
  compatibilityDate: '2026-09-09',
  devtools: { enabled: false },
  nitro: {
    // `cloudflare_module`, NO `cloudflare`: con el segundo el Worker se comporta como
    // service-worker y los assets no se sirven (trampa documentada en el CLAUDE.md global).
    preset: 'cloudflare_module',
  },
})
