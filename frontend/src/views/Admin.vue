<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { currentUser, formatPrice, products, syncProductsFromApi } from '../data/restaurant'
import {
  createProduct,
  deleteProduct,
  fetchOrders,
  fetchProducts,
  fetchSalesReport,
  updateOrderStatus,
  updateProduct,
} from '../services/api'

const orders = ref([])
const report = ref(null)
const isLoading = ref(true)
const isSavingProduct = ref(false)
const errorMessage = ref('')
const notice = ref('')
const newProduct = reactive({
  nombre: '',
  precio: 0,
  stock: 0,
  categoria: '',
  descripcion: '',
  imagen: '',
})
const totalUnits = computed(() => products.reduce((total, product) => total + product.stock, 0))
const lowStockCount = computed(() => products.filter((product) => product.stock <= 10).length)
const orderStatuses = ['Listo para recoger', 'En camino', 'Entregado']

onMounted(async () => {
  try {
    const [apiProducts, apiOrders, salesReport] = await Promise.all([
      fetchProducts(),
      fetchOrders(),
      fetchSalesReport(),
    ])
    syncProductsFromApi(apiProducts)
    orders.value = apiOrders
    report.value = salesReport
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : 'No se pudo cargar la información administrativa.'
  } finally {
    isLoading.value = false
  }
})

async function adjustStock(product, amount) {
  errorMessage.value = ''
  notice.value = ''
  const stock = product.stock + amount
  if (stock < 0) return

  try {
    const updated = await updateProduct(product.id, { stock })
    product.stock = updated.stock
    notice.value = `Se actualizó el inventario de ${product.name}.`
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : 'No se pudo actualizar el inventario.'
  }
}

async function toggleProduct(product) {
  errorMessage.value = ''
  notice.value = ''
  try {
    const updated = product.active
      ? (await deleteProduct(product.id)).producto
      : await updateProduct(product.id, { activo: true })
    product.active = updated.activo
    notice.value = `${product.name} ahora está ${product.active ? 'activo' : 'inactivo'}.`
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : 'No se pudo actualizar el producto.'
  }
}

async function addProduct() {
  errorMessage.value = ''
  notice.value = ''
  isSavingProduct.value = true
  try {
    const created = await createProduct({
      ...newProduct,
      activo: true,
    })
    products.push({
      id: created.id,
      name: created.nombre,
      category: created.categoria,
      description: created.descripcion,
      price: created.precio,
      stock: created.stock,
      imagen: created.imagen,
      icon: '🍽️',
      tag: '',
      active: created.activo,
    })
    Object.assign(newProduct, {
      nombre: '',
      precio: 0,
      stock: 0,
      categoria: '',
      descripcion: '',
      imagen: '',
    })
    notice.value = 'Producto creado correctamente.'
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : 'No se pudo crear el producto.'
  } finally {
    isSavingProduct.value = false
  }
}

async function changeOrderStatus(order, event) {
  errorMessage.value = ''
  const previousStatus = order.estado
  const selectedStatus = event.target.value
  try {
    const updated = await updateOrderStatus(order.id, selectedStatus, currentUser.name)
    order.estado = updated.estado
    if (updated.eventWarning) notice.value = updated.eventWarning
  } catch (error) {
    event.target.value = previousStatus
    errorMessage.value =
      error instanceof Error ? error.message : 'No se pudo actualizar el estado del pedido.'
  }
}
</script>

