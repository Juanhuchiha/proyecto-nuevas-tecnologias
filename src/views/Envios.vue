<script setup>
import { computed, ref } from 'vue'
import { deliveries, updateDeliveryStatus } from '../data/restaurant'

const errorMessage = ref('')
const activeDeliveries = computed(() =>
  deliveries.filter((delivery) => delivery.status !== 'Entregado'),
)
const completedDeliveries = computed(() =>
  deliveries.filter((delivery) => delivery.status === 'Entregado'),
)

function advanceDelivery(delivery) {
  errorMessage.value = ''
  const nextStatus =
    delivery.status === 'Listo para recoger' ? 'En camino' : 'Entregado'

  try {
    updateDeliveryStatus(delivery.id, nextStatus)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'No se pudo actualizar el envío.'
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

    <section class="mb-4">
      <h2 class="h4 mb-3">Entregas pendientes</h2>
      <div v-if="activeDeliveries.length === 0" class="alert alert-success">
        No tienes entregas pendientes.
      </div>

      <div class="row g-3">
        <div v-for="delivery in activeDeliveries" :key="delivery.id" class="col-md-6">
          <article class="card h-100">
            <div class="card-header bg-white d-flex justify-content-between align-items-center">
              <strong>{{ delivery.id }}</strong>
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
            </tr>
          </thead>
          <tbody>
            <tr v-for="delivery in completedDeliveries" :key="delivery.id">
              <td>{{ delivery.id }}</td>
              <td>{{ delivery.customer }}</td>
              <td>{{ delivery.address }}</td>
              <td><span class="badge text-bg-success">Entregado</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </main>
</template>
