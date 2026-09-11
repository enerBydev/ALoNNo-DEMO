<script setup lang="ts">
/**
 * La ficha de un conductor.
 *
 * Lo que habia antes ense~naba «verification 3/3» y «8 plans completed»: representacion interna
 * y vocabulario del esquema. Y no ense~naba ni una rese~na, con 1.232 en la base
 * (docs/conocimiento/20-critica-uiux.md §5).
 *
 * La pregunta que esta pantalla tiene que contestar es una sola: **¿me subo al coche de esta
 * persona?** Todo lo que no ayude a contestarla sobra.
 */
const ruta = useRoute();
const { data, error } = await useFetch<any>(`/api/persona/${ruta.params.id}`);
const p = computed(() => data.value?.persona);
const rep = computed(() => data.value?.reputacion);
const resenas = computed(() => data.value?.resenas ?? []);

useSeoMeta({
	title: () => (p.value ? `${p.value.display_name} — ALoNNo` : "Driver"),
});

const fecha = (i: string) =>
	new Date(i).toLocaleDateString("en-GB", {
		weekday: "short",
		day: "numeric",
		month: "short",
	});

const hace = (dias: number) =>
	dias < 14
		? `${dias} days ago`
		: dias < 60
			? `${Math.round(dias / 7)} weeks ago`
			: `${Math.round(dias / 30)} months ago`;

const total = computed(
	() =>
		rep.value?.reparto?.reduce((s: number, r: any) => s + r.cuantas, 0) || 0,
);

/** La traduccion se pide una vez y se guarda: una rese~na alemana leida por alguien que no lee
 *  aleman es exactamente el argumento que esta demo vende, y aqui se puede tocar. */
const traducidas = ref<Record<string, string>>({});
const traduciendo = ref<string | null>(null);
async function traducir(r: any) {
	if (traducidas.value[r.id] || traduciendo.value) return;
	traduciendo.value = r.id;
	try {
		const d = await $fetch<any>("/api/traducir", {
			method: "POST",
			body: { texto: r.texto, a: r.idioma === "de" ? "en" : "de" },
			timeout: 12_000,
		});
		if (d?.texto) traducidas.value[r.id] = d.texto;
	} catch {
		traducidas.value[r.id] = "(translation unavailable right now)";
	} finally {
		traduciendo.value = null;
	}
}

const avatar = computed(() => {
	const id = String(ruta.params.id);
	let h = 0;
	for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0;
	const tonos = [
		"#0B5F5A",
		"#A94F0A",
		"#1D4ED8",
		"#7C3AED",
		"#B42318",
		"#0F766E",
		"#9A3412",
		"#4338CA",
	];
	return tonos[h % tonos.length];
});
</script>

