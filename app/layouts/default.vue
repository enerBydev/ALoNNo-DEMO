<script setup lang="ts">
// La navegacion del producto. Dos formas: barra superior en escritorio, barra INFERIOR de cuatro
// destinos en movil.
//
// La razon del cambio (docs/conocimiento/20-critica-uiux.md §7.6, medido a 390 px): la cabecera
// de antes metia tres enlaces, la marca y un boton en 56 px, y a ancho de telefono «Post a plan»
// y «Sign in» se partian en dos lineas. Una app de movilidad se usa de pie y con una mano; los
// destinos van abajo, al alcance del pulgar, y a 56 px de alto.
const { sesion, salir } = useSesion();
const ruta = useRoute();

async function cerrar() {
	await salir();
	await navigateTo("/");
}
const activo = (p: string) =>
	ruta.path === p || (p !== "/" && ruta.path.startsWith(p));

const DESTINOS = [
	{ a: "/", etiqueta: "Search", icono: "i-lucide-search" },
	{ a: "/crear", etiqueta: "Offer a ride", icono: "i-lucide-circle-plus" },
	{ a: "/mio", etiqueta: "My rides", icono: "i-lucide-route" },
	{ a: "/como-funciona", etiqueta: "How", icono: "i-lucide-info" },
];
</script>

<template>
  <div class="marco">
    <header>
      <div class="contenedor barra-nav">
        <NuxtLink to="/" class="marca">
          <span class="punto" /> ALoNNo
          <UBadge size="sm" color="neutral" variant="subtle">demo</UBadge>
        </NuxtLink>

        <nav class="escritorio">
          <NuxtLink v-for="d in DESTINOS" :key="d.a" :to="d.a" :class="{ on: activo(d.a) }">
            {{ d.etiqueta }}
          </NuxtLink>
        </nav>

        <div class="yo">
          <template v-if="sesion">
            <NuxtLink :to="`/persona/${sesion.id}`" class="quien">
              <span class="avatar">{{ sesion.display_name.charAt(0) }}</span>
              <span class="pequeno">{{ sesion.display_name }}</span>
            </NuxtLink>
            <UButton size="xs" variant="ghost" color="neutral" @click="cerrar">sign out</UButton>
          </template>
          <UButton v-else to="/entrar" size="sm" variant="soft">Sign in</UButton>
        </div>
      </div>
    </header>

    <main>
      <slot />
    </main>

    <footer>
      <div class="contenedor minusculo">
        <strong>DEMO</strong> · synthetic data · no real personal data ·
        built by enerBydev for the ALoNNo project ·
        <NuxtLink to="/como-funciona">how the matching works</NuxtLink>
      </div>
    </footer>

    <!-- Barra inferior, solo en movil. Cuatro destinos, 56 px, al alcance del pulgar. -->
    <nav class="movil">
      <NuxtLink v-for="d in DESTINOS" :key="d.a" :to="d.a" :class="{ on: activo(d.a) }">
        <UIcon :name="d.icono" />
        <span>{{ d.etiqueta }}</span>
      </NuxtLink>
    </nav>
  </div>
</template>

<style scoped>
.marco { display: flex; flex-direction: column; min-height: 100vh; }

header {
  border-bottom: 1px solid var(--linea);
  background: color-mix(in srgb, var(--papel) 88%, transparent);
  backdrop-filter: blur(8px); position: sticky; top: 0; z-index: 20;
}
.barra-nav { display: flex; align-items: center; gap: var(--e4); height: 56px; }
.marca {
  display: flex; align-items: center; gap: var(--e1);
  font-weight: 700; text-decoration: none; letter-spacing: -.02em;
}
/* El punto de la marca NO usa el color de accion. «Lo verde» tiene que significar una sola cosa:
   esto se puede pulsar, o esto es bueno. Una marca no es ninguna de las dos. */
.punto { width: 9px; height: 9px; border-radius: 50%; background: var(--tinta); }

nav.escritorio { display: flex; gap: var(--e1); margin-left: auto; }
nav.escritorio a {
  text-decoration: none; padding: 6px var(--e3); border-radius: 8px;
  font-size: var(--t-15); color: var(--tinta-2);
}
nav.escritorio a:hover { background: var(--linea); color: var(--tinta); }
nav.escritorio a.on { color: var(--tinta); font-weight: 600; background: var(--linea); }

.yo { display: flex; align-items: center; gap: var(--e2); }
.quien { display: flex; align-items: center; gap: var(--e1); text-decoration: none; }
.avatar {
  width: 28px; height: 28px; border-radius: 50%; background: var(--tinta); color: var(--papel);
  display: grid; place-items: center; font-size: var(--t-13); font-weight: 700;
}

main { flex: 1; padding: var(--e6) 0 var(--e8); }
footer { border-top: 1px solid var(--linea); padding: var(--e4) 0; }

nav.movil { display: none; }

@media (max-width: 720px) {
  nav.escritorio { display: none; }
  main { padding-bottom: 76px; }   /* para que la barra no tape el ultimo resultado */
  nav.movil {
    display: grid; grid-template-columns: repeat(4, 1fr);
    position: fixed; inset: auto 0 0 0; height: 56px; z-index: 30;
    background: var(--superficie); border-top: 1px solid var(--linea);
    padding-bottom: env(safe-area-inset-bottom);
  }
  nav.movil a {
    display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px;
    text-decoration: none; color: var(--tinta-3); font-size: var(--t-12); font-weight: 500;
  }
  nav.movil a.on { color: var(--accion); }
  nav.movil :deep(.iconify) { width: 20px; height: 20px; }
}
</style>
