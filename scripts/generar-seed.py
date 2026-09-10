#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""generar-seed — construye `db/seed.json`, el mundo entero de la demo.

    python3 scripts/generar-seed.py

DOS REGLAS GOBIERNAN ESTE FICHERO, y las dos vienen del brief:

1. **NI UNA FECHA.** El §12 llama al seed caducado «el riesgo numero 1 de todo el proyecto»: si
   «Bayern gegen Dortmund morgen» se guarda como 2026-09-11, el dia 18 la frase 4 devuelve vacio
   delante del cliente. Aqui el tiempo son SIEMPRE desplazamientos (`dia_offset`, `hora`,
   `duracion_h`) y `scripts/sembrar.py` los materializa contra `now()`. Ver ADR-0001.

2. **CERO ALEATORIEDAD EN EJECUCION** (§9). Este script es determinista: una semilla fija, un
   `random.Random` propio (nunca el global), y `uuid5` para los ids. Ejecutarlo dos veces produce
   ficheros identicos byte a byte — comprobado por `just seed-determinista`.

El mundo tiene dos mitades y se distinguen en el campo `origen` de cada fila:

  * **los plantados** (`db/plantados/*.json`) — escritos a mano, uno por cada frase de Helder.
    Son el criterio de aceptacion: aqui viven el par reciproco 6↔1 y los cuatro near-miss.
  * **el relleno** — generado por combinatoria para que el mundo se vea denso. Sin el, cada
    busqueda devolveria solo las filas plantadas y la demo se veria de juguete.
