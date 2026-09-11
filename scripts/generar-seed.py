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
# Trayectos de diario. Son los que el docx pone PRIMERO y los que la demo no tenia.
OBJETIVO_TRAYECTOS = 120

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


# ── coche compartido: la flota, las rutas y la reputacion ─────────────────────────────────
#
# Se a~nade DESPUES de construir perfiles y planes, y sobre los dos mundos a la vez (plantados y
# relleno), porque un conductor no es otra clase de persona: es la misma persona con coche. El
# due~no del plan «Bayern-Dortmund» conduce hasta el estadio y le sobran dos plazas — y eso es,
# a la vez, el resultado de la frase 4 de Helder y un viaje del docx.

import math


def _haversine(a, b):
    """km entre dos [lon, lat]. Suficiente para una tarifa: el error es < 0,5 % a esta escala."""
    (lon1, lat1), (lon2, lat2) = a, b
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def trazar(origen, vias, destino):
    """La ruta como lista de puntos, y su longitud.

    No es una ruta de carreteras: es la polilinea por la que pasa el conductor. Basta para lo
    que el docx pide —«all drivers driving on the same route»—, porque lo que se pregunta es
    `ST_DWithin(ruta, pasajero, 2000)`, y para eso lo que importa es por donde pasa, no por que
    calle. Calcular rutas reales exigiria un servicio de routing y no cambia la demostracion.
    """
    puntos = [origen] + list(vias) + [destino]
    km = sum(_haversine(puntos[i], puntos[i + 1]) for i in range(len(puntos) - 1))
    # Las calles no son rectas: +18 % es el factor de rodeo urbano habitual.
    return puntos, round(km * 1.18, 1)


def precio_km():
    """EUR/km dentro del rango configurable del docx. Reparto de gastos, no tarifa de taxi."""
    return round(R.uniform(C.PRECIO_KM_MIN, C.PRECIO_KM_MAX), 2)


def dar_coche(perfil, i):
    """Convierte a un perfil en conductor. Determinista: el mismo perfil, el mismo coche."""
    perfil["conduce"] = True
    perfil["coche"] = C.COCHES[i % len(C.COCHES)]
    perfil["plazas_coche"] = R.choice([2, 3, 3, 4])
    perfil["desde_offset"] = R.randint(2, 40)          # meses en la plataforma
    # La nota sale de las rese~nas, no al reves: se genera despues y se recalcula.
    perfil.setdefault("nota", None)
    perfil.setdefault("notas_conteo", 0)
    return perfil


def resenas_de(conductor, autores, n):
    """n rese~nas escritas por personas distintas, con su nota.

    La distribucion esta sesgada a 5 a proposito y NO por optimismo: en las plataformas de
    transporte la media real vive entre 4,6 y 4,9, y un mundo con notas repartidas de 1 a 5 se
    ve inventado. Lo que discrimina no es la nota, es CUANTAS hay — por eso `notas_conteo`
    tambien varia mucho.
    """
    filas = []
    for k in range(n):
        autor = autores[(int(conductor["id"][:8], 16) + k * 7919) % len(autores)]
        if autor["id"] == conductor["id"]:
            continue
        estrellas = R.choices([5, 4, 3], weights=[76, 20, 4])[0]
        lang = "de" if R.random() < 0.55 else "en"
        filas.append({
            "clave": f"{conductor['clave']}/resena-{k:02d}",
            "id": ident(f"resena/{conductor['clave']}/{k:02d}"),
            "conductor_id": conductor["id"],
            "autor_id": autor["id"],
            "estrellas": estrellas,
            "texto": R.choice(C.RESENAS_DE if lang == "de" else C.RESENAS_EN),
            "texto_lang": lang,
            "dia_offset": -R.randint(2, 180),
        })
    return filas


