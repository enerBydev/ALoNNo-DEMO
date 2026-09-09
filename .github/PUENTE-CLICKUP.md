# Por que este repo NO tiene los workflows del puente a ClickUp

`nuevo-proyecto.sh` los trae al nacer (`sync-cu.yml`, `release-a-tareas.yml`,
`ci-en-rojo.yml`) y en un repo privado de `enerBydev` funcionan. **Aqui se retiraron el
9 de septiembre de 2026**, por dos razones que se suman:

1. **No pueden resolver su accion.** Los tres hacen
   `uses: enerBydev/methodOS/.github/actions/sync-cu@main`, y methodOS es un repo
   **privado**. GitHub solo comparte acciones privadas con repos **privados** del mismo
   propietario: **este repo es publico**, asi que el job muere en `Set up job` con
   *«Unable to resolve action enerbydev/methodos, not found»*. Medido en el PR #5.

   `ci.yml` no tiene ese problema porque no usa `uses:` remoto: acuna un token de App de
   solo lectura y **se trae el kit a mano**. Los del puente no hacen eso.

2. **Aunque resolvieran, no harian nada.** El puente necesita el secreto `CLICKUP_TOKEN`,
   que es el token personal de Rene con lectura y escritura sobre los **dos workspaces
   enteros**. En un repo publico eso no entra — es la misma decision que se tomo en
   `nexus-ai-gateway` (tarea `86bbvpwd4`).

**Consecuencia asumida:** los estados de las tareas de ClickUp se mueven **a mano** con el
CLI `cu`. Un check permanentemente en rojo que no significa nada es peor que no tenerlo:
ensena a ignorar los rojos, que es exactamente lo que un gate no puede permitirse.

**Cuando volver a ponerlos:** si este repo pasa a privado, o si methodOS se hace publico
(decision pendiente, tarea `86bbv563p`). El scaffold los regenera; no hay que escribirlos.
