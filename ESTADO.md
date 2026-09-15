# ESTADO — la demo es un coche compartido (11 de septiembre de 2026)

Entrega: **miercoles 16 de septiembre**. Ventana de feedback pedida: **3 dias habiles → hasta el
lunes 21**. Quedan 5 dias de construccion.

> **El giro del dia.** Hasta hoy la demo emparejaba **planes sociales**. `pickando.docx` —el
> adjunto del encargo publicado en Workana— describe una **app de coche compartido**, y es lo que
> el anuncio paga. La demo pasa a ser eso **sin tirar el motor**, porque los dos productos son el
> mismo problema: alguien con plazas libres y una ventana de tiempo, y alguien que quiere
> coincidir en espacio, direccion y hora. Las 10 frases de Helder siguen funcionando.
>
> **Sigue haciendo falta preguntarle a Helder cual de los dos productos esta vivo** (`86bbyvz4w`).

## Lo que hay construido, verificado hoy

| | Comprobacion |
|---|---|
| Nuxt 4.5.2 + Nitro, preset `cloudflare_module` | desplegado: <https://alonno-demo.enerby212.workers.dev> |
| Base en **Frankfurt** (`qbrgwphcpflbwhfqhffc`) | pgvector 0.8.2 · PostGIS 3.3.7 · pg_trgm 1.6 |
| El esquema, con la capa de coche | `profiles`/`plans`/`intents`/`intereses`/`valoraciones` · `vector(2048)` · HNSW sobre `halfvec(2048)` · `ruta geography(linestring)` con indice GiST |
| El mundo sembrado | 240 perfiles (**120 conductores**) · 300 planes, de los que **120 son trayectos de diario** y **254 tienen ruta** · 42 intents · **1.185 valoraciones** bilingues, nota media **4,72** |
| La app alcanza la base | `/api/salud` → `{"estado":"ok","bd":"ok","region_bd":"eu-central-1 (Frankfurt)"}` |
| methodOS | `just ci` exit 0 · **50 tests** · gitleaks sin fugas · `hechos` y `superficie` en verde · revisor maquina aprobando los PR |
| Base de conocimiento | **16 informes** en `docs/conocimiento/` (repo privado), con los tres de hoy |
| RLS activo en las cinco tablas | INSERT anonimo → `401 violates row-level security`; probado en `tests/rls.test.ts` |

## El motor, ahora que empareja coches

Las cinco capas del §6 siguen exactamente donde estaban. Lo que cambio es el **dominio** y una
consulta:

- **La ruta es una linea, no dos puntos.** `st_dwithin(p.ruta, punto, 2000)` encuentra al
  conductor que **pasa** por tu barrio sin salir ni llegar alli. Es el requisito central del
  docx —*«tracking within 1-2 km of all drivers driving on the same route»*— y es literalmente
  invisible con dos puntos. Medido: **8 conductores pasan por Kreuzberg** sin salir ni llegar
  a menos de 1,2 km de alli.
- **Dos radios, una consulta**: 2 km si la frase es un trayecto, 40 km si es un plan.
- **La nota del conductor pesa en el score.** Hasta hoy `trust` estaba clavado a 0,6 porque no
  habia dato. Con menos de 3 valoraciones la nota **no cuenta** (ni se ense~na): un 5,0 de una
  persona no es mejor que un 4,7 de treinta y siete.
- **Una tercera banda de calibracion**, medida y no estimada. El texto de un viaje son quince
  palabras; el de un plan, dos frases. Con la banda de los planes, el viaje perfecto se quedaba
  en 74 %. Con la suya —piso 0,30, techo 0,60, sacados de 29 similitudes reales— da **87 %**.

## Los cuatro fallos que rompian la demo antes que ningun diseno

Los encontro la critica de UI/UX **usando el producto desplegado con un navegador real**, no
leyendo el codigo. Los cuatro estan arreglados y tres tienen test:

