<script setup lang="ts">
// FLUJO 2 · «offer a ride». Y de paso, la unica pantalla donde se VE la regla 5: el viaje se
// embebe al escribirlo, una vez, y a partir de ahi aparece en las busquedas sin costar nada.
//
// REESCRITO EL 15-SEP-2026. La barra decia «Offer a ride» y esta pantalla pedia «Title», «Kind
// of plan: concert…», «Artist, team or cuisine»: el vocabulario del producto anterior, y cuatro
// agentes del programa de UX lo marcaron como bloqueante. Ahora pide lo que un conductor sabe
// sin pensar —de donde, adonde, cuando, cuantas plazas, a cuanto el km— y nada mas (P8 Lo justo
// para decidir). El titulo se escribe solo.
definePageMeta({ middleware: "sesion" });
useSeoMeta({ title: "Offer a ride — Match Engine demo" });

const { sesion } = useSesion();
const form = reactive({
	desde: "",
	hacia: "",
	dia_offset: 1,
	hora: "08:00",
	recurrente: "",
	seats_open: 2,
	precio_por_km: 0.1,
	nota: "",
});
const enviando = ref(false);
const hecho = ref<any>(null);
const error = ref<string | null>(null);

const CUANDO = [
	{ v: 0, t: "Today" },
	{ v: 1, t: "Tomorrow" },
	{ v: 2, t: "In 2 days" },
	{ v: 7, t: "Next week" },
];
const HORAS = [
	"06:30",
	"07:00",
	"07:30",
	"08:00",
	"08:30",
	"09:00",
	"12:00",
	"16:30",
	"17:00",
	"17:30",
	"18:00",
	"18:30",
	"19:00",
	"20:00",
	"22:00",
];

/** El precio antes de pedir (P3): se ense~na mientras se escribe, no despues de publicar. */
const kmEstimados = computed(() => {
	// Estimacion de pantalla; la real la calcula el servidor con las coordenadas.
	const d = form.desde.trim(),
		h = form.hacia.trim();
	if (!d || !h) return null;
	return d.toLowerCase() === h.toLowerCase() ? 0 : 6;
});
const precioEstimado = computed(() =>
	kmEstimados.value
		? new Intl.NumberFormat("en-GB", {
				style: "currency",
				currency: "EUR",
			}).format(kmEstimados.value * form.precio_por_km)
		: null,
);

async function publicar() {
	enviando.value = true;
	error.value = null;
	try {
		hecho.value = await $fetch("/api/plan", {
			method: "POST",
			body: { ...form, recurrente: form.recurrente || null },
			timeout: 20_000,
		});
	} catch (e: any) {
		error.value =
			e?.data?.statusMessage || "The ride could not be published. Try again.";
	} finally {
		enviando.value = false;
	}
}
</script>

<template>
  <div class="contenedor estrecho">
    <h1>Offer a ride</h1>
    <p class="tenue intro">
      Where you are going anyway, and how many seats you have. It becomes findable the moment you
      publish — <b>the embedding is computed now, not when someone searches</b>.
    </p>

    <div v-if="hecho" class="tarjeta ok">
      <h2>Published — {{ hecho.plan.title }}</h2>
      <p class="pequeno">
        {{ hecho.km }} km · {{ new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'EUR' }).format(hecho.precio_total) }} per seat ·
        indexed as a <b>{{ hecho.dimension }}-dimension</b> vector, once. Anyone searching that
        route from now on finds it without a single extra call.
      </p>
      <div class="acciones">
        <UButton :to="`/plan/${hecho.plan.id}`" icon="i-lucide-route">See your ride</UButton>
        <UButton :to="`/?desde=${encodeURIComponent(form.desde)}&hacia=${encodeURIComponent(form.hacia)}&q=${encodeURIComponent(`Fahrt von ${form.desde} nach ${form.hacia}`)}`" variant="soft">
          Search for it
        </UButton>
      </div>
    </div>

    <form v-else class="formulario" @submit.prevent="publicar">
      <div class="rejilla dos">
        <UFormField label="From" required>
          <UInput v-model="form.desde" placeholder="Neukölln" icon="i-lucide-circle-dot" autocomplete="off" required />
        </UFormField>
        <UFormField label="To" required>
          <UInput v-model="form.hacia" placeholder="Mitte" icon="i-lucide-map-pin" autocomplete="off" required />
        </UFormField>
      </div>

      <div class="rejilla tres">
        <UFormField label="Day">
          <select v-model.number="form.dia_offset" class="nativo" aria-label="Day">
            <option v-for="c in CUANDO" :key="c.v" :value="c.v">{{ c.t }}</option>
          </select>
        </UFormField>
        <UFormField label="Departs at">
          <select v-model="form.hora" class="nativo" aria-label="Departure time">
            <option v-for="h in HORAS" :key="h" :value="h">{{ h }}</option>
          </select>
        </UFormField>
        <UFormField label="Repeats">
          <select v-model="form.recurrente" class="nativo" aria-label="Repeats">
            <option value="">Just once</option>
            <option value="weekdays">Every weekday</option>
          </select>
        </UFormField>
      </div>

      <div class="rejilla dos">
        <UFormField label="Free seats">
          <select v-model.number="form.seats_open" class="nativo" aria-label="Free seats">
            <option v-for="n in 4" :key="n" :value="n">{{ n }}</option>
          </select>
        </UFormField>
        <UFormField label="Price per km" :hint="precioEstimado ? `about ${precioEstimado} per seat` : 'cost sharing, not a fare'">
          <UInput v-model.number="form.precio_por_km" type="number" min="0.05" max="0.5" step="0.01" icon="i-lucide-euro" />
        </UFormField>
      </div>

      <UFormField label="A line for your passengers" hint="optional · German or English">
        <UTextarea v-model="form.nota" :rows="2" placeholder="Ich fahre die Strecke sowieso. Wer mitkommen will, sagt kurz Bescheid." />
      </UFormField>

      <UAlert v-if="error" color="error" variant="subtle" icon="i-lucide-triangle-alert" :description="error" />

      <UButton type="submit" size="lg" :loading="enviando" icon="i-lucide-circle-plus" class="publicar">
        Publish the ride
      </UButton>
      <p class="minusculo">
        Publishing as <b>{{ sesion?.display_name }}</b> from {{ sesion?.city }}. Demo data: nothing here is real.
      </p>
    </form>
  </div>
</template>

<style scoped>
h1 { font-size: var(--t-28); }
.intro { margin: var(--e2) 0 var(--e5); }
.formulario { display: grid; gap: var(--e4); }
.rejilla.tres { grid-template-columns: 1fr 1fr 1fr; }
.ok { border-color: var(--exito); background: var(--exito-suave); }
.ok h2 { margin-bottom: var(--e2); }
.acciones { display: flex; gap: var(--e2); margin-top: var(--e4); flex-wrap: wrap; }
.publicar { justify-self: start; }
@media (max-width: 640px) {
  .rejilla.tres { grid-template-columns: 1fr 1fr; }
  .publicar { justify-self: stretch; }
}
</style>
