<script setup lang="ts">
/**
 * El mapa. Un coche compartido sin mapa no existe: es la pantalla que hace que alguien entienda
 * en dos segundos lo que tres parrafos no consiguen.
 *
 * DECISIONES MEDIDAS (docs/conocimiento/22-ecosistema-nuxt.md), no elegidas por costumbre:
 *
 *  * **Leaflet, no MapLibre.** 50 KB gzip contra 275 (5,5x). Y sobre todo: MapLibre exige WebGL,
 *    y en el Firefox headless de la maquina de pruebas tumba la pagina al 500. Para el proyecto
 *    pagado la recomendacion cambia —ahi si MapLibre, por licencia y por el coche en vivo—, pero
 *    eso es Etapa 1, no esta demo.
 *  * **`<LCircle :radius="2000">` es NATIVO y esta en METROS.** Es exactamente el radio del
 *    encargo («tracking within 1-2 km»), y con MapLibre habria que fabricarlo con `@turf/circle`.
 *  * **Esri World Light Gray, no CARTO.** CARTO —lo que pondria cualquiera— responde HTTP 200 y
 *    entrega la tesela con «API KEY REQUIRED» impreso encima. El sexto «200 mentiroso» del
 *    registro, y solo se caza MIRANDO la imagen.
 *  * **`:use-global-leaflet="false"`**: sin esto el modulo espera un Leaflet global que no existe.
 *
 * Coste de teselas: USD 0.
 */
const props = defineProps<{
	viajes: any[];
	/** Donde esta quien busca. Sin centro no se pinta el circulo: un radio sin centro miente
	 *  sobre lo que el motor esta haciendo. */
	centro?: [number, number] | null;
	radioKm?: number;
	seleccionado?: string | null;
}>();

/** Leaflet quiere [lat, lon]; GeoJSON da [lon, lat]. Se invierte en un solo sitio. */
const alReves = (p: [number, number]): [number, number] => [p[1], p[0]];

/**
 * NADA DE `<ClientOnly>` CON `#fallback`, Y NADA DE `v-if` PROPIO.
 *
 * Medido el 11-sep-2026, las dos variantes fallan igual: Vue reutiliza el nodo del marcador de
 * carga como contenedor del mapa y Leaflet aborta con `Map container not found`. La excepcion
 * ocurre en el hook `mounted`, revienta la hidratacion ENTERA y la pagina cae al 500 de
 * `error.vue` — un mapa accesorio se llevaba por delante toda la pantalla.
 *
 * `@nuxtjs/leaflet` ya sabe no renderizar en el servidor. Lo que hay que hacer es no ayudarle.
 */
const conRuta = computed(() =>
	props.viajes.filter((v) => v.viaje?.puntos?.length >= 2),
);

const centroMapa = computed<[number, number]>(() => {
	if (props.centro) return alReves(props.centro);
	const p =
		conRuta.value[0]?.viaje?.puntos?.[0] ?? props.viajes[0]?.viaje?.origen;
	return p ? alReves(p) : [52.52, 13.405];
});

/**
 * `invalidateSize()` DESPUES DE MONTAR, y no es opcional.
 *
 * El mapa se crea cuando su contenedor todavia no tiene altura util —esta dentro de un
 * `NuxtErrorBoundary` que aparece tras la hidratacion—, asi que Leaflet calcula 0x0 y coloca las
 * teselas fuera de la vista. Medido el 11-sep-2026: el contenedor existia (1) y las teselas se
 * descargaban (4 con HTTP 200), y la pantalla ense~naba 300 px de blanco. Una averia que solo se
 * ve MIRANDO la imagen, nunca en un log.
 */
function alEstarListo(mapa: any) {
	requestAnimationFrame(() => mapa?.invalidateSize?.());
}

/** El zoom sale de cuanto hay que abarcar: con radio 2 km se ve el barrio; con 40, la ciudad
 *  entera. Fijarlo a un numero deja la mitad de los casos fuera de cuadro. */