def trayecto_relleno(n, duenno):
    """Un trayecto de diario: casa → trabajo, con los barrios por los que pasa.

    Es el caso que el docx pone primero —«anyone on the way to work, shopping»— y el que la
    demo no tenia: hasta ahora todo plan era un evento. Sin estos, buscar «Ich fahre morgen
    frueh nach Mitte» no devuelve nada, y esa es la frase que el cliente va a teclear.
    """
    ciudad = duenno["city"]
    b_origen, b_vias, b_destino = R.choice(C.CORREDORES[ciudad])
    origen = geo(ciudad, b_origen)
    vias = [geo(ciudad, b) for b in b_vias]
    destino = geo(ciudad, b_destino)
    puntos, km = trazar(origen, vias, destino)
    motivo = R.choice(C.MOTIVOS_TRAYECTO)
    lang = "de" if R.random() < 0.55 else "en"
    hora = R.choice(["07:20", "07:45", "08:00", "08:10", "08:30", "17:30", "18:00", "18:45"]) \
        if motivo == "commute" else R.choice(["10:30", "16:00", "19:30", "20:30"])
    # El orden importa: la recurrencia se decide ANTES del titulo. Al reves salian trayectos
    # titulados «Jeden Morgen Bilk → Altstadt» con `recurrente = null`, y esa incoherencia la ve
    # cualquiera que mire dos lineas seguidas de la pantalla. «Cada ma~nana» es una afirmacion
    # sobre el dato, no un adorno del titulo.
    recurrente = "weekdays" if motivo == "commute" and R.random() < 0.7 else None
    plantillas = list(C.TITULO_TRAYECTO_DE if lang == "de" else C.TITULO_TRAYECTO_EN)
    repetidas = [p for p in plantillas if "{o}" in p and ("Jeden" in p or "every" in p)]
    plantillas = repetidas if recurrente else [p for p in plantillas if p not in repetidas]
    titulo = R.choice(plantillas).format(o=b_origen, d=b_destino, h=hora)
    return {
        "clave": f"relleno-trayecto-{n:03d}",
        "origen": "relleno",
        "id": ident(f"plan/relleno-trayecto-{n:03d}"),
        "owner_id": duenno["id"],
        "title": titulo,
        "description": R.choice(C.DESC_TRAYECTO_DE if lang == "de" else C.DESC_TRAYECTO_EN),
        "desc_lang": lang,
        "category": motivo,
        "origin_city": ciudad,
        "dest_city": ciudad,
        "is_travel": False,
        "venue": b_destino,
        "barrio": b_destino,
        "geo": destino,
        "origin_geo": origen,
        "ruta": puntos,
        "via": b_vias,
        "distancia_km": km,
        "precio_por_km": precio_km(),
        "recurrente": recurrente,
        "date_precision": "exact",
        # Un trayecto de diario vive en los proximos dias, no en seis semanas: el docx habla de
        # publicar «30-60 min antes de salir».
        "dia_offset": R.randint(0, 6),
        "hora": hora,
        "duracion_h": 1,
        # EL NUMERO DEL DOCX: «tracking within 1-2 km». Un concierto empareja a 40 km; un coche,
        # a dos. Es un campo por fila justamente para que convivan los dos mundos.
        "radius_km": 2,
        "seats_open": R.choice([1, 2, 2, 3]),
        "subject": b_destino,
        "tags": sorted(set([motivo, "rideshare", "commute" if motivo == "commute" else "ride"])),
        "budget_band": "low",
        "pace": "relaxed",
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

    # ── la capa de coche compartido ───────────────────────────────────────────────────────
    #
    # Orden importante: primero la flota (quien conduce), despues los trayectos (que cuelgan de
    # un conductor), y al final las rese~nas —que necesitan que la flota ya exista para saber a
    # quien valorar—. Cambiar el orden cambia la secuencia de `R` y por tanto el fichero entero;
    # el gate `just seed-determinista` compara dos ejecuciones, no dos versiones.
    perfiles.sort(key=lambda p: p["clave"])
    conductores = []
    for i, p in enumerate(perfiles):
        # La mitad conduce. Un mundo donde todos tienen coche no se parece a una ciudad alemana.
        if i % 2 == 0:
            conductores.append(dar_coche(p, i))
        else:
            p["conduce"] = False
            p["coche"] = None
            p["plazas_coche"] = None
            p["desde_offset"] = R.randint(1, 36)
            p["nota"] = None
            p["notas_conteo"] = 0

    # Todo plan con destino alcanzable en coche ES un viaje: quien va al concierto conduce
    # hasta alli, y le sobran plazas. Es lo que une los dos productos del hilo de Workana.
    for pl in planes:
        if "ruta" in pl:
            continue
        puntos, km = trazar(pl["origin_geo"], [], pl["geo"])
        # Mas de 700 km no se conducen para un fin de semana: eso es un vuelo. Y menos de 1,5
        # no se conducen en absoluto: eso se anda, y una tarifa de 0,14 EUR se ve ridicula.
        if km > 700 or km < 1.5:
            pl["ruta"] = None
            pl["via"] = []
            pl["distancia_km"] = None
            pl["precio_por_km"] = None
            pl["recurrente"] = None
            continue
        pl["ruta"] = puntos
        pl["via"] = []
        pl["distancia_km"] = km
        pl["precio_por_km"] = precio_km()
        pl["recurrente"] = None

    t = 0
    trayectos = []
    while len(trayectos) < OBJETIVO_TRAYECTOS:
        duenno = conductores[t % len(conductores)]
        trayectos.append(trayecto_relleno(t, duenno))
        t += 1
    planes.extend(trayectos)

    # Rese~nas. Un conductor sin ninguna tambien existe —es el que acaba de entrar— y eso es
    # informacion: en la tarjeta se ense~na «nuevo», no un 0,0 que parece una mala nota.
    valoraciones = []
    for c in conductores:
        cuantas = R.choices([0, 3, 7, 14, 28], weights=[8, 22, 30, 26, 14])[0]
        filas = resenas_de(c, perfiles, cuantas)
        valoraciones.extend(filas)
        if filas:
            c["notas_conteo"] = len(filas)
            c["nota"] = round(sum(f["estrellas"] for f in filas) / len(filas), 1)
        else:
            c["nota"] = None
            c["notas_conteo"] = 0
        # `completed_plans` tiene que ser coherente con las rese~nas: no se puede tener 14
        # valoraciones y 2 viajes. Es el tipo de incoherencia que el cliente SI mira.
        c["completed_plans"] = max(c.get("completed_plans", 0), len(filas))

    salida = {
        "meta": {
            "semilla": SEMILLA,
            "objetivo_perfiles": OBJETIVO_PERFILES,
            "objetivo_planes": OBJETIVO_PLANES,
            "objetivo_trayectos": OBJETIVO_TRAYECTOS,
            "plantados": {"perfiles": plantados_perfiles, "planes": plantados_planes,
                          "intents": len(intents), "escenarios": len(escenarios)},
            "aviso": ("Ni una fecha absoluta: el tiempo son desplazamientos que sembrar.py "
                      "materializa contra now(). Ver docs/adr/0001-como-ruedan-las-fechas.md"),
        },
        "escenarios": escenarios,
        "perfiles": perfiles,
        "planes": planes,
        "intents": intents,
        "valoraciones": valoraciones,
    }
    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")

    print(f"seed escrito: {os.path.relpath(SALIDA, RAIZ)}")
    print(f"  perfiles {len(perfiles):>4}  ({plantados_perfiles} plantados)")
    print(f"  planes   {len(planes):>4}  ({plantados_planes} plantados)")
    print(f"  intents  {len(intents):>4}")
    print(f"  de los planes, trayectos de diario: {len(trayectos)}")
    print(f"  conductores {len(conductores):>3}  ·  valoraciones {len(valoraciones)}")
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
