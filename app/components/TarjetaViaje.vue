<script setup lang="ts">
/**
 * La tarjeta de un resultado: un viaje o un conductor.
 *
 * Las medidas de aqui NO son de gusto: salen de la critica de UI/UX del 11-sep-2026
 * (docs/conocimiento/20-critica-uiux.md §4), que midio la version anterior con un navegador real
 * y encontro que **la linea que decide la compra —ciudad, km, hora, plazas— era la mas peque~na
 * de la tarjeta, a 11,84 px, y en un gris que fallaba AA (4,37:1)**. Mientras tanto, el bloque
 * mas grande era la bio: el dato menos accionable de todos.
 *
 * La jerarquia nueva es la de un producto de movilidad, en este orden:
 *   1. CUANDO sale (22 px) y POR DONDE va (18 px)
 *   2. EL DESVIO — «pasa a 0,3 km de ti» — que es el dato que solo este producto tiene
 *   3. QUIEN conduce, con su nota y su coche
 *   4. Por que encaja (la frase del modelo)
 *   5. Plazas, precio y las dos acciones
 * y el porcentaje en su propia columna de 76 px, a 32 px, para que no compita con el titulo.
 */
const props = defineProps<{
	r: any;
	idiomaConsulta?: string;
	abierto?: boolean;
}>();
const emit = defineEmits<{ (e: "alternar"): void; (e: "pedir"): void }>();

const v = computed(() => props.r.viaje);
const c = computed(() => props.r.conductor);

/** La hora de salida, y la de llegada estimada si sabemos cuanto dura. */
const horas = computed(() => {
	if (!props.r.cuando) return null;
	const sale = new Date(props.r.cuando);
	const hh = (d: Date) =>
		d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
	if (!v.value?.km) return hh(sale);
	// 28 km/h de media urbana: es lo que se mueve un coche en una ciudad alemana en hora punta,
	// y lo que hace que «37 min» se parezca a la verdad en vez de a una division de folleto.
	const min = Math.max(6, Math.round((v.value.km / 28) * 60));
	return `${hh(sale)} → ${hh(new Date(sale.getTime() + min * 60_000))}`;
});

const duracion = computed(() => {
	if (!v.value?.km) return null;
	return `${Math.max(6, Math.round((v.value.km / 28) * 60))} min`;
});

/** «sale en 26 min» pesa mas que una fecha: es lo que decide si te levantas ahora. */
const cuentaAtras = computed(() => {
	if (!props.r.cuando) return null;
	const min = Math.round(
		(new Date(props.r.cuando).getTime() - Date.now()) / 60_000,
	);
	if (min < 0 || min > 600) return null;
	return min < 60
		? `leaves in ${min} min`
		: `leaves in ${Math.round(min / 60)} h`;
});

const fecha = computed(() =>
	props.r.cuando
		? new Date(props.r.cuando).toLocaleDateString("en-GB", {
				weekday: "short",
				day: "numeric",
				month: "short",
			})
		: null,
);

const banda = computed(() =>
	props.r.porcentaje >= 80
		? "alto"
		: props.r.porcentaje >= 60
			? "medio"
			: "bajo",
);

/** Con menos de 3 valoraciones NO se ense~na nota.
 *  Un 5,0 de una persona no es mejor que un 4,7 de treinta y siete, y ense~narlo como si lo
 *  fuera premia al recien llegado por encima del veterano. Declarar «nuevo» es mas creible que
 *  ense~nar un 5,0 vacio — y es la regla 8 del proyecto aplicada a la interfaz. */
const notaUtil = computed(
	() => c.value?.nota != null && (c.value?.notas ?? 0) >= 3,
);

/** El badge de idioma solo aparece cuando DIFIERE del idioma de la consulta. Antes salia en el
 *  100 % de las filas, asi que no informaba de nada; asi es la prueba visible de que el
 *  emparejamiento cruza idiomas, que es un argumento tecnico que se estaba regalando. */
