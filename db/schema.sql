-- ALoNNo DEMO — esquema unico e idempotente (brief §5).
--
-- DEMO: sin migraciones versionadas a proposito (regla 1). Este archivo se aplica entero,
-- tantas veces como haga falta, y deja la base en el mismo sitio.
--
-- LA DIMENSION ES 2048 PORQUE EL MODELO ES `nvidia/nemotron-3-embed-1b`, servido por NVIDIA
-- NIM. Se eligio MIDIENDO (gate del §8, `scripts/gate-embeddings.py`, 9-sep-2026):
--
--   nemotron-3-embed-1b     2048 dim · recall@1 8/8 · margen +0.340   <- elegido
--   text-embedding-3-small  1536 dim · recall@1 8/8 · margen +0.319
--
-- Empatan en recall sobre 8 pares DE<->EN de las frases reales de Helder. Lo que decide NO es
-- la calidad: es que el gateway de Vercel —la unica via a text-embedding-3-small aqui— corta
-- con `429 Free tier requests on this model are rate-limited` a la segunda tanda, y sembrar
-- son ~420 items. NIM hizo 60 vectores en 4.8 s sin un fallo. Una demo que se revisa en vivo
-- no puede depender de un cupo que ya nos corto una vez.
--
-- EL INDICE VA SOBRE `halfvec`, NO SOBRE `vector`: el HNSW de pgvector topa en 2000
-- dimensiones con el tipo `vector`, y `halfvec` llega a 4000. La COLUMNA conserva precision
-- completa; solo el indice usa medias. Consecuencia que hay que respetar al consultar: la
-- consulta tiene que llevar el MISMO cast (`embedding::halfvec(2048) <=> $1::halfvec(2048)`)
-- o Postgres ignora el indice y hace un escaneo secuencial — que devuelve lo mismo, pero
-- lento, y sin avisar.
--
-- `nemotron-3-embed-1b` es ASIMETRICO: exige `input_type` — `passage` al sembrar, `query` al
-- consultar. Sin ese parametro el recall cae a 7/8 y el margen se hunde de +0.340 a +0.091.
-- Es el tipo de fallo que no da error: solo devuelve peores resultados.
--
-- Es multilingue nativo, asi que NO hay que traducir la frase al ingles antes de embeber: se
-- cae la opcion C del §8 que se planeo cuando el candidato era `gte-small`.
--
-- OJO: este archivo es idempotente, y por eso NO cambia la dimension de una columna que ya
-- existe. Cambiarla exige borrar las tablas antes (con la base vacia es trivial).

create extension if not exists vector;
create extension if not exists postgis;
create extension if not exists pg_trgm;

create table if not exists profiles (
  id                uuid primary key,
  display_name      text not null,
  age               int,
  city              text not null,              -- Berlin | Dusseldorf | Koln | Frankfurt | Munchen
  geo               geography(point,4326) not null,
  languages         text[] not null,            -- {de} {en} {de,en}
  bio_lang          text not null,              -- idioma en que esta escrita la bio: de | en
  bio               text not null,              -- ~40 palabras, en bio_lang
  interests         text[] not null,            -- tags normalizados en INGLES (clave interna)
  top_artists       text[],
  top_teams         text[],
  cuisines          text[],
  pace              text,                       -- relaxed | moderate | intense
  budget_band       text,                       -- low | mid | high
  group_pref        text,                       -- one_to_one | small_group | any
  availability      daterange[] not null,
  verification      int default 0,              -- 0..3
  completed_plans   int default 0,
  reports           int default 0,
  embedding         vector(2048),
  fts               tsvector
);

create table if not exists plans (
  id            uuid primary key,
  owner_id      uuid references profiles(id),
  title         text not null,
  description   text not null,
  desc_lang     text not null,                  -- de | en
  category      text not null,                  -- concert|football|weekend_trip|holiday|restaurant|activity
  origin_city   text not null,                  -- donde vive/parte el dueño del plan
  dest_city     text not null,                  -- donde OCURRE el plan: puede ser Barcelona, los Alpes
  is_travel     boolean not null default false, -- dest_city != origin_city
  venue         text,
  geo           geography(point,4326) not null, -- geo del DESTINO
  origin_geo    geography(point,4326) not null,
  date_precision text not null default 'exact', -- exact | weekend | month | flexible
  starts_at     timestamptz not null,
  ends_at       timestamptz not null,
  radius_km     int default 40,
  seats_open    int default 1,
  subject       text,                           -- el artista, el equipo, la cocina, el destino
  tags          text[] not null,
  budget_band   text,
  pace          text,
  language_pref text[],
  embedding     vector(2048),
  fts           tsvector
);

