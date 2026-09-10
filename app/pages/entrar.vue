<script setup lang="ts">
// «Sign in» sin contrasena, y con razon: los perfiles son sinteticos y lo que la demo tiene que
// ense~nar es el producto visto DESDE ALGUIEN. Elegir quien eres es mas honesto que inventar un
// registro que no protege nada.
useSeoMeta({ title: 'Sign in — ALoNNo demo' })
const { entrar } = useSesion()
const ruta = useRoute()
const { data, pending } = await useFetch<{ perfiles: any[] }>('/api/perfiles')
const entrando = ref<string | null>(null)

async function elegir(p: any) {
  entrando.value = p.id
  await entrar(p.id)
  await navigateTo(String(ruta.query.volver || '/buscar'))
}
</script>

<template>
  <div class="contenedor estrecho">
    <h1>Who are you today?</h1>
    <p class="tenue" style="margin-top:.6rem">
      This is a demo over synthetic profiles, so there are no passwords. Pick someone and you will
      see the product from their side: their city, their taste, their plans.
    </p>
    <p class="minusculo tenue" style="margin-top:.4rem">
      Tip: pick someone from Düsseldorf who likes afrobeats, then search sentence 1.
    </p>

    <div v-if="pending" class="tenue" style="margin-top:2rem">
      <span class="cargando" /> loading profiles…
    </div>

    <div v-else class="rejilla dos" style="margin-top:1.4rem">
      <button v-for="p in data?.perfiles" :key="p.id" class="tarjeta persona"
              :disabled="entrando === p.id" @click="elegir(p)">
        <div class="fila">
          <span class="avatar">{{ p.display_name.charAt(0) }}</span>
          <div>
            <h3>{{ p.display_name }}<span v-if="p.age" class="tenue pequeno">, {{ p.age }}</span></h3>
            <p class="minusculo tenue">{{ p.city }} · writes in {{ p.bio_lang.toUpperCase() }}</p>
          </div>
          <span v-if="entrando === p.id" class="cargando" />
        </div>
        <p class="pequeno tenue bio">{{ p.bio }}</p>
        <div class="tags">
          <span v-for="i in (p.top_artists || []).slice(0, 2)" :key="i" class="etiqueta">{{ i }}</span>
          <span v-for="i in (p.interests || []).slice(0, 3)" :key="i" class="etiqueta gris">
            {{ i.replace(/_/g, ' ') }}
          </span>
        </div>
      </button>
    </div>
  </div>
</template>

<style scoped>
.persona { text-align: left; cursor: pointer; font: inherit; color: inherit;
  transition: border-color .12s, transform .12s; }
.persona:hover:not(:disabled) { border-color: var(--acento); transform: translateY(-2px); }
.fila { display: flex; align-items: center; gap: .6rem; }
.avatar { width: 34px; height: 34px; border-radius: 50%; background: var(--acento); color: #fff;
  display: grid; place-items: center; font-weight: 700; flex: none; }
.bio { margin: .55rem 0; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden; }
.tags { display: flex; flex-wrap: wrap; gap: .25rem; }
</style>
