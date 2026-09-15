<script setup lang="ts">
/**
 * `/` ES EL PRODUCTO. No una portada que lo explica.
 *
 * Lo que habia antes era un titular, tres tarjetas de texto y una franja explicando la
 * aritmetica: el producto quedaba a dos clics. Para un cliente que ya habia dicho que **no
 * entendia que le ense~naba la pantalla**, una pagina que explica en vez de mostrar es el error
 * anterior repetido en otro sitio (docs/conocimiento/20-critica-uiux.md §6).
 *
 * Asi que esta pantalla abre con una busqueda YA HECHA y cacheada: el cliente abre el link y en el
 * primer segundo ve conductores, horas, notas y precios. Los diez segundos siguientes los gasta
 * entendiendo el producto, no buscandolo.
 */
import frases from "../../db/frases.json";

useSeoMeta({
	title: "Match Engine — find the driver going your way",
	description:
		"Say it in one sentence, in German or English. The engine reads it, filters by " +
		"route and time, ranks, and explains the number.",
});

const { sesion } = useSesion();
const ruta = useRoute();
const toast = useToast();

// LA BUSQUEDA POR DEFECTO. Esta cacheada, asi que la portada carga en milisegundos y no depende
// del proveedor de IA. Es la diferencia entre abrir el link y ver el producto, o abrir el link y
// ver un campo vacio preguntandote que escribir.
const POR_DEFECTO =
	"Ich fahre morgen um 8 von Neukolln nach Mitte, zwei Plaetze frei";

const consulta = ref(String(ruta.query.q ?? POR_DEFECTO));
const campos = reactive({
	desde: String(ruta.query.desde ?? ""),
	hacia: String(ruta.query.hacia ?? ""),
	cuando: String(ruta.query.cuando ?? ""),
});
const cargando = ref(false);
const error = ref<string | null>(null);
const datos = ref<any>(null);
const abierto = ref<Record<string, boolean>>({});
const verDescartados = ref(false);
const senalado = ref<string | null>(null);
const paso = ref(0);
const paletaAbierta = ref(false);
// La telemetria vive detras de «Why these?» (P8): el estado es el titulo de la lista.
const verPorque = ref(false);

// EL MAPA SOLO DESPUES DE QUE LA PAGINA ESTE MONTADA Y PINTADA.
//
// Esta pantalla es un componente ASINCRONO —hace `await buscar()` en el setup, para que la
// portada llegue con resultados dentro del HTML—, asi que vive dentro de un `<Suspense>`. Con
// Suspense, el `mounted` de un hijo puede correr antes de que su elemento este de verdad en el
// documento, y Leaflet aborta con `Map container not found`. Esa excepcion revienta la
// hidratacion entera: un mapa accesorio tumbaba la pantalla al 500 (medido el 11-sep-2026,
// tres intentos con `ClientOnly`, con `#fallback` y con `v-if` dentro del componente).
//
// `onMounted` + `nextTick` garantiza el orden. Y `NuxtErrorBoundary` alrededor garantiza que,
// si vuelve a fallar por otra razon, lo unico que se pierda sea el mapa.
const mapaListo = ref(false);
onMounted(() => {
	nextTick(() => {
		mapaListo.value = true;
	});
});

const PASOS = [
	"Reading the sentence",
	"Hard filters: route, time, seats",
	"Vector + text retrieval, fused",
	"Scoring, component by component",
	"Writing the reason",
];

const CUANDO = [
	{ value: "", label: "any time" },
	{ value: "hoy", label: "today" },
	{ value: "manana", label: "tomorrow" },
	{ value: "este_finde", label: "this weekend" },
	{ value: "esta_semana", label: "this week" },
	{ value: "proximo_mes", label: "next month" },
];

/** Ejemplos propios del coche compartido. Las diez del cliente siguen estando —son el criterio de
 *  aceptacion (regla 4)— pero hablan de conciertos, y esta demo tambien tiene que saber
 *  ense~nar lo que el encargo de Workana pide de verdad. Marcado como a~nadido nuestro. */
