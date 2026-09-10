-- Las capas 1 y 2 del §6, en la base — que es donde el brief las pone y donde son gratis.
--
--   CAPA 1 · filtros duros: fecha, radio (PostGIS), categoria, asientos, idioma. Deja el
--            conjunto en cientos. «Una fecha que no funciona no es un 60% de match: no es match».
--   CAPA 2 · recuperacion: HNSW sobre el vector + `tsvector` sobre el texto, fusionados por
--            Reciprocal Rank Fusion. Lo hace el mismo indice que ya existe, sin coste de API.
--
-- POR QUE RRF Y NO SOLO VECTORES: el nombre de un artista es un TOKEN, no un concepto. La
-- busqueda lexica lo encuentra exacto; la semantica encuentra a quien «le gusta ese rollo»
-- sin nombrarlo. Fusionarlas es lo que hace funcionar «alguien a quien de verdad le guste el
-- artista» (§6 del brief y seccion C de la propuesta).
--
-- El vector entra como `halfvec(2048)` PORQUE EL INDICE ES DE HALFVEC: si la consulta no lleva
-- el mismo cast, Postgres ignora el indice y hace un escaneo secuencial. Devuelve lo mismo,
-- mas lento, y sin avisar de nada.

-- ── Personas ────────────────────────────────────────────────────────────────────────────
create or replace function buscar_personas(
  q_vector      halfvec(2048),
  q_texto       text,
  q_idioma      text default 'english',
  q_lon         double precision default null,
  q_lat         double precision default null,
  q_radio_km    int default 40,
  q_desde       date default null,
  q_hasta       date default null,
  q_exacta      boolean default false,
  q_excluir     uuid default null,
  q_limite      int default 50
) returns table (
  id uuid, display_name text, city text, bio text, bio_lang text, age int,
  interests text[], top_artists text[], top_teams text[], cuisines text[],
  pace text, budget_band text, group_pref text, languages text[],
  verification int, completed_plans int, reports int,
  km double precision, disponible_exacto boolean, disponible_finde boolean,
  similitud double precision, rrf double precision
)
language sql stable as $$
  with filtrados as (
    select p.*,
           case when q_lon is null then null
                else st_distance(p.geo, st_point(q_lon, q_lat)::geography) / 1000.0 end as km_calc
    from profiles p
    where (q_excluir is null or p.id <> q_excluir)
      -- CAPA 1 · radio. Con PostGIS es un indice GiST, no una cuenta por fila.
      and (q_lon is null or st_dwithin(p.geo, st_point(q_lon, q_lat)::geography, q_radio_km * 1000.0))
      -- CAPA 1 · disponibilidad. Si la fecha es EXACTA, no estar libre elimina; si es una
      -- ventana ancha (un fin de semana, un mes), basta con solapar.
      and (
        q_desde is null
        or exists (select 1 from unnest(p.availability) a
                   where a && daterange(q_desde, coalesce(q_hasta, q_desde) + 1))
      )
  ),
  consulta as (select websearch_to_tsquery(q_idioma::regconfig, q_texto) as tq),
  vectorial as (
    select f.id, row_number() over (order by f.embedding::halfvec(2048) <=> q_vector) as puesto,
           1 - (f.embedding::halfvec(2048) <=> q_vector) as sim
    from filtrados f order by f.embedding::halfvec(2048) <=> q_vector limit q_limite * 2
  ),
  lexica as (
    select f.id, row_number() over (order by ts_rank(f.fts, c.tq) desc) as puesto
    from filtrados f, consulta c
    where c.tq is not null and f.fts @@ c.tq
    order by ts_rank(f.fts, c.tq) desc limit q_limite * 2
  ),
  fusion as (
    -- RRF: 1/(60 + puesto). El 60 amortigua las diferencias entre los primeros puestos, que es
    -- justo lo que se quiere al mezclar dos listas que miden cosas distintas.
    select coalesce(v.id, l.id) as id,
           coalesce(1.0 / (60 + v.puesto), 0) + coalesce(1.0 / (60 + l.puesto), 0) as rrf,
           coalesce(v.sim, 0) as sim
    from vectorial v full outer join lexica l on l.id = v.id
  )
  select f.id, f.display_name, f.city, f.bio, f.bio_lang, f.age,
         f.interests, f.top_artists, f.top_teams, f.cuisines,
         f.pace, f.budget_band, f.group_pref, f.languages,
         f.verification, f.completed_plans, f.reports,
         f.km_calc,
         -- Se devuelven las dos, porque el scoring de la Capa 3 las pondera distinto:
         -- estar libre EL DIA vale 1.0; estar libre ese fin de semana, 0.7.
         (q_desde is not null and exists (
            select 1 from unnest(f.availability) a where a @> q_desde)) as disp_exacto,
         (q_desde is not null and exists (
            select 1 from unnest(f.availability) a
            where a && daterange(q_desde, coalesce(q_hasta, q_desde) + 1))) as disp_finde,
         fu.sim, fu.rrf
  from fusion fu join filtrados f on f.id = fu.id
  order by fu.rrf desc
  limit q_limite;