const idiomaDistinto = computed(
	() =>
		props.idiomaConsulta &&
		props.r.idioma &&
		props.r.idioma !== props.idiomaConsulta,
);

const avatar = computed(() => {
	// Determinista por id: el mismo conductor tiene siempre la misma cara y el mismo color. Sin
	// foto real, un avatar estable es mas honesto que una foto de banco de imagenes — y ademas la
	// demo declara por escrito que los datos son sinteticos.
	const id = String(
		props.r.tipo === "PERSONA" ? props.r.id : (c.value?.nombre ?? props.r.id),
	);
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
	return {
		color: tonos[h % tonos.length],
		inicial: (c.value?.nombre ?? "?").slice(0, 1).toUpperCase(),
	};
});
</script>

<template>
  <article class="viaje" :class="{ descartado: r.motivo_descarte }">
    <div class="cuerpo">
      <!-- 1 · cuando y por donde -->
      <header class="linea1">
        <span v-if="horas" class="hora">{{ horas }}</span>
        <span v-if="v" class="ruta">{{ v.desde }} → {{ v.hasta }}</span>
        <span v-else class="ruta">{{ r.titulo }}</span>
      </header>

      <p class="linea2">
        <template v-if="v">
          <span v-if="duracion">{{ duracion }}</span>
          <span v-if="v.km">· {{ v.km }} km</span>
          <span v-if="v.via?.length">· via {{ v.via.join(', ') }}</span>
          <span v-if="v.recurrente" class="etiqueta gris">{{ v.recurrente === 'weekdays' ? 'Mon–Fri' : v.recurrente }}</span>
        </template>
        <template v-else>
          <span v-if="r.ciudad">{{ r.ciudad }}</span>
          <span v-if="r.km != null">· {{ r.km }} km away</span>
          <span v-if="r.edad">· {{ r.edad }}</span>
        </template>
        <span v-if="cuentaAtras" class="urge">· {{ cuentaAtras }}</span>
        <span v-else-if="fecha">· {{ fecha }}</span>
      </p>

      <!-- 2 · EL DESVIO. El dato diferencial del producto: siempre visible, nunca truncado. -->
      <p v-if="v?.km_de_tu_ruta != null" class="desvio" :class="{ cerca: v.km_de_tu_ruta < 1.5 }">
        <UIcon name="i-lucide-map-pin" />
        passes {{ v.km_de_tu_ruta }} km from you
      </p>

      <!-- 3 · quien conduce -->
      <div v-if="c?.nombre" class="quien">
        <span class="avatar" :style="{ background: avatar.color }">{{ avatar.inicial }}</span>
        <span class="nombre">{{ c.nombre }}</span>
        <span v-if="notaUtil" class="nota">
          <UIcon name="i-lucide-star" class="estrella" />{{ c.nota.toFixed(1) }}
          <span class="conteo">({{ c.notas }})</span>
        </span>
        <span v-else class="etiqueta ambar">New · {{ c.viajes }} rides</span>
        <span v-if="c.verificado >= 1" class="etiqueta verde"><UIcon name="i-lucide-badge-check" /> ID</span>
        <span v-if="c.coche" class="coche">{{ c.coche }}</span>
        <span v-if="idiomaDistinto" class="etiqueta gris">{{ r.idioma.toUpperCase() }}</span>
      </div>

      <!-- 4 · por que encaja -->
      <p v-if="r.explicacion" class="porque">{{ r.explicacion }}</p>
      <p v-else-if="!v" class="porque recorte">{{ r.subtitulo }}</p>

      <!-- 5 · lo que cuesta, y las acciones -->
      <footer class="acciones">
        <span v-if="r.plazas != null" class="dato">
          {{ r.plazas }} {{ r.plazas === 1 ? 'seat' : 'seats' }}
        </span>
        <span v-else-if="c?.plazas_coche" class="dato">{{ c.plazas_coche }}-seat car</span>
        <span v-if="v?.precio_total" class="dato">· {{ v.precio_total.toFixed(2) }} €</span>
        <span v-if="r.motivo_descarte" class="etiqueta gris">{{ r.motivo_descarte }}</span>
        <span class="empuja" />
        <UButton size="xs" color="neutral" variant="ghost" @click="emit('alternar')">
          {{ abierto ? 'Hide' : `Why ${r.porcentaje}%` }}
        </UButton>
        <UButton size="xs" :to="r.tipo === 'PLAN' ? `/plan/${r.id}` : `/persona/${r.id}`" variant="soft">
          {{ r.tipo === 'PLAN' ? 'View ride' : 'View profile' }}
        </UButton>
      </footer>
    </div>

    <!-- la columna del numero: propia, para que no compita con el titulo -->
    <div class="numero">
      <span class="puntuacion" :class="banda">{{ r.porcentaje }}</span>
      <span class="pct">%</span>
      <div class="barra" :class="banda"><i :style="{ width: `${r.porcentaje}%` }" /></div>
    </div>
  </article>