const EJEMPLOS_COCHE = [
	{
		texto: "Ich fahre morgen um 8 von Neukolln nach Mitte, zwei Plaetze frei",
		ciudad: "Berlin",
	},
	{
		texto: "Suche Mitfahrgelegenheit morgen frueh Richtung Mitte",
		ciudad: "Berlin",
	},
	{
		texto: "I drive to Altstadt every weekday morning, two seats free",
		ciudad: "Koln",
	},
	{
		texto: "Ich brauche eine Fahrt nach Westend am Montag",
		ciudad: "Frankfurt",
	},
	{
		texto: "Anyone driving towards Maxvorstadt tomorrow around 8?",
		ciudad: "Munchen",
	},
];

let reloj: ReturnType<typeof setInterval> | null = null;
// La ciudad del ultimo ejemplo elegido; la sesion y «Berlin» son los respaldos.
const ciudadElegida = ref<string | null>(null);
// El mapa en movil va plegado: a 390 px ocupaba 300 px del pliegue y la primera respuesta
// quedaba a y=1041 en una pantalla de 844 (medido). Un chip lo abre.
const mapaAbierto = ref(false);
function alternarMapa() {
	mapaAbierto.value = !mapaAbierto.value;
	// Leaflet mide su contenedor al montar; si estaba oculto, midio 0. Un `resize` le hace
	// volver a medir sin exponer su instancia hasta aqui.
	if (mapaAbierto.value) nextTick(() => window.dispatchEvent(new Event("resize")));
}

async function buscar(
	opciones: { frase?: string; ciudad?: string; usarCampos?: boolean; fresco?: boolean } = {},
) {
	if (cargando.value) return;
	if (opciones.frase) {
		consulta.value = opciones.frase;
		campos.desde = campos.hacia = campos.cuando = "";
		// El ejemplo de Koln se buscaba con ciudad=Berlin: `EJEMPLOS_COCHE[].ciudad` existia y no
		// se usaba (programa de UX, 15-sep). Con la ciudad del ejemplo, «Altstadt» es la de Koln.
		ciudadElegida.value = opciones.ciudad ?? null;
	}
	const q = consulta.value.trim();
	if (!q) {
		// Un «no» sin salida: la frase vacia no hacia nada, ni peticion ni mensaje (medido).
		error.value = "Type a sentence first — or use the From / To / When fields above.";
		return;
	}

	cargando.value = true;
	error.value = null;
	paso.value = 0;
	// La espera es la mejor oportunidad de venta que tiene la demo, y se estaba tirando en un
	// circulito girando. Nombrar la capa que corre vende la arquitectura sin un solo parrafo.
	//
	// Solo en el cliente: Nuxt 4 aborta con un error explicito si `setInterval` corre en el
	// servidor, y tiene razon — un temporizador en SSR no lo ve nadie. Y la primera busqueda de
	// esta pantalla ocurre precisamente en SSR, que es lo que hace que la portada llegue con
	// resultados dentro del HTML.
	if (import.meta.client) {
		reloj = setInterval(() => {
			paso.value = Math.min(paso.value + 1, PASOS.length - 1);
		}, 1100);
	}

	const query: Record<string, string> = {
		q,
		ciudad: ciudadElegida.value ?? sesion.value?.city ?? "Berlin",
	};
	if (opciones.usarCampos) {
		if (campos.desde) query.desde = campos.desde;
		if (campos.hacia) query.hacia = campos.hacia;
		if (campos.cuando) query.cuando = campos.cuando;
	}
	if (opciones.fresco) query.fresco = "1";

	try {
		// `timeout` en el navegador: sin el, un proveedor colgado deja el esqueleto puesto minuto y
		// medio sin error y sin salida. El servidor ya tiene un presupuesto de 20 s; aqui van 3 mas
		// para que el que hable sea siempre el servidor, que sabe explicar lo que paso.
		datos.value = await $fetch("/api/buscar", { query, timeout: 23_000 });
		abierto.value = {};
		verDescartados.value = false;
		// La URL se actualiza SOLO EN EL CLIENTE. Con `navigateTo()` esto corria tambien en SSR y
		// Nuxt reescribia `%20` como `+`, asi que la URL resultante no coincidia con la pedida y
		// Firefox entraba en bucle de redirecciones: ningun enlace a una busqueda funcionaba, ni
		// recargar la pagina. Medido el 11-sep-2026.
		if (import.meta.client) {
			const u = new URL(window.location.href);
			u.search = new URLSearchParams({
				q,
				...(opciones.usarCampos ? campos : {}),
			}).toString();
			window.history.replaceState({}, "", u);
		}
	} catch (e: any) {
		datos.value = null;
		error.value =
			e?.name === "TimeoutError" || /timeout/i.test(String(e?.message))
				? "The AI provider did not answer in time. Try again — or use the From / To / When fields, " +
					"which skip the model entirely and always answer in under a second."
				: e?.data?.statusMessage || e?.statusMessage || "The search failed.";
	} finally {
		cargando.value = false;
		if (reloj) {
			clearInterval(reloj);
			reloj = null;
		}
	}
}

