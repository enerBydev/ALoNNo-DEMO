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

## Proveedor de IA: RESUELTO, y el gate del §8 esta corrido

**Los tokens de NVIDIA que llegaron por chat no valian; el que estaba guardado en GCP
(`nvidia-nim`) SI.** La API trataba a los dos primeros igual que a una clave inventada —403
identico— mientras que sin cabecera devuelve 401. El endpoint y el modelo eran correctos
desde el principio.

**Gate del §8 corrido de verdad** (`scripts/gate-embeddings.py`), recall@1 cross-lingua sobre
8 pares DE↔EN construidos con las frases reales de Helder:

| modelo | dim | recall@1 | margen medio |
|---|---|---|---|
| **`nvidia/nemotron-3-embed-1b`** (NIM) | 2048 | 8/8 | **+0.340** ← elegido |
| `openai/text-embedding-3-small` (Vercel) | 1536 | 8/8 | +0.319 |
| `nemotron-3-embed-1b` **sin `input_type`** | 2048 | 7/8 | +0.091 |

Empatan en recall: **lo que decide es el cupo.** El AI Gateway de Vercel funciona pero su free
tier corta con `429 rate-limited` a la segunda tanda, y sembrar son ~420 items; NIM hizo 60
vectores en 4.8 s sin un fallo. Vercel queda como respaldo declarado.

**Decisiones cerradas (§8 dice: decidir el dia 2 y no volver a tocarlo):**

- **Embeddings**: `nvidia/nemotron-3-embed-1b` · 2048 dim · **es ASIMETRICO**: `input_type`
  = `passage` al sembrar, `query` al consultar. Sin ese parametro el recall cae a 7/8 y el
  margen se hunde a +0.091 — y no da ningun error: solo devuelve peores resultados.
- **LLM (Capas 0 y 4)**: `nvidia/nemotron-3.5-lightning-30b-a3b`, probado y respondiendo.
- **Multilingue nativo**: se cae la opcion C del §8 (traducir al ingles antes de embeber).
  Menos codigo y una llamada menos por busqueda.
- **El indice va sobre `halfvec(2048)`**, porque HNSW con el tipo `vector` topa en 2000. La
  columna guarda precision completa. **Toda consulta tiene que llevar el mismo cast** o
  Postgres ignora el indice sin avisar. Comprobado con EXPLAIN: `Index Scan using
  profiles_embedding_hnsw`.
- **Credenciales**: `NVIDIA_API_KEY` y `VERCEL_AI_GATEWAY_KEY`, en el Worker y en el repo.

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
