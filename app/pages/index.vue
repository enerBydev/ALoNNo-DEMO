<script setup lang="ts">
/**
 * `/` ES EL PRODUCTO. No una portada que lo explica.
 *
 * Lo que habia antes era un titular, tres tarjetas de texto y una franja explicando la
 * aritmetica: el producto quedaba a dos clics. Para un cliente que ya habia dicho que **no
 * entendia que le ense~naba la pantalla**, una pagina que explica en vez de mostrar es el error
 * anterior repetido en otro sitio (docs/conocimiento/20-critica-uiux.md §6).
 *
 * Asi que esta pantalla abre con una busqueda YA HECHA y cacheada: Helder abre el link y en el
 * primer segundo ve conductores, horas, notas y precios. Los diez segundos siguientes los gasta
 * entendiendo el producto, no buscandolo.
 */
import frases from "../../db/frases.json";

useSeoMeta({
	title: "ALoNNo — find the driver going your way",
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

/** Ejemplos propios del coche compartido. Los diez de Helder siguen estando —son el criterio de
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

async function buscar(
	opciones: { frase?: string; usarCampos?: boolean; fresco?: boolean } = {},
) {
	if (cargando.value) return;
	if (opciones.frase) {
		consulta.value = opciones.frase;
		campos.desde = campos.hacia = campos.cuando = "";
	}
	const q = consulta.value.trim();
	if (!q) return;

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
		ciudad: sesion.value?.city ?? "Berlin",
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
await buscar();

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
		campos.desde = d.intencion.city ?? "";
		campos.hacia = d.intencion.hacia ?? d.intencion.dest_city ?? "";
		campos.cuando = d.intencion.fecha?.expresion ?? "";
	},
	{ immediate: true },
);

const listas = computed(() => datos.value?.listas ?? []);
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
  <div class="contenedor">
    <!-- ── el buscador: los campos son la superficie, la frase es el atajo ─────────────── -->
    <section class="buscador">
      <div class="campos">
        <UFormField label="From" class="campo">
          <UInput v-model="campos.desde" placeholder="Neukolln" icon="i-lucide-circle-dot" />
        </UFormField>
        <UFormField label="To" class="campo">
          <UInput v-model="campos.hacia" placeholder="Mitte" icon="i-lucide-map-pin" />
        </UFormField>
        <UFormField label="When" class="campo estrecho-campo">
          <!-- `<select>` NATIVO, no `USelect`. El de Nuxt UI 4 rompe con «Component is missing
               template or render function: SelectItem» y esa excepcion tumba la hidratacion
               ENTERA: la pantalla caia al 500 de `error.vue` con el HTML del servidor
               perfectamente servido detras (medido el 11-sep-2026, Firefox real).
               El nativo ademas abre la rueda del sistema en movil, que se usa mejor. -->
          <select v-model="campos.cuando" class="nativo">
            <option v-for="c in CUANDO" :key="c.value" :value="c.value">{{ c.label }}</option>
          </select>
        </UFormField>
        <UButton
          size="lg" icon="i-lucide-search" :loading="cargando"
          @click="buscar({ usarCampos: true })"
        >
          Search
        </UButton>
      </div>

      <div class="frase">
        <UInput
          v-model="consulta"
          size="lg"
          class="entrada"
          placeholder="…or just say it: «Ich fahre morgen um 8 nach Mitte, zwei Plätze frei»"
          icon="i-lucide-message-square"
          @keydown.enter="buscar()"
        />
        <UButton variant="soft" size="lg" :loading="cargando" @click="buscar()">
          Read my sentence
        </UButton>
        <UButton
          variant="ghost" color="neutral" size="lg" icon="i-lucide-command"
          @click="paletaAbierta = true"
        >
          Examples
        </UButton>
      </div>

      <p class="minusculo">
        The fields fill themselves from what the sentence means. Correcting one re-runs the search
        <b>without calling the model</b> — under a second, every time.
      </p>
    </section>

    <!-- ── error ────────────────────────────────────────────────────────────────────────── -->
    <UAlert
      v-if="error" color="error" variant="subtle" icon="i-lucide-triangle-alert"
      title="That did not work" :description="error" class="hueco"
    />

    <!-- ── esperando: esqueletos con la forma del resultado, y la capa que corre ─────────── -->
    <template v-if="cargando && !datos">
      <div class="progreso">
        <UIcon name="i-lucide-loader-circle" class="gira" />
        <span>{{ PASOS[paso] }}…</span>
        <span class="minusculo">layer {{ paso }} of 4</span>
      </div>
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
      <!-- ── el mapa: un coche compartido sin mapa no existe ──────────────────────────── -->
      <NuxtErrorBoundary v-if="viajes.length && mapaListo">
        <MapaRuta
          :viajes="viajes" :centro="centro" :radio-km="radio" :seleccionado="senalado"
          class="hueco"
        />
        <!-- Si el mapa falla, se pierde el mapa y nada mas. Antes se llevaba la pantalla entera. -->
        <template #error="{ error: errorMapa }">
          <p class="minusculo hueco">Map unavailable ({{ errorMapa }}). The results below are unaffected.</p>
        </template>
      </NuxtErrorBoundary>

      <!-- ── lo que se entendio, en una linea, no en una tarjeta de taxonomia ─────────── -->
      <div class="entendido">
        <UBadge v-if="datos.directo" color="neutral" variant="subtle">
          fields · no model call
        </UBadge>
        <UBadge v-else-if="datos.degradado" color="warning" variant="subtle">
          fallback rules · the model did not answer in time
        </UBadge>
        <UBadge v-else color="primary" variant="subtle">read by the model</UBadge>
        <span class="minusculo">
          {{ datos.totales.candidatos }} candidates ·
          {{ datos.totales.viajes }} rides · {{ datos.totales.personas }} drivers ·
          within {{ radio }} km of your route · {{ datos.ventana.etiqueta }}
        </span>
        <span class="empuja" />
        <UButton
          size="xs" variant="ghost" color="neutral" icon="i-lucide-refresh-cw"
          :loading="cargando" @click="buscar({ fresco: true })"
        >
          Run it again without cache
        </UButton>
      </div>

      <!-- ── DOS LISTAS, cada una ordenada por SU numero ──────────────────────────────── -->
      <section v-for="l in listas" :key="l.clave" class="lista">
        <h2 class="titulo-lista">
          {{ l.titulo }}
          <span class="minusculo">{{ l.total }}</span>
        </h2>

        <p v-if="!l.resultados.length" class="vacio">
          Nobody is doing that right now.
          <button class="enlace" @click="campos.cuando = ''; buscar({ usarCampos: true })">
            Try without the date
          </button>
        </p>

        <template v-for="r in l.resultados" :key="r.id">
          <div @mouseenter="senalado = r.id" @mouseleave="senalado = null">
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

      <!-- ── los near-miss: por que NO salieron ───────────────────────────────────────── -->
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

      <!-- ── donde se fue el tiempo. La seccion E de la propuesta, hecha visible ──────── -->
      <p class="tiempos minusculo">
        <b>{{ datos.tiempos.total }} ms</b> —
        model {{ datos.tiempos.capa_0_llm + datos.tiempos.capa_4_llm }} ·
        embedding {{ datos.tiempos.embedding }} ·
        Postgres {{ datos.tiempos.capa_1_2_postgres }} · scoring &lt;1.
        The expensive part is the model, and it runs at most twice: once to read your sentence,
        once to phrase what you see. Everything else is an index.
      </p>
    </template>

    <!-- ── ⌘K: las diez frases de Helder, que eran el criterio de aceptacion y vivian
             escondidas dentro de un desplegable ─────────────────────────────────────────── -->
    <UModal v-model:open="paletaAbierta" title="Try a sentence">
      <template #body>
        <div class="grupo">
          <p class="grupo-t">Rideshare — what the job post asks for</p>
          <button
            v-for="e in EJEMPLOS_COCHE" :key="e.texto" class="ejemplo"
            @click="paletaAbierta = false; buscar({ frase: e.texto })"
          >
            <UBadge size="sm" color="neutral" variant="subtle">{{ e.ciudad }}</UBadge>
            {{ e.texto }}
          </button>
        </div>
        <div class="grupo">
          <p class="grupo-t">Helder's ten sentences — verbatim, the acceptance criterion</p>
          <button
            v-for="f in frases" :key="f.escenario" class="ejemplo"
            @click="paletaAbierta = false; buscar({ frase: f.frase_de_helder })"
          >
            <UBadge size="sm" color="neutral" variant="subtle">
              {{ /[äöüßÄÖÜ]|^Ich|^Meine/.test(f.frase_de_helder) ? 'DE' : 'EN' }}
            </UBadge>
            {{ f.frase_de_helder }}
          </button>
        </div>
      </template>
    </UModal>
  </div>
</template>

<style scoped>
.nativo {
	/* Los campos de Nuxt UI y este tienen que medir lo mismo o la fila se descuadra. */
	height: 40px; min-height: 40px; border-radius: var(--radio-2);
	border: 1px solid var(--linea); background: var(--superficie);
	font-size: var(--t-15); padding: 0 var(--e3);
}
.buscador { display: grid; gap: var(--e3); margin-bottom: var(--e5); }
.campos { display: flex; gap: var(--e3); align-items: flex-end; flex-wrap: wrap; }
.campo { flex: 1 1 180px; }
.estrecho-campo { flex: 0 1 150px; }
.frase { display: flex; gap: var(--e2); align-items: center; flex-wrap: wrap; }
.entrada { flex: 1 1 320px; }

.hueco { margin: var(--e4) 0; }

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
  .campos { gap: var(--e2); }
  .campo, .estrecho-campo { flex: 1 1 100%; }
  .campos > :deep(button) { width: 100%; }
  .comp { grid-template-columns: 1fr 70px 44px; }
  .comp-b { display: none; }
}
</style>
