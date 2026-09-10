<script setup lang="ts">
import frases from '../../db/frases.json'
useSeoMeta({ title: 'ALoNNo — this is my plan, who fits?' })
const ejemplo = computed(() => frases[0]?.frase_de_helder ?? '')
</script>

<template>
  <div class="contenedor">
    <section class="portada">
      <p class="etiqueta">Natural-language matching · demo</p>
      <h1>This is my plan.<br><span class="marcado">Who fits?</span></h1>
      <p class="entrada tenue">
        Write one sentence — in German or English. ALoNNo works out what you meant, finds the
        people and plans that fit, and explains every match with a number you can check.
      </p>
      <div class="acciones">
        <NuxtLink to="/buscar" class="boton">Try a search →</NuxtLink>
        <NuxtLink to="/entrar" class="boton fantasma">Sign in as someone</NuxtLink>
      </div>
      <p class="minusculo tenue muestra">e.g. “{{ ejemplo.slice(0, 96) }}…”</p>
    </section>

    <section class="tres rejilla">
      <NuxtLink to="/buscar" class="tarjeta paso">
        <span class="num">1</span>
        <h3>Find a person</h3>
        <p class="pequeno tenue">
          One sentence, no filters. The system decides what kind of question it is and searches
          for people, for plans, or for both.
        </p>
      </NuxtLink>
      <NuxtLink to="/crear" class="tarjeta paso">
        <span class="num">2</span>
        <h3>Post a plan</h3>
        <p class="pequeno tenue">
          Your plan is embedded the moment you write it — never when someone searches. That is
          what keeps the AI bill flat as searches grow.
        </p>
      </NuxtLink>
      <NuxtLink to="/mio" class="tarjeta paso">
        <span class="num">3</span>
        <h3>Agree to meet</h3>
        <p class="pequeno tenue">
          Show interest in a plan. When the other person shows interest back, it is a mutual
          match — and that is when people talk.
        </p>
      </NuxtLink>
    </section>

    <section class="tarjeta franja">
      <div>
        <h2>The number is arithmetic, not an opinion</h2>
        <p class="pequeno tenue">
          Every match opens into the seven components that produced it, each with its points. They
          add up to the percentage shown — you can check it by hand. The model writes the
          sentence; the model never writes the number.
        </p>
      </div>
      <NuxtLink to="/como-funciona" class="boton fantasma">How it works</NuxtLink>
    </section>
  </div>
</template>

<style scoped>
.portada { padding: 2.5rem 0 2.2rem; max-width: 40rem; }
.marcado { color: var(--acento); }
.entrada { font-size: 1.05rem; margin-top: .9rem; }
.acciones { display: flex; gap: .6rem; margin-top: 1.4rem; flex-wrap: wrap; }
.muestra { margin-top: 1rem; font-style: italic; }
.tres { grid-template-columns: 1fr; margin-bottom: 1.5rem; }
@media (min-width: 46rem) { .tres { grid-template-columns: repeat(3, 1fr); } }
.paso { text-decoration: none; display: block; transition: transform .12s, border-color .12s; }
.paso:hover { transform: translateY(-2px); border-color: var(--acento); }
.num { display: grid; place-items: center; width: 22px; height: 22px; border-radius: 6px;
  background: var(--acento-suave); color: var(--acento); font-size: .74rem; font-weight: 700;
  margin-bottom: .55rem; }
.paso h3 { margin-bottom: .3rem; }
.franja { display: flex; align-items: center; gap: 1.5rem; justify-content: space-between;
  flex-wrap: wrap; }
.franja h2 { margin-bottom: .35rem; }
.franja p { max-width: 40rem; }
</style>