const zoom = computed(() => {
	const r = props.radioKm ?? 5;
	return r <= 2 ? 13 : r <= 10 ? 12 : r <= 25 ? 11 : 10;
});
</script>

<template>
  <div class="marco-mapa">
    <LMap
      :zoom="zoom"
      :center="centroMapa"
      :use-global-leaflet="false"
      :options="{ scrollWheelZoom: false, attributionControl: true }"
      class="mapa"
      style="height: 300px"
      @ready="alEstarListo"
    >
      <LTileLayer
        url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}"
        attribution="Esri, HERE, Garmin, OpenStreetMap · synthetic demo data"
        layer-type="base"
        name="gris"
      />

      <!-- El radio del encargo, en metros de verdad. -->
      <LCircle
        v-if="centro"
        :lat-lng="alReves(centro)"
        :radius="(radioKm ?? 2) * 1000"
        color="#0B5F5A"
        :weight="1"
        :fill-opacity="0.06"
      />

      <template v-for="v in conRuta" :key="v.id">
        <LPolyline
          :lat-lngs="v.viaje.puntos.map(alReves)"
          :color="seleccionado === v.id ? '#A94F0A' : '#0B5F5A'"
          :weight="seleccionado === v.id ? 5 : 3"
          :opacity="seleccionado && seleccionado !== v.id ? 0.3 : 0.85"
        />
        <LCircleMarker
          v-if="v.viaje.origen"
          :lat-lng="alReves(v.viaje.origen)"
          :radius="5"
          :color="seleccionado === v.id ? '#A94F0A' : '#0B5F5A'"
          :fill-opacity="1"
        >
          <LTooltip>{{ v.viaje.desde }} → {{ v.viaje.hasta }} · {{ v.plazas }} seats</LTooltip>
        </LCircleMarker>
      </template>

      <!-- Donde esta quien busca: el punto que explica por que el desvio significa algo. -->
      <LCircleMarker
        v-if="centro"
        :lat-lng="alReves(centro)"
        :radius="7"
        color="#fff"
        :weight="3"
        fill-color="#A94F0A"
        :fill-opacity="1"
      >
        <LTooltip>You are here</LTooltip>
      </LCircleMarker>
    </LMap>
  </div>
</template>

<style>
/* NO ESTA SCOPED A PROPOSITO: Leaflet crea sus nodos fuera del arbol del componente.
   El «preflight» de Tailwind 4 pone `max-width: 100%` y `display: block` a TODA imagen, y las
   teselas de Leaflet son imagenes colocadas en absoluto dentro de un panel transformado: con ese
   `max-width` se encogen y el mapa sale en blanco aunque las 4 teselas se hayan descargado con
   HTTP 200. Es el conflicto clasico Leaflet + Tailwind, y solo se ve mirando la captura. */
.leaflet-container img,
.leaflet-pane img,
.leaflet-tile {
  max-width: none !important;
  max-height: none !important;
}
/* LA ALTURA VA EN EL CONTENEDOR DE LEAFLET, NO EN UNA CLASE SCOPED.
   Medido: con `.mapa { height: 300px }` en un `<style scoped>`, el contenedor salia de **2 px**
   de alto —el atributo del scope no llega al div que crea el componente— y el mapa era una
   franja invisible con cuatro teselas descargadas y colocadas fuera. */
/* La altura va INLINE en `<LMap>` —como en el ejemplo verificado del banco de pruebas—, porque
   ni una clase scoped ni un descendiente global llegaban a aplicarla: el contenedor salia de
   **2 px** de alto con las cuatro teselas ya descargadas y colocadas fuera de la vista. */
.marco-mapa .leaflet-container {
  width: 100%;
  border-radius: var(--radio);
  border: 1px solid var(--linea);
  background: var(--papel);
  z-index: 0;          /* Leaflet pone z-index altos; sin esto tapa la cabecera pegajosa. */
}
</style>

<style scoped>
/* El hueco reservado ANTES de que el mapa exista: sin esto la lista salta 300 px hacia abajo
   cuando Leaflet monta, y un salto de medio segundo se lee como una pagina rota. */
.marco-mapa { min-height: 300px; }
</style>
