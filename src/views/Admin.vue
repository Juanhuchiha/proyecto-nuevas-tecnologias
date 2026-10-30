<script setup>
import { computed } from 'vue'
import { formatPrice, products } from '../data/restaurant'

const totalUnits = computed(() => products.reduce((total, product) => total + product.stock, 0))
const lowStockCount = computed(() => products.filter((product) => product.stock <= 10).length)

function adjustStock(product, amount) {
  product.stock = Math.max(0, product.stock + amount)
}

function toggleProduct(product) {
  product.active = !product.active
}
</script>

<template>
  <main class="container py-4">
    <div class="d-flex flex-wrap align-items-center justify-content-between gap-3 mb-4">
      <div>
        <h1>Inventario</h1>
        <p class="text-body-secondary mb-0">
          Ajusta existencias y disponibilidad de los productos del menú.
        </p>
      </div>
      <RouterLink class="btn btn-outline-secondary" to="/catalogo">Volver al menú</RouterLink>
    </div>

    <div class="row g-3 mb-4">
      <div class="col-sm-4">
        <div class="card h-100">
          <div class="card-body">
            <span class="text-body-secondary">Productos</span>
            <p class="h3 mb-0">{{ products.length }}</p>
          </div>
        </div>
      </div>
      <div class="col-sm-4">
        <div class="card h-100">
          <div class="card-body">
            <span class="text-body-secondary">Unidades disponibles</span>
            <p class="h3 mb-0">{{ totalUnits }}</p>
          </div>
        </div>
      </div>
      <div class="col-sm-4">
        <div class="card h-100">
          <div class="card-body">
            <span class="text-body-secondary">Stock bajo</span>
            <p class="h3 mb-0">{{ lowStockCount }}</p>
          </div>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-header bg-white">
        <h2 class="h5 mb-0">Productos en inventario</h2>
      </div>
      <div class="table-responsive">
        <table class="table table-striped table-hover align-middle mb-0">
          <thead class="table-light">
            <tr>
              <th scope="col">Producto</th>
              <th scope="col">Categoría</th>
              <th scope="col">Precio</th>
              <th scope="col">Existencias</th>
              <th scope="col">Ajustar stock</th>
              <th scope="col">Estado</th>
              <th scope="col">Acciones</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="product in products" :key="product.id">
              <td>
                <span class="me-2" aria-hidden="true">{{ product.icon }}</span>
                <strong>{{ product.name }}</strong>
              </td>
              <td>{{ product.category }}</td>
              <td>{{ formatPrice(product.price) }}</td>
              <td><strong>{{ product.stock }}</strong></td>
              <td>
                <div class="btn-group btn-group-sm" role="group" :aria-label="`Ajustar stock de ${product.name}`">
                  <button
                    class="btn btn-outline-secondary"
                    type="button"
                    :aria-label="`Reducir stock de ${product.name}`"
                    :disabled="product.stock === 0"
                    @click="adjustStock(product, -1)"
                  >−</button>
                  <button
                    class="btn btn-outline-secondary"
                    type="button"
                    :aria-label="`Aumentar stock de ${product.name}`"
                    @click="adjustStock(product, 1)"
                  >+</button>
                </div>
              </td>
              <td>
                <span
                  class="badge"
                  :class="!product.active ? 'text-bg-secondary' : product.stock <= 5 ? 'text-bg-danger' : product.stock <= 10 ? 'text-bg-warning' : 'text-bg-success'"
                >
                  {{
                    !product.active
                      ? 'Inactivo'
                      : product.stock === 0
                        ? 'Agotado'
                        : product.stock <= 5
                          ? 'Agotándose'
                          : product.stock <= 10
                            ? 'Stock bajo'
                            : 'Disponible'
                  }}
                </span>
              </td>
              <td>
                <button
                  class="btn btn-sm"
                  :class="product.active ? 'btn-outline-danger' : 'btn-outline-success'"
                  type="button"
                  @click="toggleProduct(product)"
                >
                  {{ product.active ? 'Desactivar' : 'Activar' }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="card-footer text-body-secondary small">
        El inventario se actualiza al confirmar un pedido.
      </div>
    </div>
  </main>
</template>
