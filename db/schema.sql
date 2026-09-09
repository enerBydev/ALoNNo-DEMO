-- ALoNNo DEMO — esquema unico e idempotente (brief §5).
--
-- DEMO: sin migraciones versionadas a proposito (regla 1). Este archivo se aplica entero,
-- tantas veces como haga falta, y deja la base en el mismo sitio.
--
-- LA DIMENSION ES 384 PORQUE EL GENERADOR ES `gte-small`, el modelo que Supabase corre
-- dentro de sus propias Edge Functions. Se eligio asi para no depender de ninguna API de
-- embeddings externa: los vectores se producen donde se guardan.
--
-- `gte-small` es MONOLINGUE INGLES, y este producto tiene que casar aleman con ingles. La
-- salida es la opcion C del §8 del brief, textual: el LLM de la Capa 0 devuelve, en la MISMA
-- llamada, el JSON de intencion Y la frase normalizada al ingles; se embebe siempre ese texto
-- en ingles, al sembrar y al consultar. Va declarado en el mensaje de entrega: el brief pide
-- documentar este fallback, no esconderlo.
--
-- Si algun dia cambia el modelo, cambian las TRES columnas `embedding` y hay que re-embeber
-- el corpus entero.

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
  embedding         vector(384),
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
  embedding     vector(384),
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
  embedding     vector(384),
  fts           tsvector
);

-- Los indices llevan nombre explicito para que `if not exists` sirva de algo: sin nombre,
-- Postgres lo genera y la segunda pasada crearia un duplicado en vez de no hacer nada.
create index if not exists profiles_embedding_hnsw on profiles using hnsw (embedding vector_cosine_ops);
create index if not exists plans_embedding_hnsw    on plans    using hnsw (embedding vector_cosine_ops);
create index if not exists intents_embedding_hnsw  on intents  using hnsw (embedding vector_cosine_ops);

create index if not exists profiles_geo_gist on profiles using gist (geo);
create index if not exists plans_geo_gist     on plans    using gist (geo);
create index if not exists intents_geo_gist   on intents  using gist (geo);

create index if not exists profiles_fts_gin on profiles using gin (fts);
create index if not exists plans_fts_gin    on plans    using gin (fts);
create index if not exists intents_fts_gin  on intents  using gin (fts);
