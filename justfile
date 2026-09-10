# La costura de methodOS: ESTE ARCHIVO ES EL PIPELINE.
# `just ci` ejecuta exactamente lo que ejecuta .github/workflows/ci.yml — el CI lo
# invoca, así que local y remoto no pueden divergir por descuido.
#
# Extraído del gate real de calc-nuxt (2026-08-19).

# Lista los verbos disponibles
default:
    @just --list --unsorted

# ── El gate ──────────────────────────────────────────────────────────────────────
# Sin `lint`: la plantilla no impone configuración de biome/eslint que nadie decidió
# (regla 1). Cuando el repo la tenga, el verbo entra aquí y en `ci`.
ci: install catalogo cambios test audit secretos superficie hechos

# ── Los verbos ───────────────────────────────────────────────────────────────────

# Dependencias exactas del lockfile (BUILD-1)
install:
    pnpm install --frozen-lockfile

# El catálogo, cerrado por las dos puntas: ninguna dependencia catalogada se escribe con
# versión literal, y ninguna entrada del catálogo se queda sin consumidor. Lo segundo es lo
# que costó una tarde: el catálogo decía wrangler 4.129.0, nadie lo declaraba, y `pnpm exec
# wrangler` ejecutaba el 4.93.0 de nixpkgs. Una versión que nadie usa no es una versión.
catalogo:
    python3 bin/verificar-catalogo.py

# Cada paquete que cambia trae su changeset, PAQUETE POR PAQUETE (ADR-0016). `changeset status`
# solo falla si no hay NINGUN changeset nuevo: con uno que cubra otros paquetes, tocar el tuyo
# sin nombrarlo pasa. Eso es una salvaguarda que no salvaguarda. Calla si no hay `.changeset/`.
cambios:
    python3 bin/verificar-cambios.py

# Suite (vitest)
test:
    pnpm test

# Escaneo de secretos sobre TODO el historial (CODE-5). Bloqueante a proposito: una fuga
# no se integra, punto (ADR-0009). `git` escanea el historial; `dir` solo el arbol.
#
# LOCAL Y CI MIDEN LO MISMO, y esa es la unica forma de que este verbo sirva de algo.
#
# EL FALLO (2026-09-06, en el mismo run del CI de ClickUpCLI): la accion compartida escaneo
# con `--config` y dijo «no leaks found»; este verbo escaneo SIN `--config` y dijo «leaks
# found: 1», tumbando la receta. Dos veredictos opuestos sobre el mismo arbol, en el mismo
# minuto — que es justo lo que la regla 2 («el pipeline ES el justfile») existe para impedir.
#
# Y lo segundo es peor: sin `--config`, gitleaks lee el `.gitleaks.toml` DE ESTE REPO. Es el
# agujero que ADR-0009 cerro en la accion —el auditado configurando a su auditor— y que
# seguia abierto aqui. `bin/gitleaks.toml` es una COPIA de la config del gate, que el
# scaffold trae al nacer; el medidor comprueba que no divergio (CODE-5).
secretos:
    gitleaks git . --config bin/gitleaks.toml --no-banner --redact
# Auditoría de vulnerabilidades de dependencias (BUILD-4). Advisory: el '-' hace que
# just ignore el exit — una CVE nueva avisa en el log, no tumba el gate.
# EL `-` YA NO ESTÁ, y el exit code deja de perderse. `pnpm audit --audit-level moderate` encontraba una
# CVE real, la imprimía, salía 1 — y el `-` lo convertía en 0: `just ci` daba verde y el
# medidor daba BUILD-4 por cumplido. Nadie leía la salida.
#
# Quitar el `-` a secas rompería ADR-0009 —una CVE la causa el mundo, no tu diff, y tumbar un
# deploy por un evento externo incentiva silenciar el aviso—. Por eso corre el REGISTRO:
# un hallazgo nuevo se anota con su plazo y NO bloquea; uno vencido sí. La aparición la causó
# el mundo; la permanencia la causas tú.
audit:
    python3 bin/verificar-hallazgos.py

# Servidor de desarrollo (requiere script `dev` en package.json)
dev:
    pnpm dev

# Build de producción (requiere script `build`)
build:
    pnpm build

# Borra artefactos y cachés generados
clean:
    rm -rf .nuxt .output dist node_modules/.vite

# Que las banderas que este proyecto USA existan en la version que su devshell instala
# (2026-09-02). No es documentacion embebida: un documento no puede avisarte de que acabas de
# escribir una bandera que no existe. Este verbo le pregunta a la herramienta.
superficie:
    python3 bin/verificar-superficie.py

# Que lo escrito SIGA SIENDO CIERTO: rutas citadas que ya no existen, comandos `just` que nadie
# declara, entidades retiradas citadas en presente.
#
# EL FALLO QUE LO TRAE (2026-09-10, este repo): `ESTADO.md` afirmaba `vector(384)` y `gte-small`
# cuando el esquema aplicado era `vector(2048)` y el modelo nemotron — y `just ci` paso en VERDE
# con esa contradiccion dentro, porque el gate de este repo no miraba la documentacion. La
# propuesta le promete al cliente exactamente este control: *"a documentation gate breaks the
# build when the repository describes something that no longer exists"*.
#
# Un documento que narra un momento concreto (un informe fechado, un incidente) se sella en su
# cabecera con `<!-- hechos: congelado AAAA-MM-DD -->` y deja de auditarse.
hechos:
    python3 bin/verificar-hechos.py .