onBeforeUnmount(() => {
	if (reloj) clearInterval(reloj);
});

// La primera busqueda ocurre en el servidor, asi que la portada llega con resultados dentro del
// HTML. Es lo que hace que el primer vistazo sea el producto y no un formulario.
// Si la URL trae campos (p. ej. desde «Search for it» tras publicar un viaje), mandan.
await buscar({ usarCampos: Boolean(campos.desde || campos.hacia || campos.cuando) });

// Cuando la Capa 0 entiende la frase, los campos se rellenan SOLOS. No es un formulario que hay
// que rellenar: es la comprension del modelo hecha visible y corregible, que es el mejor
// argumento de venta que tiene la demo y hasta ahora vivia en una tarjeta de chips grises.
//
// `immediate: true` no es un detalle: la PRIMERA busqueda ocurre en el `await buscar()` de
// arriba, antes de que este `watch` exista, asi que sin esto la portada llegaba con los tres
// campos vacios justo debajo de unos resultados que si estaban filtrados por ellos.
watch(
	datos,
	(d) => {
		if (!d) return;
		// Si la busqueda salio de los campos, los campos son la verdad: rellenarlos con la
		// intencion pisaba la correccion del usuario con lo que decia la frase (medido).
		if (d.directo) return;
		campos.desde = d.intencion.city ?? "";
		campos.hacia = d.intencion.hacia ?? d.intencion.dest_city ?? "";
		campos.cuando = d.intencion.fecha?.expresion ?? "";
	},
	{ immediate: true },
);

const listas = computed(() => datos.value?.listas ?? []);

/** «2 rides tomorrow · Neukölln → Mitte»: el titulo ES el estado de la busqueda (P8). */
function tituloDe(l: any): string {
	const d = datos.value;
	const n = l.total;
	if (l.clave === "viajes") {
		const cuando = d?.ventana?.etiqueta ?? "";
		const desde = d?.intencion?.city ? capitalizar(d.intencion.city) : "";
		const hacia = d?.intencion?.hacia ? capitalizar(d.intencion.hacia) : "";
		const ruta = desde && hacia ? ` · ${desde} → ${hacia}` : hacia ? ` · to ${hacia}` : "";
		const que = d?.intencion?.trayecto ? (n === 1 ? "ride" : "rides") : (n === 1 ? "plan" : "plans");
		return `${n} ${que} ${cuando}${ruta}`;
	}
	return `${n} ${n === 1 ? "driver" : "drivers"} who match you`;
}
const capitalizar = (t: string) => t.replace(/(^|[\s-])(\p{L})/gu, (m) => m.toUpperCase());

/** El rotulo del mapa: el viaje se~nalado o, si no hay ninguno, el primero. */
const rotuloMapa = computed(() => {
	const lista = viajes.value;
	const r = lista.find((x: any) => x.id === senalado.value) ?? lista[0];
	if (!r) return null;
	const hora = r.cuando
		? new Date(r.cuando).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Berlin" })
		: "";
	const desvio = r.viaje?.km_de_tu_ruta != null ? ` · ${r.viaje.km_de_tu_ruta} km from you` : "";
	return `${r.conductor?.nombre ?? r.titulo} · ${hora}${desvio}`;
});
const viajes = computed(() =>
	(
		listas.value.find((l: any) => l.clave === "viajes")?.resultados ?? []
	).filter((r: any) => r.viaje),
);

