<script setup lang="ts">
/**
 * La ficha de un VIAJE.
 *
 * **SSR con datos estructurados**: la seccion K de la propuesta vende que cada viaje publico es
 * una pagina que un buscador —o un asistente— puede leer y citar. Eso solo es cierto si el HTML
 * llega hecho, que es lo que Nuxt da y lo que un cliente movil puro no puede dar.
 *
 * La reescritura del 11-sep-2026 cambia el vocabulario entero: esto ya no es «un plan con
 * plazas», es un trayecto con hora de salida, ruta, tarifa y un conductor con reputacion. El
 * motor por debajo es el mismo — que es exactamente lo que hay que ense~narle al cliente.
 */
const ruta = useRoute();
const { sesion } = useSesion();
const toast = useToast();
const { data, error, refresh } = await useFetch<any>(
	`/api/plan/${ruta.params.id}`,
);

const p = computed(() => data.value?.plan);
const geo = computed(() => data.value?.geometria);
const conductor = computed(() => p.value?.perfil);

const cuando = computed(() =>
	p.value
		? new Date(p.value.starts_at).toLocaleString("en-GB", {
				weekday: "long",
				day: "numeric",
				month: "long",
				hour: "2-digit",
				minute: "2-digit",
			})
		: "",
);

/** Un viaje es un viaje cuando tiene distancia. Un concierto en Barcelona no lo es: ahi esta
 *  pagina sigue siendo la de un plan, y se lee como tal. */
const esViaje = computed(() => p.value?.distancia_km != null);

const precioTotal = computed(() =>
	esViaje.value && p.value.precio_por_km
		? Math.round(
				Number(p.value.distancia_km) * Number(p.value.precio_por_km) * 100,
			) / 100
		: null,
);

const duracion = computed(() =>
	esViaje.value
		? Math.max(6, Math.round((Number(p.value.distancia_km) / 28) * 60))
		: null,
);

const notaUtil = computed(
	() =>
		conductor.value?.nota != null && (conductor.value?.notas_conteo ?? 0) >= 3,
);

const miembroDesde = computed(() => {
	const m = conductor.value?.desde_offset;
	if (m == null) return null;
	const d = new Date();
	d.setMonth(d.getMonth() - m);
	return d.toLocaleDateString("en-GB", { month: "long", year: "numeric" });
});

/** El mapa quiere la misma forma que le da la busqueda, asi que se fabrica un «viaje» con la
 *  geometria que devolvio Postgres. Un solo componente para las dos pantallas. */
const paraMapa = computed(() => {
	if (!geo.value?.origen) return [];
	return [
		{
			id: p.value.id,
			plazas: p.value.seats_open,
			viaje: {
				desde: p.value.origin_city,
				hasta: p.value.venue ?? p.value.dest_city,
				puntos: geo.value.ruta?.coordinates ?? null,
				origen: geo.value.origen?.coordinates ?? null,
				destino: geo.value.destino?.coordinates ?? null,
			},
		},
	];
});
const centroMapa = computed<[number, number] | null>(
	() => geo.value?.origen?.coordinates ?? null,
);

const mapaListo = ref(false);
onMounted(() => {
	nextTick(() => {
		mapaListo.value = true;
	});
});

useSeoMeta({
	title: () => (p.value ? `${p.value.title} — ALoNNo` : "Ride — ALoNNo"),
	description: () => p.value?.description ?? "",
});

// Datos estructurados: es lo que permite que un asistente cite este viaje.
useHead(() => ({
	script: p.value
		? [
				{
					type: "application/ld+json",
					innerHTML: JSON.stringify({
						"@context": "https://schema.org",
						"@type": "Event",
						name: p.value.title,
						description: p.value.description,
						startDate: p.value.starts_at,
						endDate: p.value.ends_at,
						eventStatus: "https://schema.org/EventScheduled",
						location: {
							"@type": "Place",
							name: p.value.venue ?? p.value.dest_city,
							address: {
								"@type": "PostalAddress",
								addressLocality: p.value.dest_city,
							},
						},
					}),
				},
			]
		: [],
}));