$$;

-- ── Planes ──────────────────────────────────────────────────────────────────────────────
create or replace function buscar_planes(
  q_vector      halfvec(2048),
  q_texto       text,
  q_idioma      text default 'english',
  q_lon         double precision default null,
  q_lat         double precision default null,
  q_radio_km    int default 40,
  q_desde       date default null,
  q_hasta       date default null,
  q_categoria   text default null,
  q_dest_city   text default null,
  q_excluir     uuid default null,
  q_limite      int default 50
) returns table (
  id uuid, owner_id uuid, title text, description text, desc_lang text, category text,
  origin_city text, dest_city text, is_travel boolean, venue text, subject text, tags text[],
  starts_at timestamptz, ends_at timestamptz, seats_open int, radius_km int,
  budget_band text, pace text, language_pref text[],
  km double precision, similitud double precision, rrf double precision
)
language sql stable as $$
  with filtrados as (
    select p.*,
           case when q_lon is null then null
                else st_distance(p.geo, st_point(q_lon, q_lat)::geography) / 1000.0 end as km_calc
    from plans p
    where (q_excluir is null or p.owner_id <> q_excluir)
      -- Un plan al que se llega es un plan futuro. Lo pasado no es un match peor: no es match.
      and p.ends_at >= now()
      and (q_categoria is null or p.category = q_categoria)
      -- Si la frase nombra un destino ("una reserva a Barcelona"), manda el destino y NO el radio:
      -- quien pregunta esta en Alemania y el plan ocurre a 1.500 km.
      and (q_dest_city is null or p.dest_city ilike q_dest_city)
      and (
        q_dest_city is not null or q_lon is null
        or st_dwithin(p.geo, st_point(q_lon, q_lat)::geography,
                      greatest(q_radio_km, p.radius_km) * 1000.0)
      )
      and (q_desde is null
           or tstzrange(p.starts_at, p.ends_at) &&
              tstzrange(q_desde::timestamptz, (coalesce(q_hasta, q_desde) + 1)::timestamptz))
  ),
  consulta as (select websearch_to_tsquery(q_idioma::regconfig, q_texto) as tq),
  vectorial as (
    select f.id, row_number() over (order by f.embedding::halfvec(2048) <=> q_vector) as puesto,
           1 - (f.embedding::halfvec(2048) <=> q_vector) as sim
    from filtrados f order by f.embedding::halfvec(2048) <=> q_vector limit q_limite * 2
  ),
  lexica as (
    select f.id, row_number() over (order by ts_rank(f.fts, c.tq) desc) as puesto
    from filtrados f, consulta c
    where c.tq is not null and f.fts @@ c.tq
    order by ts_rank(f.fts, c.tq) desc limit q_limite * 2
  ),
  fusion as (
    select coalesce(v.id, l.id) as id,
           coalesce(1.0 / (60 + v.puesto), 0) + coalesce(1.0 / (60 + l.puesto), 0) as rrf,
           coalesce(v.sim, 0) as sim
    from vectorial v full outer join lexica l on l.id = v.id
  )
  select f.id, f.owner_id, f.title, f.description, f.desc_lang, f.category,
         f.origin_city, f.dest_city, f.is_travel, f.venue, f.subject, f.tags,
         f.starts_at, f.ends_at, f.seats_open, f.radius_km,
         f.budget_band, f.pace, f.language_pref,
         f.km_calc, fu.sim, fu.rrf
  from fusion fu join filtrados f on f.id = fu.id
  order by fu.rrf desc
  limit q_limite;
$$;
