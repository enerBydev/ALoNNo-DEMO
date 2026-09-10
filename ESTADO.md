# ESTADO — dia 2 de 7 (jueves 10 de septiembre de 2026)

Entrega: **miercoles 16 de septiembre**. Ventana de feedback pedida: **3 dias habiles → hasta el
lunes 21**. Quedan 6 dias de construccion.

## Lo que hay construido, verificado hoy

| | Comprobacion |
|---|---|
| Nuxt 4.5.2 + Nitro, preset `cloudflare_module` | desplegado: <https://alonno-demo.enerby212.workers.dev> |
| Base en **Frankfurt** (`qbrgwphcpflbwhfqhffc`) | pgvector 0.8.2 · PostGIS 3.3.7 · pg_trgm 1.6 |
| `db/schema.sql` aplicado | `profiles`/`plans`/`intents` · **`vector(2048)`** · 12 indices · HNSW sobre **`halfvec(2048)`** · idempotencia probada |
| La app alcanza la base | `/api/salud` → `{"estado":"ok","bd":"ok","region_bd":"eu-central-1 (Frankfurt)"}` — hace una lectura real de `profiles` |
| methodOS | `just ci` exit 0 · `methodos-doctor.py .` GATE VERDE · revisor maquina aprobando los PR |
| Base de conocimiento | **13 informes** de auditoria en `docs/conocimiento/`, **9.114 lineas** (repo privado) |
| RLS activo en las tres tablas | INSERT anonimo → `401 violates row-level security`; probado como codigo en `tests/rls.test.ts` |
| Gate de documentacion | `just hechos` dentro de `just ci`: al instalarlo cazo 8 afirmaciones falsas |

**Las tres tablas tienen 0 filas.** No existe `seed.json`. No existe ninguna de las 5 capas del
motor. El dia 2 del §11 **no ha empezado**.

## Decisiones cerradas (§8 dice: decidir el dia 2 y no volver a tocarlo)

- **Hosting**: Cloudflare Workers. **Base**: Supabase Frankfurt, org `enerbydev`.
- **Embeddings**: **`nvidia/nemotron-3-embed-1b`** · **2048 dim** · via NVIDIA NIM. Elegido
  midiendo (`scripts/gate-embeddings.py`): recall@1 8/8 y margen +0.340 sobre 8 pares DE↔EN de
  las frases reales de Helder, frente a 8/8 y +0.319 de `text-embedding-3-small`. **Decidio el
  cupo, no la calidad**: el AI Gateway de Vercel corta con `429` a la segunda tanda y sembrar son
  ~420 items.
  **Es ASIMETRICO**: `input_type` = `passage` al sembrar, `query` al consultar. Sin ese parametro
  el recall cae a 7/8 y el margen se hunde a +0.091 — **sin dar ningun error**.
- **LLM (Capas 0 y 4)**: `nvidia/nemotron-3.5-lightning-30b-a3b`.
- **Multilingue nativo**: NO hay que traducir al ingles antes de embeber. Se cae la opcion C del
  §8 que se planeo cuando el candidato era `gte-small`.
- **Indice sobre `halfvec(2048)`**: HNSW con el tipo `vector` topa en 2000 dimensiones. La columna
  guarda precision completa. **Toda consulta tiene que llevar el mismo cast** o el planner ignora
  el indice sin avisar. Comprobado con EXPLAIN: `Index Scan using profiles_embedding_hnsw`.

## Dos incidentes cerrados hoy

1. **`/api/diagnostico-ia` reenviaba `Authorization: Bearer NVIDIA_API_KEY`** al host que le
   pasaran por `?base=`. Publico, sin auth, ~19 h expuesto. Retirado y desplegado.
   → `incidentes/2026-09-10-proxy-abierto.md`
2. **La base aceptaba escritura anonima**: RLS apagado en las tres tablas. Comprobado insertando
   una fila real con la clave publishable (**HTTP 201**) y borrandola. Cerrado, llevado al
   esquema y probado como codigo. → `incidentes/2026-09-10-rls-apagado.md`

**Pendiente de Rene: rotar la clave `nvidia-nim`.**

## Lo que la auditoria cambio del plan (y hay que decidir HOY)

1. **El §12 dimensiona mal el riesgo nº1.** Manda re-sembrar el 16 antes de enviar el link, pero
   la ventana de feedback llega al **lunes 21**: si Helder abre la demo el 18, «Bayern gegen
   Dortmund morgen» ya caduco y **5 de las 10 frases devuelven vacio**. Re-sembrar una vez no
   basta: **las fechas tienen que rodar solas** (Cron Trigger diario que re-ancle, o fechas
   calculadas como offset desde `now()`).
2. **La escala del scoring no llega a lo prometido.** Con las formulas del §7 tal cual, un match
   impecable da **~72%** y como maximo 79%. El brief §9 exige la banda **88–95%** y el PDF que el
   cliente tiene en la mano ense~na un **92%**. La discriminacion relativa si funciona (~72%
   frente a ~42% del near-miss). Falta decidir **la normalizacion de cada componente**.
3. **La frase 6 falla por dise~no del propio brief.** El §6 deja `has_concrete_event=true` para
   ella, pero la regla de mezcla del §7 solo sube los planes cuando es `false` — justo la unica
   frase donde el brief exige un plan en el top-1. Arreglo propuesto: separar
   `has_concrete_event` (¿existe el evento?) de `user_has_booking` (¿lo tiene el usuario?) y atar
   la regla de mezcla a la segunda.
4. **El gate de este repo no mide documentacion.** `ESTADO.md` afirmaba `vector(384)` y
   `gte-small` mientras el esquema era `vector(2048)` y el modelo nemotron — y **`just ci` paso en
   verde con esa contradiccion dentro**. Este repo corre 7 verbos de los 12 del kernel: le faltan
   `docs` y `hechos`, que son los que cazan exactamente esto.
5. **El medidor da dos verdes falsos**: REL-5 y OPS-5 dicen git-connect, pero los 9 despliegues
   son `source: wrangler` y Workers Builds responde `12000 Not found`.

## El plan revisado

**`docs/conocimiento/PLAN.md`**: el recorte de las 69,3 h que propusieron los auditores a las
~10 h de aparato que caben sin robarle tiempo al motor, con el reparto dia a dia del 11 al 16.

## Siguiente paso concreto

Dia 3 (viernes 11): el seed. ~240 perfiles, ~180 planes, los 8 escenarios plantados —**el par
reciproco 6↔1 primero**— y `seed.json` versionado, **con fechas relativas a `now()` desde la
primera linea**.

Antes de escribir una linea del generador hay que cerrar las **tres decisiones** del plan: como
ruedan las fechas, la normalizacion del score, y separar `has_concrete_event` de
`user_has_booking`.
