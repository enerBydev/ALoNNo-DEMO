#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lexer-shell — de una cadena de shell a los comandos que DE VERDAD se ejecutan.

EL ALCANCE, DECLARADO — LÉELO ANTES DE AÑADIR NADA
===================================================
Doce rondas de revisión adversarial sobre este fichero encontraron **doce variantes de la
misma clase**: una construcción de bash que el lexer no entendía. Cada ronda cerraba la
variante medida y la siguiente encontraba otra. El ritmo de hallazgo **no bajó** — porque la
sintaxis de bash no es un conjunto que se agote, y un lexer artesanal no puede converger
sobre ella.

Así que el alcance se declara aquí, y es una FRONTERA CERRADA, no una lista de tareas:

    LO QUE ESTE LEXER GARANTIZA
    Un verbo vigilado que aparece LITERALMENTE en el texto del comando, dentro de una
    envoltura enumerada, se ve — **incluidas las envolturas con opciones que llevan valor**
    (`sudo -u root X`, `ssh -i k host X`, `timeout -s TERM 5 X`). Eso es todo, y es
    exactamente lo que hace falta contra el modelo de amenaza real: un agente OLVIDADIZO,
    no un adversario. Nadie escribe `$'\x67it'` por descuido.

    Y LA REGLA DE DISEÑO QUE SOSTIENE ESO, que costó dos rondas aprender: cuando una
    envoltura admite dos lecturas —el token tras `-k`, ¿es el valor de la opción o ya el
    comando?— **no se elige a ciegas**. Elegir fue el defecto de la ronda 10 (ganó dos
    formas, perdió tres). Emitir las dos SIN CONDICIÓN fue el defecto de la ronda 11
    (40 falsos positivos: `sudo -E echo '…'` ascendía el argumento de `echo` a orden).
    Lo correcto es saber CUÁNDO hay dos lecturas: una opción solo tiene valor si ese verbo
    se lo da, y eso vive en `_OPCION_CON_VALOR`. Si el verbo no está en la tabla, no se
    salta nada: se prefiere el falso negativo —que es frontera declarada— al falso positivo,
    que es lo que hace que alguien desinstale el hook.

    LO QUE QUEDA FUERA, PARA SIEMPRE
    Todo lo que exige EVALUAR el shell en vez de analizarlo:
      · indirección por variable            C=commit; git $C
      · sustitucion de proceso              bash <(echo X)  ·  source <(…)
        La clasificacion es correcta —nadie lo ha cerrado— pero el MOTIVO que daba
        esta lista («exige evaluar el shell») no lo es para un `echo` literal: es
        la misma forma que se cerro para la tuberia en cinco lineas (ronda 11).
      · `source` / `.` de un fichero        . ./script.sh
      · el contenido de una tuberia CUYO ORIGEN NO ES LITERAL    cat f | sh
        El argumento literal de un `echo` o un `printf` SI se ve, **si el shell es la
        palabra inmediatamente posterior al `|`**: `echo 'X' | sudo bash` NO se ve, y es
        el mismo defecto que este fichero ya curo para los heredocs reusando el lexer
        (ronda 12, anotado). La primera version de esta lista declaraba fuera JUSTO LO QUE
        el fichero de al lado exigia dentro (ronda 11).
      · `coproc`, patrones de `case`, `find -exec`, `make -f -`
      · escapes ANSI-C que reconstruyen el verbo   $'\x67it'
    La mitad de esto NINGÚN parser cierra —ni `bashlex` ni ninguno—: haría falta ejecutar el
    shell para saberlo. Ponerlo aquí no es rendirse; es dejar de fingir.

POR QUÉ NO SE CAMBIA A UN PARSER DE VERDAD
-------------------------------------------
Se evaluó, y la respuesta está medida. Los tres defectos serios de la ronda 10 —el PR
equivocado en `gh pr merge --squash 42`, la regex ciega a comillas en `directorio_objetivo`,
y la continuación de línea sustituida por un espacio en vez de borrada— **no eran de
cobertura del lexer**. Un parser vendorizado no habría cazado ninguno, y habría costado la
propiedad «cero dependencias fuera de stdlib» justo en la ruta que decide permisos de toda
sesión. Donde se le mide de verdad, el lexer rinde: **cero falsos positivos** sobre los
comandos legítimos de `test-guardia.py`, solos Y COMPUESTOS con 14 prefijos con opción
—208 comprobaciones—, frente a **dos** del matcher por subcadena que había antes.

Ese «compuestos» no es adorno: la ronda 12 midió **40 falsos positivos** que ninguna de las
siete suites veía, porque el corpus de denegaciones se hizo combinatorio en la ronda 8 y el
de falsos positivos se quedó plano. Medir la mitad del sistema es no medirlo.

Y el corolario que decide dónde invertir: **en este plan de GitHub no existe un muro.** El
propio doctor lo dice en CODE-1 —«GitHub Free en privado no la da»—, así que no hay branch
protection ni revisión obligatoria del lado del servidor. Endurecer el badén hasta la décima
ronda no crea el muro que falta. Lo que sí es infalsificable por vía léxica es la MEDICIÓN A
POSTERIORI: `c_code2` lee la API y hoy dice, sobre este mismo repo, «10 de los últimos 10 PRs
sin veredicto». Ningún truco de comillas cambia eso.

QUÉ ES ESTE FICHERO
===================
Había TRES lectores de comandos en el repo y los tres se equivocaban distinto: el guardia
tenía el bueno (`verbos_efectivos`, recursivo), el hook de doctrina tenía uno propio a base
de anclas, y el primer intento de compartirlos metió el débil delante del fuerte, abriendo
una evasión de dos caracteres en un control desplegado. Un lexer compartido no es una
abstracción prematura; es lo contrario de tener tres.