1. **Ninguna llamada al proveedor tenia techo.** Una busqueda tardo **82 s** con las capas 0-3
   sumando 10: los otros 70 eran una peticion colgada. Ahora hay techo por llamada (6 s
   embedding, 14 s chat) y **presupuesto de 20 s** para la peticion entera; la Capa 4 —la prosa,
   la unica capa que el cliente no necesita— cobra lo que sobre y se salta si no sobra.
2. **El desglose no sumaba.** `28+18+15+15+10+4+3` son **93** y la pantalla decia **91**. Reparto
   del resto mayor, con `tests/reparto.test.ts`. Golpeaba la unica promesa que la demo hace en
   voz alta: *«a number you can check by hand»*.
3. **El orden contradecia al numero.** La lista salia `91·72·71·69·63·60·54·54·**86**·46`: un
   86 % nueve puestos por debajo de dos 54 %, porque se ordenaba por el numero ya multiplicado y
   se ense~naba el numero sin multiplicar. Ahora son **dos listas**, cada una con su orden.
4. **`centroDe` conocia nueve ciudades** y la Capa 0 devuelve barrios. Sin centro no hay filtro
   de radio: a un berlines se le contestaba con coches de Dusseldorf. Los 63 barrios se
   **generan** de los catalogos del seed (`scripts/generar-lugares.py`) para que no haya dos
   verdades sobre donde esta Kreuzberg.

Y uno mas, que no estaba en la lista: **`/buscar?q=…` entraba en bucle de redirecciones** porque
`navigateTo()` corria en SSR y Nuxt reescribia `%20` como `+`. Ningun enlace a una busqueda
funcionaba, ni recargar la pagina.

## La demo ya no depende del proveedor de IA

Es el cambio que mas tranquilidad compra para el dia 16. **El respaldo por reglas entiende
trayectos** («von X nach Y», «Richtung Y», «from X to Y», los digrafos `ue`/`oe`/`ae`), asi que
con la Capa 0 **apagada** la busqueda perfecta sigue dando **87 %** y el mundo sigue filtrado por
ciudad y radio. Antes, degradarse significaba `city: null` y contestar con coches de otra ciudad.

Ademas, **los campos Desde / Hasta / Cuando son un camino que no toca el modelo**: corregir uno
relanza la busqueda en menos de un segundo, siempre.

## La cara nueva

- **Un color de accion y uno de alarma.** El naranja anterior era marca, boton, barra, avatar,
  etiquetas y enlaces a la vez. Y dos colores fallaban: `--tenue` sobre `--papel` daba **4,37:1**
  —por debajo de AA— justo en la linea que decide la compra, y `--linea` daba **1,25:1**, o sea
  bordes invisibles.
- **Inter auto-alojada** por `@nuxt/fonts` (sin `<link>` a Google: el cliente es aleman), cifras
  tabulares, escala 12/13/15/16/18/22/28/40 y espaciado de 4 px.
- **La portada ES el producto**, con una busqueda ya hecha y cacheada. Antes era una pagina que
  explicaba el producto y lo dejaba a dos clics — el mismo error que hizo que este cliente dijera
  que no entendia lo que le ense~naban.
- **Mapa** con la ruta, el circulo metrico de 2 km y la posicion del pasajero.
- **La tarjeta de viaje** con jerarquia de movilidad: hora de salida a 22 px, ruta a 18, el
  desvio («pasa a 0,3 km de ti») siempre visible, foto, nota, coche, plazas, precio, y el
  porcentaje en su propia columna.

## El ecosistema: dos paquetes, no diez

Medido en un banco de pruebas con el mismo Nuxt y el mismo preset, construyendo ocho veces:
**`@nuxt/ui` 4.11.1** y **`@nuxtjs/leaflet` 1.3.2**. DevTools ya venia dentro de Nuxt y estaba
apagado. Se descartan con numeros **Content** (+148 KB gzip de Worker para tres paginas de
texto), **Image** (imposible: su proveedor de Cloudflare exige una zona y la demo vive en
`workers.dev`) y **MapLibre** (5,5x mas pesado y exige WebGL).