-- Arquetipos 3 y 4: gente con una INTENCION declarada, sin plan concreto.
-- Sin esta tabla, las frases 3, 6, 8 y 9 de Helder no tienen contra que casar.
create table if not exists intents (
  id            uuid primary key,
  owner_id      uuid references profiles(id),
  text          text not null,                  -- "quiero ir a un festival de techno en Berlin"
  text_lang     text not null,
  category      text,                           -- puede ser null: la frase 8 no tiene categoria
  subject       text,                           -- puede ser null: la frase 3 no nombra el evento
  city          text not null,
  geo           geography(point,4326) not null,
  radius_km     int default 40,
  window_start  date,                           -- null = interes permanente (frase 9)
  window_end    date,
  standing      boolean not null default false, -- true = sin fecha, interes continuo
  tags          text[] not null,
  embedding     vector(2048),
  fts           tsvector
);

-- Los indices llevan nombre explicito para que `if not exists` sirva de algo: sin nombre,
-- Postgres lo genera y la segunda pasada crearia un duplicado en vez de no hacer nada.
create index if not exists profiles_embedding_hnsw on profiles using hnsw ((embedding::halfvec(2048)) halfvec_cosine_ops);
create index if not exists plans_embedding_hnsw    on plans    using hnsw ((embedding::halfvec(2048)) halfvec_cosine_ops);
create index if not exists intents_embedding_hnsw  on intents  using hnsw ((embedding::halfvec(2048)) halfvec_cosine_ops);

create index if not exists profiles_geo_gist on profiles using gist (geo);
create index if not exists plans_geo_gist     on plans    using gist (geo);
create index if not exists intents_geo_gist   on intents  using gist (geo);

create index if not exists profiles_fts_gin on profiles using gin (fts);
create index if not exists plans_fts_gin    on plans    using gin (fts);
create index if not exists intents_fts_gin  on intents  using gin (fts);


-- ── RLS: cerrado por defecto ────────────────────────────────────────────────────────────
--
-- EL FALLO (10-sep-2026, incidente): las tres tablas nacieron con RLS APAGADO. PostgREST esta
-- expuesto en `https://<ref>.supabase.co/rest/v1/`, la clave publishable es publica por dise~no y
-- la URL del proyecto esta versionada en `wrangler.jsonc` — o sea que **cualquiera podia escribir
-- en la base de la demo**. Comprobado insertando una fila real con la clave publica: HTTP 201.
--
-- Se activa SIN NINGUNA POLICY, y eso es lo correcto aqui: RLS sin policies deniega todo al rol
-- anonimo, y `service_role` —que es con lo que habla el servidor de la demo— la salta por
-- dise~no. La demo no tiene usuarios ni auth: nadie mas necesita tocar estas tablas.
--
-- Verificado tras aplicarlo: INSERT anonimo → 401 `new row violates row-level security policy`,
-- SELECT anonimo → `[]`, y `/api/salud` sigue leyendo con la clave de servidor.
alter table profiles enable row level security;
alter table plans    enable row level security;
alter table intents  enable row level security;


-- ── El ancla del seed ───────────────────────────────────────────────────────────────────
--
-- Guarda el instante contra el que se materializaron las fechas del seed. Con eso, re-anclar
-- es un `update` que suma la diferencia a todas las fechas y **conserva las distancias
-- relativas**: el partido sigue siendo «manana» y el concierto «el mes que viene», pase el
-- tiempo que pase. Ver docs/adr/0001-como-ruedan-las-fechas.md.
--
-- Sin esto habria que re-sembrar entero cada dia —460 embeddings, ~40 s y dinero— para mover
-- unas fechas que no cambian de sitio unas respecto a otras.
create table if not exists seed_meta (
  id        int primary key default 1,
  anclado   timestamptz not null,
  semilla   bigint,
  filas     jsonb,
  constraint seed_meta_una_fila check (id = 1)
);
alter table seed_meta enable row level security;

-- ── El tercer flujo: «agree to meet» ────────────────────────────────────────────────────
--
-- La propuesta vende TRES flujos en el M1 (seccion F): *"create a plan, find a person, agree to
-- meet"*. Los dos primeros son buscar y publicar; este es el que los cierra.
--
-- Un interes es unidireccional. Cuando el dueno de un plan muestra interes de vuelta en quien
-- se apunto, hay **match mutuo** — y es entonces cuando dos personas se pueden hablar. Es el
-- «interest & mutual match» que la propuesta pone en el M3, reducido a lo que una demo necesita
-- para contar la historia.
create table if not exists intereses (
  id         uuid primary key default gen_random_uuid(),
  persona_id uuid not null references profiles(id) on delete cascade,
  plan_id    uuid not null references plans(id) on delete cascade,
  creado     timestamptz not null default now(),
  unique (persona_id, plan_id)
);
create index if not exists intereses_plan on intereses (plan_id);
create index if not exists intereses_persona on intereses (persona_id);
alter table intereses enable row level security;


