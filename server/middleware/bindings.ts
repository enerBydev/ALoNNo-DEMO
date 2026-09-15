// CAPTURA LOS BINDINGS DEL WORKER PARA LAS PETICIONES QUE NO LOS TRAEN.
//
// En Workers, `process.env` (via `nodejs_compat`) trae las variables y los secretos, pero NO los
// bindings de KV: esos solo viajan en `event.context.cloudflare.env`, y Nitro se lo pone a la
// peticion que entra por la red. El `$fetch` interno con el que la portada llama a `/api/buscar`
// durante el SSR crea un evento NUEVO, sin ese contexto: la cache caia al Map en memoria, la
// portada tardaba 15-20 s por visitante mientras la API para la misma frase contestaba HIT en
// 0,15 s, y ademas gastaba presupuesto. Lo midio la re-verificacion del programa de UX
// (15-sep-2026, regresion N2).
//
// Este middleware corre en TODA peticion, incluida la de `/`, que si lleva el contexto: guarda el
// binding en el isolate, y `kvDe()` lo usa cuando el evento no lo trae. Mismo isolate, orden
// sincrono: la peticion de fuera siempre pasa por aqui antes de que su SSR llame dentro.
export default defineEventHandler((event) => {
	const kv = (event.context as any)?.cloudflare?.env?.CACHE;
	if (kv?.get && kv?.put) (globalThis as any).__bindingsCache = kv;
});
