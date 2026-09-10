#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verificar-hechos — el gate que comprueba que lo escrito SIGUE SIENDO CIERTO.

    verificar-hechos.py [RAIZ]        # por defecto, la raíz del repo

Su hermano `verificar-docs.py` vigila la FORMA de la documentación: que los enlaces
resuelvan, que ningún doc quede huérfano. Este vigila su VERDAD.

POR QUÉ EXISTE (2026-08-26). La auditoría midió ~40 afirmaciones falsas repartidas por el
repo, y ninguna había disparado ningún gate — porque no había ninguno que mirase el mundo.
En once días hubo tres migraciones de nube y se borraron cuatro repositorios; el estándar
siguió citándolos en presente como prueba de que funcionaba. La lección no es «hay que
repasar los documentos»: es que **un barrido manual se vuelve a desincronizar en la
siguiente migración**. Lo que no tiene gate, deriva.

QUÉ COMPRUEBA, y sale != 0 si algo falla:

  1. RUTA DEL REPO      — un `path/como/este` citado en la doc que ya no existe.
  2. ENTIDAD RETIRADA   — algo declarado muerto en `docs/hechos.md` y todavía citado en
                          presente. Es el motor que habría cazado los `calc-*`.
  3. HECHO DECLARADO    — una línea de `docs/hechos.md` con su comprobación, que se ejecuta.

EL PROBLEMA DEL FALSO POSITIVO, Y CÓMO SE RESUELVE. Un ADR que narra el pasado NO es drift:
«se extrajo de calc-cli (2026-08-19)» es historia correcta y debe seguir escrita. Por eso
un documento puede llevar un SELLO en su cabecera:

    <!-- hechos: congelado 2026-08-19 -->   este doc narra un momento; no se audita
    <!-- hechos: sujeto ajeno -->           habla de otro sistema, no de este entorno

Sin sello, el documento se lee como afirmación en presente y se audita. El sello es
deliberadamente barato de poner y visible en el diff: sellar un doc vivo para silenciarlo
es indistinguible de sellarlo bien, así que su uso se revisa como cualquier otro cambio.

