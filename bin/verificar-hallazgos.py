#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verificar-hallazgos — que el output de una herramienta IMPORTE.

    verificar-hallazgos.py [RAIZ]

EL FALLO QUE LO JUSTIFICA (2026-08-27). Se plantó una vulnerabilidad real
(`time 0.1.45` → RUSTSEC-2020-0071) en un proyecto recién creado con la plantilla de Rust:

    cargo audit         detecta RUSTSEC-2020-0071 · exit 1
    just audit          EXIT=0            ← el `-` delante se traga el código de salida
    methodos-doctor     ✅ BUILD-4 «audita dependencias contra vulnerabilidades»

La herramienta corre, encuentra la vulnerabilidad, la imprime — y el gate dice verde y el
medidor dice cumple. **Nadie lee el output.** De las 13 herramientas del mapa, 5 llegaban a
ejecutarse y solo 3 tenían su salida consumida.

Y no era un caso: era una CLASE. Recorriendo el cierre transitivo de `ci` con
`just --dump --dump-format json` aparecieron **cinco** verbos que ignoran su exit code, en
las tres plantillas y en dos repos vivos, con cero falsos positivos.

QUÉ HACE, Y POR QUÉ NO SE LIMITA A BLOQUEAR
-------------------------------------------
ADR-0009 fijó el eje: **un secreto bloquea porque lo causaste tú; una CVE avisa porque la
causó el mundo.** Ese eje sigue siendo correcto, pero estaba incompleto: decidía qué pasa el
día que el hallazgo aparece, y no decía nada del día siguiente. Un aviso que nadie lee es
exactamente igual de inútil que no haber corrido la herramienta.

Este gate extiende ese eje **al tiempo**: el mundo causó la aparición, pero **tú causas la
permanencia**. Un hallazgo nuevo no tumba nada; uno que llevas meses ignorando, sí.

