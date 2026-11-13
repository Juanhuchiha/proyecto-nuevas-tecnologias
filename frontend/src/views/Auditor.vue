<script setup>
import { onMounted, ref } from 'vue'
import { formatPrice } from '../data/restaurant'
import { fetchInventoryReport, fetchSalesReport } from '../services/api'

const inventory = ref(null)
const sales = ref(null)
const startDate = ref('')
const endDate = ref('')
const isLoading = ref(true)
const isFilteringSales = ref(false)
const errorMessage = ref('')

onMounted(async () => {
  try {
    const [inventoryReport, salesReport] = await Promise.all([
      fetchInventoryReport(),
      fetchSalesReport(),
    ])
    inventory.value = inventoryReport
    sales.value = salesReport
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : 'No se pudieron cargar los reportes.'
  } finally {
    isLoading.value = false
  }
})

async function filterSales() {
  errorMessage.value = ''
  isFilteringSales.value = true
  try {
    sales.value = await fetchSalesReport({
      desde: startDate.value,
      hasta: endDate.value,
    })
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : 'No se pudo consultar el reporte de ventas.'
  } finally {
    isFilteringSales.value = false
  }
}
</script>

<template>
  <main class="container py-4">
    <div class="d-flex flex-wrap align-items-center justify-content-between gap-3 mb-4">
      <div>
        <h1>Auditoría</h1>
        <p class="text-body-secondary mb-0">
          Consulta de ventas e inventario en modo de solo lectura.
        </p>
      </div>
      <span class="badge text-bg-secondary">Auditor</span>
    </div>

    <p v-if="errorMessage" class="alert alert-danger" role="alert">
      {{ errorMessage }}
    </p>
    <p v-if="isLoading" class="alert alert-info" role="status">
      Cargando reportes...
    </p>

    <section class="card mb-4" aria-labelledby="sales-report-title">
      <div class="card-header bg-white">
        <h2 id="sales-report-title" class="h5 mb-0">Reporte de ventas</h2>
      </div>
      <div class="card-body">
        <form class="row g-3 align-items-end mb-4" @submit.prevent="filterSales">
          <div class="col-sm-5 col-md-4">
            <label class="form-label" for="sales-start-date">Desde</label>
            <input id="sales-start-date" v-model="startDate" class="form-control" type="date" />
          </div>
          <div class="col-sm-5 col-md-4">
            <label class="form-label" for="sales-end-date">Hasta</label>
            <input id="sales-end-date" v-model="endDate" class="form-control" type="date" />
          </div>
          <div class="col-sm-2">
            <button class="btn btn-primary" type="submit" :disabled="isFilteringSales">
              {{ isFilteringSales ? 'Consultando...' : 'Consultar' }}
            </button>
          </div>
        </form>

        <div v-if="sales" class="row g-3">
          <div class="col-sm-6">
            <div class="border rounded p-3 h-100">
              <span class="text-body-secondary">Pedidos registrados</span>
              <p class="h3 mb-0">{{ sales.cantidad_pedidos }}</p>
            </div>
          </div>
          <div class="col-sm-6">
            <div class="border rounded p-3 h-100">
              <span class="text-body-secondary">Ventas totales</span>
              <p class="h3 mb-0">{{ formatPrice(sales.total_ventas) }}</p>
              <span class="small text-body-secondary">
                {{ sales.desde || 'Inicio' }} — {{ sales.hasta || 'Hoy' }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="card" aria-labelledby="inventory-report-title">
      <div class="card-header bg-white">
        <h2 id="inventory-report-title" class="h5 mb-0">Reporte de inventario</h2>
      </div>
      <div v-if="inventory" class="card-body">
        <div class="row g-3 mb-4">
          <div class="col-sm-6">
            <div class="border rounded p-3 h-100">
              <span class="text-body-secondary">Productos registrados</span>
              <p class="h3 mb-0">{{ inventory.cantidad_productos }}</p>
            </div>
          </div>
          <div class="col-sm-6">
            <div class="border rounded p-3 h-100">
              <span class="text-body-secondary">Unidades disponibles</span>
              <p class="h3 mb-0">{{ inventory.unidades_disponibles }}</p>
            </div>
          </div>
        </div>

        <div class="table-responsive">
          <table class="table table-striped table-hover align-middle mb-0">
            <thead class="table-light">
              <tr>
                <th scope="col">Producto</th>
                <th scope="col">Categoría</th>
                <th scope="col">Existencias</th>
                <th scope="col">Estado</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="product in inventory.productos" :key="product.id">
                <td>{{ product.nombre }}</td>
                <td>{{ product.categoria }}</td>
                <td>{{ product.stock }}</td>
                <td>
                  <span
                    class="badge"
                    :class="product.activo ? 'text-bg-success' : 'text-bg-secondary'"
                  >
                    {{ product.activo ? 'Activo' : 'Inactivo' }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>
  </main>
</template>
