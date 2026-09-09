#!/usr/bin/env python3
"""El catálogo de versiones, cerrado por las dos puntas.

1. Ninguna dependencia que esté en el catálogo aparece con versión literal en un
   package.json: se escribe "catalog:". Subir Nuxt 5 es editar UNA línea.
2. Ninguna entrada del catálogo se queda sin consumidor. Medido el 4-sep-2026 (T-03):
   el catálogo decía wrangler 4.129.0 y ningún package.json lo consumía, así que
   `pnpm exec wrangler` ejecutaba el 4.93.0 de Nix y `dev --local` no arrancaba. Una
   versión que nadie usa no es una versión: es una mentira que parece una decisión.

Sale 1 nombrando archivo y línea. Sin dependencias: lee YAML y JSON a mano, porque
el catálogo es plano y PyYAML no está en el devshell.
"""
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SECCIONES = ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies")


def leer_catalogo() -> dict[str, str]:
    texto = (RAIZ / "pnpm-workspace.yaml").read_text(encoding="utf-8")
    dentro, catalogo = False, {}
    for linea in texto.splitlines():
        if re.match(r"^catalog:\s*$", linea):
            dentro = True
            continue
        if dentro and re.match(r"^\S", linea):  # otra clave de primer nivel
            dentro = False
        if not dentro:
            continue
        m = re.match(r'^\s+"?([^":#]+)"?\s*:\s*(\S+)\s*$', linea)
        if m:
            catalogo[m.group(1).strip()] = m.group(2).strip()
    return catalogo


def package_jsons():
    """Los manifiestos DEL REPO. Lo que vive en un directorio oculto no es suyo.

    SE DESCARTA POR FORMA, NO POR LISTA. Esto enumeraba `node_modules`, `.output` y `.nuxt`,
    y se quedo corto el 2026-09-08 con `.methodos`: el directorio donde el CI hace checkout
    del kit compartido cuando el repo no puede resolver la accion directamente (repos de una
    organizacion, o publicos). El gate de `OnlyHouseMX/site` cayo en su PRIMERA ejecucion
    real acusando a un `package.json` de PLANTILLA de methodOS de no usar el catalogo... del
    repo auditado. Un veredicto sobre codigo que no es del repo.

    Enumerar lo conocido falla cada vez que aparece un directorio que no estaba en la cabeza
    de quien escribio la lista. Un directorio oculto nunca es codigo fuente del repo, y esa
    si es una regla que no caduca."""
    for p in RAIZ.rglob("package.json"):
        if any(parte.startswith(".") or parte == "node_modules" for parte in p.parts):
            continue
        yield p


def main() -> int:
    catalogo = leer_catalogo()
    if not catalogo:
        # SIN CATÁLOGO NO SE OPINA. En el repo donde nació esto siempre había uno, así que
        # ausencia y error eran lo mismo. Como verbo de la plantilla ya no: un proyecto de
        # una sola app no necesita catálogo, y tratar su ausencia como fallo obligaría a
        # inventarse una sección vacía para pasar el gate — que es la forma exacta de
        # convertir un control en un trámite (regla 1: nada impuesto sin decidirlo).
        print("verificar-catalogo: sin sección `catalog:` — nada que comprobar")
        return 0

    fallos, consumidores = [], {k: 0 for k in catalogo}
    for pj in package_jsons():
        lineas = pj.read_text(encoding="utf-8").splitlines()
        datos = json.loads("\n".join(lineas))
        for seccion in SECCIONES:
            for nombre, version in (datos.get(seccion) or {}).items():
                if nombre in catalogo:
                    if version.startswith("catalog:"):
                        consumidores[nombre] += 1
                    else:
                        num = next((i + 1 for i, l in enumerate(lineas)
                                    if re.search(rf'"{re.escape(nombre)}"\s*:', l)), "?")
                        fallos.append(f"{pj.relative_to(RAIZ)}:{num}  {nombre}: \"{version}\" "
                                      f"→ escribe \"catalog:\" (el catálogo dice {catalogo[nombre]})")

    huerfanas = [k for k, n in consumidores.items() if n == 0]
    print(f"verificar-catalogo: {len(catalogo)} entradas, "
          f"{sum(consumidores.values())} consumos, {len(fallos)} literal(es), "
          f"{len(huerfanas)} sin consumidor")
    for f in fallos:
        print(f"  ✗ {f}")
    for k in huerfanas:
        print(f"  ✗ {k}: {catalogo[k]} está en el catálogo y NADIE lo consume — "
              f"o se declara en un package.json, o se borra (T-03)")
    return 1 if (fallos or huerfanas) else 0


if __name__ == "__main__":
    sys.exit(main())
