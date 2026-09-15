#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sembrar — lleva `db/seed.json` a Postgres, con sus embeddings.

    python3 scripts/sembrar.py              # borra y siembra todo (calcula ~460 embeddings)
    python3 scripts/sembrar.py --reanclar   # solo desplaza las fechas. Sin tocar embeddings

LO QUE HACE, Y POR QUE ASI:

* **Materializa el tiempo.** `seed.json` no tiene ni una fecha: tiene desplazamientos. Aqui se
  convierten en `timestamptz` contra `now()`, y el instante usado queda guardado en `seed_meta`.
  Ver ADR-0001 — es la defensa contra el riesgo numero 1 del proyecto.

* **Embebe al ESCRIBIR, nunca al consultar** (regla 5 del proyecto y control 1 de la seccion E de
  la propuesta): es el argumento de coste que se le vendio al cliente.

* **`input_type: "passage"`.** `nemotron-3-embed-1b` es asimetrico: lo que se guarda es un
  *passage* y lo que se busca es una *query*. Sin ese parametro el recall cae de 8/8 a 7/8 y el
  margen se hunde de +0.340 a +0.091 — **sin dar ningun error**. Es el fallo mas silencioso de
  todo el motor.

* **`--reanclar` no vuelve a embeber.** Las fechas se mueven; el texto no. Re-embeber cada dia
  seria pagar 460 llamadas para nada.
