#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""calentar — deja la cache de la demo caliente y SIN respuestas degradadas.

    python3 scripts/calentar.py                       # contra produccion
    python3 scripts/calentar.py --url http://127.0.0.1:3311

POR QUE EXISTE. El proveedor de IA a veces no contesta (medido el 15-sep-2026: 2,2 s una llamada,
mas de 40 s la siguiente). Cuando eso pasa, la busqueda cae a reglas y **ese resultado degradado
se guarda en la cache** seis horas: el cliente abriria la demo y veria «fallback rules · the model
did not answer in time» en la portada, aunque el proveedor ya estuviera bien.

Esto pide cada frase con `?fresco=1` —que salta la cache y sobreescribe la entrada— hasta que la
respuesta venga del modelo, con un maximo de intentos. Se corre **antes de mandar el link**, y
es el paso 4 de la lista del dia 16 en ESTADO.md.

Las frases son las 10 del cliente (`db/frases.json`, el criterio de aceptacion) mas las de coche
compartido que la portada ofrece como ejemplos y la busqueda por defecto de `/`.
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://match-engine.enerby212.workers.dev"
INTENTOS = 4

# Las mismas que `app/pages/index.vue` ofrece. Si cambian alli, cambian aqui.
COCHE = [
    ("Berlin", "Ich fahre morgen um 8 von Neukolln nach Mitte, zwei Plaetze frei"),
    ("Berlin", "Suche Mitfahrgelegenheit morgen frueh Richtung Mitte"),
    ("Koln", "I drive to Altstadt every weekday morning, two seats free"),
    ("Frankfurt", "Ich brauche eine Fahrt nach Westend am Montag"),
    ("Munchen", "Anyone driving towards Maxvorstadt tomorrow around 8?"),
]


def pedir(base, q, ciudad, fresco):
    params = {"q": q, "ciudad": ciudad}
    if fresco:
        params["fresco"] = "1"
    url = f"{base}/api/buscar?{urllib.parse.urlencode(params)}"
    t0 = time.time()
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "match-engine-calentador/1.0"}),
                                timeout=60) as r:
        return json.loads(r.read()), round(time.time() - t0, 1)


def main():
    base = BASE
    if "--url" in sys.argv:
        base = sys.argv[sys.argv.index("--url") + 1].rstrip("/")

    with open(os.path.join(RAIZ, "db", "frases.json"), encoding="utf-8") as f:
        cliente = [("Berlin", x["frase_del_cliente"]) for x in json.load(f)]
    frases = COCHE + cliente

    print(f"calentando {len(frases)} frases contra {base}\n")
    quedaron_degradadas = 0
    for ciudad, q in frases:
        estado = "?"
        for i in range(1, INTENTOS + 1):
            try:
                d, seg = pedir(base, q, ciudad, fresco=(i > 1))
            except Exception as e:
                estado = f"error {str(e)[:40]}"
                continue
            if not d.get("degradado"):
                top = (d.get("listas") or [{}])[0].get("resultados") or [{}]
                estado = f"✓ {seg:>5}s · intento {i} · {top[0].get('porcentaje', '?')}% {str(top[0].get('titulo', ''))[:34]}"
                break
            estado = f"~ degradada tras {i} intento(s) ({d.get('motivo_degradado')})"
        if estado.startswith("~") or estado.startswith("error"):
            quedaron_degradadas += 1
        print(f"  {estado:<62} {q[:44]}")

    print()
    if quedaron_degradadas:
        print(f"{quedaron_degradadas} frase(s) siguen degradadas: el proveedor no contesto en "
              f"{INTENTOS} intentos. Vuelve a correr esto en unos minutos.")
        return 1
    print("todas las frases estan en cache y vienen del modelo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