const centro = computed<[number, number] | null>(() => {
	const v = viajes.value.find((r: any) => r.viaje?.origen);
	return v?.viaje?.origen ?? null;
});
const radio = computed(() => (datos.value?.intencion?.trayecto ? 2 : 40));

function pedirPlaza(r: any) {
	// DEMO: no escribe en la base. El flujo completo («agree to meet») vive en /plan/[id], que si
	// guarda el interes; aqui lo que importa es que la accion tenga una respuesta VISIBLE, que es
	// lo que no tenia: se pulsaba y no pasaba nada.
	toast.add({
		title: `Seat requested — ${r.conductor?.nombre ?? r.titulo}`,
		description: r.viaje
			? `${r.viaje.desde} → ${r.viaje.hasta} · waiting for the driver to confirm`
			: "waiting for a reply",
		icon: "i-lucide-check",
		color: "primary",
	});
}

defineShortcuts({
	meta_k: () => {
		paletaAbierta.value = true;
	},
});
</script>

<template>
  <div class="contenedor pagina">
    <!-- ── COLUMNA DEL PRODUCTO ──────────────────────────────────────────────────────────── -->
    <div class="producto">
      <!-- Sin h1, nada decia que hace el producto: el primer texto era «From» a 13 px (medido).
           Cuatro palabras (P1: ≤ 4), en segunda persona (P14). -->
      <header class="titular">
        <h1>Rides on your route</h1>
        <p class="tenue">Drivers already going your way, at your time.</p>
      </header>

      <!-- ── el buscador: los campos son la superficie, la frase es el atajo ────────────── -->
      <section class="buscador" :class="{ buscando: cargando }" aria-label="Find a ride">
        <div class="campos">
          <UFormField label="From" class="campo">
            <UInput v-model="campos.desde" size="xl" placeholder="Neukölln" icon="i-lucide-circle-dot" @keydown.enter="buscar({ usarCampos: true })" />
          </UFormField>
          <UFormField label="To" class="campo">
            <UInput v-model="campos.hacia" size="xl" placeholder="Mitte" icon="i-lucide-map-pin" @keydown.enter="buscar({ usarCampos: true })" />
          </UFormField>
          <UFormField label="When" class="campo estrecho-campo">
            <!-- `<select>` NATIVO, no `USelect`: el de Nuxt UI 4 rompe la hidratacion en SSR
                 (medido el 11-sep) y el nativo abre la rueda del sistema en movil. -->
            <select v-model="campos.cuando" class="nativo alto" aria-label="When">
              <option v-for="c in CUANDO" :key="c.value" :value="c.value">{{ c.label }}</option>
            </select>
          </UFormField>
          <!-- UNA primaria por pantalla (P5). Antes habia tres botones para la misma accion. -->
          <UButton size="xl" class="primaria" :loading="cargando" @click="buscar({ usarCampos: true })">
            Find rides
          </UButton>
        </div>

        <!-- La frase: Enter envia. Sin boton propio: la joya no necesita un segundo CTA. -->
        <UInput
          v-model="consulta"
          size="xl"
          class="entrada"
          placeholder="Or just say it — &quot;Ich fahre morgen um 8 von Neukölln nach Mitte&quot;"
          icon="i-lucide-message-square"
          aria-label="Say what you need, in German or English. Press Enter to search."
          @keydown.enter="buscar()"
        />

        <!-- Los atajos a la vista (P2), no detras de un glifo de Mac. -->
        <p class="ejemplos-linea">
          <span class="minusculo">Try:</span>
          <button v-for="e in EJEMPLOS_COCHE.slice(3, 5)" :key="e.texto" class="chip-ejemplo" type="button" @click="buscar({ frase: e.texto, ciudad: e.ciudad })">
            {{ e.texto }}
          </button>
          <button class="enlace" type="button" @click="paletaAbierta = true">all 15 sentences</button>
        </p>
      </section>

      <!-- ── error ────────────────────────────────────────────────────────────────────── -->
      <UAlert
        v-if="error" color="error" variant="subtle" icon="i-lucide-triangle-alert"
        :description="error" class="hueco"
      />

      <!-- ── esperando: la capa que corre, en TODA busqueda; esqueletos solo sin datos ───── -->
      <div v-if="cargando" class="progreso" role="status" aria-live="polite">
        <UIcon name="i-lucide-loader-circle" class="gira" />
        <span>{{ PASOS[paso] }}…</span>
        <span class="minusculo">step {{ paso + 1 }} of {{ PASOS.length }}</span>
      </div>
      <template v-if="cargando && !datos">
        <div v-for="n in 3" :key="n" class="hueso">
          <USkeleton class="h-5 w-2/5" />
          <USkeleton class="h-4 w-3/5" />
          <div class="hueso-fila">
            <USkeleton class="h-11 w-11 rounded-full" />
            <USkeleton class="h-4 w-1/3" />
          </div>
        </div>
      </template>

      <template v-if="datos">
        <!-- El caso degradado SI se avisa en linea: cambia lo que el usuario ve. El resto de
             la telemetria vive detras de «Why these?» (P8). -->
        <UAlert
          v-if="datos.degradado" color="warning" variant="subtle" icon="i-lucide-info" class="hueco"
          description="We couldn't read your sentence in time, so this search ran on rules and the three fields above. Correct one to search again."
        />

        <!-- El mapa en movil: plegado tras un chip. En escritorio vive en la columna derecha. -->
        <button v-if="viajes.length" class="chip-mapa" type="button" :aria-expanded="mapaAbierto" @click="alternarMapa">
          <UIcon :name="mapaAbierto ? 'i-lucide-chevron-up' : 'i-lucide-map'" />
          {{ mapaAbierto ? 'Hide map' : 'Show map' }}
        </button>
        <div v-if="viajes.length && mapaAbierto" class="solo-movil">
          <NuxtErrorBoundary v-if="mapaListo">
            <MapaRuta :viajes="viajes" :centro="centro" :radio-km="radio" :seleccionado="senalado" class="hueco" />
            <template #error><p class="minusculo hueco">Map unavailable. The results are unaffected.</p></template>
          </NuxtErrorBoundary>
        </div>

        <!-- ── DOS LISTAS, cada una ordenada por SU numero; el estado es el titulo (P8) ──── -->
        <section v-for="(l, i) in listas" :key="l.clave" class="lista">
          <div class="titulo-fila">
            <h2 class="titulo-lista">{{ tituloDe(l) }}</h2>
            <button v-if="i === 0" class="enlace" type="button" :aria-expanded="verPorque" @click="verPorque = !verPorque">
              {{ verPorque ? 'Hide' : 'Why these?' }}
            </button>
          </div>

          <!-- «Why these?»: lo que se entendio, el embudo y los tiempos — a un clic, no encima. -->
          <div v-if="i === 0 && verPorque" class="porque-estas">
            <p>
              <UBadge v-if="datos.directo" color="neutral" variant="subtle">From your fields</UBadge>
              <UBadge v-else-if="datos.degradado" color="warning" variant="subtle">Read without AI</UBadge>
              <UBadge v-else color="neutral" variant="subtle">Understood from your sentence</UBadge>
              <span class="minusculo">
                {{ datos.totales.candidatos }} candidates · {{ datos.totales.viajes }} rides ·
                {{ datos.totales.personas }} drivers · within {{ radio }} km of your route · {{ datos.ventana.etiqueta }}
              </span>
            </p>
            <p class="minusculo">
              <b>{{ datos.tiempos.total }} ms</b> — model {{ datos.tiempos.capa_0_llm + datos.tiempos.capa_4_llm }} ·
              embedding {{ datos.tiempos.embedding }} · Postgres {{ datos.tiempos.capa_1_2_postgres }} · scoring &lt;1.
              The model runs at most twice: once to read your sentence, once to phrase what you see.
              <button class="enlace" type="button" :disabled="cargando" @click="buscar({ fresco: true })">Run again without cache</button>
            </p>
          </div>

          <!-- Un «no» con dos salidas (P15). -->
          <div v-if="!l.resultados.length" class="vacio">
            <p>No one {{ l.clave === 'viajes' ? 'drives that route' : 'matches that' }} {{ datos.ventana.etiqueta }}.</p>
            <div class="salidas">
              <UButton size="sm" variant="soft" @click="campos.cuando = ''; buscar({ usarCampos: true })">Try any day</UButton>
              <UButton v-if="l.clave === 'viajes'" size="sm" variant="ghost" color="neutral" @click="campos.cuando = 'esta_semana'; buscar({ usarCampos: true })">
                See who drives it other days
              </UButton>
            </div>
          </div>

          <template v-for="r in l.resultados" :key="r.id">
            <div class="fila-resultado" @mouseenter="senalado = r.id" @mouseleave="senalado = null">
              <TarjetaViaje
                :r="r" :idioma-consulta="datos.intencion.language" :abierto="abierto[r.id]"
                @alternar="abierto[r.id] = !abierto[r.id]"
                @pedir="pedirPlaza(r)"
              />
            </div>

            <!-- el desglose: siete enteros que SUMAN el numero de al lado -->
            <div v-if="abierto[r.id]" class="desglose">
              <div v-for="c in r.componentes" :key="c.nombre" class="comp">
                <span class="comp-n">
                  {{ c.etiqueta_en }}
                  <em v-if="c.detalle">{{ c.detalle }}</em>
                </span>
                <UProgress :model-value="c.valor * 100" size="xs" class="comp-b" />
                <span class="comp-v">{{ c.valor.toFixed(2) }} × {{ c.peso.toFixed(2) }}</span>
                <b class="comp-p">+{{ c.puntos_enteros }}</b>
              </div>
              <div class="comp suma">
                <span class="comp-n">adds up to</span>
                <span class="comp-b" /><span class="comp-v" />
                <b class="comp-p">{{ r.porcentaje }}</b>
              </div>
            </div>
          </template>
        </section>

        <!-- ── los near-miss: por que NO salieron ─────────────────────────────────────── -->
        <section v-if="datos.descartados.length" class="hueco">
          <UButton
            variant="ghost" color="neutral" size="sm"
            :icon="verDescartados ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'"
            @click="verDescartados = !verDescartados"
          >
            Ruled out, and why ({{ datos.totales.descartados }})
          </UButton>
          <ul v-if="verDescartados" class="descartados">
            <li v-for="r in datos.descartados" :key="r.id">
              <b>{{ r.porcentaje }}%</b> {{ r.titulo }} — <i>{{ r.motivo_descarte }}</i>
            </li>
          </ul>
        </section>
      </template>
    </div>

    <!-- ── COLUMNA DEL MAPA (escritorio) ─────────────────────────────────────────────────── -->
    <aside v-if="datos && viajes.length" class="lateral">
      <NuxtErrorBoundary v-if="mapaListo">
        <MapaRuta :viajes="viajes" :centro="centro" :radio-km="radio" :seleccionado="senalado" />
        <template #error><p class="minusculo">Map unavailable. The results are unaffected.</p></template>
      </NuxtErrorBoundary>
      <!-- El rotulo del viaje se~nalado: el mapa contesta algo, no solo decora (P8). -->
      <p v-if="rotuloMapa" class="rotulo">{{ rotuloMapa }}</p>
      <p class="minusculo pie-mapa">
        A portfolio demo by enerBydev. Synthetic drivers and rides; a real engine.
        <NuxtLink to="/como-funciona">How the matching works →</NuxtLink>
      </p>
    </aside>

    <!-- ── las 15 frases: las diez del cliente mas las cinco de coche ────────────────────── -->
    <UModal v-model:open="paletaAbierta" title="Try a sentence">
      <template #body>
        <div class="grupo">
          <p class="grupo-t">Rides — say it your way</p>
          <button
            v-for="e in EJEMPLOS_COCHE" :key="e.texto" class="ejemplo"
            @click="paletaAbierta = false; buscar({ frase: e.texto, ciudad: e.ciudad })"
          >
            <UBadge size="sm" color="neutral" variant="subtle">{{ e.ciudad }}</UBadge>
            {{ e.texto }}
          </button>
        </div>
        <div class="grupo">
          <p class="grupo-t">Plans — concerts, matches, trips</p>
          <button
            v-for="f in frases" :key="f.escenario" class="ejemplo"
            @click="paletaAbierta = false; buscar({ frase: f.frase_del_cliente })"
          >
            <UBadge size="sm" color="neutral" variant="subtle">
              {{ /[äöüßÄÖÜ]|^Ich|^Meine/.test(f.frase_del_cliente) ? 'DE' : 'EN' }}
            </UBadge>
            {{ f.frase_del_cliente }}
          </button>
        </div>
      </template>
    </UModal>
  </div>
