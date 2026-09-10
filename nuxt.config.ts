// Nuxt 4 + Nitro. El destino es Cloudflare Workers (decidido el dia 1).
export default defineNuxtConfig({
  compatibilityDate: '2026-09-09',
  devtools: { enabled: false },
  nitro: {
    // `cloudflare_module`, NO `cloudflare`: con el segundo el Worker se comporta como
    // service-worker y los assets no se sirven (trampa documentada en el CLAUDE.md global).
    preset: 'cloudflare_module',
    // La cache de Nitro sobre el KV del Worker. Es lo que hace que una frase repetida no vuelva
    // a pagar 4 s de LLM ni una llamada de embeddings: las 10 frases de Helder son clicables y
    // se van a repetir muchas veces el dia de la revision.
    storage: {
      cache: { driver: 'cloudflare-kv-binding', binding: 'CACHE' },
    },
  },
})
