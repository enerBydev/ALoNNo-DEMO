# ESTADO — prototipo navegable y las 5 capas (11 de septiembre de 2026)

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

### Dia 6 · la UI (hecho)

Una sola pagina, como pide el §10. **Sin selector de modo**: el sistema deduce el arquetipo, que
es la respuesta de producto a «no quiero que los usuarios llenen 20 filtros».

- Un textarea, y debajo **las 10 frases de Helder, verbatim y clicables** (regla 4).
- **Panel «asi lo entendi»**: el arquetipo en lenguaje humano —«You have a plan and you are
  looking for a person»—, mas ciudad, categoria, tema y fecha.
- Resultados **etiquetados PERSONA / PLAN**, con el porcentaje grande, la explicacion en el
  idioma de la consulta, y un desplegable con **los 7 componentes y sus puntos**.
- Enlace **«ver descartados»** con el motivo de cada uno.
- Pie con el **desglose de tiempos por capa** y el aviso de datos sinteticos.
- Selector DE/EN de la interfaz.

**Verificado en un navegador real** (Chromium + Playwright, no un `curl`): la pagina monta, las
10 frases son clicables, una busqueda devuelve 12 resultados, el desglose tiene 7 filas y **suma
exactamente el porcentaje que ense~na**, y no hay ni un error de consola.

### Dia 7 · calibracion (hecho)

**El match impecable de la frase 1 pasa de 68% a 91%**, dentro de la banda 88-95% que exige el
§9 y coherente con el 92% que el cliente tiene en su PDF.

La leccion del dia 7, medida: **la similitud coseno no vive en el mismo sitio segun que se
compare.** Consulta contra la bio de una persona da como maximo **0,424** en este corpus;
consulta contra el texto de un plan llega a **0,724**. Con una sola banda de normalizacion, un
perfil perfecto se quedaba en 12,5 de los 30 puntos que el peso del gusto promete. Ahora hay dos
bandas declaradas, y **los pesos del §7 siguen intactos** — que es lo que la regla 7 protege.

Y un fallo que las pruebas no cazaban: `reforzarFecha` corregia la fecha **despues** de que
`normalizar` hubiera decidido el arquetipo, asi que la correccion no llegaba a ninguna parte. La
prueba unitaria llamaba a las dos funciones por separado — que es justo lo que el codigo real no
hace. Corregido, y la prueba ahora comprueba el objeto que devuelve la funcion.

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

## Las 10 frases de Helder, ahora mismo

| # | Arquetipo | Top 1 | |
|---|---|---|---|
| 1 · DE Burna Boy | `plan_seeks_person` | **91%** PERSONA [en] Amara | ✓ |
| 2 · EN Colonia | `plan_seeks_plan` | 61% PLAN | ~ hibrida: deberia mezclar persona y plan |
| 3 · DE techno | `intent_seeks_any` | 72% PERSONA [en] | ✓ |
| 4 · EN Bayern | `plan_seeks_person` | 79% PERSONA [en] | ✓ |
| 5 · DE Frankfurt | `plan_seeks_person` | 72% PERSONA [en] | ✓ |
| **6 · EN Coldplay** | `intent_seeks_any` | **89% PLAN [de] «ein Ticket übrig»** | ✓ **el momento estrella** |
| 7 · DE Barcelona | `plan_seeks_plan` | 74% PLAN | ✓ |
| 8 · EN Berlin abierto | `intent_seeks_any` | 70% PLAN [de] Livemusik | ✓ |
| 9 · DE afrobeats | `standing_interest` | 66-81% PERSONA | ✓ sin fecha, como pide |
| 10 · EN senderismo | `plan_seeks_person` | 80% PERSONA [en] | ✓ |

**Las 10 devuelven resultado**, y en 9 de 10 hay un resultado del top 3 escrito en el idioma
contrario al de la consulta — el criterio del §3.

## Lo que queda flojo, y se dice (regla 8)

- **La frase 2 es hibrida** y hoy resuelve como `plan_seeks_plan`: deberia devolver personas
  **y** planes mezclados. El brief lo marca como caso limite y la auditoria tambien.
- **La latencia en frio va de 13 s a 46 s** por variabilidad del proveedor. Con la cache
  caliente son **0,2-0,4 s**, y por eso `just frases` se corre **siempre antes de ense~nar la
  demo**. Si el limite de 12 s salta, la respuesta usa el parser de reglas y **lo declara**.
- **La cache se invalida subiendo la version de la clave** (`v5:` hoy). Hay que subirla al tocar
  CUALQUIER capa, no solo el scoring: paso hoy y las frases seguian dando el resultado viejo.

## Lo que cambio el 10-11 de septiembre

- **El prototipo** (ADR-0004): la demo pasa de una pagina a **ocho rutas** con los tres flujos
  que vende la propuesta —*create a plan, find a person, agree to meet*— y sesion basica.
  Verificado en Chromium: publicar un plan nuevo y **encontrarlo el primero** al buscarlo en
  lenguaje natural.
- **Workers Builds conectado**: el despliegue sale de `main`, no de esta maquina. Cierra REL-5 y
  sostiene el *"nothing is staged for a demo; the demo is the branch"* de la propuesta.
- **Aparecio `pickando.docx`** y cambia el panorama: el encargo publicado en Workana describe una
  **app de coche compartido**, no ALoNNo. El paneo esta en el repo privado, en
  `conocimiento/07-pickando-vs-alonno.md`.
  **Hay que preguntarle a Helder cual de los dos productos esta vivo antes de seguir.**

## La lista de comprobacion del dia 16, antes de mandar el link

1. `just seed` y `just sembrar` — **re-sembrar**, para que las fechas vuelvan a ser relativas a
   ese dia. Es el riesgo numero 1 del §12.
2. Subir la version de la clave de cache en `server/api/buscar.get.ts` y desplegar.
3. `just frases` — comprueba las 10 y **deja la cache caliente**: el cliente no espera nunca.
4. Comprobar que no hay rutas de diagnostico publicadas.
5. Escribir el mensaje del §13 en ingles, con los 11 puntos, **incluido lo que no quedo**.
