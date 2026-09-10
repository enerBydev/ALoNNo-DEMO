#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""frases — las 10 frases de Helder contra la demo desplegada.

    python3 scripts/frases.py                    # contra produccion
    python3 scripts/frases.py --url http://…     # contra otra URL

Hace tres cosas a la vez, y por eso existe:

1. **Es el criterio de aceptacion.** La regla 4 del proyecto dice que las 10 frases del §9-A son
   el criterio, y el §11 pide un smoke test para no romper la demo el dia 7. Esto lo ejecuta.
2. **Pre-calienta la cache.** La Capa 0 tarda entre 4 s y 16 s por variabilidad del proveedor;
   cacheada, la misma frase responde en 0,3 s. Las 10 frases son clicables en la UI: el dia 16 se
   corre esto ANTES de mandar el link y el cliente no espera nunca.
3. **Comprueba el cruce de idiomas**, que es el criterio del §3: en cada frase tiene que haber
   un resultado del top 3 escrito en el idioma contrario al de la consulta.

Las frases se leen de `db/plantados/*.json`, donde estan VERBATIM. No se copian aqui para que no
puedan divergir de las que el seed planto.
"""
import argparse
import glob
import json
import os
import time
import urllib.parse
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "https://alonno-demo.enerby212.workers.dev"

V = "\033[32m"; R = "\033[31m"; A = "\033[33m"; G = "\033[90m"; N = "\033[0m"


def frases():
    fuera = []
    for f in sorted(glob.glob(os.path.join(RAIZ, "db", "plantados", "*.json"))):
        d = json.load(open(f, encoding="utf-8"))
        if d.get("frase_de_helder"):
            fuera.append((d["escenario"], d["frase_de_helder"], d.get("que_debe_devolver", "")))
    return fuera


def buscar(base, q):
    url = f"{base}/api/buscar?" + urllib.parse.urlencode({"q": q})
    t0 = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": "alonno-frases/1.0"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read()), time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=URL)
    args = ap.parse_args()

    lista = frases()
    print(f"{len(lista)} frases de Helder contra {args.url}\n")
    fallos = 0
    for escenario, q, esperado in lista:
        try:
            d, seg = buscar(args.url, q)
        except Exception as e:
            print(f"  {R}✗{N} {escenario:<26} {e}")
            fallos += 1
            continue

        res = d.get("resultados") or []
        i = d.get("intencion") or {}
        if not res:
            print(f"  {R}✗{N} {escenario:<26} SIN RESULTADOS  ({i.get('archetype')})")
            fallos += 1
            continue

        top = res[0]
        idioma_consulta = i.get("language")
        # El criterio del §3: un resultado del top 3 en el idioma contrario al de la consulta.
        cruce = any(r.get("idioma") and r["idioma"] != idioma_consulta for r in res[:3])
        marca = V + "✓" + N if cruce else A + "~" + N
        print(f"  {marca} {escenario:<26} {i.get('archetype','?'):<18} "
              f"{top['porcentaje']:>3}%  {top['tipo']:<7} [{top.get('idioma')}] "
              f"{(top['titulo'] or '')[:30]:<30} {G}{seg:5.1f}s{N}")
        if top.get("explicacion"):
            print(f"      {G}«{top['explicacion'][:96]}»{N}")
        if not cruce:
            print(f"      {A}sin resultado en el idioma contrario dentro del top 3{N}")

    print()
    if fallos:
        print(f"{R}{fallos} frase(s) sin resultado.{N} La regla 4 dice que las 10 son el criterio.")
        raise SystemExit(1)
    print(f"{V}las {len(lista)} frases devuelven algo.{N} La cache queda caliente.")


if __name__ == "__main__":
    main()