<template>
  <div class="contenedor estrecho">
    <p v-if="error" class="tarjeta">That profile does not exist.</p>

    <template v-else-if="p">
      <NuxtLink to="/" class="volver minusculo">← back to search</NuxtLink>

      <header class="cabecera">
        <span class="avatar" :style="{ background: avatar }">{{ p.display_name.charAt(0) }}</span>
        <div class="quien">
          <h1>{{ p.display_name }}</h1>
          <p class="tenue">
            {{ p.city }}<template v-if="p.age"> · {{ p.age }}</template>
            · speaks {{ (p.languages || []).join(', ').toUpperCase() }}
          </p>
        </div>
      </header>

      <!-- ── EL BLOQUE DE REPUTACION. No una caja titulada «track record». ──────────────── -->
      <section class="reputacion">
        <div class="nota-grande">
          <template v-if="rep.nota != null">
            <div class="nota">
              <span class="estrella" aria-hidden="true">★</span>{{ rep.nota.toFixed(1) }}
            </div>
            <p class="minusculo">{{ rep.conteo }} ratings</p>
          </template>
          <template v-else>
            <UBadge color="warning" variant="subtle" size="lg">New driver</UBadge>
            <p class="minusculo">{{ rep.conteo }} ratings — not enough to show a score</p>
          </template>
        </div>

        <div class="reparto">
          <div v-for="r in rep.reparto" :key="r.estrellas" class="fila-reparto">
            <span class="n">{{ r.estrellas }}</span>
            <UProgress :model-value="total ? (r.cuantas / total) * 100 : 0" size="sm" class="b" />
            <span class="n tenue">{{ r.cuantas }}</span>
          </div>
        </div>
      </section>

      <div class="hechos">
        <UBadge
          v-for="v in rep.verificaciones" :key="v.clave"
          :color="v.hecha ? 'success' : 'neutral'" :variant="v.hecha ? 'subtle' : 'outline'"
        >
          <UIcon :name="v.hecha ? 'i-lucide-badge-check' : 'i-lucide-circle-dashed'" />
          {{ v.etiqueta }}
        </UBadge>
      </div>

      <p class="linea-hechos">
        <span v-if="rep.viajes">{{ rep.viajes }} rides</span>
        <span v-if="rep.miembro_desde">· member since {{ rep.miembro_desde }}</span>
        <span v-if="rep.coche">· {{ rep.coche }}<template v-if="rep.plazas_coche"> · {{ rep.plazas_coche }} seats</template></span>
      </p>

      <!-- La reciprocidad: lo que distingue un coche compartido de un taxi. -->
      <p v-if="rep.valora_a_sus_pasajeros_con" class="reciproco">
        <UIcon name="i-lucide-arrow-left-right" />
        Rates their passengers {{ rep.valora_a_sus_pasajeros_con.toFixed(1) }} on average
      </p>

      <p class="bio">{{ p.bio }}</p>

      <!-- ── LAS RESE~NAS ───────────────────────────────────────────────────────────────── -->
      <section v-if="resenas.length" class="bloque">
        <h2>What passengers say</h2>
        <article v-for="r in resenas.slice(0, 3)" :key="r.id" class="resena">
          <header>
            <b>{{ r.autor }}</b>
            <span class="minusculo">· {{ hace(r.hace_dias) }}</span>
            <span class="empuja" />
            <span class="estrellitas">
              <span
                v-for="n in 5" :key="n" aria-hidden="true"
                :class="n <= r.estrellas ? 'llena' : 'vacia'"
              >★</span>
            </span>
          </header>
          <p class="texto">«{{ r.texto }}»</p>
          <p v-if="traducidas[r.id]" class="traducido">→ {{ traducidas[r.id] }}</p>
          <UButton
            v-else size="xs" variant="ghost" color="neutral" icon="i-lucide-languages"
            :loading="traduciendo === r.id" @click="traducir(r)"
          >
            Translate from {{ r.idioma.toUpperCase() }}
          </UButton>
        </article>
      </section>

      <!-- ── LO QUE CONDUCE ────────────────────────────────────────────────────────────── -->
      <section v-if="data.planes.length" class="bloque">
        <h2>Rides they publish</h2>
        <NuxtLink v-for="v in data.planes" :key="v.id" :to="`/plan/${v.id}`" class="viajecito">
          <b>{{ v.title }}</b>
          <span class="minusculo">
            {{ fecha(v.starts_at) }}
            <template v-if="v.distancia_km"> · {{ v.distancia_km }} km</template>
            <template v-if="v.via?.length"> · via {{ v.via.join(', ') }}</template>
            · {{ v.seats_open }} {{ v.seats_open === 1 ? 'seat' : 'seats' }}
          </span>
        </NuxtLink>
      </section>

      <section v-if="data.apuntada.length" class="bloque">
        <h2>Rides they joined</h2>
        <NuxtLink v-for="v in data.apuntada" :key="v.id" :to="`/plan/${v.id}`" class="viajecito">
          <b>{{ v.title }}</b>
          <span class="minusculo">{{ fecha(v.starts_at) }}</span>
        </NuxtLink>
      </section>

      <div class="tags">
        <UBadge v-for="a in p.top_artists || []" :key="a" color="neutral" variant="subtle">{{ a }}</UBadge>
        <UBadge v-for="t in p.top_teams || []" :key="t" color="neutral" variant="subtle">{{ t }}</UBadge>
        <UBadge v-for="i in p.interests || []" :key="i" color="neutral" variant="outline">
          {{ i.replace('_', ' ') }}
        </UBadge>
      </div>
    </template>
  </div>
