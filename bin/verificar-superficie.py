#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verificar-superficie — que las banderas que el repo USA existan de verdad.

    verificar-superficie.py [RUTA]        # verifica y actualiza el registro
    verificar-superficie.py --mostrar     # imprime la superficie, para leerla

POR QUE EXISTE, Y POR QUE NO ES «EMBEBER LA DOCUMENTACION» (2026-09-02)
    La tarea nacio de un problema real y bien diagnosticado: **la IA inventa banderas,
    variables y argumentos que no existen**. La solucion obvia —copiar la documentacion de
    cada herramienta al repo— no lo resuelve, y conviene decir por que antes de no hacerla:

      · es enorme y se queda vieja el dia que se escribe;
      · nadie la lee en el instante en que se inventa algo;
      · y sobre todo, NO AVISA. Un documento no puede decirte que acabas de usar una bandera
        que no existe.

    Se midieron las seis alucinaciones de una sola sesion de trabajo (2026-09-01/02):

        METHODOS_RAIZ                    variable inexistente
        permissions: administration:read scope inexistente — tumbo un workflow entero
        «GitHub prohibe gh pr review --comment»   falso: solo prohibe --approve
        json.loads sobre govulncheck     es un FLUJO de objetos, no un documento
        gofmt -l sale 1 al fallar        imprime y sale 0
        pnpm audit no responde con npm   corepack lo shimea y responde vacio

    **Las seis son superficie de CLI, y las seis se cazaron EJECUTANDO la herramienta.** Eso
    es lo que esta pieza automatiza: no guarda prosa, guarda LA SUPERFICIE REAL de lo que hay
    instalado, y falla cuando el repo usa algo que esa superficie no declara.

LAS DOS PREGUNTAS QUE PLANTEO RENE, CONTESTADAS
    · ¿POR PROYECTO O GLOBAL? Las dos cosas, y no es una evasiva: el MECANISMO es global
      —vive aqui y el scaffold lo reparte, como `verificar-hallazgos.py`— y el REGISTRO es
      por proyecto, porque las versiones las fija el `flake.lock` de cada repo. Un registro
      global describiria versiones que el proyecto no usa, que es peor que no tenerlo.
    · ¿SE ACTUALIZA SOLA? Si, y sin proceso aparte: se recaptura en cada `just ci` desde las
      herramientas INSTALADAS. Si una subio de version, el registro lo refleja en el diff;
      si una bandera desaparecio y el repo la usa, el gate FALLA con su nombre.

LA ASIMETRIA, que es la misma de ADR-0009
    Una bandera NUEVA no bloquea: la anadio el mundo. Una bandera que el repo USA y que la
    herramienta YA NO declara si bloquea: esa la causas tu. Y una bandera que nunca existio,
    tambien — que es el caso de la alucinacion.