**SIN EFECTOS AL IMPORTARSE.** Lo importan dos hooks que hablan un protocolo JSON por
stdout: un `print` suelto aquí lo corrompería en toda sesión de la máquina.
"""
import os
import re


# ── Heredocs y comentarios: qué es dato y qué es orden ───────────────────────────
#
# LA PROPIEDAD DE BASH QUE ESTO RESPETA, medida el 2026-08-27 con un testigo:
#
#     cat <<EOF     ... $(verbo) ... EOF   ->  bash EJECUTA `verbo`
#     cat <<'EOF'   ... $(verbo) ... EOF   ->  no ejecuta nada
#
# El cuerpo de un heredoc es literal SOLO si el delimitador va entrecomillado o escapado.
# Desnudo, bash expande `$(…)`, `` `…` `` y `$((…))` ahí dentro. Las dos primeras versiones
# de esta función borraban el cuerpo SIEMPRE, así que un `$(gh pr merge 1)` metido en un
# heredoc con delimitador desnudo desaparecía del análisis y se ejecutaba igual — tres
# formas que el guardia denegaba antes de este cambio y dejaba pasar después (ronda 4).
#
# Tres versiones seguidas de esta función han debilitado un control desplegado. La causa era
# siempre la misma: **suponer la semántica del shell en vez de medirla.**
# El abridor de un heredoc. Se escanea en vez de sustituir con una sola expresión, porque
# el delimitador manda sobre TRES decisiones distintas y una regex sola no las separa bien.
#
# EL DELIMITADOR NO ES `\w+`. Exigirlo denegaba trabajo legítimo —séptima aparición de la
# clase de falso positivo (ronda 5)— en cinco formas medidas: `<<'EOF' > "$HOME/x"`,
# `<<'EOF' | tee f`, `<<'E-O-F'`, `<<'EOF.txt'` y `<<'FIN AQUI'`. Ahora entre comillas vale
# cualquier cosa, y desnudo vale todo lo que no sea un metacarácter de shell.
_ABRE_HEREDOC = re.compile(
    r"(?<![\w><])<<-?[ \t]*"
    r"(?:'([^']+)'|\"([^\"]+)\"|(\\?)([^\s;&|<>()'\"]+)(?!['\"]))")
# Lo que bash EXPANDE dentro de un heredoc con delimitador desnudo.
_EXPANSION = re.compile(r"\$\(([^()]*)\)|`([^`]*)`|\$\(\(([^()]*)\)\)")
# Una barra al final de línea es una CONTINUACIÓN: `gh pr \\<salto> merge 11` es un
# solo comando, y sin unirlas el troceo partía el verbo en dos (ronda 4).
# BASH LA BORRA, no la sustituye por un separador, y CONSERVA la sangría siguiente. La
# primera versión hacía `sub(" ")` sobre `\\\n[ \t]*`, dos errores compuestos: una
# continuación DENTRO de una palabra partía el verbo, y `git com\<salto>mit -m x` —que bash
# ejecuta— no casaba con ninguna regla. No es un constructo que el lexer no conozca: es uno
# que declara implementar desde la ronda 4 y que implementaba con otra semántica (ronda 10).
_CONTINUACION = re.compile(r"\\\n")
_SEPARADOR = re.compile(r"[;&|\n(){]")


def _verbo_antes_de(texto, pos):
    """TODOS los verbos del comando en el que cae `pos`, no el primero.

    Es lo que decide si el cuerpo de un heredoc son órdenes o datos, y devolver solo el
    primer token lo rompía en cuanto había un envoltorio delante:

        bash <<EOF       -> 'bash'   -> órdenes, correcto
        sudo bash <<EOF  -> 'sudo'   -> DATOS, y el cuerpo se tiraba entero

    `sudo bash <<EOF` no es rebuscado: es la forma normal de correr un bloque con
    privilegios. Medido con testigo: `sudo`, `env`, `timeout 5` y `nohup` delante de un
    `bash <<'EOF'` ejecutan el cuerpo, y el guardia pasaba de `deny` a silencio en **144
    pares** — 18 prefijos que YA estaban en el corpus × 4 formas que YA estaban en el suelo.
    Sueltos, los dos ingredientes se denegaban; compuestos, no (ronda 8).

    Y es la TERCERA vez que este fichero tropieza con lo mismo: «un envoltorio ya
    desenvuelto no conserva su nombre», que él documenta en `_duenio_del_flag` justo debajo,
    donde ya se arregló devolviendo todos los candidatos. Aquí seguía devolviendo uno."""
    ini = 0
    for m in _SEPARADOR.finditer(texto, 0, pos):
        ini = m.end()
    return [os.path.basename(tok) for tok in texto[ini:pos].strip().split()
            if not tok.startswith("-") and "=" not in tok]


def sin_datos(cmd):
    """El comando sin comentarios ni la parte de los heredocs que NO se ejecuta.

    Tres casos, y confundirlos ha costado tres rondas de revisión:

      · `bash <<EOF … EOF`      -> el cuerpo son ÓRDENES. Un heredoc hacia un shell es su
        entrada, igual que un herestring; se conserva entero. Cuatro formas (`bash <<EOF`,
        `bash <<'EOF'`, `bash -s <<EOF`, `sh <<EOF`) pasaban de `deny` a silencio (ronda 5).
      · `cat <<'EOF' … EOF`     -> literal: el cuerpo son DATOS y se tira.
      · `cat <<EOF … EOF`       -> bash EXPANDE `$( )`, backticks y `$(( ))` ahí dentro
        (medido con testigo, ronda 4), así que se conserva solo eso.
    """
    texto = sin_comentarios(cmd or "")
    salida, pos = [], 0
    while True:
        m = _ABRE_HEREDOC.search(texto, pos)
        if not m:
            break
        tag = m.group(1) or m.group(2) or m.group(4) or ""
        literal = bool(m.group(1) or m.group(2) or m.group(3))
        salto = texto.find("\n", m.end())
        if not tag or salto < 0:
            break
        cierre = re.compile(r"^[ \t]*" + re.escape(tag) + r"[ \t]*$", re.M).search(texto, salto + 1)
        if not cierre:
            break
        cuerpo = texto[salto + 1:cierre.start()]
        # EL RESTO DE LA LÍNEA DEL ABRIDOR NO SON DATOS. `cat <<'EOF' && git commit -m x`
        # ejecuta el commit (testigo), y la versión anterior de este escáner tiraba ese tramo
        # en las tres ramas del `if`: ocho formas pasaban de `deny` a silencio en los DOS
        # hooks (ronda 6). Es donde viven `&&`, `;`, `|` y las redirecciones.
        resto_linea = texto[m.end():salto]
        # Y el destino puede ser un intérprete AUNQUE el verbo del heredoc sea `cat`:
        # `cat <<'EOF' | bash` ejecuta el cuerpo. La premisa «entrecomillado ⇒ no se ejecuta»
        # solo vale si nadie se lo pasa a un shell después.
        # SE REUSA EL LEXER SOBRE SÍ MISMO, no una regex nueva. La primera versión exigía
        # que el intérprete fuera la palabra INMEDIATAMENTE posterior al `|`, así que
        # `cat <<'EOF' | sudo bash` —la forma más común que existe— tiraba el cuerpo como
        # datos mientras bash lo ejecutaba. Nueve formas, todas de `deny` a silencio.
        #
        # Y el defecto de fondo era peor que el síntoma: era un CUARTO lector de comandos a
        # base de regex, metido dentro del fichero cuyo docstring denuncia exactamente eso.
        # `resto_linea` no contiene heredocs, así que no hay recursión.
        va_a_un_shell = any(
            os.path.basename((v.split() or [""])[0]) in _INTERPRETES
            for v in verbos_efectivos(resto_linea, profundidad=5))
        if any(v in _SHELLS for v in _verbo_antes_de(texto, m.start())) \
                or va_a_un_shell:
            conservado = "\n" + cuerpo                       # órdenes
        elif literal:
            conservado = ""                                  # datos
        else:
            dentro = [a or b or c for a, b, c in _EXPANSION.findall(cuerpo)]
            conservado = ("\n" + "\n".join(dentro)) if dentro else ""
        salida.append(texto[pos:m.start()] + "<<" + tag + resto_linea + conservado)
        pos = cierre.end()
    salida.append(texto[pos:])
    return _CONTINUACION.sub("", "".join(salida))


def _escapado(cmd, i):
    """¿El carácter en `i` va precedido por un NÚMERO IMPAR de barras?

    Mirar solo una barra atrás es falso para un número PAR: `echo "a\\\\"` cierra la comilla en
    bash, pero el lexer la daba por escapada y se tragaba el resto del guion — `echo "a\\\\" ;
    gh repo delete foo` colapsaba en un solo verbo y los dos hooks callaban (testigo: bash
    ejecuta el segundo comando).
    
    La mitad de COMILLA SIMPLE de este mismo bug se cerró en la ronda 5; la de comilla DOBLE
    quedó viva en las dos máquinas de estados (2026-09-01, CR2-2)."""
    n = 0
    while i - 1 - n >= 0 and cmd[i - 1 - n] == "\\":
        n += 1
    return n % 2 == 1


def sin_comentarios(cmd):
    """Quita los comentarios de shell, RESPETANDO COMILLAS.

    Un `re.M` sobre el inicio de linea no basta: con `X='<salto>#'`, el `#'` es el cierre de una cadena,
    no un comentario, y borrarlo dejaba la comilla abierta — el troceo posterior se tragaba
    el resto del guion y el comando real desaparecía del análisis (ronda 4). La máquina de
    estados ya existía en `partes_shell`; esta es la misma idea."""
    salida, comilla, i, n = [], None, 0, len(cmd or "")
    while i < n:
        ch = cmd[i]
        if comilla:
            salida.append(ch)
            if ch == comilla and (comilla == "'" or not _escapado(cmd, i)):
                comilla = None
        elif ch in "'\"":
            comilla = ch
            salida.append(ch)
        elif ch == "#" and (not salida or salida[-1] in " \t\n"):
            while i < n and cmd[i] != "\n":
                i += 1
            continue
        else:
            salida.append(ch)
        i += 1
    return "".join(salida)




# ── Envoltorios: cómo llegar al comando interno ──────────────────────────────────
# (a) FLAGS: todo lo que sigue al flag es otro comando.
# EL FLAG NO BASTA: DEPENDE DEL VERBO. Cuando esto vivía solo en el guardia, `-e` significaba
# `perl -e`. Al compartirse con el hook de doctrina pasó a aplicarse a TODO comando Bash de
# TODA sesión, y entonces `grep -e 'git commit' -r docs/`, `echo -e 'git commit'` y
# `sed -e 's/gh pr merge/X/'` se leían como si ejecutaran lo que sigue al flag: denegados los
# tres (ronda 4). Es la 5ª y 6ª aparición de la clase de falso positivo que este repo lleva
# contando, sobre los dos comandos más frecuentes que existen — y el fichero de al lado dice
# que un falso positivo aquí «es la garantía de que alguien lo desactive».
_SHELLS = {"bash", "sh", "zsh", "dash", "ksh", "ash", "busybox"}
# `su`, `npx` y compañía también acaban ejecutando lo que va tras `-c`. Se añaden como
# DUEÑOS en vez de invertir la polaridad del flag (que sería «todos ejecutan salvo estos»):
# invertirla resucitaría la clase de falso positivo que este repo lleva contando siete veces,
# porque `-c` significa otra cosa en `grep`, `tar`, `gcc`, `sort`, `wc`, `head`, `curl`,
# `jq`, `ssh` y `kubectl`, y esa lista no es corta ni cerrada.
# Los que DESCARGAN Y EJECUTAN otra cosa. Son a la vez envoltorio (`npx <verbo>`) y dueño
# legítimo de un `-c` (`npx foo -c 'X'`), y hacen falta las dos lecturas.
_LANZADORES = {"npx", "bunx", "uvx", "pipx", "su"}

_INTERPRETES = _SHELLS | {"python", "python2", "python3", "perl", "ruby", "node", "deno",
                          "su", "npx", "bunx", "uvx", "pipx", "nix-shell", "env",
                          "zx", "tsx"}
# `None` = sin restricción de verbo. Solo se restringen los flags que además significan otra
# cosa en herramientas corrientes: `-e` (grep, echo, sed) y `-c` (grep -c cuenta). Restringir
# `--command` fue un error medido al instante: tras desenvolver `nix develop . --command …`
# el verbo base pasa a ser `.` y la comprobación fallaba, dejando pasar el comando interno —
# tres casos del guardia en rojo. Un envoltorio ya desenvuelto no conserva su nombre.
FLAGS_POR_VERBO = {
    # `-c` PARA TODOS LOS INTÉRPRETES, pero el payload de uno que NO es shell solo se mira si
    # es de UNA LÍNEA. Ver `_payload_analizable`.
    "-c": _INTERPRETES, "-lc": _SHELLS, "-ic": _SHELLS, "-lic": _SHELLS,
    "-e": {"perl", "ruby", "node", "zsh"}, "--eval": {"perl", "ruby", "node", "zsh", "deno"},
    "--command": None, "-ex": None, "--exec": None,
}


# QUÉ OPCIONES TOMAN VALOR, POR VERBO ENVOLVENTE. Mismo idioma que `FLAGS_POR_VERBO`, y por
# la misma razón: el flag no basta, depende del verbo.
#
# EL FALLO QUE LO JUSTIFICA (ronda 12). El arreglo anterior asumía que TODA opción antes del
# token de parada había tomado valor, y saltaba ese token — que a veces es el VERBO REAL:
#
#     sudo -E echo 'gh repo delete no se usa'
#        -> candidato: «gh repo delete no se usa»   ← el ARGUMENTO de `echo`, ascendido a orden
#
# Basta una opción BOOLEANA (`-E`, `-i`, `-r`, `-n`, `--preserve-status`) para dispararlo.
# Medido: **40 comandos legítimos** pasaban de silencio a `deny` contra la política real, y
# 18 de 100 pares del propio `NO_DEBEN_MOLESTAR` compuestos con un solo prefijo. El comentario
# de diseño decía «un candidato de más es ruido»: era falso, porque las reglas anclan al
# principio y el candidato de más EMPIEZA justo en la carga. Un candidato de más es un `deny`.
#
# Si el verbo no está en esta tabla, NO se salta ningún valor: se prefiere el falso negativo
# —que es la frontera declarada— al falso positivo, que es lo que hace que alguien desinstale
# el hook. Novena aparición de esa clase, y la primera que me la cazó el corpus de falsos
# positivos por NO ser combinatorio.
_OPCION_CON_VALOR = {
    # `exec -a nombre <verbo>` renombra el proceso: el token tras `-a` es el nombre,
    # no el comando. Una forma enumerada más, cerrada porque cuesta una línea.
    "exec": {"-a"},
    "timeout": {"-k", "-s", "--kill-after", "--signal"},
    "nice": {"-n", "--adjustment"},
    "ionice": {"-c", "-n", "-p", "--class", "--classdata", "--pid"},
    "chrt": {"-p", "--pid"},
    "flock": {"-w", "-E", "--timeout", "--wait", "--conflict-exit-code"},
    "ssh": {"-p", "-i", "-l", "-o", "-F", "-c", "-b", "-D", "-L", "-R", "-W", "-e", "-m", "-S"},
    "sudo": {"-u", "-g", "-U", "-C", "-h", "-p", "-r", "-t", "--user", "--group"},
    "doas": {"-u", "-C"},
    "chroot": {"-u", "--userspec", "--groups"},
    "unshare": {"-S", "-G", "-R", "--setuid", "--setgid", "--root", "--wd"},
    "su": {"-s", "-g", "-G", "--shell", "--group"},
    "env": {"-u", "-C", "-S", "--unset", "--chdir"},
    "watch": {"-n", "--interval"},
    "xargs": {"-I", "-n", "-P", "-s", "-L", "-d", "-E", "-a", "--max-args", "--max-procs"},
    "parallel": {"-j", "--jobs"},
    "time": {"-f", "-o", "--format", "--output"},
    "stdbuf": {"-i", "-o", "-e", "--input", "--output", "--error"},
}


def _toma_valor(base, opcion):
    """¿Esta opción de este verbo lleva un valor detrás?"""
    if "=" in opcion:
        return False                     # `--signal=TERM` ya lo lleva pegado
    return opcion in _OPCION_CON_VALOR.get(base, ())


def _duenio_del_flag(toks, i):
    """El verbo AL QUE PERTENECE el flag: el último token no-opción antes de él.

    Usar `toks[0]` era el mismo error que este fichero ya documenta para `--command` dos
    entradas más arriba, y se dejó vivo en `-c`. Con cualquier envoltorio que deje un token
    posicional delante del shell —`direnv exec DIR bash -c`, `sudo -u root bash -c`,
    `docker run IMG bash -c`, `nice -n 5 bash -c`— el primer token no es el intérprete, la
    comprobación fallaba, y el comando interno dejaba de verse. Doce envoltorios cotidianos
    pasaban de `deny` a silencio contra la política REAL de la máquina (ronda 5).

    Es la cuarta vez que este control sale de un arreglo más débil de lo que entró, y la
    cuarta con la misma causa: arreglar el caso medido en vez de la propiedad."""
    # SE DEVUELVEN TODOS LOS CANDIDATOS, no el último. «El último token no-opción antes del
    # flag» es falso en cuanto una opción lleva argumento propio: en `bash -o pipefail -c X`
    # el último es `pipefail`, no `bash`, y el comando interno dejaba de verse. Nueve formas
    # cotidianas —`bash -o`, `bash -O`, `--rcfile`, `--init-file`, `sh -o`, `python3 -W`,
    # `perl -I`, `su - u -c`— pasaban de `deny` a silencio (ronda 6).
    #
    # `npx -y foo -c` figuraba en esta lista y NO se habia recuperado: seguia pasando,
    # porque `npx` estaba a la vez aqui y en `VERBOS_EJECUCION`, y el pelado ganaba.
    # Se cerro en la ronda 7. Escribir «recuperada» sobre algo que no lo estaba, en el
    # comentario que explica por que hay que medir, es el mismo fallo un nivel arriba.
    #
    # Es el mismo error que el docstring de arriba denuncia, cometido en la línea siguiente:
    # el arreglo de la ronda 5 recuperó doce formas y perdió nueve distintas, y la suite solo
    # tenía las doce recuperadas.
    return [os.path.basename(t) for t in toks[:i] if not t.startswith("-")] or (
        [os.path.basename(toks[0])] if toks else [])


# `bash -ec 'X'`, `-xc`, `-cex`… son el MISMO flag con opciones booleanas pegadas. Cerrarlo
# como clase evita la cuarta entrada suelta en la tabla — y es justo lo que este fichero
# predica: descubrir, no enumerar (ronda 10).
# El racimo de opciones cortas: `-ec`, `-lc`, y también las MAYÚSCULAS. Restringirlo a
# minúsculas dejaba fuera opciones reales de bash (`-E`, `-B`, `-C`, `-H`, `-P`, `-T`):
# `bash -Ec 'X'` ejecuta X y el lexer no veía ningún verbo interno, así que
# `bash -Ec "git commit -m x"` se colaba por LOOP-1 (2026-09-01, CR2-1).
_RACIMO = re.compile(r"^-[A-Za-z]*c[A-Za-z]*$")


# Un payload de varias líneas para un intérprete que NO es shell es un PROGRAMA, y leerlo con
# el lexer del shell produce falsos positivos: una cadena de Python que empiece por un verbo
# vigilado se ascendía a orden ejecutable, y eso bloqueó un comando de sondeo REAL durante una
# revisión — décima aparición de la clase que este repo lleva contando (2026-09-01, CR4-5).
#
# Quitar los intérpretes de `-c` a secas era peor: el suelo midió **200 pares de protección
# perdidos** frente a `main`. La salida no es elegir entre el falso positivo y el agujero,
# sino separar los dos casos: una línea suelta es donde vive una evasión de verdad
# (`python3 -c 'os.system(...)'` cabe en una); un programa de varias líneas, no.
def _payload_analizable(base, payload):
    return base in _SHELLS or base in _LANZADORES or "\n" not in payload


def _flag_ejecuta(flag, candidatos):
    """¿Alguno de los verbos del prefijo es dueño legítimo de este flag?"""
    permitidos = FLAGS_POR_VERBO.get(flag)
    if permitidos is None:
        return True
    return any(c in permitidos for c in candidatos)
FLAGS_EJECUCION = set(FLAGS_POR_VERBO)
# (b) VERBOS: `<verbo> [n args fijos] <comando…>`. El int es cuántos tokens saltar.
VERBOS_EJECUCION = {
    # gestor de entorno  (el caso que nos ocupó)
    "nix-shell": 0, "direnv": 0,
    # ecosistema JS/Python: descargan Y ejecutan
    # `npx`, `bunx`, `uvx`, `pipx`: van AQUÍ **y** en `_INTERPRETES`, y hacen falta las dos.
    #
    # Quitarlos de aquí en la ronda 7 —para que su `-c` no quedara huérfano de dueño— fue una
    # REGRESIÓN FRENTE A `main` que ninguna suite vio: `npx wrangler d1 delete x` dejó de
    # desenvolverse, o sea que la forma MÁS COMÚN de `npx` pasó de `deny` a silencio. El
    # corpus solo ejercitaba `npx -y zx -c`, nunca `npx <verbo>` a secas (2026-09-01, CR2-3).
    #
    # Y la forma con `-c` sigue funcionando porque el verbo interno (`zx`, `tsx`, un shell)
    # ya está en `_INTERPRETES`: tras pelar `npx`, el dueño del `-c` es él.
    "npx": 0, "bunx": 0, "uvx": 0, "pipx": 0,
    # envoltorios de proceso: transparentes al comando que envuelven
    # `exec` y `command` reemplazan/invocan el verbo que siguen: eran dos de las formas que
    # ejecutaban un merge de verdad mientras el hook callaba (ronda 4).
    "exec": 0, "command": 0, "builtin": 0,
    # AÑADIDOS TRAS MEDIRLOS (ronda 5): los doce de arriba pasaban de `deny` a silencio.
    # La lista sigue siendo una lista —y este repo tiene un incidente titulado «una lista
    # escrita a mano es una mentira con fecha de caducidad»— pero aquí no hay nada que
    # descubrir: el conjunto de envoltorios de proceso de un Unix no está en el disco.
    # Lo honesto es decir que es una deny-list y que los hooks fallan abiertos por eso.
    "flock": 1, "watch": 0, "chroot": 1, "unshare": 0, "parallel": 0,
    # `su` NO va aquí: lo que ejecuta viene tras su `-c`, y tratarlo como
    # envoltorio de salto 0 dejaba ese `-c` huérfano de dueño (ronda 6).
    "sudo": 0, "doas": 0, "nohup": 0, "setsid": 0, "stdbuf": 0, "ionice": 0,
    "nice": 0, "time": 0, "xargs": 0, "env": 0, "timeout": 1, "chrt": 1,
    # AÑADIDOS TRAS MEDIRLOS (2026-09-01, CR22-8): `strace -f git commit -m x` daba SILENCIO
    # sobre un commit real a `main`, mientras `timeout`, `flock`, `nice`, `nohup`, `sudo` y
    # `time` sí estaban. Los tres son envoltorios de proceso del mismo tipo, y faltaban solo
    # porque nadie los había escrito.
    "strace": 0, "ltrace": 0, "ltrace-": 0, "catchsegv": 0, "valgrind": 0, "gdbserver": 1,
    # `eval` ejecuta su argumento como comando: era la 7ª evasión de la ronda 3.
    "eval": 0,
    # remoto y contenedores
    "ssh": 1,
}
# (c) PARES: `<a> <b> <comando…>`  — verbo de dos palabras.
PARES_EJECUCION = {
    ("nix", "develop"), ("nix", "shell"), ("nix", "run"),
    ("pnpm", "exec"), ("pnpm", "dlx"), ("npm", "exec"), ("yarn", "dlx"),
    ("uv", "run"), ("poetry", "run"), ("pdm", "run"), ("rye", "run"),
    ("cargo", "run"), ("bundle", "exec"), ("direnv", "exec"),
    ("docker", "run"), ("podman", "run"), ("docker", "exec"), ("podman", "exec"),
}
# Prefijos que consumen argumentos propios antes del comando interno.
_OPCION = re.compile(r"^-")
# UNA ASIGNACIÓN ES UN TOKEN ENTERO, no cualquier cosa que lleve un `=`. `shlex` entrega el
# argumento entrecomillado de un envoltorio como UN SOLO token, así que con `"=" in tok` un
# `eval 'FOO=1 git commit -m x'` —o un mensaje de commit con un `=`, que en esta máquina es
# cotidiano (`CARGO_INCREMENTAL=0`)— se tomaba por asignación de entorno, se saltaba, y el
# comando interno ENTERO desaparecía del análisis (ronda 9).
_ASIGNACION = re.compile(r"^\w+=\S*$")



def partes_shell(cmd):
    """Trocea por operadores de shell de nivel superior, respetando comillas."""
    partes, buf, comilla, i = [], [], None, 0
    while i < len(cmd):
        ch = cmd[i]
        if comilla:
            buf.append(ch)
            # EN BASH, DENTRO DE COMILLAS SIMPLES NO HAY ESCAPES: `'a\\'` cierra la cadena.
            # Tratarlas como las dobles hacía que `echo 'a\\' ; git commit -m x` se leyera
            # como un solo verbo, y el commit desaparecía del análisis — testigo: bash lo
            # ejecuta (ronda 5, D2).
            if ch == comilla and (comilla == "'" or not _escapado(cmd, i)):
                comilla = None
        elif ch in "'\"":
            comilla = ch
            buf.append(ch)
        elif cmd[i:i + 2] == "$(" or ch == "`":
            # UNA SUSTITUCIÓN ES UN ÁTOMO. Sin esto, el `;` de dentro partía el comando ANTES
            # de analizarlo: `$({ git commit -m x ; })` quedaba en «$({ git commit -m x» y
            # ninguna regla casaba, aunque bash lo ejecuta (testigo, ronda 9). El interior lo
            # analiza `verbos_efectivos` después, que para eso busca `$(…)` y backticks.
            cierre, prof = ("`", 0) if ch == "`" else (")", 0)
            j = i + (1 if ch == "`" else 2)
            buf.append(cmd[i:j])
            while j < len(cmd):
                if ch != "`" and cmd[j] == "(":
                    prof += 1
                elif cmd[j] == cierre and prof == 0:
                    break
                elif cmd[j] == cierre:
                    prof -= 1
                buf.append(cmd[j])
                j += 1
            if j < len(cmd):
                buf.append(cmd[j])
            i = j + 1
            continue
        elif ch in ";\n":
            partes.append("".join(buf))
            buf = []
        elif ch == "&" and cmd[i : i + 2] == "&&":
            partes.append("".join(buf)); buf = []; i += 1
        # EL `&` SUELTO Y EL `|&` TAMBIÉN SEPARAN, y faltaban. El docstring de arriba dice
        # «operadores de shell de nivel superior», y el conjunto es CERRADO —cinco— y este
        # repo ya lo enumera bien DOS FICHEROS MÁS ALLÁ: `hook-guardia-ejecutores.py` cita
        # «&&, ||, |, ;, &» y `methodos-permisos.py` añade `|&`.
        #
        # Sin ellos todo caía en un mismo trozo, y como las tres reglas del hook de doctrina
        # anclan con `^`, ninguna casaba: `true & git commit -m x` apagaba LOOP-1, FUERZA y
        # CODE-2 a la vez, con dos caracteres y un testigo que confirma que bash lo ejecuta.
        # Y el suelo congelado no podía verlo, porque su corpus trae `'%s &'` —la carga
        # DELANTE del `&`— y nunca `'X & %s'` (ronda 13).
        #
        # No es «una envoltura más» de la cinta de correr del lexer: es un miembro que
        # faltaba de una lista terminada.
        elif ch == "&" and (cmd[i - 1:i] == ">" or cmd[i + 1:i + 2] == ">"):
            # EL `&` DE UNA REDIRECCIÓN NO SEPARA: `>&2`, `2>&1`, `&>/dev/null`. Tratarlo
            # como separador partía el comando A MITAD DE LA REDIRECCIÓN y dejaba el verbo
            # real huérfano en un fragmento que empieza por un dígito:
            #
            #     `2>&1 git commit -m x`  ->  ['1 git commit -m x']
            #
            # Como las tres reglas anclan con `^`, ninguna casaba: LOOP-1, CODE-2 y el deny
            # del guardia, apagados con tres caracteres. Y `2>&1` no es adversarial: es la
            # redirección más común que existe. Misma clase que el arreglo del `&` de la
            # ronda 13, sobre los miembros del conjunto que se quedaron fuera (CR3-1).
            buf.append(ch)
        elif ch == "&":
            partes.append("".join(buf)); buf = []
        elif ch == "|" and cmd[i : i + 2] == "||":
            partes.append("".join(buf)); buf = []; i += 1
        elif ch == "|":
            partes.append("".join(buf)); buf = []
            if cmd[i + 1 : i + 2] == "&":      # `|&` es un solo operador
                i += 1
        else:
            buf.append(ch)
        i += 1
    partes.append("".join(buf))
    return [p.strip() for p in partes if p.strip()]


def tokens(s):
    """shlex tolerante: una comilla sin cerrar no debe tumbar el guardia.

    `$'…'` (ANSI-C) se normaliza a `'…'` antes de trocear: shlex no lo entiende y dejaba el
    `$` pegado al primer token, así que `bash -c $'git commit -m x'` producía el verbo
    «$git commit -m x» y ninguna regla casaba, aunque bash lo ejecuta (testigo, ronda 5)."""
    import shlex
    s = re.sub(r"\$(?=['\"])", "", s)
    try:
        return shlex.split(s)
    except ValueError:
        try:
            return shlex.split(s + '"')
        except ValueError:
            return s.split()


def sin_comillas(tok):
    # `$'…'` (ANSI-C) es una cadena, y el `$` no es parte de ella. Sin quitarlo,
    # `bash -c $'git commit -m x'` producía el verbo «$git commit -m x» y ninguna regla
    # casaba, aunque bash lo ejecuta (testigo, ronda 5, D3).
    if len(tok) > 2 and tok[0] == "$" and tok[1] in "'\"":
        tok = tok[1:]
    if len(tok) >= 2 and tok[0] == tok[-1] and tok[0] in "'\"":
        return tok[1:-1]
    return tok


# Palabras y signos que NO son un comando: estructura del shell. Sin quitarlos, el verbo
# efectivo de `if true; then gh pr merge 11; fi` era «then gh pr merge 11» y ninguna regla
# casaba; lo mismo con `( … )` y `{ …; }` (ronda 3).
_ESTRUCTURA = {"if", "then", "else", "elif", "fi", "while", "until", "for", "do", "done",
               "case", "esac", "in", "select", "function", "!", "(", ")", "{", "}", "[[", "]]"}

# `nombre()` ES LA CABECERA DE UNA FUNCIÓN, no un verbo. `f() { git commit -m x; }; f` daba
# SILENCIO porque `desnuda` dejaba `f()` de primer token y ningún verbo efectivo empezaba por
# `git`. El cuerpo se ejecuta igual, y con el nombre por delante o por detrás
# (2026-09-01, CR22-8).
_CABECERA_FUNCION = re.compile(r"^[\w.-]+\(\)$")


# `<shell> <<< '…'` mete órdenes por stdin. Con cualquier otro verbo delante, es un dato.
_HERESTRING = re.compile(r"\b(bash|sh|zsh|dash|ksh)\s+<<<\s*(?:'([^']*)'|\"([^\"]*)\"|(\S+))")


_PIPE_A_SHELL = re.compile(
    r"\b(?:echo|printf)\s+(?:'([^']*)'|\"([^\"]*)\")[^|]*\|\s*(?:\S*/)?"
    r"(?:bash|sh|zsh|dash|ksh)\b")


# Una redirección que va DELANTE del comando no es el comando. `&>/dev/null git commit -m x`
# es bash válido —la redirección puede ir primero— y dejaba el verbo detrás de un token que
# ninguna regla reconoce (CR3-1, segunda mitad).
_REDIR_SOLA = re.compile(r"^(?:&>>?|\d*[<>]{1,2}&?\d*)$")        # `>`, `2>`, `2>&1`, `&>`
_REDIR_PEGADA = re.compile(r"^(?:&>>?|\d*[<>]{1,2})\S+$")          # `&>/dev/null`, `2>/tmp/f`


def desnuda(toks):
    """Los tokens sin la estructura de shell que los rodea.

    También despega los paréntesis y llaves ADHERIDOS al verbo: `(gh pr merge 11)` sin
    espacios llegaba como un solo token `(gh` y ninguna regla casaba (ronda 4)."""
    # HASTA PUNTO FIJO, no una pasada. El pelado corría UNA vez sobre el token original,
    # así que cuando el paréntesis exterior era su propio token se lo llevaba él y el
    # interior quedaba PEGADO al verbo:
    #
    #     ( (git commit -m x) )  ->  ['(git', 'commit', '-m', 'x)']  ->  ninguna regla casa
    #
    # Medido con testigo: bash SÍ commitea, `main` denegaba y HEAD callaba. Doce regresiones,
    # y seis formas cotidianas que saltaban el gate CODE-2 recién instalado —un subshell
    # dentro de un bucle o de un condicional es scripting normal (ronda 9).
    toks = list(toks)
    for _ in range(8):
        antes = list(toks)
        if toks:
            toks[0] = toks[0].lstrip("({")
            toks[-1] = toks[-1].rstrip(")};")
            toks = [t for t in toks if t]
        i, j = 0, len(toks)
        # `>/dev/null git commit -m x` es válido en bash y el verbo va DETRÁS. Una
        # redirección antepuesta no es un comando (ronda 10).
        while i < j and (toks[i] in _ESTRUCTURA or toks[i] in "(){}"
                         or _CABECERA_FUNCION.match(toks[i])
                         or _REDIR_SOLA.match(toks[i])
                         or _REDIR_PEGADA.match(toks[i])
                         or _ASIGNACION.match(toks[i])):
            i += 1
            # Una redirección SUELTA se lleva además su destino; una que ya lo
            # lleva dentro (`2>&1`, `&>/dev/null`) no. La regex de la ronda 10
            # empezaba por `\\d*[<>]`, así que `&>/dev/null git commit -m x`
            # —bash válido— dejaba el verbo detrás de un token que ninguna
            # regla reconoce, y los tres gates callaban (CR3-1).
            if i < j and _REDIR_SOLA.match(toks[i - 1]) and "&" not in toks[i - 1]:
                i += 1
        while j > i and (toks[j - 1] in _ESTRUCTURA or toks[j - 1] in "(){};"):
            j -= 1
        toks = toks[i:j]
        if toks == antes:
            break
    return toks


def carga_de_tuberia(cmd):
    """El texto que una tubería manda a un intérprete, con sus comillas intactas.

    `verbos_efectivos` ya modela `echo 'X' | sh`, pero devuelve el verbo REJUNTADO, y quien
    necesita los tokens no puede reconstruirlo. Peor: quien trocea por partes ANTES de
    preguntar al lexer no lo ve siquiera, porque `partes_shell` corta por el `|` y destruye
    justo la relación que este patrón existe para modelar (2026-09-01, CR18-1).

    Se expone aquí y no se copia allí: el criterio de qué es una tubería hacia un shell vive
    en un solo sitio, que es la lección que costó unificar los tres lexers en uno."""
    m = _PIPE_A_SHELL.search(cmd or "")
    if not m:
        return None
    dentro = m.group(1) or m.group(2) or ""
    return dentro if dentro.strip() else None


def verbos_efectivos(cmd, profundidad=0):
    """Devuelve todos los comandos que este string acaba ejecutando de verdad.

    Recursivo: `nix develop . --command bash -c 'X'` -> [..., 'X'].
    """
    if profundidad > 6 or not cmd:
        return []
    salida = []
    # Una TUBERÍA hacia un intérprete lleva órdenes, igual que un heredoc o un herestring:
    # `echo 'X' | sh` ejecuta X. Es la lógica que `sin_datos` ya aplicaba a los heredocs y que
    # no se aplicaba al pipe (ronda 10). Solo se mira el argumento literal de un `echo` o un
    # `printf`: si el contenido viene de otro sitio, no se puede saber, y eso está declarado
    # fuera de alcance en la cabecera.
    m_pipe = _PIPE_A_SHELL.search(cmd)
    if m_pipe and profundidad < 5:
        dentro = m_pipe.group(1) or m_pipe.group(2) or ""
        if dentro.strip():
            salida += verbos_efectivos(dentro, profundidad + 1)

    for parte in partes_shell(cmd):
        # Un herestring hacia un shell es ENTRADA DE ÓRDENES: `bash <<< 'gh pr merge 11'`
        # ejecuta el merge (medido, ronda 4). El herestring hacia cualquier otra cosa son
        # datos y no se toca — por eso el patrón exige un shell delante.
        m_here = _HERESTRING.search(parte)
        if m_here:
            salida += verbos_efectivos(
                m_here.group(2) or m_here.group(3) or m_here.group(4) or "",
                profundidad + 1)
        # Sustituciones de comando: $(…) y `…` ejecutan por su cuenta.
        for anidado in re.findall(r"\$\(([^()]*)\)|`([^`]*)`", parte):
            interno = anidado[0] or anidado[1]
            if interno.strip():
                salida += verbos_efectivos(interno, profundidad + 1)
        toks = desnuda(tokens(parte))
        if not toks:
            continue
        salida.append(" ".join(toks))  # el comando tal cual (peleado de comillas)
        # `find … -exec <comando> ;` EJECUTA. No es un flag de ejecución de los de arriba
        # porque su payload no es UN token ni «todo lo que sigue»: termina en `;` o `+`, y
        # `{}` es el hueco del fichero. Medido: `find . -maxdepth 0 -exec git commit -m x \;`
        # daba SILENCIO sobre un commit real a `main` (2026-09-01, CR22-8).
        if os.path.basename(toks[0]) in ("find", "fd", "fdfind"):
            i_ex = next((k for k, t in enumerate(toks)
                         if t in ("-exec", "-execdir", "-ok", "-okdir", "-x", "--exec")), None)
            if i_ex is not None and i_ex + 1 < len(toks):
                fin = next((k for k in range(i_ex + 1, len(toks))
                            if toks[k] in (";", "\\;", "+")), len(toks))
                dentro = [t for t in toks[i_ex + 1:fin] if t not in ("{}", "\"")]
                if dentro:
                    salida += verbos_efectivos(" ".join(dentro), profundidad + 1)
        i = 0
        while i < len(toks):
            t = toks[i]
            base = os.path.basename(t)
            resto = None
            # (a) flag de ejecución -> lo que sigue es otro comando
            duenio = _duenio_del_flag(toks, i)
            if (_RACIMO.match(t) and t not in FLAGS_EJECUCION and i + 1 < len(toks)
                    and any(c in _SHELLS for c in duenio)):
                resto = toks[i + 1:]
            elif t in FLAGS_EJECUCION and i + 1 < len(toks) and _flag_ejecuta(t, duenio):
                resto = toks[i + 1:]
                # CUALQUIER candidato, no solo el último. `_duenio_del_flag` devuelve TODOS
                # a propósito —`bash -o pipefail -c X`— y la rama de arriba ya hace `any(...)`;
                # mirar solo `duenio[-1]` deshacía ese arreglo justo aquí, y el cuerpo de un
                # `bash -o pipefail -c` multilínea —scripting corriente— desaparecía de los
                # dos hooks (2026-09-01, CR5-3).
                if not any(_payload_analizable(c, " ".join(resto)) for c in duenio):
                    resto = None
            elif "=" in t and t.split("=", 1)[0] in FLAGS_EJECUCION \
                    and _flag_ejecuta(t.split("=", 1)[0], duenio):
                resto = [t.split("=", 1)[1]] + toks[i + 1 :]
            # (c) verbo de dos palabras
            elif i + 1 < len(toks) and (base, toks[i + 1]) in PARES_EJECUCION:
                j = i + 2
                while j < len(toks) and (_OPCION.match(toks[j]) or _ASIGNACION.match(toks[j]) or "#" in toks[j]):
                    j += 1
                # `nix develop <DIR> --command X`: el DIR queda antes del flag,
                # y el flag lo recoge la rama (a) en la siguiente vuelta.
                resto = toks[j:] if j < len(toks) else None
            # (b) verbo simple envolvente
            elif base in VERBOS_EJECUCION:
                salto = VERBOS_EJECUCION[base]
                j = i + 1
                # EL BUCLE PARABA EN EL ARGUMENTO DE LA OPCIÓN. `nice -n 5 git commit -m x`
                # dejaba el verbo en «-n 5 git commit -m x» y ninguna regla casaba: siete
                # regresiones frente a `main`, encontradas al COMPONER prefijos con formas
                # (ronda 8) — cosa que el corpus plano no podía ver, porque sueltos los dos
                # ingredientes sí se denegaban.
                #
                # Se salta también el valor numérico que sigue a una opción corta, que es la
                # forma que tienen `nice -n 5`, `timeout -k 1`, `flock -w 1` e `ionice -c 2`.
                while j < len(toks) and (
                        _OPCION.match(toks[j]) or _ASIGNACION.match(toks[j])
                        or (j > i + 1 and _OPCION.match(toks[j - 1])
                            and _toma_valor(base, toks[j - 1]))):
                    j += 1
                # NO SE ELIGE UNA LECTURA A CIEGAS: SE EMITEN TODAS. Con
                # `timeout --preserve-status 5 git commit`, el bucle de opciones consume la
                # opción Y el `5`, y luego `salto` se llevaba también el `git`. El arreglo de
                # la ronda 10 —«no apliques `salto` si el bucle ya avanzó»— era un
                # INTERCAMBIO, no un arreglo: ganó `--preserve-status` y `chrt -f 10`, y
                # perdió `timeout -k 1 5`, `ssh -p 22 host` y `flock -w 1 /tmp/f`, que bash
                # ejecuta y `main` cortaba (ronda 11).
                #
                # La causa era elegir entre dos lecturas sin poder saber cuál. La salida es
                # no elegir: se emiten las dos como candidatas, y las reglas —que anclan al
                # principio— descartan la que no case. Un candidato de más es ruido; uno de
                # menos es un agujero.
                alternativas = []
                # UN LANZADOR ES TAMBIÉN DUEÑO DEL `-c` QUE VENGA DETRÁS. `uvx ruff -c 'X'`
                # ejecuta X, pero al pelar `uvx` el dueño del flag pasa a ser `ruff`, que no
                # es intérprete, y el comando interno desaparecía. Restaurar estos verbos aquí
                # (CR2-3) arreglaba `npx <verbo>` y rompía `npx <verbo> -c` — 100 pares del
                # suelo en rojo.
                #
                # Es la misma tensión de la ronda 11, y la misma salida: NO SE ELIGE UNA
                # LECTURA, se emiten las dos. Un candidato de más es ruido; uno de menos es un
                # agujero (2026-09-01).
                if base in _LANZADORES:
                    for k in range(i + 1, len(toks) - 1):
                        if toks[k] in FLAGS_EJECUCION or _RACIMO.match(toks[k]):
                            alternativas.append(toks[k + 1:])
                            break
                if j == i + 1:
                    j += salto
                elif salto and j + salto < len(toks):
                    alternativas.append(toks[j + salto:])
                # Y la opción con valor NO numérico (`sudo -u root X`, `ssh -i k host X`,
                # `timeout -s TERM 5 X`): el bucle para en el valor. Se emite también la
                # lectura que lo salta. La afirmación anterior —«ahí el verbo interno se ve
                # igual porque `sudo` lleva su propio salto»— era FALSA y estaba medida:
                # `sudo -u root git commit -m x` pasaba (ronda 11).
                if j > i + 1 and _OPCION.match(toks[j - 1]) \
                        and _toma_valor(base, toks[j - 1]):
                    # Solo si la opción TOMA valor. Sin esa condición, una opción booleana
                    # hacía saltar el verbo real: `sudo -E echo '…'` ascendía el argumento
                    # de `echo` a orden (ronda 12).
                    for n in (1, 1 + salto):
                        if j + n < len(toks):
                            alternativas.append(toks[j + n:])
                resto = toks[j:] if j < len(toks) else None
                for alt in alternativas:
                    salida.append(" ".join(alt))
                    salida += verbos_efectivos(" ".join(alt), profundidad + 1)
            if resto:
                interno = " ".join(resto)
                salida.append(interno)
                if len(resto) == 1:  # venía entrecomillado: analizar su interior
                    salida += verbos_efectivos(sin_comillas(resto[0]), profundidad + 1)
                else:
                    salida += verbos_efectivos(interno, profundidad + 1)
                break
            i += 1
    return [s for s in dict.fromkeys(salida) if s]


