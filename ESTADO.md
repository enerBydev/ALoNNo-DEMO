# ESTADO — dia 1 de 7 (miercoles 9 de septiembre de 2026)

Entrega: **miercoles 16 de septiembre**. Quedan 7 dias.
Tarea de ClickUp: `86bbx99au` (Dia 1), en `in progress`.

## Que quedo funcionando

| | Comprobacion |
|---|---|
| **methodOS instalado** (plantilla `node`) | `nix develop . -c just ci` en verde · `methodos-doctor.py .` → **GATE VERDE**, 40 de 40 capacidades evaluadas |
| **Nuxt 4.5.2 + Nitro** con preset `cloudflare_module` | `pnpm build` genera `.output/` |
| **Desplegado y respondiendo** | <https://alonno-demo.enerby212.workers.dev> → HTTP 200 en ~0.16 s · `/api/salud` → `{"estado":"ok"}` · el HTML servido dice `backend: ok`, o sea que la ruta de servidor se ejecuta de verdad, no solo llegan bytes |
| **`db/schema.sql`** escrito, idempotente | Aun **sin aplicar**: no hay base |

## Decisiones cerradas hoy

- **Hosting**: Cloudflare Workers (no Vercel/Netlify). El brief no le promete al cliente un
  proveedor concreto; el token de Cloudflare ya esta y el git-connect se hace por API.
- **IA**: NVIDIA NIM, con el token que aporto Rene. **Cambia el §8 del brief**: los modelos de
  NIM no incluyen `text-embedding-3-small`, asi que el gate del dia 2 se corre contra un
  modelo multilingue de NIM (opcion B del brief) y la **dimension del vector puede dejar de
  ser 1536** — si cambia, hay que editar las tres columnas de `db/schema.sql`.
- **Repo publico**: se queda publico. Consecuencia: `CLICKUP_TOKEN` no entra como secreto y
  el puente `sync-cu` sigue inerte → **los estados se mueven a mano con `cu`**.

## Que falta, y que bloquea

1. **BLOQUEANTE — no hay base de datos.** Supabase rechazo el tercer proyecto:
   *«2 project limit»* en el plan Free de la organizacion `OnlyServicesMX`. Sin BD no hay
   dia 2 (no hay donde sembrar). Decision pendiente de Rene: pausar un proyecto, subir a Pro,
   o el plan B del §12 (Postgres con pgvector+PostGIS en contenedor, desplegado aparte).
2. **El token de NVIDIA NIM no esta en GCP Secret Manager.** La SA de la VM es de solo lectura
   a proposito: crear el secreto es tarea de Rene desde su cuenta.
3. Falta conectar Workers Builds al repo (git-connect). Hoy el deploy fue imperativo desde la
   maquina, que es un ❌ declarado del medidor (REL-5, no bloqueante).

## Siguiente paso concreto

Desbloquear la base de datos. En cuanto exista, aplicar `db/schema.sql` y empezar el dia 2:
generador de datos sinteticos + los 8 escenarios plantados + el gate de embeddings
**con fechas relativas a `now()`** (brief §9: es el bug numero 1 del proyecto).
