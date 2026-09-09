# Por qué existe cada cosa de este directorio

> **Regla 7 de methodOS: nada entra a `.claude/` hasta que un error real lo justifique.**
> Cada entrada lleva pegada la fecha y el fallo que la causó. Este archivo lo generó el
> scaffold de methodOS; los fallos citados son los originales que motivaron cada regla.

## `permissions.allow` — verbos envueltos en `direnv exec` con ruta absoluta

**Fallo (2026-08-19):** fuera del devshell no existen node, pnpm y wrangler (el sistema no tiene Node a propósito). Todo comando útil va envuelto
en `direnv exec <raíz>`, y sin declararlo el loop se detiene a pedir confirmación.
**El modo real en que muere un loop desatendido es quedarse parado pidiendo permiso a las
tres de la mañana.**

La ruta va **absoluta y completa** a propósito: `Bash(direnv exec:*)` sería un ejecutor
delegado sin acotar — exactamente el agujero del
[incidente de los ejecutores](https://github.com/enerBydev/methodos/blob/main/docs/incidentes/2026-08-19-ejecutores-delegados.md),
donde tres reglas así anulaban 81 denegaciones.

## Sin hook de formato a propósito

La plantilla no trae configuración de biome/eslint: un hook que invoque un formateador
sin configuración impone un estilo que nadie decidió (regla 1). Cuando exista la
configuración, entran a la vez el hook, el verbo `lint` y su sitio en `just ci`.

## `permissions.ask` / `deny`

Push, PR y deploy salen del repo y los ve otra gente. Publicar en un registro es
**irreversible** y `push --force` sobre `main` reescribe historia ajena: `deny`.

## Revisión (LOOP-5)

El harness se poda tan deliberadamente como se construye. A los ~6 meses de crear el
repo: qué regla no se usó nunca, qué hook sobra, qué se volvió primitiva nativa.