const enviando = ref(false);
const resultado = ref<any>(null);
async function apuntarse(quitar = false) {
	if (!sesion.value)
		return navigateTo(`/entrar?volver=/plan/${ruta.params.id}`);
	enviando.value = true;
	try {
		resultado.value = await $fetch("/api/interes", {
			method: "POST",
			body: { plan_id: ruta.params.id, quitar },
		});
		await refresh();
		// El fallo que esto arregla: se pulsaba «pedir plaza» y no pasaba NADA visible. Una accion
		// sin respuesta se lee como una accion que no funciono, y el usuario la repite.
		toast.add({
			title: quitar ? "Request withdrawn" : "Seat requested",
			description: quitar
				? "You are no longer on this ride."
				: `Waiting for ${conductor.value?.display_name} to confirm.`,
			icon: quitar ? "i-lucide-undo-2" : "i-lucide-check",
			color: quitar ? "neutral" : "primary",
		});
	} finally {
		enviando.value = false;
	}
}
</script>

<template>
  <div class="contenedor estrecho">
    <p v-if="error" class="tarjeta">That ride does not exist.</p>

    <template v-else-if="p">
      <NuxtLink to="/" class="volver minusculo">← back to search</NuxtLink>

      <div class="fila-titulo">
        <UBadge color="primary" variant="subtle">
          {{ esViaje ? (p.recurrente === 'weekdays' ? 'Every weekday' : 'Ride') : p.category.replace('_', ' ') }}
        </UBadge>
        <UBadge v-if="p.is_travel" color="neutral" variant="subtle">travel</UBadge>
        <UBadge color="neutral" variant="outline">{{ p.desc_lang.toUpperCase() }}</UBadge>
      </div>

      <h1>{{ p.title }}</h1>

      <!-- La linea que decide: cuando sale, cuanto dura, cuanto cuesta. -->
      <p class="cuando">{{ cuando }}</p>
      <p class="hechos">
        <span v-if="esViaje">{{ p.origin_city }} → {{ p.venue ?? p.dest_city }}</span>
        <span v-else>{{ p.venue || p.dest_city }}</span>
        <span v-if="p.via?.length">· via {{ p.via.join(', ') }}</span>
        <span v-if="esViaje">· {{ p.distancia_km }} km · about {{ duracion }} min</span>
        <span v-if="precioTotal">· <b>{{ precioTotal.toFixed(2) }} €</b> ({{ p.precio_por_km }} €/km)</span>
      </p>

      <NuxtErrorBoundary v-if="paraMapa.length && mapaListo">
        <MapaRuta :viajes="paraMapa" :centro="centroMapa" :radio-km="p.radius_km ?? 2" class="hueco" />
        <template #error><p class="minusculo hueco">Map unavailable. Everything else works.</p></template>
      </NuxtErrorBoundary>

      <p class="descripcion">{{ p.description }}</p>

      <!-- ── plazas y la accion ────────────────────────────────────────────────────────── -->
      <div class="tarjeta plazas">
        <div>
          <b class="grande">{{ p.seats_open }}</b>
          {{ p.seats_open === 1 ? 'seat' : 'seats' }} left
          <p class="minusculo">
            {{ data.apuntados.length }}
            {{ data.apuntados.length === 1 ? 'person has' : 'people have' }} asked to join
          </p>
        </div>
        <UButton
          v-if="!data.soy_el_dueno"
          size="lg" :loading="enviando"
          :color="data.yo_apuntado ? 'success' : 'primary'"
          :variant="data.yo_apuntado ? 'soft' : 'solid'"
          :icon="data.yo_apuntado ? 'i-lucide-check' : 'i-lucide-hand'"
          @click="apuntarse(data.yo_apuntado)"
        >
          {{ data.yo_apuntado ? 'Requested — tap to withdraw' : 'Request a seat' }}
        </UButton>
        <UBadge v-else color="neutral" variant="subtle">your ride</UBadge>
      </div>

      <UAlert
        v-if="resultado?.mutuo" class="hueco" color="success" variant="subtle"
        icon="i-lucide-handshake" title="Mutual match"
        :description="`${conductor.display_name} is interested in your ride «${resultado.plan_suyo?.title}» too. `
          + 'In the real product this is the moment the chat opens — the demo stops here on purpose: '
          + 'no chat, no notifications, no payments.'"
      />

      <!-- ── quien conduce ─────────────────────────────────────────────────────────────── -->
      <h2 class="titulo2">{{ esViaje ? 'Your driver' : 'Organised by' }}</h2>
      <NuxtLink :to="`/persona/${conductor.id}`" class="tarjeta duenno">
        <span class="avatar">{{ conductor.display_name.charAt(0) }}</span>
        <div class="det">
          <h3>{{ conductor.display_name }}</h3>
          <p class="linea-conf">
            <span v-if="notaUtil" class="nota">
              <span class="estrella" aria-hidden="true">★</span>{{ Number(conductor.nota).toFixed(1) }}
              <span class="conteo">({{ conductor.notas_conteo }})</span>
            </span>
            <UBadge v-else color="warning" variant="subtle" size="sm">
              New · {{ conductor.completed_plans }} rides
            </UBadge>
            <UBadge v-if="conductor.verification >= 1" color="success" variant="subtle" size="sm">
              <UIcon name="i-lucide-badge-check" /> ID
            </UBadge>
            <span v-if="conductor.coche" class="coche">{{ conductor.coche }}</span>
          </p>
          <p class="minusculo">
            {{ conductor.city }}
            <template v-if="miembroDesde"> · member since {{ miembroDesde }}</template>
            <template v-if="conductor.completed_plans"> · {{ conductor.completed_plans }} rides</template>
          </p>
          <p class="pequeno recorte">{{ conductor.bio }}</p>
        </div>
      </NuxtLink>

      <template v-if="data.apuntados.length">
        <h2 class="titulo2">Who is coming</h2>
        <div class="rejilla dos">
          <NuxtLink
            v-for="a in data.apuntados" :key="a.id" :to="`/persona/${a.id}`"
            class="tarjeta apuntado"
          >
            <span class="avatar chico">{{ a.display_name.charAt(0) }}</span>
            <div>
              <b>{{ a.display_name }}</b>
              <p class="minusculo">{{ a.city }}</p>
            </div>
          </NuxtLink>
        </div>
      </template>
    </template>
  </div>