El Worker pesa **1,46 MB** sin comprimir: el **2,3 %** del limite de 64 MiB.

## Lo que queda flojo, y se dice (regla 8)

1. **`main` no esta protegida.** El unico ruleset es `prueba-de-disponibilidad-BORRAR`,
   desactivado, y se ve en un repo publico.
2. **`/api/salud` siempre responde `ok`.** Contesto en 0,29 s mientras `/api/buscar` colgaba
   92 s. Una sonda que no puede estar en rojo no es una sonda.
3. **La latencia en frio sigue siendo del proveedor**: la Capa 0 tarda entre **6,8 y 9,2 s**
   (medido dos veces seguidas, 1.108 tokens de entrada y 190 de salida — el coste esta en la
   salida). Con cache, 0,3 s. El plan para el dia 16 es **calentar la cache** de todas las frases
   antes de mandar el link, y que el camino de los campos exista para lo que el cliente teclee.
4. **El contador de solicitudes en la cabecera** no esta. Pedir plaza si responde: sale un aviso
   y el boton cambia en el sitio.
5. **Las bios del seed se repiten**: cuatro perfiles con el mismo texto literal pueden salir en
   la misma pantalla, y eso se lee como datos falsos.

## Workers Builds SI despliega desde `main` — y el indicador que decia lo contrario miente

La auditoria de DevOps de hoy concluyo que Workers Builds no estaba conectado, porque **las 39
versiones del Worker decian `source: wrangler`**. La conclusion era razonable y es **falsa**, y
conviene que conste por que:

**Workers Builds ejecuta `npx wrangler deploy` DENTRO de la construccion**, asi que la version
que crea queda etiquetada igual que un despliegue desde un portatil. El campo `source` no
distingue las dos cosas, y no hay ningun otro campo que lo haga.

Comprobado hoy extremo a extremo, que es la unica forma:

| | |
|---|---|
| merge del PR #20 a `main` | 10:42 |
| version 40 del Worker | **10:43:37**, 73 s despues |
| ¿desplego alguien a mano? | no: nadie corrio `wrangler deploy`, y `.github/workflows/` solo tiene `ci.yml`, que **no despliega** |
| ¿sirve produccion el codigo nuevo? | si: `<title>ALoNNo — find the driver going your way</title>`, mapa con 10 teselas y 6 tarjetas, en Firefox real |

La leccion es la de siempre en este repo: **un campo que se lee como una prueba no siempre lo
es**. Lo que prueba el git-connect es la cadena entera —empujar, esperar, y ver el cambio en
produccion—, no un `source` en una respuesta JSON.

## Lo siguiente, en orden

1. Proteger `main` y borrar el ruleset de prueba.
2. `/api/salud` que pueda estar en rojo: que toque el proveedor de IA y la base, con tiempos.
3. Diversificar las bios del seed.
4. **Re-sembrar el dia 16** y calentar la cache antes de mandar el link.
5. El mensaje de entrega con la contrapropuesta y **la pregunta de cual de los dos productos
   esta vivo**.

## La lista de comprobacion del dia 16, antes de mandar el link

1. `just seed` y `just sembrar` — **re-sembrar**, para que las fechas vuelvan a ser relativas a
   ese dia. Es el bug mas probable de todo el proyecto y ocurre delante del cliente.
2. `just frases` — las 10 frases de Helder, y que ninguna devuelva vacio.
3. Abrir la demo en un navegador de verdad, no con `curl`.
4. Calentar la cache de las frases y de los ejemplos de coche compartido.
5. Escribir en el mensaje lo que **no** entra: pagos, tiempo real, chat, notificaciones, apps
   nativas. Es literalmente lo que hizo que este cliente volviera despues de desaparecer una vez.
