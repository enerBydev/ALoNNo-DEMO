<script setup lang="ts">
useSeoMeta({ title: 'How the matching works — ALoNNo demo' })
const capas = [
  { n: 0, t: 'Understanding the sentence', c: 'one small-model call',
    d: 'Your sentence becomes a structured object: what kind of question it is, the city, the date, the subject, what must match. If the model gets the archetype wrong, the code corrects it — the decision tree is deterministic once you have the facts.' },
  { n: 1, t: 'Hard filters', c: 'plain SQL, zero AI cost',
    d: 'Date and availability, radius with PostGIS, category, seats, language. This turns thousands of rows into hundreds. A date that does not work is not a 60% match: it is not a match.' },
  { n: 2, t: 'Retrieval', c: 'an index lookup',
    d: 'Vector search over the filtered set AND keyword search over the same set, fused with Reciprocal Rank Fusion. An artist name is a token; a taste is a concept. Fusing both is what makes “someone who actually likes the artist” work.' },
  { n: 3, t: 'Scoring', c: 'arithmetic, zero cost',
    d: 'Seven weighted components. This is where the percentage comes from — the same arithmetic every time, testable, and openable on every result.' },
  { n: 4, t: 'Explanation', c: 'one call, only for what you see',
    d: 'The top few results get one sentence each, written from the components that already exist. The model writes the sentence. The model never writes the number.' },
]
</script>

<template>
  <div class="contenedor estrecho">
    <h1>How the matching works</h1>
    <p class="tenue" style="margin-top:.6rem">
      Five layers, cheapest first. Expensive intelligence only runs on what the cheap layers have
      already narrowed down.
    </p>

    <div v-for="c in capas" :key="c.n" class="tarjeta capa">
      <div class="num">{{ c.n }}</div>
      <div>
        <div class="fila-titulo"><h3>{{ c.t }}</h3><span class="etiqueta gris">{{ c.c }}</span></div>
        <p class="pequeno tenue">{{ c.d }}</p>
      </div>
    </div>

    <div class="tarjeta destacado">
      <h2>Your AI bill scales with content written, not searches performed</h2>
      <p class="pequeno">
        Profiles and plans are embedded when they are written. A search costs one small call to
        read your sentence and one to phrase the results you actually see — no matter how many
        candidates were evaluated.
      </p>
    </div>

    <h2 style="margin-top:1.6rem">What is demo and what is reusable</h2>
    <div class="rejilla dos">
      <div class="tarjeta">
        <h3>Reusable — the architecture</h3>
        <ul class="pequeno tenue">
          <li>The five-layer design and their order</li>
          <li>The schema: profiles, plans, intents</li>
          <li>The scoring model and its components</li>
          <li>Hybrid retrieval fused by RRF</li>
          <li>Embedding on write</li>
        </ul>
      </div>
      <div class="tarjeta">
        <h3>Demo — throwaway</h3>
        <ul class="pequeno tenue">
          <li>This code: no real auth, no RLS policies, no migrations</li>
          <li>The synthetic seed and its planted scenarios</li>
          <li>This single-page UI</li>
          <li>The provider choice</li>
        </ul>
      </div>
    </div>
  </div>
</template>

<style scoped>
.capa { display: flex; gap: 1rem; margin-bottom: .6rem; }
.num { width: 34px; height: 34px; border-radius: 9px; background: var(--acento-suave);
  color: var(--acento); display: grid; place-items: center; font-weight: 700; flex: none; }
.fila-titulo { display: flex; gap: .5rem; align-items: center; margin-bottom: .25rem; }
.destacado { margin-top: 1.2rem; border-left: 3px solid var(--acento); }
ul { margin: .4rem 0 0; padding-left: 1.1rem; }
li { margin-bottom: .2rem; }
</style>
