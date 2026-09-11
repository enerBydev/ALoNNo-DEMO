#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""generar-lugares — escribe `server/utils/lugares.ts` desde `scripts/catalogos.py`.

    python3 scripts/generar-lugares.py

EL FALLO QUE LO TRAJO (11-sep-2026). `centroDe()` solo conocia NUEVE ciudades, y la Capa 0
devuelve lo que la persona escribe. «Ich fahre morgen von Neukolln nach Mitte» ponia
`city: "Neukolln"` — un barrio— , `centroDe` devolvia null, y sin centro **no hay filtro de
radio**: la busqueda de un berlines contestaba con coches de Dusseldorf. No daba error; solo
devolvia mal.

Los barrios ya existian, con coordenadas reales, en los catalogos del seed. Duplicarlos a mano en
TypeScript habria sido crear dos verdades que se separan en cuanto alguien a~nade un barrio, asi
que se generan. `just lugares` lo rehace y `tests/lugares.test.ts` comprueba que el fichero
generado sigue siendo el que corresponde al catalogo.
"""
import os
import sys
import unicodedata

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "scripts"))
import catalogos as C  # noqa: E402

SALIDA = os.path.join(RAIZ, "server", "utils", "lugares.ts")


def clave(t):
    """Sin diacriticos, en minusculas y sin guiones: «Neukölln», «Neukolln» y «neukolln» iguales."""
    return "".join(c for c in unicodedata.normalize("NFD", str(t))
                   if unicodedata.category(c) != "Mn").lower().replace("-", " ").strip()


def main():
    ciudades = {}
    barrios = {}
    for ciudad, sus_barrios in C.CIUDADES.items():
        lats = [v[0] for v in sus_barrios.values()]
        lons = [v[1] for v in sus_barrios.values()]
        ciudades[clave(ciudad)] = (round(sum(lons) / len(lons), 4), round(sum(lats) / len(lats), 4))
        for barrio, (lat, lon) in sus_barrios.items():
            k = clave(barrio)
            # Hay barrios repetidos entre ciudades («Altstadt» esta en cuatro). El primero gana y
            # el resto quedan accesibles por «ciudad/barrio»; una frase que solo dice «Altstadt»
            # es genuinamente ambigua, y resolverla a la primera ciudad es mejor que no resolverla.
            barrios.setdefault(k, (round(lon, 4), round(lat, 4), clave(ciudad)))
            barrios[f"{clave(ciudad)}/{k}"] = (round(lon, 4), round(lat, 4), clave(ciudad))

    lineas = [
        "// GENERADO por `scripts/generar-lugares.py` desde `scripts/catalogos.py`. NO SE EDITA.",
        "//",
        "// El seed y el buscador tienen que coincidir en donde esta cada sitio, o la columna de",
        "// proximidad deja de significar nada. Se genera para que haya una sola verdad.",
        "//",
        f"// {len(ciudades)} ciudades · {len(set(k for k in barrios if '/' not in k))} barrios.",
        "",
        "/** [lon, lat] del centro de cada ciudad. Clave sin diacriticos y en minusculas. */",
        "export const CIUDADES: Record<string, [number, number]> = {",
    ]
    for k in sorted(ciudades):
        lon, lat = ciudades[k]
        lineas.append(f"  '{k}': [{lon}, {lat}],")
    lineas += [
        "}",
        "",
        "/** [lon, lat, ciudad] de cada barrio. Tambien indexado como `ciudad/barrio`. */",
        "export const BARRIOS: Record<string, [number, number, string]> = {",
    ]
    for k in sorted(barrios):
        lon, lat, ciudad = barrios[k]
        lineas.append(f"  '{k}': [{lon}, {lat}, '{ciudad}'],")
    lineas += ["}", ""]

    with open(SALIDA, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas))
    print(f"escrito: {os.path.relpath(SALIDA, RAIZ)} "
          f"({len(ciudades)} ciudades, {len(barrios)} claves de barrio)")


if __name__ == "__main__":
    main()
