// Nuxt 4 + Nitro. El destino es Cloudflare Workers (decidido el dia 1).
export default defineNuxtConfig({
  compatibilityDate: '2026-09-09',

  // DevTools NO se instala: `nuxt@4.5.2` ya declara `@nuxt/devtools ^3.4.1` y el arbol tiene el
  // 3.4.2. Estaba apagado y era algo ya pagado que no se usaba. No llega a produccion (medido:
  // una sola aparicion de la cadena en el build, y es un gancho de Vue).
  devtools: { enabled: true },

  modules: ['@nuxt/ui', '@nuxtjs/leaflet'],

  // `main.css` trae Tailwind 4 y el tema de Nuxt UI; `base.css` es el sistema propio y sigue
  // mandando en las pantallas que ya existen. Conviven a proposito: migrar las ocho paginas
  // enteras son ~5 h que no compran nada.
  css: ['~/assets/css/main.css', '~/assets/css/base.css'],

  // LA TRAMPA QUE NINGUNA GUIA AHORRA (medida el 11-sep-2026). Con el preset de Workers,
  // `serverBundle` cae en `'auto'` → `remote`, y eso genera un fichero con 100+ colecciones
  // declaradas como `createRemoteCollection("https://cdn.jsdelivr.net/…")`: **cada render de
  // servidor con un icono se trae una coleccion entera desde jsdelivr**. La demo del 16
  // dependeria de un CDN de terceros para pintar un coche.
  //
  // Anclar `lucide` cuesta +86 KB gzip en el Worker —irrelevante contra el limite de 64 MiB SIN
  // comprimir, del que hoy se usa el 1,7 %— y es la unica opcion que pinta el icono ya en el
  // HTML del servidor, sin parpadeo al hidratar.
  icon: {
    serverBundle: { collections: ['lucide'] },
    clientBundle: { scan: true },
  },

  app: {
    // Transicion entre paginas: es lo que hace que se sienta una aplicacion y no una web de 2004.
    pageTransition: { name: 'pagina', mode: 'out-in' },
    head: { htmlAttrs: { lang: 'en' } },
  },

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