"""
import json
import os
import random
import unicodedata
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalogos as C

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLANTADOS = os.path.join(RAIZ, "db", "plantados")
SALIDA = os.path.join(RAIZ, "db", "seed.json")

SEMILLA = 20260910
ESPACIO = uuid.UUID("a10c0de0-0000-4000-8000-000000000000")  # "alonno" en hex valido

OBJETIVO_PERFILES = 240
OBJETIVO_PLANES = 180

R = random.Random(SEMILLA)


def ident(clave):
    """Id estable derivado de la clave: el mismo mundo en cada ejecucion y en cada maquina."""
    return str(uuid.uuid5(ESPACIO, clave))


def sin_tildes(t):
    """«Neukölln» y «Neukolln» son el mismo barrio.

    Los escenarios los escriben personas (y agentes) que teclean el nombre correcto, con umlaut;
    los catalogos estan en ASCII para que el fichero sea portable. Comparar sin diacriticos evita
    que un barrio bien escrito acabe sustituido en silencio por otro al azar — que es peor que un
    error, porque mueve un plan de sitio sin avisar.
    """
    if not t:
        return t
    return "".join(c for c in unicodedata.normalize("NFD", str(t))
                   if unicodedata.category(c) != "Mn").lower().replace("-", " ").strip()


def geo(ciudad, barrio=None):
    """(lon, lat) del barrio, con jitter determinista de ~±400 m.

    El jitter no es adorno: sin el, veinte perfiles de Kreuzberg comparten coordenada exacta y
    la componente de proximidad deja de discriminar entre ellos.
    """
    barrios = C.CIUDADES.get(ciudad)
    if not barrios:
        indice = {sin_tildes(c): c for c in C.CIUDADES}
        ciudad_real = indice.get(sin_tildes(ciudad))
        if not ciudad_real:
            raise SystemExit(f"ciudad desconocida en los catalogos: {ciudad!r} — anadela a scripts/catalogos.py")
        barrios = C.CIUDADES[ciudad_real]
    if barrio not in barrios:
        indice = {sin_tildes(b): b for b in barrios}
        barrio = indice.get(sin_tildes(barrio)) or R.choice(sorted(barrios))
    lat, lon = barrios[barrio]
    return [round(lon + R.uniform(-0.005, 0.005), 6), round(lat + R.uniform(-0.004, 0.004), 6)]


def muestra(lista, n):
    return R.sample(sorted(lista), min(n, len(lista)))


# ── el relleno ────────────────────────────────────────────────────────────────────────────

def perfil_relleno(n):
    ciudad = C.CIUDADES_CLIENTE[n % len(C.CIUDADES_CLIENTE)]
    barrio = R.choice(sorted(C.CIUDADES[ciudad]))
    # ~55% aleman / ~45% ingles (§8): el corpus tiene que estar mezclado a proposito, o el
    # matching cross-lingua no tiene nada que demostrar.
    lang = "de" if R.random() < 0.55 else "en"
    intereses = muestra(C.INTERESES, R.randint(3, 6))
    artistas = muestra(C.ARTISTAS, R.randint(0, 3))
    plantilla = R.choice(C.BIO_DE if lang == "de" else C.BIO_EN)
    bio = plantilla.format(
        c=ciudad,
        i=", ".join(intereses[:3]).replace("_", " "),
        a=artistas[0] if artistas else R.choice(C.GENEROS).replace("_", " "),
    )
    idiomas = ["de", "en"] if R.random() < 0.45 else [lang]
    disponible = []
    # Entre uno y tres tramos libres dentro de los proximos 45 dias.
    for _ in range(R.randint(1, 3)):
        d = R.randint(0, 40)
        disponible.append({"desde_offset": d, "hasta_offset": d + R.randint(1, 4)})
    return {
        "clave": f"relleno-perfil-{n:03d}",
        "origen": "relleno",
        "id": ident(f"perfil/relleno-{n:03d}"),
        "display_name": C.NOMBRES[n % len(C.NOMBRES)],
        "age": R.randint(21, 48),
        "city": ciudad,
        "barrio": barrio,
        "geo": geo(ciudad, barrio),
        "languages": idiomas,
        "bio_lang": lang,
        "bio": bio,
        "interests": intereses,
        "top_artists": artistas,
        "top_teams": muestra(C.EQUIPOS, R.randint(0, 2)),
        "cuisines": muestra(C.COCINAS, R.randint(1, 3)),
        "pace": R.choice(C.PACE),
        "budget_band": R.choice(C.BUDGET),
        "group_pref": R.choice(C.GRUPO),
        "disponible": disponible,
        "verification": R.choice([0, 1, 1, 2, 2, 3]),
        "completed_plans": R.randint(0, 22),
        "reports": 0 if R.random() < 0.96 else 1,
    }


def plan_relleno(n, duenno):
    cat = R.choice(C.CATEGORIAS)
    origen_ciudad = duenno["city"]
    viaje = cat in ("weekend_trip", "holiday") and R.random() < 0.65
    destino = R.choice(["Barcelona", "Lissabon", "Wien", "Amsterdam", "Garmisch", "Rugen"]) if viaje \
        else origen_ciudad
    barrio_destino = R.choice(sorted(C.CIUDADES[destino]))
    lang = "de" if R.random() < 0.55 else "en"
    titulos = C.TITULO_DE if lang == "de" else C.TITULO_EN
    if cat == "concert":
        sujeto = R.choice(C.ARTISTAS)
    elif cat == "football":
        sujeto = R.choice(C.EQUIPOS)
    elif cat == "restaurant":
        sujeto = R.choice(C.COCINAS)
    else:
        sujeto = destino if viaje else R.choice(C.INTERESES)
    titulo = R.choice(titulos[cat]).format(a=sujeto, c=origen_ciudad, d=destino)
    etiquetas = [cat] + muestra(C.INTERESES, 2)
    if cat == "concert":
        etiquetas.append(R.choice(C.GENEROS))
    dia = R.randint(0, 42)
    return {
        "clave": f"relleno-plan-{n:03d}",
        "origen": "relleno",
        "id": ident(f"plan/relleno-{n:03d}"),
        "owner_id": duenno["id"],
        "title": titulo,
        "description": R.choice(C.DESC_DE if lang == "de" else C.DESC_EN),
        "desc_lang": lang,
        "category": cat,
        "origin_city": origen_ciudad,
        "dest_city": destino,
        "is_travel": destino != origen_ciudad,
        "venue": None,
        "barrio": barrio_destino,
        "geo": geo(destino, barrio_destino),
        "origin_geo": duenno["geo"],
        "date_precision": R.choice(["exact", "exact", "weekend", "flexible"]),
        "dia_offset": dia,
        "hora": R.choice(["10:00", "15:00", "19:00", "20:00", "21:00"]),
        "duracion_h": R.choice([3, 4, 6, 24, 48]) if not viaje else R.choice([48, 72, 120]),
        "radius_km": R.choice([25, 40, 40, 60]),
        "seats_open": R.choice([1, 1, 1, 2, 3]),
        "subject": sujeto,
        "tags": sorted(set(etiquetas)),
        "budget_band": R.choice(C.BUDGET),
        "pace": R.choice(C.PACE),
        "language_pref": ["de", "en"] if R.random() < 0.5 else [lang],
    }


# ── los plantados ─────────────────────────────────────────────────────────────────────────

def cargar_plantados():
    perfiles, planes, intents, escenarios = [], [], [], []
    if not os.path.isdir(PLANTADOS):
        return perfiles, planes, intents, escenarios
    for nombre in sorted(os.listdir(PLANTADOS)):
        if not nombre.endswith(".json"):
            continue
        ruta = os.path.join(PLANTADOS, nombre)
        with open(ruta, encoding="utf-8") as f:
            d = json.load(f)
        esc = d.get("escenario") or nombre[:-5]
        escenarios.append({
            "escenario": esc,
            "frase_de_helder": d.get("frase_de_helder"),
            "que_debe_devolver": d.get("que_debe_devolver"),
        })
        por_clave = {}
        for p in d.get("perfiles", []):
            clave = f"{esc}/{p['clave']}"
            fila = dict(p)
            fila.update({
                "clave": clave,
                "origen": f"{esc}/{p.get('rol', 'sin-rol')}",
                "id": ident(f"perfil/{clave}"),
                "geo": geo(p["city"], p.get("barrio")),
            })
            fila.setdefault("disponible", [])
            for campo, defecto in (("top_artists", []), ("top_teams", []), ("cuisines", []),
                                   ("verification", 1), ("completed_plans", 3), ("reports", 0)):
                fila.setdefault(campo, defecto)
            por_clave[p["clave"]] = fila["id"]
            perfiles.append(fila)
        for p in d.get("planes", []):
            clave = f"{esc}/{p['clave']}"
            duenno = por_clave.get(p.get("owner"))
            if duenno is None:
                raise SystemExit(f"{nombre}: el plan {p['clave']!r} apunta a un perfil que no declara: {p.get('owner')!r}")
            destino = p.get("dest_city", p["origin_city"])
            fila = dict(p)
            fila.update({
                "clave": clave,
                "origen": f"{esc}/{p.get('rol', 'sin-rol')}",
                "id": ident(f"plan/{clave}"),
                "owner_id": duenno,
                "dest_city": destino,
                "is_travel": destino != p["origin_city"],
                "geo": geo(destino, p.get("barrio")),
                "origin_geo": geo(p["origin_city"]),
            })
            fila.setdefault("venue", None)
            fila.setdefault("date_precision", "exact")
            fila.setdefault("radius_km", 40)
            fila.setdefault("seats_open", 1)
            planes.append(fila)
        for p in d.get("intents", []):
            clave = f"{esc}/{p['clave']}"
            duenno = por_clave.get(p.get("owner"))
            if duenno is None:
                raise SystemExit(f"{nombre}: el intent {p['clave']!r} apunta a un perfil que no declara: {p.get('owner')!r}")
            fila = dict(p)
            fila.update({
                "clave": clave,
                "origen": f"{esc}/{p.get('rol', 'sin-rol')}",
                "id": ident(f"intent/{clave}"),
                "owner_id": duenno,
                "geo": geo(p["city"], p.get("barrio")),
            })
            fila.setdefault("standing", False)
            fila.setdefault("radius_km", 40)
            intents.append(fila)
    return perfiles, planes, intents, escenarios


def main():
    perfiles, planes, intents, escenarios = cargar_plantados()
    plantados_perfiles, plantados_planes = len(perfiles), len(planes)

    n = 0
    while len(perfiles) < OBJETIVO_PERFILES:
        perfiles.append(perfil_relleno(n))
        n += 1
    # Los planes de relleno cuelgan de perfiles de relleno: los plantados tienen su due~no
    # escrito a mano y no se les a~naden planes por la espalda.
    candidatos = [p for p in perfiles if p["origen"] == "relleno"]
    m = 0
    while len(planes) < OBJETIVO_PLANES:
        planes.append(plan_relleno(m, candidatos[m % len(candidatos)]))
        m += 1

    salida = {
        "meta": {
            "semilla": SEMILLA,
            "objetivo_perfiles": OBJETIVO_PERFILES,
            "objetivo_planes": OBJETIVO_PLANES,
            "plantados": {"perfiles": plantados_perfiles, "planes": plantados_planes,
                          "intents": len(intents), "escenarios": len(escenarios)},
            "aviso": ("Ni una fecha absoluta: el tiempo son desplazamientos que sembrar.py "
                      "materializa contra now(). Ver docs/adr/0001-como-ruedan-las-fechas.md"),
        },
        "escenarios": escenarios,
        "perfiles": perfiles,
        "planes": planes,
        "intents": intents,
    }
    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")

    print(f"seed escrito: {os.path.relpath(SALIDA, RAIZ)}")
    print(f"  perfiles {len(perfiles):>4}  ({plantados_perfiles} plantados)")
    print(f"  planes   {len(planes):>4}  ({plantados_planes} plantados)")
    print(f"  intents  {len(intents):>4}")
    print(f"  escenarios plantados: {len(escenarios)}")

    # Las 10 frases, aparte y en pequeno: la UI las ense~na CLICABLES (regla 4) y no puede
    # cargar un seed de 450 KB para leer diez lineas. Salen de los mismos ficheros plantados,
    # asi que no pueden divergir de lo que se sembro.
    ruta_frases = os.path.join(RAIZ, "db", "frases.json")
    with open(ruta_frases, "w", encoding="utf-8") as f:
        json.dump(escenarios, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"  frases de Helder: {os.path.relpath(ruta_frases, RAIZ)}")


if __name__ == "__main__":
    main()