CERO dependencias fuera de stdlib. Sin las herramientas instaladas degrada a ⊘, nunca a error.
"""
import os
import re
import subprocess
import sys

REGISTRO = "superficie.toml"
AQUI = os.path.dirname(os.path.realpath(__file__))
V, R, A, N, D = "\033[32m", "\033[31m", "\033[33m", "\033[0m", "\033[2m"
if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
    V = R = A = N = D = ""

# Interpretes: cuando les sigue un script, las banderas son DEL SCRIPT y su superficie no
# esta en el `--help` del interprete. Medido: `python3 verificar-hechos.py --proponer` hacia
# que se buscara `--proponer` en el help de python3, donde por supuesto no esta.
_INTERPRETES = {"python3", "python", "node", "bash", "sh", "ruby", "perl", "deno", "bun"}
# Lo que NO es una herramienta cuya superficie tenga sentido capturar.
_NO_HERRAMIENTA = {"echo", "cd", "export", "set", "printf", "true", "false", "exit", "read",
                   "then", "else", "fi", "do", "done", "case", "esac", "function", "local"}


def _lexer():
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "lexer_shell", os.path.join(AQUI, "lexer-shell.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except BaseException:
        return None


_LX = _lexer()


def fuentes(raiz):
    """Donde vive lo que el repo EJECUTA de verdad: su justfile y sus workflows.

    No se lee el codigo fuente: un `subprocess.run([...])` dentro de un script es una
    invocacion mas dificil de atribuir y mucho mas ruidosa. El justfile es, por diseno de
    este estandar, el sitio donde vive el pipeline — asi que es donde estan los comandos que
    importan."""
    textos = [lee(raiz, "justfile")]
    d = os.path.join(raiz, ".github", "workflows")
    if os.path.isdir(d):
        for n in sorted(os.listdir(d)):
            if n.endswith((".yml", ".yaml")):
                textos.append(lee(raiz, ".github", "workflows", n))
    return "\n".join(t for t in textos if t)


def lee(raiz, *partes):
    try:
        with open(os.path.join(raiz, *partes), encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except OSError:
        return ""


def usos(texto):
    """`{ "gh pr review": {"--comment", ...} }` — lo que el repo usa, por verbo.

    SE TROCEA CON EL LEXER DEL REPO, no con una regex. La primera version partia por lineas
    y atribuia mal: `bash --ci` (era `just ci` dentro de la linea) y `python3 --proponer` (la
    bandera es del script). El lexer ya sabe de quien es cada bandera —tiene una funcion que
    se llama asi— y usarlo evita tener dos criterios distintos en el mismo repo."""
    salida = {}
    if _LX is None:
        return salida
    for linea in texto.split("\n"):
        # `linea` y no `l`: la ele minuscula se confunde con el uno, y el linter de un repo
        # consumidor lo marco (E741) al adoptar este fichero (2026-09-02).
        limpia = linea.strip().lstrip("-@")
        # `run: |` y amigos: se queda el contenido, no la clave de YAML.
        limpia = re.sub(r"^\s*-?\s*(run|shell)\s*:\s*\|?\s*", "", limpia)
        if not limpia or limpia.startswith("#") or limpia.endswith(":"):
            continue
        try:
            partes = _LX.partes_shell(_LX.sin_datos(limpia))
        except Exception:
            continue
        for parte in partes:
            for verbo in _LX.verbos_efectivos(parte):
                toks = _LX.desnuda(_LX.tokens(verbo))
                if not toks:
                    continue
                base = os.path.basename(toks[0])
                if base in _NO_HERRAMIENTA or not re.fullmatch(r"[a-z][\w.-]*", base):
                    continue
                resto = toks[1:]
                if base in _INTERPRETES:
                    # Con un script detras, la superficie es la del script: no se mide aqui.
                    if any(re.search(r"\.(py|sh|js|ts|rb|pl)$", t) for t in resto):
                        continue
                # El subcomando: el primer positional que parece un verbo. Y LO QUE VA
                # ANTES ES DEL COMANDO BASE, no del subcomando — `git --no-pager diff --stat`
                # usa una bandera de `git` y otra de `git diff`, y colgarle las dos a
                # `git diff` inventa un fallo: `--no-pager` no esta en su ayuda porque no es
                # suya. Es la misma clase de mala atribucion que ya costo un prototipo (la de
                # colgarle al interprete las banderas del script), reaparecida un nivel mas
                # abajo. La cazo este mismo gate, sobre un comando que escribi yo mismo en el
                # justfile media hora antes (2026-09-02).
                corte = next((k for k, t in enumerate(resto)
                              if not t.startswith("-")
                              and re.fullmatch(r"[a-z][\w-]*", t)), None)
                sub = resto[corte] if corte is not None else None
                antes = resto[:corte] if corte is not None else resto
                despues = resto[corte + 1:] if corte is not None else []

                def _flags(toks):
                    return {t.split("=", 1)[0] for t in toks
                            if t.startswith("--") and len(t) > 2}

                if _flags(antes):
                    salida.setdefault(base, set()).update(_flags(antes))
                if sub and _flags(despues):
                    salida.setdefault(f"{base} {sub}", set()).update(_flags(despues))
                elif not sub and _flags(antes):
                    pass
    return salida


def superficie(clave):
    """`(version, banderas_declaradas)` de la herramienta INSTALADA, o `None` si no esta.

    Se pregunta a la herramienta, que es la unica fuente que no puede estar desactualizada.
    Y se lee tanto stdout como stderr: muchas escriben su ayuda por stderr, y mirar solo una
    haria pensar que no declaran ninguna bandera."""
    partes = clave.split()
    herramienta = partes[0]
    try:
        ver = subprocess.run([herramienta, "--version"], capture_output=True, text=True,
                             timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    version = ((ver.stdout or "") + (ver.stderr or "")).strip().split("\n")[0][:80]
    try:
        ayuda = subprocess.run(partes + ["--help"], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return (version, set())
    texto = (ayuda.stdout or "") + (ayuda.stderr or "")
    return (version, set(re.findall(r"(?<![\w-])(--[a-z][\w-]*)", texto)))


def registro_previo(raiz):
    """Lo que el registro YA declaraba. Se lee para no perderlo, no para confiar en ello."""
    texto = lee(raiz, REGISTRO)
    if not texto:
        return {}
    try:
        import tomllib
        return (tomllib.loads(texto).get("herramienta") or {})
    except BaseException:
        return {}


def escribir(raiz, registro):
    lineas = [
        "# superficie.toml — las banderas que este repo USA, y la version que las declara.",
        "#",
        "# Lo ESCRIBE la maquina en cada `just ci`, preguntandole a las herramientas",
        "# INSTALADAS. No es documentacion: es el contrato entre lo que el repo invoca y lo",
        "# que existe. Si una bandera que aqui figura deja de existir, el gate falla con su",
        "# nombre — que es la unica forma de que «esa bandera no existe» se sepa ANTES de que",
        "# lo diga el CI de otro.",
        "#",
        "# Se lee, ademas, en el instante en que hace falta: antes de escribir un comando,",
        "# esto dice que banderas acepta de verdad la version que hay instalada aqui.",
        "",
    ]
    for clave in sorted(registro):
        d = registro[clave]
        lineas.append('[herramienta."%s"]' % clave)
        lineas.append('version = "%s"' % str(d.get("version", "")).replace('"', "'"))
        lineas.append("usa = [%s]" % ", ".join('"%s"' % f for f in sorted(d.get("usa", []))))
        lineas.append("declara = %d" % d.get("declara", 0))
        # LAS VERIFICADAS A MANO SE CONSERVAN. Son banderas que la herramienta acepta y su
        # `--help` no lista; quien las anadio dejo la prueba en el commit. Se arrastran igual
        # que el resto del registro: perderlas volveria a tumbar el gate con un falso positivo.
        if d.get("verificadas"):
            lineas.append("# existen, pero el `--help` no las lista (ver el commit que las anadio)")
            lineas.append("verificadas = [%s]"
                          % ", ".join('"%s"' % f for f in sorted(d["verificadas"])))
        lineas.append("")
    with open(os.path.join(raiz, REGISTRO), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lineas))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    raiz = os.path.abspath(args[0]) if args else os.getcwd()
    solo_mostrar = "--mostrar" in sys.argv

    texto = fuentes(raiz)
    if not texto:
        print(f"verificar-superficie: {os.path.basename(raiz)}")
        print(f"  {A}sin justfile ni workflows{N}: no hay comandos que verificar")
        return 0

    print(f"verificar-superficie: {os.path.basename(raiz)}")
    previo = registro_previo(raiz)
    registro, fallos, ausentes, heredados = {}, [], [], []
    for clave, banderas in sorted(usos(texto).items()):
        s = superficie(clave)
        if s is None:
            # AUSENTE NO ES FALLO — pero TAMPOCO ES OLVIDO, y esa segunda mitad faltaba.
            #
            # LO QUE PASO (medido el 2026-09-02 sobre la historia del propio fichero): el
            # registro fue de 4 entradas a 3 y de vuelta a 4 en tres PRs seguidos, y los tres
            # gates salieron VERDES. La entrada de `gitleaks` —25 banderas— desaparecio y
            # volvio sin que nada chistara, porque una ejecucion desde un entorno sin la
            # herramienta simplemente no la escribia. Un registro que se sobrescribe con
            # menos de lo que sabia no puede ponerse rojo nunca: pierde cobertura en silencio.
            #
            # Ahora se ARRASTRA lo que ya se sabia, marcado como no re-verificado aqui. Se
            # pierde una entrada solo cuando el repo DEJA DE USAR esa herramienta, que es la
            # unica razon legitima para que salga del registro.
            heredado = previo.get(clave)
            if not heredado:
                ausentes.append(clave)
            else:
                heredados.append(clave)
                registro[clave] = {"version": heredado.get("version", ""),
                                   "usa": sorted(set(heredado.get("usa", [])) | banderas),
                                   "declara": heredado.get("declara", 0)}
            continue
        version, declaradas = s
        registro[clave] = {"version": version, "usa": sorted(banderas),
                           "declara": len(declaradas)}
        if not declaradas:
            continue                      # la herramienta no publica su ayuda: no se opina
        # UNA BANDERA QUE EL `--help` NO DECLARA PUEDE EXISTIR IGUAL, y eso es un fallo del
        # metodo, no del repo que la usa. Medido el 4-sep-2026 en OnlyHouseMX/site:
        # `pnpm --filter` esta documentada, funciona y NO sale en el `--help` global, porque
        # no es una opcion de comando sino un selector de workspace. El gate la marcaba como
        # inventada, tumbaba el pipeline, y obligo a reescribir una receta correcta.
        #
        # LO QUE NO FUNCIONA, Y SE MIDIO ANTES DE DESCARTARLO: probar la bandera. Se propuso
        # «ante una no declarada, ejecutarla y ver si la herramienta la rechaza», y la
        # medicion lo refuta en LAS DOS direcciones —con pnpm 11.20.0:
        #
        #     pnpm --inventadisima-que-no-existe --help   ->  exit 0 (imprime la ayuda)
        #     pnpm --filter --help                        ->  exit 1 («Unknown option»)
        #
        # O sea que probar habria dado por buena una bandera inventada y por inventada una
        # que existe. Peor que no probar.
        #
        # LA CURA ES LA DEL REGISTRO DE HALLAZGOS (ADR-0009): lo que el gate no puede decidir
        # se DECLARA con su prueba y queda en el diff, donde alguien lo revisa. Una bandera
        # anotada en `verificadas` pasa; una nueva y no declarada, no. El gate no se ablanda:
        # cambia «adivinar» por «afirmar con nombre y fecha».
        verificadas = set((previo.get(clave) or {}).get("verificadas") or [])
        if verificadas:
            registro[clave]["verificadas"] = sorted(verificadas)
        for f in sorted(banderas - declaradas - verificadas):
            fallos.append((clave, f, version))

    # POR QUE NO HAY UN GUARDIA QUE FALLE SI EL REGISTRO ENCOGE, aunque se escribio y se
    # probo (2026-09-02). Con el arrastre de arriba, una herramienta que el repo SIGUE usando
    # ya no puede desaparecer; la unica forma de que una entrada se vaya es que el repo deje
    # de usarla, y eso es una retirada LEGITIMA. El guardia fallaba justo en ese caso —lo
    # disparo el propio commit que simplificaba el justfile— y un gate que castiga lo correcto
    # se apaga. Ademas fallaba en el CI: `git` no viene del devshell sino de la imagen del
    # runner, asi que su version difiere entre maquinas de forma legitima y exigir un fichero
    # identico en todas partes era pedir algo falso (medido en el PR #25).
    #
    # Lo que queda como registro de lo que cambia es el DIFF, que es donde se mira.
    if not solo_mostrar:
        escribir(raiz, registro)

    for clave in sorted(registro):
        d = registro[clave]
        marca = f"{A}↺{N}" if clave in heredados else f"{V}✓{N}"
        print(f"  {marca} {clave:22} {D}{d['version'][:38]}{N}  "
              f"{len(d['usa'])} usada(s) de {d['declara']} declaradas")
    if heredados:
        print(f"  {A}↺ no instaladas aqui{N}: {', '.join(heredados)}  "
              f"{D}(se conserva lo que el registro ya sabia; no se re-verifico){N}")
    if ausentes:
        print(f"  {A}⊘ no instaladas aqui{N}: {', '.join(ausentes)}  "
              f"{D}(fuera del devshell no se puede preguntar){N}")
    if fallos:
        print()
        for clave, f, version in fallos:
            print(f"  {R}NO EXISTE{N} `{f}` en `{clave}` — {version} no la declara")
        print(f"\n  {R}{len(fallos)} bandera(s) sin declarar{N} — el repo invoca algo que el "
              f"`--help` de la herramienta no menciona.")
        print(f"  {D}Si la bandera NO existe, arregla el comando. Si SI existe y la ayuda no la"
              f" lista\n  (pasa: `pnpm --filter` es un selector de workspace, no una opcion de"
              f" comando),\n  declarala en {REGISTRO} con la prueba de que funciona:{N}")
        for clave, f, _ in fallos[:3]:
            print(f'    {D}[herramienta."{clave}"]{N}')
            print(f'    {D}verificadas = ["{f}"]   # que la probo, y donde{N}')
        return 1
    print(f"  {V}toda bandera que el repo usa existe en la version instalada{N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
