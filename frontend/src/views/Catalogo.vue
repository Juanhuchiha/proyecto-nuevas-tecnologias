<script setup>
import { computed, onMounted, ref } from 'vue'
import { fetchProducts } from '../services/api'
import {
  addToCart,
  categories,
  formatPrice,
  products,
  syncProductsFromApi,
} from '../data/restaurant'

const activeCategory = ref('Todos')
const notice = ref('')
const isLoading = ref(true)
const loadError = ref('')

const visibleProducts = computed(() =>
  products.filter(
    (product) =>
      product.active &&
      (activeCategory.value === 'Todos' || product.category === activeCategory.value),
  ),
)

function addProduct(product) {
  notice.value = addToCart(product)
    ? `${product.name} se agregó al carrito.`
    : `No hay más unidades disponibles de ${product.name}.`
}

onMounted(async () => {
  try {
    syncProductsFromApi(await fetchProducts())
  } catch (error) {
    loadError.value =
      error instanceof Error
        ? `No se pudo conectar con el backend (${error.message}). Se muestran los datos locales.`
        : 'No se pudo conectar con el backend. Se muestran los datos locales.'
  } finally {
    isLoading.value = false
  }
})
</script>

<template>
  <main class="container py-4">
    <div class="mb-4">
      <h1>Menú</h1>
      <p class="text-body-secondary">Escoge tus favoritos y agrégalos al carrito.</p>
    </div>

    <div v-if="isLoading" class="alert alert-info" role="status">
      Cargando productos del servidor...
    </div>
    <div v-if="loadError" class="alert alert-warning" role="alert">{{ loadError }}</div>

    <div class="d-flex flex-wrap gap-2 mb-4" role="group" aria-label="Filtrar por categoría">
      <button
        v-for="category in categories"
        :key="category"
        class="btn"
        :class="activeCategory === category ? 'btn-primary' : 'btn-outline-secondary'"
        type="button"
        @click="activeCategory = category"
      >
        {{ category }}
      </button>
    </div>

    <p v-if="notice" class="alert alert-info py-2" role="status">{{ notice }}</p>

    <div class="row g-3">
      <div v-for="product in visibleProducts" :key="product.id" class="col-sm-6 col-lg-4 col-xl-3">
        <article class="card h-100">
          <img
            :src="product.imagen"
            class="card-img-top product-image"
            :alt="product.name"
            loading="lazy"
          />
          <div class="card-body d-flex flex-column">
            <div class="d-flex align-items-start justify-content-between mb-2">
              <span class="small text-body-secondary">{{ product.category }}</span>
              <span v-if="product.tag" class="badge text-bg-warning">{{ product.tag }}</span>
            </div>
            <h2 class="h5 card-title mt-1">{{ product.name }}</h2>
            <p class="card-text text-body-secondary small">{{ product.description }}</p>
            <div class="mt-auto d-flex align-items-center justify-content-between gap-2">
              <strong>{{ formatPrice(product.price) }}</strong>
              <button
                class="btn btn-primary btn-sm"
                type="button"
                :disabled="product.stock === 0 || !product.active"
                @click="addProduct(product)"
              >
                Agregar al carrito
              </button>
            </div>
          </div>
        </article>
      </div>
    </div>
  </main>
</template>

<style scoped>
.product-image {
  height: 190px;
  object-fit: cover;
}
</style>