LA MÁQUINA REGISTRA; LA PERSONA DECIDE. El script solo AÑADE entradas y rellena campos
derivados. Los estados los mueve una persona, a mano, y se ven en el diff — que es donde se
mira una decisión.
"""
import datetime
import json
import os
import subprocess
import sys

REGISTRO = "hallazgos.toml"

# Los plazos, por gravedad. El presupuesto (regla 6) es un dev solo, así que la unidad de
# trabajo es la semana y no el sprint.
#
# El 180 no es redondo por casualidad: coincide con la poda semestral de la regla 8. Así
# ninguna entrada sobrevive a su propia revisión — cuando toca preguntar «¿qué gate no ha
# fallado nunca?», los hallazgos más viejos vencen a la vez. Un mecanismo cuyo plazo más
# largo cae FUERA de su ciclo de revisión envejece a escondidas.
TOPES = {"critica": 7, "alta": 30, "media": 90, "baja": 180, "informativa": 180}

# Lista CERRADA. Un motivo libre es un campo donde escribir «lo miraré luego» para siempre;
# tres de estos cuatro se pueden contrastar contra la salida de la propia herramienta.
MOTIVOS = {
    "no-alcanzable": "el código vulnerable no se invoca desde este repo",
    "sin-parche": "no existe versión corregida todavía",
    "solo-dev": "la dependencia no entra en el artefacto de producción",
    "riesgo-aceptado": "se acepta a sabiendas, y por eso caduca antes",
}
ESTADOS = {"nuevo", "aceptado", "silenciado", "resuelto"}

V, R, A, N, D = "\033[32m", "\033[31m", "\033[33m", "\033[0m", "\033[2m"
if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
    V = R = A = N = D = ""


def hoy():
    """La fecha, inyectable para que la suite no dependa del calendario."""
    f = os.environ.get("METHODOS_HOY")
    if f:
        return datetime.date.fromisoformat(f)
    return datetime.date.today()


# ── (5) EL HUECO DE GATE: un verbo alcanzable desde `ci` que ignora su exit code ──────
def huecos_de_gate(raiz, raiz_verbo="ci"):
    """Verbos alcanzables desde `ci` con líneas que empiezan por `-`.

    DESCUBRIR, NO ENUMERAR, aplicado al propio gate. `just --dump --dump-format json` expone
    el cuerpo y las dependencias de cada receta; se recorre el cierre transitivo desde `ci` y
    se marca toda línea prefijada. Los `-` legítimos viven en `clean`, que `ci` no alcanza,
    así que el ruido es cero — medido sobre 3 plantillas y 2 repos vivos: 5 huecos, 0 falsos.

    Esto habría cazado el bug de `cargo audit` el día que nació, sin saber que existía."""
    try:
        r = subprocess.run(["just", "--dump", "--dump-format", "json"],
                           cwd=raiz, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return None                      # sin justfile o sin just: no es asunto de aquí
        recetas = (json.loads(r.stdout or "{}") or {}).get("recipes") or {}
    except (OSError, subprocess.SubprocessError, ValueError):
        return None

    if raiz_verbo not in recetas:
        return []
    vistos, cola, fallos = set(), [raiz_verbo], []
    while cola:
        v = cola.pop()
        if v in vistos or v not in recetas:
            continue
        vistos.add(v)
        for dep in recetas[v].get("dependencies") or []:
            nombre = dep.get("recipe") if isinstance(dep, dict) else dep
            if nombre:
                cola.append(nombre)
        continuada = False
        for linea in recetas[v].get("body") or []:
            texto = "".join(t if isinstance(t, str) else t.get("text", "")
                            for t in (linea if isinstance(linea, list) else [linea]))
            # UNA CONTINUACIÓN DE LÍNEA NO EMPIEZA UN COMANDO. `just` vuelca cada línea física
            # por separado, así que un comando partido dejaba el flag corto de la siguiente al
            # principio del texto: `cargo build \` / `  -q \` daba «HUECO DE GATE: -q». Y este
            # script lo copia `nuevo-proyecto.sh` a CADA proyecto nuevo, así que era un falso
            # positivo garantizado en cualquier receta multilínea — la clase que este repo dice
            # que mata los gates (2026-09-01, CR9-3).
            if continuada:
                continuada = texto.rstrip().endswith("\\")
                continue
            continuada = texto.rstrip().endswith("\\")
            # `just` acepta `@` y `-` EN CUALQUIER ORDEN: `-@cmd`, `@-cmd`. Mirar solo si la
            # línea empieza por `-` dejaba pasar `@-false`, o sea que EL DEFECTO QUE ORIGINÓ
            # ESTA PIEZA pasaba por su propio detector (2026-09-01, CR2-6).
            crudo = texto.lstrip().lstrip("@")
            if crudo.startswith("-") and not crudo.startswith("--"):
                fallos.append((v, texto.strip()))
    return fallos


# ── LOS RECOLECTORES: qué herramienta mira qué, DESCUBIERTO por el manifiesto ─────────
# No hay lista de ecosistemas: se mira qué manifiestos hay y se corre lo que corresponda.
# Añadir un ecosistema es añadir una entrada aquí, no tocar el flujo.
def _json_de(cmd, raiz, timeout=180):
    try:
        r = subprocess.run(cmd, cwd=raiz, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None                          # herramienta ausente: se degrada, no se cae
    # SE PRUEBA EL TEXTO ENTERO Y LUEGO LA ÚLTIMA LÍNEA. La versión anterior era código
    # muerto —`(A, B)[:1]` descartaba B— así que cualquier herramienta que imprima un aviso
    # ANTES del JSON se reportaba como AUSENTE en vez de como ejecutada. Y eso alimentaba el
    # agujero de `ya_no_esta`: «nadie miró» se confundía con «está arreglado» (CR2-15).
    for texto in (r.stdout, r.stderr):
        if not texto:
            continue
        candidatos = [texto]
        lineas = texto.strip().splitlines()
        if lineas:
            candidatos.append(lineas[-1])
        for candidato in candidatos:
            try:
                d = json.loads(candidato)
            except ValueError:
                continue
            # SOLO UN DICT. Los recolectores hacen `.get()` sobre esto, así que una lista
            # —`cargo audit` puede emitirla— reventaba el gate con un `AttributeError` y
            # tumbaba `just ci` entero, justo lo contrario de lo declarado («herramienta
            # ausente: se degrada, no se cae»). Y es la MISMA clase que `methodos-doctor`
            # arregló en CR-2, en este mismo PR (2026-09-01, CR7-4).
            return d if isinstance(d, dict) else None
    return None


def _cargo_audit(raiz):
    d = _json_de(["cargo", "audit", "--json"], raiz)
    if d is None:
        return None
    salida = []
    for v in ((d.get("vulnerabilities") or {}).get("list") or []):
        aviso = v.get("advisory") or {}
        cvss = ((v.get("versions") or {}).get("cvss") or aviso.get("cvss"))
        salida.append({
            "id": aviso.get("id") or "?",
            "paquete": (v.get("package") or {}).get("name") or "?",
            "gravedad": _gravedad(cvss, aviso.get("severity")),
            "titulo": (aviso.get("title") or "")[:120],
        })
    for clase in ("unmaintained", "unsound", "yanked"):
        for w in ((d.get("warnings") or {}).get(clase) or []):
            aviso = w.get("advisory") or {}
            salida.append({
                "id": aviso.get("id") or f"{clase}:{(w.get('package') or {}).get('name')}",
                "paquete": (w.get("package") or {}).get("name") or "?",
                "gravedad": "informativa",
                "titulo": (aviso.get("title") or clase)[:120],
            })
    return salida


def _pnpm_audit(raiz):
    d = _json_de(["pnpm", "audit", "--json"], raiz)
    if d is None:
        return None
    salida = []
    for clave, av in (d.get("advisories") or {}).items():
        salida.append({
            "id": f"GHSA:{av.get('github_advisory_id') or clave}",
            "paquete": av.get("module_name") or "?",
            "gravedad": _gravedad(None, av.get("severity")),
            "titulo": (av.get("title") or "")[:120],
        })
    return salida


# Cada recolector declara SU manifiesto, SUS lockfiles y el nombre de su herramienta. Los
# lockfiles importan: la version anterior derivaba el culpable como `package.json` ->
# `package-lock.json`, pero esta pila es pnpm-only, asi que `pnpm-lock.yaml` NO SE MIRABA
# NUNCA y una vulnerabilidad de JS traida por un bump de lock jamas se te atribuia. Y el
# bucle culpaba al manifiesto de TODOS los ecosistemas por un hallazgo de UNO (CR2-14).
def _npm_audit(raiz):
    """Los hallazgos de `npm audit --json`, que NO tiene la forma de `pnpm audit`.

    POR QUE EXISTE (2026-09-02, E-3). `cu-webhook` usa `package-lock.json`, el recolector de
    node solo sabia hablar `pnpm audit`, y por tanto su `just audit` no auditaba NADA. Medido
    el dia que se le adopto methodOS: **7 vulnerabilidades reales, 6 altas y 1 critica**, que
    llevaban ahi sin que nadie las viera. Es la misma clase «herramienta cuyo output no se
    lee» que originó esta pieza, un gestor de paquetes mas alla.

    UNA ENTRADA POR PAQUETE AFECTADO, no por aviso. npm agrupa asi —`metadata.total` cuenta
    paquetes— y un aviso de `undici` aparece en dieciseis `via` distintos: emitir por aviso
    multiplicaría el registro por cuatro sin decir nada nuevo. El numero que sale aqui es el
    mismo que imprime `npm audit`, y esa correspondencia importa: un registro que no cuadra
    con la herramienta que lo alimenta se deja de creer."""
    d = _json_de(["npm", "audit", "--json"], raiz)
    if d is None or "vulnerabilities" not in d:
        return None
    salida = []
    for nombre, v in (d.get("vulnerabilities") or {}).items():
        avisos = [a for a in (v.get("via") or []) if isinstance(a, dict)]
        indirecto = [a for a in (v.get("via") or []) if isinstance(a, str)]
        primero = avisos[0] if avisos else {}
        arreglo = v.get("fixAvailable")
        if isinstance(arreglo, dict):
            nota = f" · corregido en {arreglo.get('name')}@{arreglo.get('version')}"
            if arreglo.get("isSemVerMajor"):
                nota += " (cambio mayor)"
        elif arreglo:
            nota = " · hay arreglo con `npm audit fix`"
        else:
            nota = " · SIN arreglo disponible"
        titulo = primero.get("title") or (
            "afectado a traves de " + ", ".join(indirecto[:3]) if indirecto else "vulnerable")
        salida.append({
            "id": (f"GHSA:{primero.get('source')}" if primero.get("source")
                   else f"npm:{nombre}"),
            "paquete": nombre,
            "gravedad": _gravedad(None, v.get("severity")),
            "titulo": (titulo[:90] + nota),
        })
    return salida


def _audit_node(raiz):
    """El auditor de node, elegido POR EL LOCKFILE que el repo tiene commiteado.

    LA PRIMERA VERSION PROBABA `pnpm` Y LUEGO `npm`, quedandose con el primero que
    contestara. Parecia razonable y estaba mal, y se vio en el estreno: en `cu-webhook`
    —`package-lock.json`, sin pnpm-lock— `pnpm audit` **si responde**, porque `corepack`
    viene con Node 22 y lo shimea, y devuelve una lista VACIA. Cero hallazgos ganaban a los
    SIETE que `npm audit` tenia justo detras (6 altos y 1 critico, reales, en produccion).

    «El primero que conteste» es un criterio que suena a robustez y es adivinacion: la
    herramienta correcta la dice el lockfile, que es un hecho del repo y no del PATH
    (2026-09-02, E-3)."""
    if os.path.isfile(os.path.join(raiz, "pnpm-lock.yaml")):
        return _pnpm_audit(raiz)
    if os.path.isfile(os.path.join(raiz, "package-lock.json")):
        return _npm_audit(raiz)
    # Sin lockfile reconocible se prueban los dos, por si el repo usa otro gestor con
    # interfaz compatible. Aqui sí vale «el primero que conteste»: no hay hecho que consultar.
    for recolector in (_pnpm_audit, _npm_audit):
        h = recolector(raiz)
        if h:
            return h
    return None


def _govulncheck(raiz):
    """Los hallazgos de `govulncheck`, que emite UN FLUJO de objetos, no un documento.

    `_json_de` no sirve: hace `json.loads` sobre la salida entera y govulncheck escribe varios
    objetos JSON pegados. Medido sobre un módulo con `golang.org/x/text v0.3.7`:

        179 registros · 172 `osv` · 3 `finding` sobre 2 avisos

    SOLO LOS QUE TIENEN `finding`, Y ESA ES LA DECISIÓN QUE HACE ÚTIL ESTA PIEZA. Los 172
    `osv` son la porción de la base de datos que govulncheck CONSULTÓ —casi toda la stdlib—,
    no lo que te afecta. La primera versión los emitía todos: 171 entradas en el registro por
    un proyecto con UNA dependencia vulnerable. Un registro así no se lee, y un registro que
    no se lee es peor que no tenerlo, porque parece control (2026-09-02, E-2).

    LA GRAVEDAD SALE DE LA PROFUNDIDAD DE LA TRAZA, que es lo que govulncheck sabe y los
    demás auditores no:

        función en la traza  ->  tu código LLAMA al símbolo vulnerable      -> alta
        paquete en la traza  ->  lo importas, no consta que lo llames       -> media
        solo módulo          ->  está en el árbol de dependencias           -> baja

    Con el vector CVSS por delante si el aviso lo trae: la base de datos de Go a menudo no
    publica uno, y poner la misma gravedad a todo esconde lo que sí se llama detrás de lo que
    no."""
    try:
        r = subprocess.run(["govulncheck", "-format", "json", "./..."],
                           cwd=raiz, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.SubprocessError):
        return None                          # herramienta ausente: se degrada, no se cae
    texto = r.stdout or ""
    dec, i, registros = json.JSONDecoder(), 0, []
    while i < len(texto):
        while i < len(texto) and texto[i].isspace():
            i += 1
        if i >= len(texto):
            break
        try:
            obj, fin = dec.raw_decode(texto, i)
        except ValueError:
            break
        registros.append(obj)
        i = fin
    if not registros:
        return None

    avisos, hallado = {}, {}
    for reg in registros:
        if "osv" in reg:
            avisos[(reg["osv"] or {}).get("id") or "?"] = reg["osv"] or {}
        elif "finding" in reg:
            f = reg["finding"] or {}
            vid = f.get("osv") or "?"
            traza = f.get("trace") or []
            # 3 = se llama la función · 2 = se importa el paquete · 1 = está en el árbol
            hondo = max([3 if (t or {}).get("function") else
                         2 if (t or {}).get("package") else 1 for t in traza] or [1])
            previo = hallado.get(vid) or {"hondo": 0, "arreglado": None, "modulo": None}
            if hondo >= previo["hondo"]:
                previo = {"hondo": hondo,
                          "arreglado": f.get("fixed_version") or previo["arreglado"],
                          "modulo": next((t.get("module") for t in traza if t.get("module")),
                                         previo["modulo"])}
            hallado[vid] = previo

    POR_HONDURA = {3: "alta", 2: "media", 1: "baja"}
    ALCANCE = {3: "se llama la función vulnerable",
               2: "se importa el paquete afectado",
               1: "solo está en el árbol de dependencias"}
    salida = []
    for vid, datos in sorted(hallado.items()):
        osv = avisos.get(vid) or {}
        vector = next((sv.get("score") for sv in (osv.get("severity") or [])
                       if str(sv.get("type", "")).startswith("CVSS")), None)
        gravedad = _gravedad(vector, None) if vector else POR_HONDURA[datos["hondo"]]
        arreglo = f" · corregido en {datos['arreglado']}" if datos["arreglado"] else ""
        salida.append({
            "id": vid,
            "paquete": datos["modulo"] or "?",
            "gravedad": gravedad,
            "titulo": ((osv.get("summary") or osv.get("details") or "")[:90]
                       + f"  [{ALCANCE[datos['hondo']]}{arreglo}]"),
        })
    return salida


RECOLECTORES = [
    ("Cargo.toml", ["Cargo.lock"], "cargo-audit", _cargo_audit),
    ("package.json", ["pnpm-lock.yaml", "package-lock.json", "yarn.lock", "bun.lockb"],
     "pnpm-audit o npm-audit", _audit_node),
    # AÑADIDO CON LA PLANTILLA DE GO (2026-09-02, E-2). Sin él, un proyecto de Go nacía con
    # un verbo `audit` en su justfile que no auditaba NADA: exactamente la clase «herramienta
    # cuyo output no se lee» que este fichero existe para cerrar.
    ("go.mod", ["go.sum"], "govulncheck", _govulncheck),
]


# El peso de cada métrica del vector CVSS 3.1 que de verdad mueve la puntuación base. No se
# calcula la fórmula entera —no hace falta para elegir un plazo— sino la clase.
_IMPACTO = {"H": 3, "L": 1, "N": 0}


def _de_vector_cvss(vector):
    """La gravedad a partir de un VECTOR `CVSS:3.1/AV:N/...`, que es lo que emite cargo-audit.

    `float(cvss)` reventaba con el vector y TODO hallazgo de RUSTSEC caía a `informativa`:
    180 días de plazo para una vulnerabilidad crítica, y el escalado `critica: 7 / alta: 30`
    MUERTO PARA TODO EL ECOSISTEMA RUST — incluido el RUSTSEC-2020-0071 que motivó la pieza
    (2026-09-01, CR4-7)."""
    m = dict(p.split(":", 1) for p in vector.split("/")[1:] if ":" in p)
    impacto = sum(_IMPACTO.get(m.get(k, "N"), 0) for k in ("C", "I", "A"))
    remoto = m.get("AV") == "N"
    sin_privilegios = m.get("PR") == "N"
    sin_usuario = m.get("UI") == "N"
    # NO ES UNA IMPLEMENTACIÓN DE CVSS, y no finge serlo: es una heurística para elegir un
    # PLAZO. Calibrada contra los cuatro casos canónicos, y en la dirección conservadora —
    # ante la duda, plazo más corto, porque acortar siempre se puede y alargar no.
    if impacto >= 8 and remoto and sin_privilegios and sin_usuario:
        return "critica"          # C:H/I:H/A:H sin barreras
    if remoto and impacto >= 3:
        return "alta"             # explotable en red con impacto real
    if impacto >= 2:
        return "media"
    if impacto >= 1:
        return "baja"
    return "informativa"


def _gravedad(cvss, etiqueta):
    """CVSS si lo hay; si no, la etiqueta de la herramienta. Sin CVSS ni etiqueta: informativa."""
    if isinstance(cvss, str) and cvss.upper().startswith("CVSS:"):
        return _de_vector_cvss(cvss)
    try:
        n = float(cvss)
        return ("critica" if n >= 9 else "alta" if n >= 7 else
                "media" if n >= 4 else "baja")
    except (TypeError, ValueError):
        pass
    e = (etiqueta or "").lower()
    return {"critical": "critica", "high": "alta", "moderate": "media",
            "medium": "media", "low": "baja"}.get(e, "informativa")


def recolectar(raiz):
    """Los hallazgos de hoy, y qué herramientas no se pudieron correr.

    Devuelve (hallazgos, ausentes, corrieron). `corrieron` importa tanto como los otros
    dos: sin él no se distingue «la herramienta miró y ya no lo ve» —está arreglado— de
    «nadie miró», y confundirlos convierte desinstalar la herramienta en la forma barata de
    silenciar un vencimiento. Una herramienta ausente NO es un fallo: se declara, y el
    resto del gate sigue funcionando contra el fichero y la fecha. Es el mismo patrón que el
    doctor con `gh`: se degrada a ⊘, nunca a error."""
    hallazgos, ausentes, corrieron = {}, [], []
    for manifiesto, _locks, nombre, fn in RECOLECTORES:
        if not os.path.isfile(os.path.join(raiz, manifiesto)):
            continue
        res = fn(raiz)
        if res is None:
            ausentes.append(nombre)
            continue
        corrieron.append(nombre)
        for h in res:
            hallazgos[h["id"]] = dict(h, origen=nombre)
    return hallazgos, ausentes, corrieron


# ── EL REGISTRO ──────────────────────────────────────────────────────────────────────
SIN_TOMLLIB = object()


def leer_toml(texto):
    """El registro parseado, `None` si NO PARSEA, o `SIN_TOMLLIB` si falta el módulo.

    TRES RESPUESTAS, NO DOS. Con `None` para las dos cosas, cualquier intérprete anterior a
    Python 3.11 producía «REGISTRO ILEGIBLE: está commiteado y no parsea», el gate salía 1 y
    la rama `registro_ilegible` se negaba además a escribir: rojo permanente acusando a un
    fichero que está perfecto.

    Y no es teórico: `bin/nuevo-proyecto.sh` copia este script a `bin/` de CADA proyecto
    nuevo —rust, node, dioxus—, donde el `python3` lo fija el devshell de ESE repo y no éste.
    Un gate que miente sobre la causa es peor que uno que falta, porque manda a arreglar lo
    que no está roto (2026-09-01, CR11-4)."""
    try:
        import tomllib
    except ImportError:
        return SIN_TOMLLIB
    try:
        return (tomllib.loads(texto) or {}).get("hallazgo") or {}
    except Exception:
        return None


def registro_commiteado(raiz):
    """El registro tal como está EN HEAD, no en el árbol de trabajo.

    La evaluación va contra lo commiteado y la escritura al árbol: así local y CI corren el
    MISMO código sin un modo `--ci`. En local te aparece sucio en `git status` después de un
    `just ci` que ibas a correr igualmente (regla 3: no hay nada que recordar invocar); en CI
    se escribe sobre un checkout que se tira, y la decisión es idéntica."""
    try:
        r = subprocess.run(["git", "-C", raiz, "show", f"HEAD:{REGISTRO}"],
                           capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            return {}
        leido = leer_toml(r.stdout)
        if leido is SIN_TOMLLIB:
            # SE DEVUELVE EL CENTINELA, NO SE SALE. `raise SystemExit(0)` aquí terminaba el
            # proceso ANTES de imprimir nada, y para cuando se llega a esta función
            # `huecos_de_gate` YA encontró sus fallos —que no tienen nada que ver con TOML—.
            # Medido en un repo con `-cargo test` en el justfile: **rc=1 con tomllib, rc=0
            # sin él**, y la línea `HUECO DE GATE` ni se llegaba a imprimir.
            #
            # Lo más caro: la ronda 13 arregló ESTA MISMA avería en el lector del árbol de
            # trabajo, doscientas líneas más abajo, y dejó ésta —que dispara primero— intacta.
            # El arreglo quedó inalcanzable y el gate siguió poniéndose verde por falta de un
            # módulo de la stdlib. Arreglar la segunda aparición y no la primera es la forma
            # más silenciosa de no arreglar nada (2026-09-01, CR14-1).
            return SIN_TOMLLIB
        return leido
    except (OSError, subprocess.SubprocessError):
        return {}


def fecha_commit(raiz, ruta):
    try:
        r = subprocess.run(["git", "-C", raiz, "log", "-1", "--format=%ct", "--", ruta],
                           capture_output=True, text=True, timeout=10)
        s = (r.stdout or "").strip()
        return int(s) if s.isdigit() else None
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def escribir(raiz, entradas):
    """Emisor de ~20 líneas: la forma es fija y solo se AÑADEN bloques."""
    lineas = [
        "# hallazgos.toml — el registro de hallazgos de este repositorio.",
        "#",
        "# Lo ESCRIBE la máquina (`just ci`): solo entradas nuevas y solo campos derivados.",
        "# Los ESTADOS los mueve una PERSONA, a mano, y se ven en el diff — que es donde se",
        "# mira una decisión. Lo VIGILA templates/bin/verificar-hallazgos.py, en el mismo gate.",
        "#",
        "# Un hallazgo nuevo NO tumba nada el día que aparece: lo causó el mundo (ADR-0009).",
        "# Uno VENCIDO sí: la aparición la causó el mundo, la permanencia la causas tú.",
        "",
    ]
    for hid in sorted(entradas):
        e = entradas[hid]
        lineas.append(f'[hallazgo."{hid}"]')
        # LAS CLAVES DESCONOCIDAS SE CONSERVAN. La lista fija borraba en silencio cualquier
        # campo que una persona hubiera añadido a mano —un `enlace` al advisory, por ejemplo—
        # al reescribir el fichero. QUINTA aparición de «la máquina rompiendo lo que la
        # persona firmó» (CR2-5, CR3-3, CR4-6, CR6-3), y la única que no necesita ni un error
        # para ocurrir: basta con correr el gate (2026-09-01, CR7-5).
        conocidas = ("paquete", "gravedad", "titulo", "origen", "visto", "vence", "estado",
                     "quien", "motivo", "nota")
        for k in list(conocidas) + sorted(k for k in e if k not in conocidas):
            if e.get(k) not in (None, ""):
                # SE ESCAPA. Interpolar sin escapar hacía que un `titulo` de advisory con una
                # comilla o una barra produjera un fichero que `leer_toml` devuelve como
                # `None` — y ahí caía en el fallo de arriba: registro ilegible, todos los
                # plazos reiniciados y las decisiones humanas (`estado`, `quien`, `motivo`)
                # sobrescritas. La máquina rompiendo lo que la persona firmó (CR2-5).
                valor = str(e[k]).replace("\\", "\\\\").replace('"', '\\"')
                valor = valor.replace("\n", " ").replace("\r", " ")
                lineas.append(f'{k} = "{valor}"')
        lineas.append("")
    with open(os.path.join(raiz, REGISTRO), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lineas))


def main():
    raiz = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.getcwd()
    fallos, avisos = [], []
    print(f"{D}verificar-hallazgos:{N} {os.path.basename(raiz)}")

    # ── (5) EL HUECO DE GATE ─────────────────────────────────────────────────────────
    # Va primero porque es el defecto que originó todo esto, y porque no depende de que
    # ninguna herramienta esté instalada: se lee del propio justfile.
    huecos = huecos_de_gate(raiz)
    if huecos is None:
        print(f"  {D}sin justfile legible: no se miran huecos de gate{N}")
    for verbo, linea in (huecos or []):
        fallos.append(("HUECO DE GATE", f"`{verbo}` ignora su exit code: {linea[:60]}"))

    # ── el registro y los hallazgos de hoy ───────────────────────────────────────────
    commiteado = registro_commiteado(raiz)
    if commiteado is SIN_TOMLLIB:
        # Ni se evalúa el registro ni se escribe, PERO lo ya medido se informa y bloquea.
        sys.stderr.write("verificar-hallazgos: este python3 no trae `tomllib` (< 3.11); "
                         "el registro no se evalúa y NO se toca\n")
        commiteado, sin_toml = {}, True
    else:
        sin_toml = False
    # SIN `tomllib` TAMBIÉN ES ILEGIBLE, y por la misma razón: no se puede saber qué hay
    # dentro, así que no se pisa. Poner esto ANTES de la línea siguiente la dejaba sin efecto.
    registro_ilegible = sin_toml or commiteado is None
    if commiteado is None:
        # UN REGISTRO ILEGIBLE NO ES UN REGISTRO VACÍO. Tratarlo como vacío hacía que UNA
        # LÍNEA MALA en el único fichero que edita una persona a mano desactivara TODOS los
        # vencimientos, y el gate salía 0 diciendo «sin hallazgos vencidos». Es la forma más
        # barata que existe de apagar este mecanismo, y no hace falta mala fe: basta una
        # coma (2026-09-01, CR2-4).
        fallos.append(("REGISTRO ILEGIBLE",
                       f"{REGISTRO} está commiteado y no parsea: no se puede saber qué "
                       f"venció, así que no se da por bueno"))
        commiteado = {}
    hallazgos, ausentes, corrieron = recolectar(raiz)
    for h in ausentes:
        print(f"  {D}⊘ {h} no se pudo correr: se degrada, no se cae{N}")

    hoy_ = hoy()
    # COPIA PROFUNDA. `dict(commiteado)` es superficial, así que el `update` de abajo mutaba
    # los mismos dicts que el bucle de evaluación recorre después: el tope se calculaba con la
    # gravedad DE HOY, no con la registrada. Un advisory reclasificado de `baja` (180 días) a
    # `critica` (7) hacía fallar el gate con «vence 180 días después de verse; el tope para
    # `critica` es 7» — culpando a la persona por un plazo QUE ESCRIBIÓ LA MÁQUINA, y citando
    # un tope que no existía cuando la entrada nació (2026-09-01, CR3-6).
    import copy
    entradas = copy.deepcopy(commiteado)
    nuevos = []
    for hid, h in sorted(hallazgos.items()):
        if hid in entradas:
            antes = entradas[hid].get("gravedad")
            entradas[hid].update({k: h[k] for k in ("paquete", "gravedad", "titulo", "origen")
                                  if k in h})
            # SI CAMBIA LA GRAVEDAD, EL PLAZO SE RECALCULA. Refrescarla sin tocar `vence`
            # dejaba una entrada reclasificada de `baja` a `critica` con su plazo de 180 días,
            # y la pasada SIGUIENTE fallaba con «vence 180 días después de verse; el tope para
            # critica es 7» — culpando a la persona por un plazo QUE ESCRIBIÓ LA MÁQUINA
            # (2026-09-01, CR4-8).
            if antes and antes != entradas[hid].get("gravedad"):
                try:
                    base = datetime.date.fromisoformat(entradas[hid].get("visto") or "")
                except ValueError:
                    base = hoy_
                nuevo_tope = TOPES.get(entradas[hid]["gravedad"], 180)
                entradas[hid]["vence"] = (base + datetime.timedelta(days=nuevo_tope)).isoformat()
            continue
        plazo = TOPES.get(h["gravedad"], 180)
        entradas[hid] = dict(h, visto=hoy_.isoformat(), estado="nuevo",
                             vence=(hoy_ + datetime.timedelta(days=plazo)).isoformat())
        nuevos.append(hid)

    # ── (1) VENCIDO · (3) MENTIRA · (4) SILENCIO MAL FUNDADO ─────────────────────────
    for hid, e in sorted(commiteado.items()):
        estado = (e.get("estado") or "nuevo").lower()
        if estado not in ESTADOS:
            fallos.append(("ESTADO INVÁLIDO", f"{hid}: «{estado}» no es uno de {sorted(ESTADOS)}"))
            continue
        if estado == "resuelto":
            # (3) LA MENTIRA. Lo escrito dejó de ser cierto: la herramienta lo sigue viendo.
            if hid in hallazgos:
                fallos.append(("SIGUE VIVO", f"{hid} está marcado `resuelto` y la herramienta "
                                             f"lo sigue reportando"))
            continue
        vence = e.get("vence") or ""
        try:
            caduca = datetime.date.fromisoformat(vence)
        except ValueError:
            fallos.append(("SIN PLAZO", f"{hid}: `vence` ausente o ilegible"))
            continue
        # (4) EL SILENCIO MAL FUNDADO. Un silencio sin condiciones es un `-` delante del
        # verbo con otra sintaxis. Se exige quién y por qué, y el plazo tiene tope.
        if estado in ("aceptado", "silenciado"):
            if not e.get("quien"):
                fallos.append(("SIN DUEÑO", f"{hid} está `{estado}` y nadie lo firma"))
            if estado == "silenciado" and (e.get("motivo") or "") not in MOTIVOS:
                fallos.append(("MOTIVO NO VÁLIDO",
                               f"{hid}: «{e.get('motivo') or 'ninguno'}» no está en "
                               f"{sorted(MOTIVOS)}"))
        tope = TOPES.get((e.get("gravedad") or "informativa").lower(), 180)
        try:
            visto = datetime.date.fromisoformat(e.get("visto") or "")
            if (caduca - visto).days > tope:
                # ACORTAR SE PUEDE, ALARGAR NO. El script recalcula el tope en cada pasada.
                fallos.append(("PLAZO ESTIRADO",
                               f"{hid} vence {(caduca - visto).days} días después de verse; "
                               f"el tope para `{e.get('gravedad')}` es {tope}"))
        except ValueError:
            pass
        # (1) VENCIDO. El caso que este mecanismo existe para cazar: el mundo causó la
        # aparición, **tú causas la permanencia**.
        #
        # Dispara AUNQUE LA HERRAMIENTA NO HAYA PODIDO CORRER, y esa es la decisión que hace
        # que el mecanismo no se pueda apagar: si bastara con que `cargo audit` no estuviera
        # instalado para que un vencimiento dejara de bloquear, desinstalarlo sería la forma
        # barata de silenciarlo todo — el `-` delante del verbo otra vez, con más pasos.
        # La única excusa válida es que la herramienta SÍ corrió y ya no lo reporta: entonces
        # está arreglado, y lo que falta es mover el estado a `resuelto`.
        # «Arreglado» solo si ALGUIEN MIRÓ y ya no lo ve. Sin manifiesto, o con la
        # herramienta ausente, nadie miró: entonces el vencimiento manda.
        # POR ECOSISTEMA, NO GLOBAL. `bool(corrieron)` daba por «arreglado» un hallazgo de
        # Rust porque habia corrido `pnpm audit`: bastaba anadir un `package.json` a un repo
        # con `Cargo.toml` para silenciar los vencimientos de cargo-audit — el agujero que el
        # comentario de justo arriba dice cerrar (2026-09-01, CR2-8).
        #
        # Una entrada sin `origen` es de antes de este campo: se exige que TODOS los
        # recolectores aplicables hayan corrido, que es la lectura conservadora.
        origen = e.get("origen")
        if origen:
            miro_el_suyo = origen in corrieron
        else:
            aplicables = {n for m, _l, n, _f in RECOLECTORES
                          if os.path.isfile(os.path.join(raiz, m))}
            miro_el_suyo = bool(aplicables) and aplicables <= set(corrieron)
        ya_no_esta = miro_el_suyo and hid not in hallazgos
        if caduca < hoy_ and not ya_no_esta:
            fallos.append(("VENCIDO", f"{hid} venció el {vence} y sigue abierto "
                                      f"({e.get('gravedad')}, {e.get('paquete')})"))
        elif ya_no_esta:
            avisos.append(f"{hid} ya no lo reporta la herramienta: muévelo a `resuelto`")

    # ── (2) SIN REGISTRAR Y TOCASTE EL MANIFIESTO ────────────────────────────────────
    # No bloquea el día que aparece —lo causó el mundo, ADR-0009— pero sí si lo traes tú:
    # si el manifiesto se commiteó DESPUÉS que el registro, el hallazgo está en tu diff.
    sin_registrar = [h for h in nuevos]
    if sin_registrar:
        t_reg = fecha_commit(raiz, REGISTRO)
        # SOLO LOS FICHEROS DEL ECOSISTEMA QUE PRODUJO EL HALLAZGO. Culpar al manifiesto de
        # todos era atribuir a tu diff de Rust un aviso de npm, y viceversa (CR2-14).
        origenes = {entradas[h].get("origen") for h in sin_registrar} - {None}
        culpables = []
        for manifiesto, locks, nombre, _f in RECOLECTORES:
            if origenes and nombre not in origenes:
                continue
            for f in [manifiesto, *locks]:
                t_man = fecha_commit(raiz, f)
                # SI EL REGISTRO NUNCA SE COMMITEÓ, NADIE ES CULPABLE. Con `t_reg is None`
                # todo manifiesto salía culpable, así que adoptar el mecanismo en un repo que
                # ya arrastra una vulnerabilidad fallaba con «se commiteó después que
                # hallazgos.toml: están en tu diff» — aunque el manifiesto llevara meses ahí y
                # el hallazgo no estuviera en el diff. Contradice el eje del propio fichero:
                # un hallazgo nuevo no tumba nada el día que aparece (2026-09-01, CR3-7).
                if t_man and t_reg is not None and t_man > t_reg:
                    culpables.append(f)
        if culpables:
            fallos.append(("SIN REGISTRAR", f"{len(sin_registrar)} hallazgo(s) nuevo(s) y "
                                            f"{', '.join(sorted(set(culpables)))} se commiteó "
                                            f"después que {REGISTRO}: están en tu diff"))
        else:
            avisos.append(f"{len(sin_registrar)} hallazgo(s) nuevo(s) registrados con su plazo: "
                          f"{', '.join(sin_registrar[:3])}")

    # NO SE PISA LO QUE LA PERSONA ACABA DE ESCRIBIR. La evaluación va contra HEAD —para que
    # local y CI decidan igual— pero la ESCRITURA iba al árbol de trabajo sin mirar qué había
    # allí: alguien marcaba una entrada `silenciado` con su `quien` y su `motivo`, corría
    # `just ci`, y el fichero volvía a `nuevo` con los dos campos borrados. Sin aviso.
    #
    # Y ese es EXACTAMENTE el flujo documentado (editar a mano → correr el gate → commitear),
    # o sea el mismo «la máquina rompiendo lo que la persona firmó» que CR2-5 decía cerrar
    # (2026-09-01, CR3-3).
    #
    # Los campos de la persona ganan siempre; los derivados los refresca la máquina.
    en_el_arbol = {}
    try:
        with open(os.path.join(raiz, REGISTRO), encoding="utf-8") as fh:
            # `or {}` NO SIRVE CON UN CENTINELA: `SIN_TOMLLIB` es un `object()`, y un
            # `object()` es VERDADERO, así que el `or` no disparaba y la línea siguiente
            # llamaba `.items()` sobre él. `AttributeError`, traceback, gate rojo — y justo
            # en el escenario para el que se escribió el centinela: python sin `tomllib`, con
            # el registro ya en el árbol y todavía no en HEAD. O sea la SEGUNDA corrida de
            # cualquier proyecto recién creado por `nuevo-proyecto.sh`, que es donde este
            # script vive de verdad.
            #
            # Un centinela no se comprueba con la veracidad; se comprueba con `is`
            # (2026-09-01, CR12-1).
            _leido = leer_toml(fh.read())
            if _leido is SIN_TOMLLIB:
                # NI SE EVALÚA NI SE ESCRIBE, PERO TAMPOCO SE PERDONA LO YA MEDIDO. Seguir
                # con `{}` reemplazaba el fichero entero, borrando los estados que puso una
                # persona —`aceptado`, `silenciado`, su dueño, su motivo—. Y salir 0 aquí era
                # peor todavía: para cuando se llega a esta línea, `huecos_de_gate` YA
                # encontró sus fallos, que no tienen nada que ver con TOML. Medido: un
                # `justfile` con `-cargo test` daba `rc=1` con tomllib y `rc=0` sin él. Un
                # gate que se pone verde porque falta un módulo de la stdlib miente en la
                # dirección más cara (2026-09-01, CR13-3 y CR13-4).
                sys.stderr.write("verificar-hallazgos: este python3 no trae `tomllib` "
                                 "(< 3.11); el registro no se evalúa y NO se toca\n")
                registro_ilegible = True
                en_el_arbol = {}
            elif _leido is None:
                # UN REGISTRO DEL ÁRBOL QUE NO PARSEA TAMPOCO SE PISA. `registro_ilegible`
                # solo cubre el de HEAD, así que una comilla sin cerrar en una `nota` escrita
                # a mano llegaba aquí como `{}` y la escritura la borraba sin decir nada. Es
                # la clase «la máquina rompiendo lo que la persona firmó» (CR4-6), un fichero
                # más allá (2026-09-01, CR13-4).
                fallos.append(("REGISTRO ILEGIBLE EN EL ÁRBOL",
                               f"{REGISTRO} está en el árbol y no parsea: no se toca, "
                               f"porque reescribirlo borraría lo que haya escrito una persona"))
                registro_ilegible = True
                en_el_arbol = {}
            else:
                en_el_arbol = _leido
    except OSError:
        pass
    DE_LA_PERSONA = ("estado", "quien", "motivo", "nota")
    for hid, e in en_el_arbol.items():
        destino = entradas.setdefault(hid, dict(e))
        for k in DE_LA_PERSONA:
            if e.get(k) not in (None, ""):
                destino[k] = e[k]
        # `vence` NO ESTÁ EN LA LISTA DE ARRIBA, y la razón es sutil: el valor del árbol de
        # trabajo suele ser el que escribió LA MÁQUINA en la pasada anterior, no una decisión
        # humana. Conservarlo a ciegas pisaba el recálculo por reclasificación de gravedad y
        # RECREABA CR4-8: la entrada quedaba `critica` con su plazo viejo de 180 días y la
        # pasada siguiente culpaba a la persona por una fecha que escribió la máquina
        # (2026-09-01, CR5-4).
        #
        # Se aplica la regla que ya rige el resto del fichero: ACORTAR SE PUEDE, ALARGAR NO.
        # SIN `vence` EN EL COMMITEADO, EL DE LA PERSONA VALE. Exigir que el destino ya
        # tuviera uno descartaba el plazo que alguien acababa de escribir a mano para reparar
        # un `SIN PLAZO`: la corrección se perdía y el gate volvía a fallar por lo mismo.
        # Cuarta aparición de «la máquina rompiendo lo que la persona firmó» (CR6-3).
        if e.get("vence") and (not destino.get("vence") or e["vence"] < destino["vence"]):
            destino["vence"] = e["vence"]

    # CON EL REGISTRO ILEGIBLE NO SE ESCRIBE. Si el commiteado no parsea, `commiteado` y
    # `en_el_arbol` valen `{}` los dos, y escribir igual SOBRESCRIBÍA el fichero con las
    # entradas de hoy: se perdían el `estado`, el `quien`, el `motivo` y la `nota` de la
    # persona **y el fichero que necesitaba para repararlo**. Es la tercera vez que aparece
    # «la máquina rompiendo lo que la persona firmó» —CR2-5 y CR3-3 decían cerrarla— y la
    # primera con pérdida de datos irreversible (2026-09-01, CR4-6).
    if registro_ilegible:
        print(f"  {A}no se reescribe {REGISTRO}{N}: no se puede leer, y sobrescribirlo "
              f"perdería lo que haya firmado una persona")
    elif hallazgos or commiteado or en_el_arbol:
        escribir(raiz, entradas)

    # ── informe ──────────────────────────────────────────────────────────────────────
    for a in avisos:
        print(f"  {A}aviso{N} {a}  {D}(no bloquea: lo causó el mundo){N}")
    for clase, detalle in fallos:
        print(f"  {R}{clase}{N} {detalle}")
    if not fallos:
        print(f"  {V}sin hallazgos vencidos, ni silencios mal fundados, ni huecos de gate{N}")
    else:
        print(f"\n  {R}{len(fallos)} problema(s){N} — un hallazgo ignorado bloquea; uno nuevo, no.")
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
