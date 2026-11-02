<script setup>
import { computed, onMounted, ref } from 'vue'
import {
  currentUser,
  deliveries,
  syncDeliveriesFromApi,
} from '../data/restaurant'
import {
  fetchOrderHistory,
  fetchOrders,
  updateOrderStatus,
} from '../services/api'

const errorMessage = ref('')
const historyError = ref('')
const history = ref(null)
const selectedOrderId = ref(null)
const warningMessage = ref('')
const isLoading = ref(true)
const loadingHistory = ref(false)
const activeDeliveries = computed(() =>
  deliveries.filter((delivery) => delivery.status !== 'Entregado'),
)
const completedDeliveries = computed(() =>
  deliveries.filter((delivery) => delivery.status === 'Entregado'),
)
const historyEvents = computed(() => {
  if (!history.value) return []
  return [
    ...history.value.historial.map((event) => ({
      ...event,
      source: 'Estado del pedido',
      title: event.estado_anterior
        ? `${event.estado_anterior} → ${event.estado_nuevo}`
        : `Pedido creado: ${event.estado_nuevo}`,
    })),
    ...history.value.actividades.map((event) => ({
      ...event,
      source: 'Actividad',
      title: event.tipo,
    })),
    ...history.value.registros_sistema.map((event) => ({
      ...event,
      source: 'Registro del sistema',
      title: event.descripcion,
    })),
  ].sort((first, second) => new Date(first.fecha) - new Date(second.fecha))
})

onMounted(async () => {
  errorMessage.value = ''
  try {
    syncDeliveriesFromApi(await fetchOrders())
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : 'No se pudieron cargar los pedidos.'
  } finally {
    isLoading.value = false
  }
})

async function advanceDelivery(delivery) {
  errorMessage.value = ''
  warningMessage.value = ''
  const nextStatus =
    delivery.status === 'Listo para recoger' ? 'En camino' : 'Entregado'

  try {
    const updatedOrder = await updateOrderStatus(
      delivery.id,
      nextStatus,
      currentUser.name,
    )
    delivery.status = updatedOrder.estado
    warningMessage.value = updatedOrder.eventWarning
    if (selectedOrderId.value === delivery.id) {
      history.value = await fetchOrderHistory(delivery.id)
    }
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : 'No se pudo actualizar el envío.'
  }
}

async function toggleHistory(orderId) {
  if (selectedOrderId.value === orderId) {
    selectedOrderId.value = null
    history.value = null
    historyError.value = ''
    return
  }

  selectedOrderId.value = orderId
  history.value = null
  historyError.value = ''
  loadingHistory.value = true
  try {
    history.value = await fetchOrderHistory(orderId)
  } catch (error) {
    historyError.value =
      error instanceof Error ? error.message : 'No se pudo consultar el historial.'
  } finally {
    loadingHistory.value = false
  }
}
</script>

<template>
  <main class="container py-4">
    <div class="mb-4">
      <h1>Seguimiento de envíos</h1>
      <p class="text-body-secondary">Consulta tus entregas y actualiza su estado.</p>
    </div>

    <p v-if="errorMessage" class="alert alert-danger" role="alert">{{ errorMessage }}</p>
    <p v-if="warningMessage" class="alert alert-warning" role="status">{{ warningMessage }}</p>

    <section class="mb-4">
      <h2 class="h4 mb-3">Entregas pendientes</h2>
      <div v-if="isLoading" class="alert alert-info" role="status">
        Cargando pedidos...
      </div>
      <div
        v-else-if="activeDeliveries.length === 0"
        class="alert alert-success"
      >
        No hay pedidos pendientes.
      </div>

      <div class="row g-3">
        <div v-for="delivery in activeDeliveries" :key="delivery.id" class="col-md-6">
          <article class="card h-100">
            <div class="card-header bg-white d-flex justify-content-between align-items-center">
              <strong>PED-{{ delivery.id }}</strong>
              <span
                class="badge"
                :class="delivery.status === 'En camino' ? 'text-bg-primary' : 'text-bg-warning'"
              >
                {{ delivery.status }}
              </span>
            </div>
            <div class="card-body">
              <p class="mb-2"><strong>Cliente:</strong> {{ delivery.customer }}</p>
              <p class="mb-2"><strong>Dirección:</strong> {{ delivery.address }}</p>
              <p class="small text-body-secondary">{{ delivery.items }}</p>
              <button class="btn btn-primary btn-sm" type="button" @click="advanceDelivery(delivery)">
                {{ delivery.status === 'En camino' ? 'Marcar como entregado' : 'Iniciar entrega' }}
              </button>
              <button
                class="btn btn-outline-secondary btn-sm ms-2"
                type="button"
                @click="toggleHistory(delivery.id)"
              >
                {{ selectedOrderId === delivery.id ? 'Ocultar historial' : 'Ver historial' }}
              </button>
            </div>
          </article>
        </div>
      </div>
    </section>

    <section>
      <h2 class="h4 mb-3">Entregas completadas</h2>
      <div v-if="completedDeliveries.length === 0" class="alert alert-light border">
        Aún no hay entregas completadas.
      </div>
      <div v-else class="table-responsive">
        <table class="table table-striped table-hover align-middle">
          <thead class="table-light">
            <tr>
              <th scope="col">Pedido</th>
              <th scope="col">Cliente</th>
              <th scope="col">Dirección</th>
              <th scope="col">Estado</th>
              <th scope="col">Historial</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="delivery in completedDeliveries" :key="delivery.id">
              <td>PED-{{ delivery.id }}</td>
              <td>{{ delivery.customer }}</td>
              <td>{{ delivery.address }}</td>
              <td><span class="badge text-bg-success">Entregado</span></td>
              <td>
                <button
                  class="btn btn-outline-secondary btn-sm"
                  type="button"
                  @click="toggleHistory(delivery.id)"
                >
                  {{ selectedOrderId === delivery.id ? 'Ocultar' : 'Ver historial' }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section
      v-if="selectedOrderId !== null"
      class="card mt-4"
      aria-live="polite"
    >
      <div class="card-header bg-white">
        <h2 class="h5 mb-0">Historial del pedido PED-{{ selectedOrderId }}</h2>
        <p class="small text-body-secondary mb-0">
          Información combinada de PostgreSQL y MongoDB.
        </p>
      </div>
      <div class="card-body">
        <p v-if="loadingHistory" class="text-body-secondary">
          Consultando las bases de datos...
        </p>
        <p v-if="historyError" class="alert alert-danger" role="alert">
          {{ historyError }}
        </p>
        <ol v-if="historyEvents.length" class="list-group list-group-flush">
          <li
            v-for="(event, index) in historyEvents"
            :key="`${event.source}-${event.id || index}`"
            class="list-group-item px-0"
          >
            <strong>{{ event.title }}</strong>
            <span class="d-block small text-body-secondary">
              {{ event.source }} · {{ new Date(event.fecha).toLocaleString() }}
            </span>
          </li>
        </ol>
        <p
          v-else-if="history && !loadingHistory && !historyError"
          class="text-body-secondary mb-0"
        >
          Aún no hay eventos registrados.
        </p>
      </div>
    </section>
  </main>
</template>