</template>

<style scoped>
.volver { text-decoration: none; display: inline-block; margin-bottom: var(--e4); }

.cabecera { display: flex; align-items: center; gap: var(--e4); margin-bottom: var(--e5); }
.avatar {
  width: 72px; height: 72px; border-radius: 50%; color: #fff; flex: none;
  display: grid; place-items: center; font-size: var(--t-28); font-weight: 600;
}
.quien h1 { font-size: var(--t-28); }

.reputacion {
  display: grid; grid-template-columns: 150px 1fr; gap: var(--e5); align-items: center;
  padding: var(--e5); border: 1px solid var(--linea); border-radius: var(--radio);
  background: var(--superficie); margin-bottom: var(--e3);
}
.nota-grande { text-align: center; }
.nota {
  display: inline-flex; align-items: center; gap: var(--e1);
  font-size: var(--num-56); font-weight: 700; line-height: 1;
  font-variant-numeric: tabular-nums;
}
/* El glifo ★ y no `i-lucide-star`: `UIcon` pinta con `mask-image`, asi que `fill` no hace nada
   y la estrella sale hueca al lado de la nota. Las fuentes Noto de esta maquina lo cubren, y en
   un movil tambien: es un caracter de 1993, no un emoji. */
.estrella { color: #E8A33D; font-size: 34px; line-height: 1; }
.reparto { display: grid; gap: 3px; }
.fila-reparto { display: grid; grid-template-columns: 16px 1fr 32px; gap: var(--e2); align-items: center; }
.fila-reparto .n { font-size: var(--t-13); text-align: right; font-variant-numeric: tabular-nums; }

.hechos { display: flex; gap: var(--e2); flex-wrap: wrap; margin-bottom: var(--e2); }
.linea-hechos { font-size: var(--t-15); color: var(--tinta-2); display: flex; gap: var(--e1); flex-wrap: wrap; }
.reciproco {
  display: inline-flex; align-items: center; gap: var(--e1);
  font-size: var(--t-15); color: var(--accion); font-weight: 500; margin-top: var(--e2);
}
.bio { margin: var(--e5) 0; font-size: var(--t-16); color: var(--tinta-2); }

.bloque { margin-top: var(--e6); }
.bloque h2 { font-size: var(--t-18); margin-bottom: var(--e3); }

.resena {
  border: 1px solid var(--linea); border-radius: var(--radio-2);
  padding: var(--e4); margin-bottom: var(--e2); background: var(--superficie);
}
.resena header { display: flex; align-items: center; gap: var(--e1); margin-bottom: var(--e2); }
.empuja { flex: 1 1 auto; }
.estrellitas { display: inline-flex; gap: 1px; }
/* `i-lucide-star` es un contorno: sin `fill` las cinco estrellas se ven iguales y la nota no se
   lee de un vistazo, que es justo para lo que existe una fila de estrellas. */
.estrellitas span { font-size: var(--t-15); line-height: 1; }
.llena { color: #E8A33D; }
.vacia { color: var(--linea); }
.texto { font-size: var(--t-15); }
.traducido {
  font-size: var(--t-15); color: var(--accion); margin-top: var(--e2);
  padding-left: var(--e3); border-left: 2px solid var(--accion-suave);
}

.viajecito {
  display: flex; justify-content: space-between; align-items: baseline; gap: var(--e3);
  text-decoration: none; padding: var(--e3) var(--e4); margin-bottom: var(--e1);
  border: 1px solid var(--linea); border-radius: var(--radio-2); background: var(--superficie);
}
.viajecito:hover { border-color: var(--accion); }

.tags { display: flex; gap: var(--e1); flex-wrap: wrap; margin-top: var(--e6); }

@media (max-width: 640px) {
  .reputacion { grid-template-columns: 1fr; gap: var(--e3); }
  .nota-grande { text-align: left; }
}
</style>
