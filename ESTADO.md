# ESTADO — dias 2, 3, 4 y 5 hechos (jueves 10 de septiembre de 2026)

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

### Dia 3 · el seed (hecho)

240 perfiles · 180 planes · 42 intents sembrados en Frankfurt con sus embeddings. De ellos,
**100 perfiles y 40 planes plantados a mano**, uno por cada frase de Helder, con su match
perfecto y sus cuatro near-miss. `db/seed.json` **no contiene ni una fecha**: el tiempo son
desplazamientos que `just sembrar` materializa y `just reanclar` desplaza. Determinismo
comprobado por `just seed-determinista`.

### Dia 4 · Capas 0, 1 y 2 (hecho)

`GET /api/buscar?q=<frase>` responde con la intencion interpretada y los candidatos.

- **Capa 0** — el modelo extrae los HECHOS; **el codigo aplica el arbol del §9-A**. Medido: el
  modelo acertaba `user_has_booking` y fallaba la taxonomia, clasificando la frase 6 como
  `plan_seeks_person`. Ahora el arquetipo lo decide `decidirArquetipo()`, que esta probado.
  Tambien **el modelo no escribe fechas**: devuelve una expresion de un conjunto cerrado y
  `resolverVentana()` la resuelve contra el reloj.
- **Capa 1 y 2** — en Postgres (`db/funciones.sql`): filtros duros con PostGIS y fusion RRF de
  HNSW + `tsvector`.
- **`thinking: false` NO es opcional**: medido, baja la Capa 0 de 6,9 s a 0,5 s en una llamada
  simple. Sin el, el modelo gasta los 300 tokens de salida enteros razonando.

### Dia 5 · Capas 3 y 4 (hecho)

- **Capa 3 · scoring determinista.** Los siete pesos del §7 intactos; lo que se a~nade es la
  normalizacion del ADR-0002 (piso y techo declarados por componente). **19 pruebas**, entre
  ellas que un match impecable entra en la banda **88-95%** que exige el §9.
- **Capa 4 · explicaciones.** El modelo recibe los tres componentes que mas aportan, **con sus
  puntos ya calculados**, y escribe una frase. Si se cuela un numero en la prosa, se borra: el
  modelo escribe la oracion, nunca el numero (regla 6).
- **La regla de mezcla por arquetipo.** El §9-A pide cosas distintas segun la frase: la 1 quiere
  personas (quien pregunta ya tiene la entrada), la 7 quiere planes, la 6 mezcla. Es un
  multiplicador por tipo, no un filtro: los dos siguen apareciendo y etiquetados (§10.4).
- **Cache sobre KV**: la misma frase pasa de **15,9 s a 0,33 s**. Las 10 frases son clicables y
  se van a repetir el dia de la revision.
- **Resistencia**: reintento con espera en las llamadas al proveedor —dos de diez frases dieron
  502 en una tanda y funcionaron al reintentar— y un **parser de reserva por reglas** si la Capa
  0 no responde. Se pierde precision, no la demo, y la respuesta lo declara con `degradado: true`.

**Las 10 frases de Helder devuelven resultado**, todas con un resultado del top 3 en el idioma
contrario al de la consulta. `just frases` lo comprueba y de paso calienta la cache.

**Falta la UI (dia 6) y la calibracion (dia 7).**

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

## Lo verificado contra el despliegue

| Frase | Resultado |
|---|---|
| **1** (DE, Burna Boy) | `plan_seeks_person` · Dusseldorf · «am Samstag» → 2026-09-12 exacta. Top 1: **Amara, bio en INGLES**, a 0,5 km, con Burna Boy en sus artistas — el cross-lingua del §3, demostrado |
| **6** (EN, Coldplay) | `intent_seeks_any` ✓ (el modelo decia `plan_seeks_person`; lo corrige el arbol). `has_concrete_event: true` + `user_has_booking: false`, que es justo la distincion del ADR-0003 |
| **9** (DE, afrobeats) | `standing_interest` ✓ · Koln · **sin ventana temporal**, que es lo que la frase pide |

## El problema abierto, y es de latencia

La Capa 0 tarda entre **3,9 s y 15 s** contra el mismo modelo y la misma frase: la variabilidad
es del proveedor, no del codigo (con `thinking:false` y el prompt real, tres frases seguidas dan
3,8 · 3,8 · 3,9 s). **La demo no puede depender de eso en vivo.**

La respuesta esta en el plan y hay que construirla el dia 5: **cache por frase normalizada** y
**pre-calentado de las 10 frases de Helder** antes de mandar el link. Las diez frases clicables
no deben tocar el LLM en vivo.

## Lo que el dia 7 tiene que calibrar (medido hoy, no adivinado)

| | |
|---|---|
| **La escala real** | El match de la frase 6 da **89%** (banda correcta), pero las frases de tipo persona se quedan en **55-74%**. La similitud consulta↔bio vive en una banda mas baja que texto↔texto: los pisos y techos del ADR-0002 necesitan valores propios para cada tipo de comparacion |
| **La frase 8** | Sale `standing_interest` y deberia ser `intent_seeks_any`: «this weekend» es una ventana temporal y el parser no la esta viendo |
| **La frase 2** | Es hibrida (persona **y** plan) y hoy devuelve solo personas |
| **El idioma de dos explicaciones** | Las frases 5 y 7 tienen explicaciones en espanol **cacheadas** de antes del arreglo. La cache hay que **purgarla** antes de pre-calentar el dia 16 |

## Siguiente paso concreto

Dia 6: la UI del §10 — el textarea, las 10 frases clicables, el panel «asi lo entendi» editable,
los resultados etiquetados PERSONA/PLAN con su porcentaje y su desglose de componentes, el enlace
«ver descartados» y el pie con el desglose de tiempos por capa.
