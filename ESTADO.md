# ESTADO — dia 1 de 7 CERRADO (miercoles 9 de septiembre de 2026)

Entrega: **miercoles 16 de septiembre**. Quedan 7 dias.

## Que quedo funcionando (todo comprobado, no declarado)

| | Comprobacion |
|---|---|
| **methodOS instalado** (plantilla `node`) | `nix develop . -c just ci` verde · `methodos-doctor.py .` → GATE VERDE, 40/40 capacidades evaluadas |
| **El CI ejecuta el gate de verdad** | antes salia `success` **sin ejecutar nada** (paso «sin kit, se informa el hueco»). `instalar-revisor.sh` puso los secretos del App; ahora corre `nix develop -c just ci` + gitleaks + medidor |
| **Revision por otra identidad (CODE-2)** | el App `methodos-revisor` aprueba los PR |
| **Nuxt 4.5.2 + Nitro**, preset `cloudflare_module` | `pnpm build` genera `.output/` |
| **Desplegado** | <https://alonno-demo.enerby212.workers.dev> |
| **Base de datos en Frankfurt** | proyecto Supabase `qbrgwphcpflbwhfqhffc`, org `enerbydev`, region **eu-central-1** |
| **`db/schema.sql` APLICADO** | pgvector 0.8.2 · PostGIS 3.3.7 · pg_trgm 1.6 · `profiles`/`plans`/`intents` · `vector(384)` · indices HNSW + GIN + GiST. **Idempotencia probada**: segunda aplicacion sin error |
| **La app ALCANZA la base** | `/api/salud` → `{"estado":"ok","bd":"ok","region_bd":"eu-central-1 (Frankfurt)"}`. No mide el proceso: hace una lectura real de `profiles` |

## Decisiones cerradas

- **Hosting**: Cloudflare Workers.
- **Base**: Supabase Frankfurt, en la org `enerbydev` (la otra org tenia el cupo lleno).
- **Embeddings: `gte-small` de Supabase, 384 dimensiones**, ejecutado dentro de Supabase — sin
  API de embeddings externa. Es monolingue ingles, asi que el cruce DE↔EN se resuelve con la
  **opcion C del §8 del brief**: el LLM de la Capa 0 devuelve, en la misma llamada, el JSON de
  intencion **y** la frase normalizada al ingles; se embebe siempre el texto en ingles, al
  sembrar y al consultar. Va declarado en el mensaje de entrega, no escondido.
- **Secretos**: en el Worker (`wrangler secret`) y en el repo de GitHub. No en GCP: la SA de
  esta VM no puede escribir secretos, y el repo es publico pero sus secretos de Actions no se
  exponen a forks.

## Lo unico que bloquea

**No hay credencial de LLM que funcione.** El token de NVIDIA NIM esta guardado
(`NVIDIA_API_KEY`, en el Worker y en el repo) pero **rechaza toda inferencia**: HTTP 403
`Authorization failed` en `/v1/embeddings` y en `/v1/chat/completions`, probado con 7 modelos
de 4 familias (DeepSeek, Nemotron, Mistral, Phi). `/v1/models` devuelve 200, pero ese endpoint
responde igual con claves muertas: no prueba nada.

Sin LLM no hay Capa 0 (parser + normalizacion al ingles) ni Capa 4 (explicaciones), y sin la
normalizacion al ingles tampoco hay embeddings utiles. **Es el camino critico del dia 2.**

**Se probaron DOS tokens de NVIDIA y los dos dan 403 en chat y en embeddings.** El segundo se
probo ademas **desde el Worker desplegado** —desde el edge de Cloudflare, no desde esta VM—,
lo que descarta la red y la IP de origen.

Lo que lo cierra es esta comparacion contra el mismo endpoint:

| Credencial | Respuesta |
|---|---|
| sin cabecera `Authorization` | **401** · `Header of type authorization was missing` |
| una clave **inventada** (`nvapi-000...000`) | **403** · `Authorization failed` |
| los dos tokens reales | **403** · `Authorization failed` |

La API trata los tokens **igual que a una clave inventada**: no los reconoce. Descartado
tambien que sea el endpoint (`ai.api.nvidia.com/v1` devuelve 404: no es ruta valida) y que
sea el modelo (`nvidia/nemotron-3.5-lightning-30b-a3b` SI figura en el catalogo de
`/v1/models`, que responde 200). Y no parece cupo agotado: eso daria 402 o 429.

Hace falta una API key nueva emitida en build.nvidia.com.

La sonda que lo mide vive en `/api/diagnostico-ia` y **hay que retirarla antes del 16**
(tarea `86bbxv2wx`): devuelve solo codigos de estado, nunca el token, pero un cliente que la
abra lee «Authorization failed» y eso no cuenta bien la historia.

Candidatos que Rene ya tiene en GCP Secret Manager y que la SA aun no puede leer:
`vercel-ai-gateway` y `zai`. Se desbloquean dando a
`dev-vm-sa@enerby-workstation.iam.gserviceaccount.com` el rol *Secret Accessor* sobre uno.

## Huecos declarados (no bloquean)

- El deploy es imperativo desde la maquina (REL-5 en rojo). Falta conectar Workers Builds.
- La contrasena de Postgres la genero Supabase y no la conocemos: `SUPABASE_DB_PASSWORD` estaba
  vacia al crear el proyecto. **No estorba**: el SQL se aplica por la Management API con el PAT
  y la app habla por PostgREST con la clave `secret`. Si algun dia hace falta `psql`, hay que
  resetearla en el dashboard.
- El puente `sync-cu` sigue inerte (repo publico → sin `CLICKUP_TOKEN`): los estados de las
  tareas se mueven a mano con `cu`.

## Siguiente paso concreto (dia 2)

En cuanto haya LLM: generador de datos sinteticos con **fechas relativas a `now()`** (brief §9:
es el bug numero 1 del proyecto), los 8 escenarios plantados —incluido el par reciproco 6↔1—,
y el gate de recall@5 cross-lingua medido de verdad sobre 20 pares DE↔EN.