SIN RED, a propósito: corre dentro de `just ci`, y un gate que necesita internet falla los
días que no lo hay y enseña a ignorarlo. Lo que exige red (¿existe este repo en GitHub?)
se comprueba en el trabajo de plataforma, no aquí.
"""
import os
import platform
import re
import shutil
import sys

# `.methodos` NO estaba en esta lista y rompio el CI de este repo el 2026-09-10, la primera vez
# que se adopto el verbo `hechos`. El `ci.yml` del estandar clona el kit de methodOS DENTRO del
# arbol de trabajo (`path: .methodos`) porque `uses: ./...` lo exige, asi que este verificador
# auditaba los ficheros de PLANTILLA y fallaba por un `just panel` que existe en methodOS y no en
# el consumidor. Es el mismo patron que ya rompio dos gates el 2026-09-08 con el verificador de
# catalogo y con vitest: lo que el CI deja caer en el arbol no es del repo que se audita.
# Corregido aqui y reportado a la fuente: tarea 86bbyfjf1.
EXCLUIDOS = {".git", "node_modules", ".direnv", "target", "archivo-v1", ".methodos"}
REGISTRO = os.path.join("docs", "hechos.md")

SELLO = re.compile(r"<!--\s*hechos:\s*(congelado|sujeto ajeno)", re.I)
# Rutas del repo citadas en prosa o en código: `templates/bin/algo.py`, `docs/kernel.md`.
RUTA = re.compile(r"`([a-zA-Z0-9_][a-zA-Z0-9_./-]*/[a-zA-Z0-9_.-]+)`")
# Una entrada del registro: `- nombre — razón` bajo la sección de retiradas.
RETIRADA = re.compile(r"^\s*-\s+`([^`]+)`\s*—", re.M)


def docs_md(raiz):
    """Todos los .md del repo, menos los excluidos."""
    out = []
    for base, dirs, fs in os.walk(raiz):
        dirs[:] = [d for d in dirs if d not in EXCLUIDOS]
        for f in fs:
            if f.endswith(".md"):
                out.append(os.path.relpath(os.path.join(base, f), raiz))
    return sorted(out)


def leer(ruta):
    try:
        with open(ruta, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def sellado(texto):
    """¿El documento entero declara que narra un momento congelado o habla de otro sistema?"""
    return bool(SELLO.search(texto[:1200]))


def parte_viva(texto):
    """El texto que SÍ se audita, cuando el sello aparece a mitad de documento.

    Un roadmap es mixto por naturaleza: arriba el estado de hoy, abajo el registro de las
    fases ya cerradas. Obligar a elegir entre auditarlo entero o eximirlo entero llevaría a
    lo segundo, y entonces el gate no vigilaría el documento que más cambia. Con el sello
    en medio, lo de arriba se audita y lo de abajo queda como lo que es: historia."""
    m = SELLO.search(texto)
    return texto[:m.start()] if m else texto


def entidades_retiradas(raiz):
    """Lo que `docs/hechos.md` declara muerto: nombres que ya no deben citarse en presente."""
    texto = leer(os.path.join(raiz, REGISTRO))
    if not texto:
        return []
    # Solo la sección de retiradas, para no capturar otras listas del documento.
    trozo = texto.split("## Entidades retiradas", 1)
    if len(trozo) < 2:
        return []
    return RETIRADA.findall(trozo[1].split("\n## ", 1)[0])


# UNA RUTA QUE TODAVIA NO EXISTE PERO VA A EXISTIR (2026-09-04, OnlyHouseMX/site).
#
# `docs/DESGLOSE-V1.md` —un plan VIGENTE, no un historico— citaba `apps/carrito`, que es de
# la fase 2 y aun no existe. El gate lo dio por RUTA INEXISTENTE, y las dos unicas salidas
# eran malas: sellar el documento como historico (falso: es un plan vivo) o quitar los
# backticks, que es lo que se hizo y pierde el enlace semantico.
#
# Un plan que no puede nombrar lo que va a construir es un plan peor. El marcador exime esa
# cita concreta —no el documento— y es barato de leer para un humano:
#
#     `apps/carrito` (futuro)
#     `apps/carrito` <!-- futura -->
#
# Y cuando la ruta YA EXISTE, el gate lo dice: el marcador sobra y hay que retirarlo, o el
# documento acumula «futuros» que ya son presente — que es la misma clase de mentira que
# este gate existe para impedir.
_FUTURA = re.compile(r"`([^`]+)`\s*(?:\((?:futuro|futura|pendiente)\)|<!--\s*futur[ao]\s*-->)")


def rutas_futuras(texto):
    """Las rutas que el documento declara como todavia no existentes."""
    return {m.group(1) for m in _FUTURA.finditer(texto or "")}


def futuras_ya_presentes(raiz, doc, texto):
    """Las marcadas como futuras que YA existen: el marcador sobra y hay que quitarlo."""
    return [(doc, r) for r in sorted(rutas_futuras(texto))
            if os.path.exists(os.path.join(raiz, r))]


def rutas_del_repo_rotas(raiz, doc, texto):
    """Rutas del propio repo citadas entre comillas que ya no existen."""
    fallos = []
    futuras = rutas_futuras(texto)
    for candidata in set(RUTA.findall(texto)):
        if candidata in futuras:
            continue
        # Solo se auditan las que parecen del repo: su primer segmento existe como
        # directorio o el propio fichero existe. Así una ruta de otro sistema
        # (`/etc/nix/nix.conf`, `~/.cargo/config.toml`) no se confunde con una nuestra.
        raiz_seg = candidata.split("/", 1)[0]
        if raiz_seg.startswith((".", "~", "/")) or not os.path.isdir(os.path.join(raiz, raiz_seg)):
            continue
        if not os.path.exists(os.path.join(raiz, candidata)):
            fallos.append((doc, candidata))
    return fallos


def citas_de_muertos(doc, texto, muertos):
    """Entidades declaradas retiradas y todavía citadas por un documento sin sellar.

    Se buscan también las formas con COMODÍN. El gate comparaba nombres exactos y el README
    escribía «los 3 `calc-*`»: la cita que motivó construir este gate era justo la que se le
    escapaba (medido 2026-08-27). Para `calc-cli` se vigilan además `calc-*` y `calc*`."""
    fallos = []
    for muerto in muertos:
        formas = [re.escape(muerto)]
        if "-" in muerto:
            raiz = muerto.rsplit("-", 1)[0]
            formas.append(re.escape(raiz) + r"-?\*")
        for forma in formas:
            if re.search(r"(?<![\w-])" + forma + r"(?![\w-])", texto):
                fallos.append((doc, muerto))
                break
    return fallos


# Las comprobaciones que este gate sabe hacer. UNA LISTA CERRADA, implementada aquí en
# Python, sin pasar por un shell.
#
# LA PRIMERA VERSIÓN ERA UN INTÉRPRETE (2026-08-26 → corregido el 2026-08-27). El registro
# declaraba el COMANDO junto al hecho y esto hacía `subprocess.run(cmd, shell=True)` con esa
# cadena. Suena inofensivo hasta que se mira dónde corre: en `just ci` y **dentro de la
# acción compartida del CI**. Cualquiera que pudiera editar un fichero Markdown ejecutaba
# comandos en el gate de todos los repos del namespace. Lo escribió el mismo que reparaba
# una auditoría sobre gates que no protegen: el camino al infierno, etc.
#
# Ahora el registro solo puede elegir de esta lista. Añadir una comprobación nueva es tocar
# ESTE fichero —código, revisado, con su test— y no una línea de prosa.
def _comp_arquitectura(valor):
    return platform.machine() == valor


def _comp_herramienta(valor):
    return shutil.which(valor) is not None


def _comp_fichero(valor):
    return os.path.exists(valor)


COMPROBACIONES = {
    "arquitectura": (_comp_arquitectura, "la arquitectura de la máquina"),
    "herramienta": (_comp_herramienta, "un ejecutable presente en el PATH"),
    "fichero": (_comp_fichero, "una ruta que debe existir"),
}


def hechos_declarados(raiz):
    """Hechos declarados en `docs/hechos.md`, con el TIPO de comprobación (no un comando):

        - `x86_64` la arquitectura de esta máquina — comprobación: `arquitectura`

    El tipo debe estar en COMPROBACIONES; cualquier otro es un error del registro, no un
    comando que ejecutar."""
    texto = leer(os.path.join(raiz, REGISTRO))
    if "## Hechos comprobables" not in texto:
        return []
    trozo = texto.split("## Hechos comprobables", 1)[1].split("\n## ", 1)[0]
    patron = re.compile(r"^\s*-\s+`([^`]+)`\s+.*?comprobaci[oó]n:\s*`([a-z]+)`\s*$", re.M | re.I)
    fallos = []
    for valor, tipo in patron.findall(trozo):
        entrada = COMPROBACIONES.get(tipo.lower())
        if entrada is None:
            fallos.append((REGISTRO,
                           f"comprobación desconocida «{tipo}»; las válidas son: "
                           + ", ".join(sorted(COMPROBACIONES))))
            continue
        fn, desc = entrada
        try:
            ok = fn(valor)
        except Exception:
            ok = False
        if not ok:
            fallos.append((REGISTRO, f"«{valor}» ya no es cierto ({desc})"))
    return fallos


# ── UN DOCUMENTO QUE DESCRIBE UN CODIGO QUE YA CAMBIO ────────────────────────────────
#
# LA CLASE QUE FALTABA, y costo tres casos en un solo dia (2026-09-06/07):
#
#   · el README publicaba `ci: lint test secretos …` y a la receta real le faltaban TRES verbos
#   · el mapa decia «accion `sync-cu` — no existe» con la accion funcionando
#   · el manual del revisor decia `gh pr review` y el codigo hacia `POST /pulls/N/reviews`
#
# Los tres los encontro una persona mirando. Este gate ya cazaba rutas muertas y entidades
# retiradas —lo que el repo dice sobre EL MUNDO— y no miraba lo que dice sobre SI MISMO.
#
# NO SE MECANIZA «el doc describe mal el codigo»: eso es tan vago que no se puede comprobar. Se
# mecanizan las dos formas concretas que produjeron los tres casos, y se dice cual es la que
# queda fuera.
_VERBO_CITADO = re.compile(r"`just ([a-z][a-z-]*)`")
_RECETA = re.compile(r"^([a-z][a-z-]*):", re.M)


def _verbos_que_existen(raiz):
    """Todas las recetas de este repo Y de sus plantillas: un doc puede citar las dos."""
    verbos = set()
    justfiles = [os.path.join(raiz, "justfile")]
    plantillas = os.path.join(raiz, "templates", "proyectos")
    if os.path.isdir(plantillas):
        for d in sorted(os.listdir(plantillas)):
            justfiles.append(os.path.join(plantillas, d, "justfile"))
    for j in justfiles:
        try:
            with open(j, encoding="utf-8") as fh:
                verbos |= set(_RECETA.findall(fh.read()))
        except OSError:
            continue
    return verbos


def comandos_inventados(raiz, docs):
    """Documentos que citan un `just <verbo>` que no existe en ningun justfile.

    Un doc puede citar verbos de las PLANTILLAS —`just build` es de un proyecto de node, no de
    aqui— y por eso se admiten los dos conjuntos. Lo que no se admite es un verbo que no exista
    en ninguna parte: eso es un comando que alguien leera y no podra ejecutar.

    Los documentos SELLADOS se saltan, con el mismo sello que ya usa el resto de este gate: un
    ADR narra una decision de su momento, y un blueprint describe un destino. Ninguno de los dos
    miente por citar algo que hoy no existe — mentiria un manual."""
    existen = _verbos_que_existen(raiz)
    if not existen:
        return []
    fuera = []
    for ruta in docs:
        try:
            with open(ruta, encoding="utf-8") as fh:
                texto = fh.read()
        except OSError:
            continue
        if sellado(texto):
            continue
        for verbo in sorted(set(_VERBO_CITADO.findall(texto))):
            if verbo not in existen:
                fuera.append((os.path.relpath(ruta, raiz), verbo))
    return fuera


def receta_publicada(raiz, docs):
    """La receta `ci:` que un documento publica tiene que ser la que el justfile ejecuta.

    EL CASO (2026-09-07): el README publicaba `ci: lint test secretos docs hechos hallazgos
    superficie doctor` y la real llevaba tres verbos mas. Quien lo leyera para saber que esta
    protegido se llevaba una idea falsa — y es la primera cosa que se lee del repo."""
    try:
        with open(os.path.join(raiz, "justfile"), encoding="utf-8") as fh:
            real = next((l.strip() for l in fh if l.startswith("ci:")), None)
    except OSError:
        return []
    if not real:
        return []
    fuera = []
    for ruta in docs:
        try:
            with open(ruta, encoding="utf-8") as fh:
                texto = fh.read()
        except OSError:
            continue
        if sellado(texto):
            continue
        for linea in texto.split("\n"):
            l = linea.strip()
            if l.startswith("ci:") and l != real:
                fuera.append((os.path.relpath(ruta, raiz), l, real))
    return fuera


def main():
    raiz = os.path.realpath(sys.argv[1]) if len(sys.argv) > 1 else \
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
    os.chdir(raiz)

    muertos = entidades_retiradas(raiz)
    rotas, muertas, sellados = [], [], 0

    for doc in docs_md(raiz):
        texto = leer(os.path.join(raiz, doc))
        if sellado(texto):
            sellados += 1
            continue
        if doc == REGISTRO:      # el registro nombra a los muertos por definición
            continue
        vivo = parte_viva(texto)
        rotas += rutas_del_repo_rotas(raiz, doc, vivo)
        muertas += citas_de_muertos(doc, vivo, muertos)

    hechos = hechos_declarados(raiz)
    total = len(rotas) + len(muertas) + len(hechos)

    _docs = list(docs_md(raiz))
    inventados = comandos_inventados(raiz, _docs)
    desfasadas = receta_publicada(raiz, _docs)

    print(f"verificar-hechos: {len(docs_md(raiz))} docs · {sellados} sellados como históricos · "
          f"{len(muertos)} entidades retiradas vigiladas")

    for doc, ruta in rotas:
        print(f"  RUTA INEXISTENTE  {doc} cita `{ruta}`, que no existe")
        print(f"                    (si va a existir, marcala: `{ruta}` (futuro))")
    for doc, muerto in muertas:
        print(f"  ENTIDAD RETIRADA  {doc} cita `{muerto}` en presente (ver {REGISTRO})")
    for _doc, msg in hechos:
        print(f"  HECHO CADUCADO    {msg}")
    for doc, verbo in inventados:
        print(f"  COMANDO QUE NO EXISTE  {doc} cita `just {verbo}` y no hay tal receta "
              f"ni aquí ni en las plantillas")
    for doc, publicada, real in desfasadas:
        print(f"  RECETA DESFASADA  {doc} publica una `ci:` que no es la real")
        print(f"                    publica: {publicada}")
        print(f"                    real:    {real}")

    total += len(inventados) + len(desfasadas)

    if total:
        print(f"\n  {total} afirmación(es) que ya no son ciertas. Corrígelas, o sella el "
              f"documento como histórico si narra un momento concreto.")
        return 1
    print("  todo cierto — rutas resueltas, nada retirado citado en presente, hechos vigentes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