</template>

<style scoped>
.volver { display: inline-block; margin-bottom: var(--e3); text-decoration: none; }
.fila-titulo { display: flex; gap: var(--e1); margin-bottom: var(--e2); flex-wrap: wrap; }
h1 { font-size: var(--t-28); }
.cuando { margin: var(--e3) 0 var(--e1); font-size: var(--t-22); font-weight: 600; }
.hechos {
  display: flex; gap: var(--e1); flex-wrap: wrap;
  font-size: var(--t-15); color: var(--tinta-2); margin-bottom: var(--e4);
}
.hueco { margin: var(--e4) 0; }
.descripcion { margin: var(--e4) 0; color: var(--tinta-2); }

.plazas { display: flex; align-items: center; justify-content: space-between; gap: var(--e4); flex-wrap: wrap; }
.grande { font-size: var(--t-28); font-variant-numeric: tabular-nums; }

.titulo2 { margin-top: var(--e6); margin-bottom: var(--e3); font-size: var(--t-18); }
.duenno, .apuntado { display: flex; gap: var(--e3); align-items: center; text-decoration: none; }
.duenno:hover, .apuntado:hover { border-color: var(--accion); }
.det { min-width: 0; }
.linea-conf { display: flex; align-items: center; gap: var(--e2); flex-wrap: wrap; margin: var(--e1) 0; }
.nota { display: inline-flex; align-items: center; gap: 2px; font-weight: 600; }
.estrella { color: #E8A33D; font-size: 1.05em; line-height: 1; }
.conteo { font-size: var(--t-13); font-weight: 400; color: var(--tinta-3); }
.coche { font-size: var(--t-13); color: var(--tinta-2); }
.avatar {
  width: 48px; height: 48px; border-radius: 50%; background: var(--tinta); color: var(--papel);
  display: grid; place-items: center; font-weight: 700; flex: none;
}
.avatar.chico { width: 32px; height: 32px; font-size: var(--t-13); }
.recorte {
  display: -webkit-box; -webkit-line-clamp: 2; line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden; color: var(--tinta-2);
}
</style>
