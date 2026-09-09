#!/usr/bin/env python3
"""Cada paquete que cambia trae su changeset — PAQUETE POR PAQUETE.

`pnpm changeset status --since=origin/main` sólo falla cuando hay paquetes cambiados y
NINGÚN changeset nuevo. Medido el 4-sep-2026: con un changeset que cubría otros paquetes,
tocar dominios/carrito sin nombrarlo pasaba el gate. Eso es una salvaguarda que no
salvaguarda (el patrón de `varies`, T-08). Este script hace la comprobación de verdad:

  paquetes cambiados desde origin/main  −  ignore  −  paquetes cubiertos por changesets nuevos

Si queda algo, falla y lo nombra. Lee git (commits + índice + no rastreados), no la memoria.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BASE = "origin/main"


def git(*args: str) -> list[str]:
    r = subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True, check=False)
    if r.returncode != 0:
        # `origin/main` puede no existir —un repo recien nacido, un clon sin remoto— y eso no
        # es un fallo del repo: es que no hay contra que comparar. Se dice y se sale limpio.
        if any(BASE in a for a in args):
            print(f"verificar-cambios: `{BASE}` no existe aqui — sin base contra la que comparar")
            sys.exit(0)
        # Un ref inválido devolvía [] y eso parecía «no cambió nada»: verde sin proteger (D6).
        print(f"verificar-cambios: `git {' '.join(args)}` falló ({r.returncode}): {r.stderr.strip()}")
        sys.exit(1)
    return [l for l in r.stdout.splitlines() if l.strip()]


def archivos_cambiados() -> set[str]:
    return set(git("diff", "--name-only", f"{BASE}...HEAD")
               + git("diff", "--name-only", "--cached")
               + git("diff", "--name-only")
               + git("ls-files", "--others", "--exclude-standard"))


def paquetes_del_workspace() -> dict[str, str]:
    """directorio → nombre, para todo package.json del workspace (sin node_modules)."""
    mapa = {}
    for pj in RAIZ.rglob("package.json"):
        if any(p in pj.parts for p in ("node_modules", ".output", ".nuxt")):
            continue
        rel = pj.parent.relative_to(RAIZ).as_posix()
        mapa["." if rel == "." else rel] = json.loads(pj.read_text(encoding="utf-8")).get("name", rel)
    return mapa


def paquetes_cubiertos(archivos: set[str]) -> set[str]:
    cubiertos = set()
    for a in archivos:
        if not (a.startswith(".changeset/") and a.endswith(".md") and a != ".changeset/README.md"):
            continue
        ruta = RAIZ / a
        if not ruta.exists():
            continue
        m = re.match(r"^---\n(.*?)\n---", ruta.read_text(encoding="utf-8"), re.S)
        if not m:
            continue
        for linea in m.group(1).splitlines():
            k = re.match(r'^\s*"?([^"\s:]+)"?\s*:', linea)
            if k:
                cubiertos.add(k.group(1))
    return cubiertos


def main() -> int:
    # SIN CHANGESETS ADOPTADO NO SE OPINA. Como verbo de plantilla esto corre en repos que aun
    # no han decidido nada sobre releases (regla 1: nada impuesto sin una config decidida), y
    # un `.changeset/config.json` que no existe no es un incumplimiento: es que la herramienta
    # no esta. Tratarlo como fallo obligaria a inventarse el fichero para pasar el gate, que es
    # la forma exacta de convertir un control en un tramite.
    cfg = RAIZ / ".changeset/config.json"
    if not cfg.is_file():
        print("verificar-cambios: sin `.changeset/` — este repo no usa Changesets, nada que comprobar")
        return 0
    config = json.loads(cfg.read_text(encoding="utf-8"))
    ignorados = set(config.get("ignore", []))
    archivos = archivos_cambiados()
    mapa = paquetes_del_workspace()

    cambiados = set()
    for a in archivos:
        # el paquete más profundo que contenga el archivo
        candidatos = [d for d in mapa if d != "." and (a == d or a.startswith(d + "/"))]
        if candidatos:
            cambiados.add(mapa[max(candidatos, key=len)])

    cubiertos = paquetes_cubiertos(archivos)
    faltan = sorted(cambiados - ignorados - cubiertos)
    print(f"verificar-cambios: {len(cambiados)} paquete(s) cambiado(s) desde {BASE}, "
          f"{len(cambiados & ignorados)} ignorado(s), {len(cubiertos)} cubierto(s) por changesets nuevos")
    for p in faltan:
        print(f"  ✗ {p} cambió y ningún changeset nuevo lo nombra — `pnpm changeset` y elígelo")
    return 1 if faltan else 0


if __name__ == "__main__":
    sys.exit(main())