</template>

<style scoped>
.viaje {
  display: grid;
  grid-template-columns: 1fr 76px;
  gap: var(--e4);
  background: var(--superficie);
  border: 1px solid var(--linea);
  border-radius: var(--radio);
  padding: var(--e5);
  transition: border-color .15s, transform .08s;
}
.viaje:hover { border-color: var(--linea-fuerte); transform: translateY(-1px); }
.viaje.descartado { opacity: .62; }

.cuerpo { display: flex; flex-direction: column; gap: var(--e2); min-width: 0; }

.linea1 { display: flex; align-items: baseline; gap: var(--e3); flex-wrap: wrap; min-width: 0; }
.hora { font-size: var(--t-22); font-weight: 600; font-variant-numeric: tabular-nums; }
.ruta {
  font-size: var(--t-18); font-weight: 600; color: var(--tinta);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0;
}

.linea2 {
  display: flex; gap: var(--e1); flex-wrap: wrap; align-items: center;
  font-size: var(--t-13); font-weight: 500; color: var(--tinta-2);
}
.urge { color: var(--alta); font-weight: 600; }

/* El desvio es lo unico que este producto sabe y los demas no. No se trunca nunca. */
.desvio {
  display: inline-flex; align-items: center; gap: var(--e1);
  font-size: var(--t-13); font-weight: 600; color: var(--tinta-2);
}
.desvio.cerca { color: var(--alta); }

.quien { display: flex; align-items: center; gap: var(--e2); flex-wrap: wrap; }
.avatar {
  width: 44px; height: 44px; border-radius: 50%; color: #fff;
  display: inline-flex; align-items: center; justify-content: center;
  font-weight: 600; font-size: var(--t-18); flex: none;
}
.nombre { font-size: var(--t-16); font-weight: 600; }
.nota { display: inline-flex; align-items: center; gap: 2px; font-size: var(--t-15); font-weight: 600; }
.estrella { color: #E8A33D; }
.conteo { font-size: var(--t-13); font-weight: 400; color: var(--tinta-3); }
.coche { font-size: var(--t-13); color: var(--tinta-2); }

.porque { font-size: var(--t-15); color: var(--tinta-2); }
.recorte { display: -webkit-box; -webkit-line-clamp: 2; line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }

.acciones { display: flex; align-items: center; gap: var(--e2); flex-wrap: wrap; }
.dato { font-size: var(--t-15); font-weight: 600; }
.empuja { flex: 1 1 auto; }

.numero { display: flex; flex-direction: column; align-items: flex-end; gap: var(--e1); }
.numero .pct { font-size: var(--t-13); color: var(--tinta-3); margin-top: -6px; }
.numero .barra { width: 100%; }
.barra.alto { color: var(--accion); }
.barra.medio { color: var(--tinta-2); }
.barra.bajo { color: var(--tinta-3); }

@media (max-width: 640px) {
  .viaje { grid-template-columns: 1fr 60px; padding: var(--e4); }
  .hora { font-size: var(--t-18); }
  .ruta { font-size: var(--t-16); }
  .puntuacion { font-size: var(--t-28); }
}
</style>