"""
import hashlib
import json
import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import subprocess
import sys
import time
import urllib.error
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = os.path.join(RAIZ, "db", "seed.json")

PROYECTO = "qbrgwphcpflbwhfqhffc"
API_SQL = f"https://api.supabase.com/v1/projects/{PROYECTO}/database/query"
NIM = "https://integrate.api.nvidia.com/v1/embeddings"
MODELO = "nvidia/nemotron-3-embed-1b"
LOTE_EMB = 24          # medido: 60 vectores en 4,8 s sin un fallo
LOTE_SQL = 15          # 15 filas x 2048 floats ~ 600 KB por peticion

# El WAF de Cloudflare que hay delante de la API de Supabase responde **403 con `error code:
# 1010`** al user-agent por defecto de urllib. No es un permiso: es la firma del cliente.
# Costo una tanda entera de embeddings descubrirlo (10-sep-2026).
AGENTE = "match-engine-sembrador/1.0"

# Cache de embeddings en disco, por hash del texto. Un fallo despues de embeber —como el 1010—
# no puede obligar a pagar otra vez 420 llamadas.
CACHE = os.path.join(os.environ.get("TMPDIR", "/tmp"), "match-engine-embeddings.json")


def secreto_gcp(nombre):
    return subprocess.run(
        ["gcloud", "secrets", "versions", "access", "latest", "--secret", nombre,
         "--project", "enerby-workstation"],
        capture_output=True, text=True, check=True).stdout.strip()


def pedir(url, cuerpo, cabeceras, intentos=4):
    cabeceras = {**cabeceras, "User-Agent": AGENTE}
    """POST con reintento exponencial: una tanda de 460 embeddings no puede morir por un 429."""
    datos = json.dumps(cuerpo).encode()
    for i in range(intentos):
        try:
            req = urllib.request.Request(url, data=datos, headers=cabeceras, method="POST")
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            cuerpo_err = e.read()[:300].decode(errors="replace")
            if e.code in (429, 500, 502, 503, 504) and i < intentos - 1:
                espera = 2 ** i
                print(f"    HTTP {e.code}, reintento en {espera}s", flush=True)
                time.sleep(espera)
                continue
            raise SystemExit(f"{url} -> HTTP {e.code}: {cuerpo_err}")
    raise SystemExit("agotados los reintentos")


def sql(consulta, token):
    return pedir(API_SQL, {"query": consulta},
                 {"Authorization": f"Bearer {token}", "Content-Type": "application/json"})


def lit(v):
    """Literal SQL. Nada de esto viene de un usuario: es un fichero versionado del repo."""
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, list):
        return "array[" + ",".join(lit(x) for x in v) + "]" if v else "'{}'"
    return "'" + str(v).replace("'", "''") + "'"


def texto_perfil(p):
    """Lo que se embebe de un perfil (§5): bio + intereses + artistas + equipos + cocinas.

    Va con nombre propio porque es una decision de producto: el nombre y la edad NO entran.
    La seccion J de la propuesta lo promete — "minimal personal data in embeddings: interests
    and stated preferences, not identifying text".
    """
    partes = [p["bio"], " ".join(p.get("interests") or [])]
    for campo in ("top_artists", "top_teams", "cuisines"):
        if p.get(campo):
            partes.append(" ".join(p[campo]))
    return " · ".join(x for x in partes if x)


def texto_plan(p):
    partes = [p["title"], p["description"], p.get("subject") or "",
              " ".join(p.get("tags") or []), p["category"]]
    # Los barrios por los que pasa la ruta entran en el embedding a proposito: «Ich suche eine
    # Mitfahrgelegenheit durch Kreuzberg» tiene que encontrar al conductor que NO sale de
    # Kreuzberg pero pasa por alli. Con solo origen y destino, ese conductor es invisible.
    if p.get("via"):
        partes.append("via " + " ".join(p["via"]))
    return " · ".join(x for x in partes if x)


def texto_intent(p):
    partes = [p["text"], p.get("subject") or "", " ".join(p.get("tags") or []),
              p.get("category") or ""]
    return " · ".join(x for x in partes if x)


def _cache_leer():
    try:
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def embeber(textos, clave):
    """Embebe en lotes, con cache en disco. `input_type: passage` NO es opcional — ver cabecera."""
    cache = _cache_leer()
    firma = lambda t: hashlib.sha256((MODELO + "\x00passage\x00" + t).encode()).hexdigest()
    pendientes = [t for t in dict.fromkeys(textos) if firma(t) not in cache]
    if pendientes:
        cab = {"Authorization": f"Bearer {clave}", "Content-Type": "application/json"}
        hechos = 0
        for i in range(0, len(pendientes), LOTE_EMB):
            trozo = pendientes[i:i + LOTE_EMB]
            r = pedir(NIM, {"model": MODELO, "input": trozo, "input_type": "passage",
                            "truncate": "END", "encoding_format": "float"}, cab)
            for d in sorted(r["data"], key=lambda d: d["index"]):
                cache[firma(trozo[d["index"]])] = d["embedding"]
            hechos += len(trozo)
            print(f"    {hechos}/{len(pendientes)} nuevos", flush=True)
        with open(CACHE, "w", encoding="utf-8") as f:
            json.dump(cache, f)
    else:
        print(f"    {len(textos)} en cache, ninguna llamada", flush=True)
    return [cache[firma(t)] for t in textos]


def vec(v):
    return "'[" + ",".join(f"{x:.6f}" for x in v) + "]'"


def punto(g):
    return f"'SRID=4326;POINT({g[0]} {g[1]})'"


def linea(puntos):
    """La ruta como `geography(linestring)`. `null` cuando el plan no se conduce (un vuelo)."""
    if not puntos or len(puntos) < 2:
        return "null"
    pares = ",".join(f"{p[0]} {p[1]}" for p in puntos)
    return f"'SRID=4326;LINESTRING({pares})'"


def fecha_de(hoy, dia_offset, recurrente, generado):
    """La fecha real de un plan a partir de su desplazamiento, CONSERVANDO EL DIA DE LA SEMANA.

    Un `dia_offset` se eligio mirando el calendario del dia en que se genero el seed: «este finde»
    desde un jueves son +2 y +3. Desplazar por dias enteros desde OTRO dia mueve el finde a jueves y
    viernes, y «Techno-Festival am Wochenende» devolvia cero planes (aceptacion v10, bloqueante B2).
      * offset 0 y 1 significan «hoy» y «ma~nana»: se respetan tal cual;
      * un offset mayor conserva el dia de la semana que tenia al generarse, en la fecha mas cercana
        (±3 dias) y nunca antes de pasado ma~nana;
      * un viaje de diario («weekdays») que caiga en sabado o domingo pasa al lunes.
    """
    if dia_offset <= 1:
        d = hoy + timedelta(days=dia_offset)
    else:
        objetivo = hoy + timedelta(days=dia_offset)
        dia_semana = (generado + timedelta(days=dia_offset)).weekday()
        k = min((k for k in range(-3, 4) if (objetivo + timedelta(days=k)).weekday() == dia_semana),
                key=abs)
        d = objetivo + timedelta(days=k)
        if d < hoy + timedelta(days=2):
            d += timedelta(days=7)
    if recurrente == "weekdays" and d.weekday() >= 5:
        d += timedelta(days=7 - d.weekday())
    return d


def generado_del_seed(meta):
    """El dia en que se genero el seed: la semilla ES esa fecha (20260910 → 2026-09-10)."""
    return datetime.strptime(str(meta["semilla"]), "%Y%m%d").date()


def hoy_berlin():
    return datetime.now(ZoneInfo("Europe/Berlin")).date()


def rango(d):
    """Un tramo de disponibilidad, materializado contra `now()` como el resto del tiempo."""
    return (f"daterange((now() + interval '{d['desde_offset']} days')::date, "
            f"(now() + interval '{d['hasta_offset']} days')::date, '[]')")


def main():
    reanclar = "--reanclar" in sys.argv
    token = os.environ.get("SUPABASE_ACCESS_TOKEN") or secreto_gcp("devenv-supabase")

    if reanclar:
        # Desplaza TODAS las fechas por DIAS ENTEROS entre hoy y el ancla. Las distancias
        # relativas se conservan: «manana» sigue siendo manana el dia 21, sin re-embeber nada.
        #
        # DOS FALLOS PAGADOS EL 15-SEP-2026, al re-anclar por primera vez de verdad:
        #   * el delta era `now() - anclado`, con horas y minutos: un viaje de las 08:10 paso a
        #     salir a las 03:43. El desplazamiento tiene que ser en dias enteros.
        #   * `interval::int` no existe en Postgres (42846) y el UPDATE de `availability`
        #     reventaba DESPUES de haber movido planes e intents, y ANTES de actualizar el ancla:
        #     un segundo intento habria movido los planes otra vez. Ahora es una sola transaccion.
        r = sql("""
            begin;
            with d as (select (now()::date - anclado::date) as dias from seed_meta where id = 1)
            update plans set starts_at = starts_at + make_interval(days => (select dias from d)),
                             ends_at   = ends_at   + make_interval(days => (select dias from d));
            with d as (select (now()::date - anclado::date) as dias from seed_meta where id = 1)
            update intents set window_start = window_start + (select dias from d),
                               window_end   = window_end   + (select dias from d)
            where standing = false;
            with d as (select (now()::date - anclado::date) as dias from seed_meta where id = 1)
            update profiles set availability = (
              select coalesce(array_agg(daterange(lower(x) + (select dias from d),
                                                  upper(x) + (select dias from d), '[)')),
                              '{}'::daterange[])
              from unnest(availability) x);
            update seed_meta set anclado = now() where id = 1;
            commit;
            select (select count(*) from plans where ends_at >= now()) as futuros,
                   (select anclado from seed_meta where id = 1) as anclado;""", token)
        print("re-anclado:", json.dumps(r[0] if isinstance(r, list) and r else r, ensure_ascii=False))
        # Y los planes del seed, a su fecha por DIA DE LA SEMANA (ver `fecha_de`). El desplazamiento
        # por dias enteros de arriba vale para intents y disponibilidad; para los planes, no.
        with open(SEED, encoding="utf-8") as f:
            seed = json.load(f)
        hoy = hoy_berlin(); gen = generado_del_seed(seed["meta"])
        valores = ",".join(
            f"('{p['id']}'::uuid, date '{fecha_de(hoy, p['dia_offset'], p.get('recurrente'), gen).isoformat()}')"
            for p in seed["planes"])
        r2 = sql(f"""
            update plans p
               set starts_at = (v.d + (p.starts_at at time zone 'Europe/Berlin')::time) at time zone 'Europe/Berlin',
                   ends_at   = (v.d + (p.starts_at at time zone 'Europe/Berlin')::time) at time zone 'Europe/Berlin'
                               + (p.ends_at - p.starts_at)
              from (values {valores}) as v(id, d)
             where p.id = v.id;
            select count(*) filter (where extract(isodow from starts_at at time zone 'Europe/Berlin') in (6, 7)) as en_finde,
                   count(*) as planes from plans;""", token)
        print("planes por dia de la semana:", json.dumps(r2[0] if isinstance(r2, list) and r2 else r2, ensure_ascii=False))
        return

    with open(SEED, encoding="utf-8") as f:
        seed = json.load(f)
    perfiles, planes, intents = seed["perfiles"], seed["planes"], seed["intents"]
    print(f"seed: {len(perfiles)} perfiles · {len(planes)} planes · {len(intents)} intents "
          f"· {len(seed.get('valoraciones') or [])} valoraciones")

    clave_nim = os.environ.get("NVIDIA_API_KEY") or secreto_gcp("nvidia-nim")
    print("  embeddings de perfiles…")
    emb_perf = embeber([texto_perfil(p) for p in perfiles], clave_nim)
    print("  embeddings de planes…")
    emb_plan = embeber([texto_plan(p) for p in planes], clave_nim)
    emb_int = []
    if intents:
        print("  embeddings de intents…")
        emb_int = embeber([texto_intent(p) for p in intents], clave_nim)

    print("  vaciando…")
    sql("truncate valoraciones, intereses, intents, plans, profiles restart identity cascade", token)

    # El ancla se fija UNA vez, antes de insertar, para que todas las filas cuelguen del mismo
    # instante. Si se tomara `now()` por fila, dos filas de la misma tanda quedarian a distinta
    # distancia relativa y el mundo dejaria de ser reproducible.
    sql("insert into seed_meta (id, anclado, semilla, filas) values (1, now(), "
        f"{seed['meta']['semilla']}, '{json.dumps({k: len(v) for k, v in ((chr(112)+'erfiles', perfiles), ('planes', planes), ('intents', intents))})}'::jsonb) "
        "on conflict (id) do update set anclado = excluded.anclado, semilla = excluded.semilla, "
        "filas = excluded.filas", token)

    print("  insertando perfiles…")
    for i in range(0, len(perfiles), LOTE_SQL):
        filas = []
        for p, e in zip(perfiles[i:i + LOTE_SQL], emb_perf[i:i + LOTE_SQL]):
            # `availability` se materializa contra `now()`, igual que el resto del tiempo.
            disp = ("array[" + ",".join(rango(d) for d in p["disponible"]) + "]") \
                if p["disponible"] else "'{}'::daterange[]"
            filas.append(
                f"({lit(p['id'])}::uuid, {lit(p['display_name'])}, {lit(p['age'])}, {lit(p['city'])}, "
                f"{punto(p['geo'])}, {lit(p['languages'])}::text[], {lit(p['bio_lang'])}, {lit(p['bio'])}, "
                f"{lit(p['interests'])}::text[], {lit(p.get('top_artists'))}::text[], "
                f"{lit(p.get('top_teams'))}::text[], {lit(p.get('cuisines'))}::text[], "
                f"{lit(p.get('pace'))}, {lit(p.get('budget_band'))}, {lit(p.get('group_pref'))}, "
                f"{disp}, {lit(p.get('verification', 0))}, {lit(p.get('completed_plans', 0))}, "
                f"{lit(p.get('reports', 0))}, "
                f"{lit(bool(p.get('conduce')))}, {lit(p.get('coche'))}, "
                f"{lit(p.get('plazas_coche'))}, {lit(p.get('desde_offset'))}, "
                f"{lit(p.get('nota'))}, {lit(p.get('notas_conteo', 0))}, {vec(e)}::vector, "
                f"to_tsvector({lit('german' if p['bio_lang'] == 'de' else 'english')}, {lit(texto_perfil(p))}))")
        sql("insert into profiles (id, display_name, age, city, geo, languages, bio_lang, bio, "
            "interests, top_artists, top_teams, cuisines, pace, budget_band, group_pref, "
            "availability, verification, completed_plans, reports, conduce, coche, "
            "plazas_coche, desde_offset, nota, notas_conteo, embedding, fts) values "
            + ",".join(filas), token)
        print(f"    {min(i + LOTE_SQL, len(perfiles))}/{len(perfiles)}", flush=True)

    print("  insertando planes…")
    for i in range(0, len(planes), LOTE_SQL):
        filas = []
        for p, e in zip(planes[i:i + LOTE_SQL], emb_plan[i:i + LOTE_SQL]):
            # EN HORA DE BERLIN. Antes era `date + time` a secas, que Postgres interpreta en la zona
            # de la sesion (UTC): un viaje sembrado «08:00» salia a las 10:00 en la pantalla en cuanto
            # esta empezo a pintar la hora de Berlin (programa de UX, 15-sep-2026). La demo es
            # Alemania: la hora que escribe el conductor es la de Alemania.
            dia = fecha_de(hoy_berlin(), p["dia_offset"], p.get("recurrente"), generado_del_seed(seed["meta"]))
            inicio = f"(date '{dia.isoformat()}' + time '{p['hora']}') at time zone 'Europe/Berlin'"
            filas.append(
                f"({lit(p['id'])}::uuid, {lit(p['owner_id'])}::uuid, {lit(p['title'])}, "
                f"{lit(p['description'])}, {lit(p['desc_lang'])}, {lit(p['category'])}, "
                f"{lit(p['origin_city'])}, {lit(p['dest_city'])}, {lit(p['is_travel'])}, "
                f"{lit(p.get('venue'))}, {punto(p['geo'])}, {punto(p['origin_geo'])}, "
                f"{lit(p.get('date_precision', 'exact'))}, {inicio}, "
                f"{inicio} + interval '{p.get('duracion_h', 3)} hours', "
                f"{lit(p.get('radius_km', 40))}, {lit(p.get('seats_open', 1))}, "
                f"{lit(p.get('subject'))}, {lit(p['tags'])}::text[], {lit(p.get('budget_band'))}, "
                f"{lit(p.get('pace'))}, {lit(p.get('language_pref'))}::text[], "
                f"{linea(p.get('ruta'))}, {lit(p.get('via'))}::text[], "
                f"{lit(p.get('distancia_km'))}, {lit(p.get('precio_por_km'))}, "
                f"{lit(p.get('recurrente'))}, {vec(e)}::vector, "
                f"to_tsvector({lit('german' if p['desc_lang'] == 'de' else 'english')}, {lit(texto_plan(p))}))")
        sql("insert into plans (id, owner_id, title, description, desc_lang, category, origin_city, "
            "dest_city, is_travel, venue, geo, origin_geo, date_precision, starts_at, ends_at, "
            "radius_km, seats_open, subject, tags, budget_band, pace, language_pref, "
            "ruta, via, distancia_km, precio_por_km, recurrente, embedding, fts) "
            "values " + ",".join(filas), token)
        print(f"    {min(i + LOTE_SQL, len(planes))}/{len(planes)}", flush=True)

    if intents:
        print("  insertando intents…")
        for i in range(0, len(intents), LOTE_SQL):
            filas = []
            for p, e in zip(intents[i:i + LOTE_SQL], emb_int[i:i + LOTE_SQL]):
                if p.get("standing") or p.get("ventana_desde_offset") is None:
                    ini, fin = "null", "null"
                else:
                    ini = f"(now() + interval '{p['ventana_desde_offset']} days')::date"
                    fin = f"(now() + interval '{p['ventana_hasta_offset']} days')::date"
                filas.append(
                    f"({lit(p['id'])}::uuid, {lit(p['owner_id'])}::uuid, {lit(p['text'])}, "
                    f"{lit(p['text_lang'])}, {lit(p.get('category'))}, {lit(p.get('subject'))}, "
                    f"{lit(p['city'])}, {punto(p['geo'])}, {lit(p.get('radius_km', 40))}, "
                    f"{ini}, {fin}, {lit(bool(p.get('standing')))}, {lit(p['tags'])}::text[], "
                    f"{vec(e)}::vector, to_tsvector("
                    f"{lit('german' if p['text_lang'] == 'de' else 'english')}, {lit(texto_intent(p))}))")
            sql("insert into intents (id, owner_id, text, text_lang, category, subject, city, geo, "
                "radius_km, window_start, window_end, standing, tags, embedding, fts) values "
                + ",".join(filas), token)

    valoraciones = seed.get("valoraciones") or []
    if valoraciones:
        print("  insertando valoraciones…")
        # Sin embedding: una rese~na no se busca por semantica, se LEE en la ficha del conductor.
        # Embeber 1.200 frases cortas y repetidas seria pagar por ruido.
        for i in range(0, len(valoraciones), 60):
            filas = []
            for v in valoraciones[i:i + 60]:
                filas.append(
                    f"({lit(v['id'])}::uuid, {lit(v['conductor_id'])}::uuid, "
                    f"{lit(v['autor_id'])}::uuid, {lit(v['estrellas'])}, {lit(v.get('texto'))}, "
                    f"{lit(v.get('texto_lang'))}, {lit(v['dia_offset'])}, "
                    f"now() + interval '{v['dia_offset']} days')")
            sql("insert into valoraciones (id, conductor_id, autor_id, estrellas, texto, "
                "texto_lang, dia_offset, creado) values " + ",".join(filas), token)
        print(f"    {len(valoraciones)}/{len(valoraciones)}", flush=True)

    r = sql("select (select count(*) from profiles) perfiles, (select count(*) from plans) planes, "
            "(select count(*) from intents) intents, "
            "(select count(*) from valoraciones) valoraciones, "
            "(select count(*) from plans where ruta is not null) con_ruta, "
            "(select anclado from seed_meta where id=1) anclado", token)
    print("sembrado:", json.dumps(r[0] if isinstance(r, list) and r else r, ensure_ascii=False))


if __name__ == "__main__":
    main()
