<script setup lang="ts">
// La cabecera: navegacion real entre las paginas del producto y quien eres.
const { sesion, salir } = useSesion()
const ruta = useRoute()

async function cerrar() {
  await salir()
  await navigateTo('/')
}
const activo = (p: string) => ruta.path === p || (p !== '/' && ruta.path.startsWith(p))
</script>

<template>
  <div class="marco">
    <header>
      <div class="contenedor barra-nav">
        <NuxtLink to="/" class="marca">
          <span class="punto" /> ALoNNo
          <span class="etiqueta gris">demo</span>
        </NuxtLink>

        <nav>
          <NuxtLink to="/buscar" :class="{ on: activo('/buscar') }">Search</NuxtLink>
          <NuxtLink to="/crear" :class="{ on: activo('/crear') }">Post a plan</NuxtLink>
          <NuxtLink v-if="sesion" to="/mio" :class="{ on: activo('/mio') }">Mine</NuxtLink>
        </nav>

        <div class="yo">
          <template v-if="sesion">
            <NuxtLink :to="`/persona/${sesion.id}`" class="quien">
              <span class="avatar">{{ sesion.display_name.charAt(0) }}</span>
              <span class="pequeno">{{ sesion.display_name }}</span>
            </NuxtLink>
            <button class="salir minusculo tenue" @click="cerrar">sign out</button>
          </template>
          <NuxtLink v-else to="/entrar" class="boton fantasma pequeno">Sign in</NuxtLink>
        </div>
      </div>
    </header>

    <main>
      <slot />
    </main>

    <footer>
      <div class="contenedor minusculo tenue">
        <strong>DEMO</strong> · synthetic data · no real personal data ·
        built by enerBydev for the ALoNNo project ·
        <NuxtLink to="/como-funciona">how the matching works</NuxtLink>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.marco { display: flex; flex-direction: column; min-height: 100vh; }
header { border-bottom: 1px solid var(--linea); background: color-mix(in srgb, var(--papel) 88%, transparent);
  backdrop-filter: blur(8px); position: sticky; top: 0; z-index: 10; }
.barra-nav { display: flex; align-items: center; gap: 1.2rem; height: 56px; }
.marca { display: flex; align-items: center; gap: .45rem; font-weight: 700; text-decoration: none;
  letter-spacing: -.02em; }
.punto { width: 9px; height: 9px; border-radius: 50%; background: var(--acento); }
nav { display: flex; gap: .25rem; margin-left: auto; }
nav a { text-decoration: none; padding: .35rem .6rem; border-radius: 7px; font-size: .9rem;
  color: var(--tenue); }
nav a:hover { background: var(--linea); color: var(--tinta); }
nav a.on { color: var(--tinta); font-weight: 600; background: var(--linea); }
.yo { display: flex; align-items: center; gap: .5rem; }
.quien { display: flex; align-items: center; gap: .4rem; text-decoration: none; }
.avatar { width: 26px; height: 26px; border-radius: 50%; background: var(--acento); color: #fff;
  display: grid; place-items: center; font-size: .78rem; font-weight: 700; }
.salir { background: none; border: none; cursor: pointer; text-decoration: underline; padding: 0; }
main { flex: 1; padding: 1.8rem 0 3rem; }
footer { border-top: 1px solid var(--linea); padding: 1.1rem 0; }
@media (max-width: 33rem) {
  nav a { padding: .35rem .4rem; font-size: .82rem; }
  .quien .pequeno { display: none; }
}
</style>
