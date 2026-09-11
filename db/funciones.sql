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

-- `create or replace` NO basta cuando cambia el tipo de retorno: Postgres responde
-- `42P13 cannot change return type of existing function`. Y aqui cambia cada vez que el motor
-- aprende a devolver un dato nuevo —paso el 11-sep-2026 al a~nadir la ruta del viaje—, asi que
-- el fichero empieza tirandolas. Sigue siendo idempotente: `if exists` no falla si no estan.
drop function if exists buscar_personas(halfvec, text, text, double precision, double precision, int, date, date, boolean, uuid, int);
drop function if exists buscar_planes(halfvec, text, text, double precision, double precision, int, date, date, text, text, uuid, int);

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
  -- La reputacion viaja con la persona. La lista «conductores que encajan contigo» sin nota ni
  -- coche es una lista de nombres, y nadie se sube al coche de un nombre.
  conduce boolean, coche text, plazas_coche int, nota numeric, notas_conteo int, desde_offset int,
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
         f.conduce, f.coche, f.plazas_coche, f.nota, f.notas_conteo, f.desde_offset,
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
  via text[], distancia_km numeric, precio_por_km numeric, recurrente text,
  -- El conductor viaja CON el viaje. Sin esto la tarjeta de un resultado no puede ense~nar
  -- quien conduce, y «driver rating & review» del docx obligaria a una segunda consulta por
  -- fila —el N+1 clasico— para pintar una estrella.
  conductor text, conductor_coche text, conductor_nota numeric, conductor_notas int,
  conductor_verificado int, conductor_viajes int,
  -- La geometria sale como GeoJSON para que el mapa la pinte sin una segunda consulta. Son tres
  -- o cuatro puntos por viaje: no justifica un endpoint aparte, y un mapa que pide los datos por
  -- su cuenta es un mapa que puede quedarse en blanco mientras la lista ya esta puesta.
  ruta_geojson text, origen_geojson text, destino_geojson text,
  km double precision, km_ruta double precision, similitud double precision, rrf double precision
)
language sql stable as $$
  with filtrados as (
    select p.*,
           -- A que distancia esta quien pregunta de ESTE viaje. Para un concierto es la
           -- distancia al sitio; para un coche es la distancia A LA RUTA, que casi siempre es
           -- menor: el conductor pasa cerca de ti sin salir ni llegar donde tu estas.
           case when q_lon is null then null
                else least(
                  st_distance(p.geo, st_point(q_lon, q_lat)::geography),
                  coalesce(st_distance(p.ruta, st_point(q_lon, q_lat)::geography), 1e12)
                ) / 1000.0 end as km_calc,
           case when q_lon is null or p.ruta is null then null
                else st_distance(p.ruta, st_point(q_lon, q_lat)::geography) / 1000.0
           end as km_ruta_calc
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
        -- EL REQUISITO CENTRAL DE `pickando.docx`: «Passenger: tracking within 1-2 km of all
        -- drivers driving on the same route». Un pasajero de Wannsee no esta ni en Berlin-Mitte
        -- ni en Potsdam, pero el conductor le pasa a 800 m. Con dos puntos ese pasajero NO
        -- EXISTE; con la polilinea, aparece. Es la diferencia entre «cerca de mi» y «va por
        -- donde yo voy», y es la unica consulta que distingue un coche compartido de un
        -- tablon de anuncios.
        or st_dwithin(p.ruta, st_point(q_lon, q_lat)::geography,
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
         f.via, f.distancia_km, f.precio_por_km, f.recurrente,
         d.display_name, d.coche, d.nota, d.notas_conteo, d.verification, d.completed_plans,
         st_asgeojson(f.ruta), st_asgeojson(f.origin_geo), st_asgeojson(f.geo),
         f.km_calc, f.km_ruta_calc, fu.sim, fu.rrf
  from fusion fu
  join filtrados f on f.id = fu.id
  left join profiles d on d.id = f.owner_id
  order by fu.rrf desc
  limit q_limite;
$$;


-- ── La geometria de un viaje, en GeoJSON ────────────────────────────────────────────────
--
-- PostgREST devuelve una columna `geography` como WKB HEXADECIMAL: una cadena de 300 caracteres
-- que el navegador no sabe dibujar. La conversion la hace Postgres, que ya tiene la funcion.
--
-- Va como funcion y no como columna calculada porque la ficha de un viaje la pide UNA vez, y
-- meterla en el `select=*` de todas las consultas de planes seria pagarla siempre.
create or replace function geometria_de_plan(p_id uuid)
returns json language sql stable as $$
  select json_build_object(
    'ruta',    case when p.ruta is null then null else st_asgeojson(p.ruta)::json end,
    'origen',  st_asgeojson(p.origin_geo)::json,
    'destino', st_asgeojson(p.geo)::json,
    'radio_km', p.radius_km)
  from plans p where p.id = p_id;
$$;