<template>
  <main class="container py-4">
    <div class="d-flex flex-wrap align-items-center justify-content-between gap-3 mb-4">
      <div>
        <h1>Administración</h1>
        <p class="text-body-secondary mb-0">
          Gestiona productos, inventario y pedidos.
        </p>
      </div>
      <RouterLink class="btn btn-outline-secondary" to="/catalogo">Volver al menú</RouterLink>
    </div>

    <p v-if="errorMessage" class="alert alert-danger" role="alert">{{ errorMessage }}</p>
    <p v-if="notice" class="alert alert-info" role="status">{{ notice }}</p>
    <p v-if="isLoading" class="alert alert-info" role="status">
      Cargando productos, pedidos y reportes...
    </p>

    <section class="row g-3 mb-4" aria-label="Resumen de ventas">
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
            <span class="text-body-secondary">Ventas registradas</span>
            <p class="h3 mb-0">
              {{ report ? formatPrice(report.total_ventas) : '—' }}
            </p>
            <span v-if="report" class="small text-body-secondary">
              {{ report.cantidad_pedidos }} pedidos · {{ lowStockCount }} productos con stock bajo
            </span>
          </div>
        </div>
      </div>
    </section>

    <section class="card mb-4">
      <div class="card-header bg-white">
        <h2 class="h5 mb-0">Agregar producto</h2>
      </div>
      <form class="card-body row g-3" @submit.prevent="addProduct">
        <div class="col-md-4">
          <label class="form-label" for="product-name">Nombre</label>
          <input id="product-name" v-model="newProduct.nombre" class="form-control" required />
        </div>
        <div class="col-md-3">
          <label class="form-label" for="product-category">Categoría</label>
          <input id="product-category" v-model="newProduct.categoria" class="form-control" required />
        </div>
        <div class="col-md-2">
          <label class="form-label" for="product-price">Precio (COP)</label>
          <input
            id="product-price"
            v-model.number="newProduct.precio"
            class="form-control"
            type="number"
            min="0"
            required
          />
        </div>
        <div class="col-md-3">
          <label class="form-label" for="product-stock">Existencias</label>
          <input
            id="product-stock"
            v-model.number="newProduct.stock"
            class="form-control"
            type="number"
            min="0"
            required
          />
        </div>
        <div class="col-md-6">
          <label class="form-label" for="product-description">Descripción</label>
          <input
            id="product-description"
            v-model="newProduct.descripcion"
            class="form-control"
          />
        </div>
        <div class="col-md-6">
          <label class="form-label" for="product-image">URL de imagen</label>
          <input id="product-image" v-model="newProduct.imagen" class="form-control" type="url" />
        </div>
        <div class="col-12">
          <button class="btn btn-primary" type="submit" :disabled="isSavingProduct">
            {{ isSavingProduct ? 'Guardando...' : 'Crear producto' }}
          </button>
        </div>
      </form>
    </section>

    <section class="card mb-4">
      <div class="card-header bg-white">
        <h2 class="h5 mb-0">Productos e inventario</h2>
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
              <td><strong>{{ product.name }}</strong></td>
              <td>{{ product.category }}</td>
              <td>{{ formatPrice(product.price) }}</td>
              <td><strong>{{ product.stock }}</strong></td>
              <td>
                <div class="btn-group btn-group-sm" role="group" :aria-label="`Ajustar stock de ${product.name}`">
                  <button
                    class="btn btn-outline-secondary"
                    type="button"
                    :disabled="product.stock === 0"
                    :aria-label="`Reducir stock de ${product.name}`"
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
                <span class="badge" :class="product.active ? 'text-bg-success' : 'text-bg-secondary'">
                  {{ product.active ? 'Activo' : 'Inactivo' }}
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
    </section>

    <section class="card">
      <div class="card-header bg-white">
        <h2 class="h5 mb-0">Pedidos</h2>
      </div>
      <div v-if="orders.length === 0 && !isLoading" class="card-body text-body-secondary">
        No hay pedidos registrados.
      </div>
      <div v-else class="table-responsive">
        <table class="table table-striped table-hover align-middle mb-0">
          <thead class="table-light">
            <tr>
              <th scope="col">Pedido</th>
              <th scope="col">Cliente</th>
              <th scope="col">Total</th>
              <th scope="col">Estado</th>
              <th scope="col">Actualizar estado</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="order in orders" :key="order.id">
              <td>#{{ order.id }}</td>
              <td>{{ order.cliente.nombre }}</td>
              <td>{{ formatPrice(order.total) }}</td>
              <td>{{ order.estado }}</td>
              <td>
                <select
                  class="form-select form-select-sm"
                  :value="order.estado"
                  :aria-label="`Estado del pedido ${order.id}`"
                  @change="changeOrderStatus(order, $event)"
                >
                  <option v-for="status in orderStatuses" :key="status" :value="status">
                    {{ status }}
                  </option>
                </select>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </main>
</template>