-- ════════════════════════════════════════════════════════════════════════════════════════
-- EL GIRO A COCHE COMPARTIDO (11-sep-2026)
-- ════════════════════════════════════════════════════════════════════════════════════════
--
-- `pickando.docx` —el adjunto del encargo de Workana— describe una app de coche compartido,
-- no un emparejamiento de planes sociales. Ver docs/conocimiento/07-pickando-vs-alonno.md.
--
-- El motor de 5 capas NO se toca. Lo que cambia es el dominio, y encaja casi entero:
--
--   plans.origin_geo  → donde RECOGE el conductor        plans.geo       → donde DEJA
--   plans.starts_at   → hora de salida                   plans.seats_open → plazas libres
--   plans.radius_km   → «pasajeros a 1-2 km de mi ruta»  intereses       → solicitud de plaza
--   intents.standing  → «preferred route» del docx       profiles.*      → conductor/pasajero
--
-- Lo que SI falta, y es lo que a~naden estas columnas: la ruta como linea (no dos puntos),
-- la tarifa por km, el coche, y la reputacion del conductor con numero y rese~nas.

-- ── La ruta como LINESTRING, no como par de puntos ──────────────────────────────────────
--
-- «Passenger: tracking within 1-2 km of all drivers driving on the same route» no es lo mismo
-- que «cerca de mi». Un conductor Berlin→Potsdam pasa a 800 m de alguien de Wannsee que no
-- esta ni en el origen ni en el destino: con dos puntos ese pasajero no existe; con la
-- polilinea, `ST_DWithin(ruta, pasajero, 2000)` lo encuentra.
--
-- `geography(linestring,4326)` mide en METROS sobre el elipsoide, asi que el radio del docx
-- se escribe tal cual: 2000. No hay que proyectar nada.
alter table plans add column if not exists ruta geography(linestring,4326);
alter table plans add column if not exists via  text[];            -- los barrios por los que pasa
create index if not exists plans_ruta_gist on plans using gist (ruta);

-- ── Tarifa: «the system gives a parameter (min. and max.) for the price/km» ──────────────
--
-- El docx pide que el precio se calcule por km y que el rango sea CONFIGURABLE. Se guarda la
-- distancia ya calculada (la ruta no cambia) y el precio por km que puso el conductor; el
-- total es una multiplicacion, no un servicio.
alter table plans add column if not exists distancia_km   numeric(6,1);
alter table plans add column if not exists precio_por_km  numeric(4,2);   -- EUR/km
alter table plans add column if not exists recurrente     text;           -- null | weekdays | daily

-- ── El coche y quien lo conduce ─────────────────────────────────────────────────────────
alter table profiles add column if not exists conduce      boolean not null default false;
alter table profiles add column if not exists coche        text;          -- «VW Golf · gris»
alter table profiles add column if not exists plazas_coche int;
alter table profiles add column if not exists desde_offset int;           -- meses como miembro

-- ── Driver rating & review ──────────────────────────────────────────────────────────────
--
-- El esquema ya tenia `verification` (0..3), `completed_plans` y `reports`, y los tres pesan en
-- el componente `trust` del scoring. Lo que faltaba es lo que el pasajero MIRA antes de subirse:
-- una nota y rese~nas escritas por personas con nombre.
--
-- La nota se guarda DESNORMALIZADA en el perfil porque la demo la lee en cada tarjeta de
-- resultado y no vamos a hacer un `avg()` por fila; `valoraciones` es la fuente y el trigger
-- no existe a proposito (regla 1: sin migraciones, el seed escribe las dos cosas coherentes).
alter table profiles add column if not exists nota          numeric(2,1);  -- 0.0 .. 5.0
alter table profiles add column if not exists notas_conteo  int not null default 0;

create table if not exists valoraciones (
  id           uuid primary key default gen_random_uuid(),
  conductor_id uuid not null references profiles(id) on delete cascade,
  autor_id     uuid not null references profiles(id) on delete cascade,
  estrellas    int  not null check (estrellas between 1 and 5),
  texto        text,
  texto_lang   text,                                -- de | en — la demo es bilingue tambien aqui
  dia_offset   int  not null default -7,            -- relativo, como TODA fecha del seed (regla 3)
  creado       timestamptz not null default now()
);
create index if not exists valoraciones_conductor on valoraciones (conductor_id);
alter table valoraciones enable row level security;