</template>


<style scoped>
/* Dos columnas en escritorio: 600 de producto, 20 de aire, 360 de mapa (spec §4.3 del informe
   05). Antes el mapa ocupaba el 28 % del viewport y la primera respuesta quedaba bajo el
   pliegue a 1280x800 (medido). En movil, una columna y el mapa tras un chip. */
.pagina { display: grid; grid-template-columns: 1fr; gap: var(--e5); align-items: start; }
.lateral { display: none; }
@media (min-width: 1024px) {
  .pagina { grid-template-columns: 600px 360px; column-gap: 20px; }
  .lateral { display: block; position: sticky; top: 72px; padding-top: 40px; }
  .chip-mapa, .solo-movil { display: none !important; }
}
.rotulo { font-size: var(--t-13); font-weight: 600; margin-top: var(--e2); }
.pie-mapa { margin-top: var(--e3); color: var(--tinta-3); }
.pie-mapa a { display: block; margin-top: 2px; }
.primaria { min-width: 120px; }
/* A 600 px de columna: From y To reparten, When 130, boton 120, en UNA fila (spec §4.3). */
@media (min-width: 1024px) {
  .campos { flex-wrap: nowrap; }
  .campo { flex: 1 1 0; min-width: 0; }
  .estrecho-campo { flex: 0 0 130px; }
  .primaria { flex: 0 0 120px; }
}
.titulo-fila .enlace { white-space: nowrap; }
.nativo.alto { height: 48px; min-height: 48px; }
.ejemplos-linea { display: flex; align-items: center; gap: var(--e2); flex-wrap: wrap; }
.chip-ejemplo {
  font: inherit; font-size: var(--t-13); color: var(--tinta-2); background: transparent;
  border: 1px solid var(--linea-fuerte); border-radius: 999px; padding: 4px var(--e3);
  cursor: pointer; max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.chip-ejemplo:hover { border-color: var(--accion); color: var(--accion); }
.titulo-fila { display: flex; align-items: baseline; justify-content: space-between; gap: var(--e3); margin-bottom: var(--e3); }
.titulo-fila .titulo-lista { margin-bottom: 0; }
.porque-estas { display: grid; gap: var(--e2); padding: var(--e3) var(--e4); margin-bottom: var(--e3);
  border: 1px solid var(--linea); border-radius: var(--radio-2); background: var(--superficie); }
.porque-estas p { display: flex; gap: var(--e2); align-items: center; flex-wrap: wrap; }
.salidas { display: flex; gap: var(--e2); margin-top: var(--e2); flex-wrap: wrap; }
.buscador { display: grid; gap: var(--e3); margin-bottom: var(--e5); }
.campos { display: flex; gap: var(--e3); align-items: flex-end; flex-wrap: wrap; }
.campo { flex: 1 1 180px; }
.estrecho-campo { flex: 0 1 150px; }
.entrada { width: 100%; }

.hueco { margin: var(--e4) 0; }
.titular { margin-bottom: var(--e4); }
.titular h1 { font-size: var(--t-40); line-height: 1.1; margin-bottom: var(--e2); }
.titular p { font-size: var(--t-16); }
.buscando .campos, .buscando .frase { opacity: .7; }
/* 12 px entre tarjetas, como manda la especificacion: el selector viejo no casaba con el
   envoltorio (medido: 0 px). */
.fila-resultado { margin-bottom: var(--e3); }
.chip-mapa { display: none; }
@media (max-width: 720px) {
  .titular h1 { font-size: var(--t-22); }
  .titular p { font-size: var(--t-15); }
  .chip-mapa {
    display: inline-flex; align-items: center; gap: var(--e1); font: inherit; font-size: var(--t-13);
    font-weight: 600; color: var(--accion); background: var(--accion-suave); border: 0;
    border-radius: 999px; padding: 8px var(--e3); min-height: 36px; margin: var(--e2) 0; cursor: pointer;
  }
  .mapa-portada:not(.abierto) { display: none; }
}

.progreso {
  display: flex; align-items: center; gap: var(--e2);
  padding: var(--e4); border: 1px solid var(--linea); border-radius: var(--radio);
  background: var(--superficie); margin: var(--e4) 0 var(--e3);
  font-size: var(--t-15); font-weight: 500;
}
.gira { animation: giro 1s linear infinite; color: var(--accion); }

.hueso {
  display: grid; gap: var(--e2); padding: var(--e5); margin-bottom: var(--e3);
  border: 1px solid var(--linea); border-radius: var(--radio); background: var(--superficie);
}
.hueso-fila { display: flex; align-items: center; gap: var(--e2); }

.entendido {
  display: flex; align-items: center; gap: var(--e2); flex-wrap: wrap;
  padding: var(--e3) 0; border-top: 1px solid var(--linea); border-bottom: 1px solid var(--linea);
  margin-bottom: var(--e4);
}
.empuja { flex: 1 1 auto; }

.lista { margin-bottom: var(--e7); }
.titulo-lista {
  display: flex; align-items: baseline; gap: var(--e2);
  margin-bottom: var(--e3); font-size: var(--t-22);
}
.lista > :deep(.viaje) { margin-bottom: var(--e3); }

.vacio {
  padding: var(--e5); border: 1px dashed var(--linea); border-radius: var(--radio);
  color: var(--tinta-2); font-size: var(--t-15);
}
.enlace { background: none; border: none; font: inherit; color: var(--accion); cursor: pointer; text-decoration: underline; padding: 0; }

.desglose {
  margin: calc(var(--e3) * -1) 0 var(--e3);
  padding: var(--e4) var(--e5);
  background: var(--papel); border: 1px solid var(--linea); border-top: 0;
  border-radius: 0 0 var(--radio) var(--radio);
}
.comp {
  display: grid; grid-template-columns: 1fr 90px 110px 44px;
  gap: var(--e2); align-items: center;
  font-size: var(--t-13); padding: 3px 0;
}
.comp-n em { color: var(--tinta-3); font-style: normal; }
.comp-v { text-align: right; color: var(--tinta-3); font-variant-numeric: tabular-nums; }
.comp-p { text-align: right; font-variant-numeric: tabular-nums; }
.suma { border-top: 1px solid var(--linea); margin-top: var(--e1); padding-top: var(--e2); }
.suma .comp-p { font-size: var(--t-16); }

.descartados { list-style: none; padding: var(--e2) 0 0; font-size: var(--t-13); color: var(--tinta-2); }
.descartados li { padding: 2px 0; }

.tiempos { margin-top: var(--e6); border-top: 1px solid var(--linea); padding-top: var(--e3); }

.grupo { margin-bottom: var(--e4); }
.grupo-t { font-size: var(--t-13); font-weight: 600; color: var(--tinta-3); margin-bottom: var(--e2); }
.ejemplo {
  display: flex; gap: var(--e2); align-items: flex-start; width: 100%; text-align: left;
  font: inherit; font-size: var(--t-15); cursor: pointer; color: inherit;
  background: var(--superficie); border: 1px solid var(--linea);
  border-radius: var(--radio-2); padding: var(--e2) var(--e3); margin-bottom: var(--e1);
}
.ejemplo:hover { border-color: var(--accion); background: var(--accion-suave); }

@media (max-width: 640px) {
  /* Dos filas de 44 px —From | To · When | Search— como pide la especificacion del primer
     viewport: apilado a ancho completo, la primera respuesta quedaba a y=1041 en una pantalla
     de 844 (medido). */
  .campos { display: grid; grid-template-columns: 1fr 1fr; gap: var(--e2); align-items: end; }
  .campo, .estrecho-campo { flex: none; min-width: 0; }
  .campos > :deep(button) { width: 100%; }
  .ejemplos-linea .chip-ejemplo { max-width: 100%; }
  .comp { grid-template-columns: 1fr 70px 44px; }
  .comp-b { display: none; }
}
</style>
