<script setup>
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  cart,
  clearCart,
  changeCartQuantity,
  registerDeliveryFromOrder,
  formatPrice,
  productForCartItem,
  removeFromCart,
  syncProductsFromApi,
  currentUser,
} from '../data/restaurant'
import { createOrder, fetchProducts } from '../services/api'

const router = useRouter()
const orderPlaced = ref(false)
const orderNumber = ref(null)
const orderError = ref('')
const orderWarning = ref('')
const attemptedSubmit = ref(false)
const shippingForm = ref(null)
const isSubmitting = ref(false)
const shipping = reactive({
  name: currentUser.name,
  email: currentUser.email,
  address: '',
  city: '',
})

const cartItems = computed(() =>
  cart.map((item) => ({ ...item, product: productForCartItem(item) })).filter((item) => item.product),
)
const subtotal = computed(() =>
  cartItems.value.reduce((total, item) => total + item.product.price * item.quantity, 0),
)
const deliveryFee = computed(() => (subtotal.value > 0 ? 5000 : 0))
const total = computed(() => subtotal.value + deliveryFee.value)

function isInvalid(field) {
  if (!attemptedSubmit.value) return false
  if (!shipping[field].trim()) return true
  if (field === 'email') {
    return !shippingForm.value.querySelector('#customer-email').validity.valid
  }
  return false
}

async function submitOrder() {
  if (isSubmitting.value) return

  attemptedSubmit.value = true
  orderError.value = ''
  orderWarning.value = ''
  const hasBlankField = Object.values(shipping).some((value) => !value.trim())
  if (hasBlankField || !shippingForm.value.checkValidity()) {
    orderError.value = 'Completa correctamente todos los campos de entrega.'
    return
  }

  isSubmitting.value = true
  try {
    if (!Number.isInteger(currentUser.id) || currentUser.id < 1) {
      throw new Error('No se encontró tu cuenta. Cierra sesión e inicia sesión nuevamente.')
    }

    const order = await createOrder({
      usuario_id: currentUser.id,
      direccion: `${shipping.address.trim()}, ${shipping.city.trim()}`,
      productos: cartItems.value.map((item) => ({
        producto_id: item.id,
        cantidad: item.quantity,
      })),
    })

    orderWarning.value = order.eventWarning || ''
    orderNumber.value = order.id
    clearCart()
    registerDeliveryFromOrder(order)
    orderPlaced.value = true

    try {
      syncProductsFromApi(await fetchProducts())
    } catch (error) {
      const catalogWarning =
        error instanceof Error
          ? `No se pudo actualizar el catálogo: ${error.message}`
          : 'No se pudo actualizar el catálogo.'
      orderWarning.value = [orderWarning.value, catalogWarning]
        .filter(Boolean)
        .join(' ')
    }
  } catch (error) {
    orderError.value =
      error instanceof Error ? error.message : 'No se pudo enviar el pedido al servidor.'
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <main class="container py-4">
    <div class="d-flex flex-wrap align-items-center justify-content-between gap-3 mb-4">
      <div>
        <h1>Carrito y pedido</h1>
        <p class="text-body-secondary mb-0">Revisa tu pedido y completa los datos de entrega.</p>
      </div>
      <RouterLink class="btn btn-outline-secondary" to="/catalogo">Seguir comprando</RouterLink>
    </div>

    <div v-if="orderPlaced" class="alert alert-success" role="status">
      <h2 class="h4">¡Gracias, {{ shipping.name.split(' ')[0] }}!</h2>
      <p class="mb-2">Tu pedido PED-{{ orderNumber }} ha sido confirmado.</p>
      <p v-if="orderWarning" class="alert alert-warning" role="alert">{{ orderWarning }}</p>
      <p class="mb-3">El restaurante ya recibió la información para prepararlo.</p>
      <button class="btn btn-primary" type="button" @click="router.push('/catalogo')">
        Volver al menú
      </button>
    </div>

    <div v-else-if="cartItems.length === 0" class="card">
      <div class="card-body text-center py-5">
        <p class="display-5" aria-hidden="true">🛒</p>
        <h2 class="h4">El carrito está vacío</h2>
        <p class="text-body-secondary">Agrega productos del catálogo para continuar.</p>
        <RouterLink class="btn btn-primary" to="/catalogo">Ver catálogo</RouterLink>
      </div>
    </div>

    <div v-else class="row g-4">
      <section class="col-lg-7">
        <div class="card mb-4">
          <div class="card-header bg-white d-flex justify-content-between align-items-center">
            <h2 class="h5 mb-0">Productos seleccionados</h2>
            <span class="badge text-bg-secondary">{{ cartItems.length }}</span>
          </div>
          <ul class="list-group list-group-flush">
            <li
              v-for="item in cartItems"
              :key="item.id"
              class="list-group-item d-flex align-items-center gap-3"
            >
              <span class="fs-2" aria-hidden="true">{{ item.product.icon }}</span>
              <div class="flex-grow-1">
                <h3 class="h6 mb-1">{{ item.product.name }}</h3>
                <span class="small text-body-secondary">
                  {{ formatPrice(item.product.price) }} cada uno
                </span>
              </div>
              <div class="btn-group btn-group-sm" role="group" :aria-label="`Cantidad de ${item.product.name}`">
                <button
                  class="btn btn-outline-secondary"
                  type="button"
                  :aria-label="`Quitar una unidad de ${item.product.name}`"
                  @click="changeCartQuantity(item.id, -1)"
                >−</button>
                <span class="btn btn-outline-secondary disabled">{{ item.quantity }}</span>
                <button
                  class="btn btn-outline-secondary"
                  type="button"
                  :aria-label="`Agregar una unidad de ${item.product.name}`"
                  :disabled="item.quantity >= item.product.stock"
                  @click="changeCartQuantity(item.id, 1)"
                >+</button>
              </div>
              <button
                class="btn btn-sm btn-outline-danger"
                type="button"
                :aria-label="`Eliminar ${item.product.name} del carrito`"
                @click="removeFromCart(item.id)"
              >
                Quitar
              </button>
            </li>
          </ul>
        </div>

        <form
          id="shipping-form"
          ref="shippingForm"
          class="card"
          novalidate
          @submit.prevent="submitOrder"
        >
          <div class="card-header bg-white">
            <h2 class="h5 mb-0">Datos de entrega</h2>
          </div>
          <div class="card-body">
            <div class="mb-3">
              <label class="form-label" for="customer-name">Nombre completo</label>
              <input
                id="customer-name"
                v-model="shipping.name"
                class="form-control"
                :class="{ 'is-invalid': isInvalid('name') }"
                readonly
                required
                autocomplete="name"
              />
              <div v-if="isInvalid('name')" class="invalid-feedback">Ingresa tu nombre completo.</div>
            </div>
            <div class="mb-3">
              <label class="form-label" for="customer-email">Correo electrónico</label>
              <input
                id="customer-email"
                v-model="shipping.email"
                class="form-control"
                :class="{ 'is-invalid': isInvalid('email') }"
                type="email"
                readonly
                required
                autocomplete="email"
              />
              <div v-if="isInvalid('email')" class="invalid-feedback">Ingresa un correo válido.</div>
            </div>
            <div class="mb-3">
              <label class="form-label" for="customer-address">Dirección</label>
              <input
                id="customer-address"
                v-model="shipping.address"
                class="form-control"
                :class="{ 'is-invalid': isInvalid('address') }"
                required
                autocomplete="street-address"
              />
              <div v-if="isInvalid('address')" class="invalid-feedback">Ingresa la dirección de entrega.</div>
            </div>
            <div>
              <label class="form-label" for="customer-city">Barrio y ciudad</label>
              <input
                id="customer-city"
                v-model="shipping.city"
                class="form-control"
                :class="{ 'is-invalid': isInvalid('city') }"
                required
                autocomplete="address-level2"
              />
              <div v-if="isInvalid('city')" class="invalid-feedback">Ingresa el barrio y la ciudad.</div>
            </div>
          </div>
        </form>
      </section>

      <aside class="col-lg-5">
        <div class="card">
          <div class="card-header bg-white">
            <h2 class="h5 mb-0">Resumen del pedido</h2>
          </div>
          <div class="card-body">
            <div class="d-flex justify-content-between mb-2">
              <span>Subtotal</span>
              <span>{{ formatPrice(subtotal) }}</span>
            </div>
            <div class="d-flex justify-content-between mb-3">
              <span>Envío</span>
              <span>{{ formatPrice(deliveryFee) }}</span>
            </div>
            <div class="d-flex justify-content-between border-top pt-3 mb-3">
              <strong>Total</strong>
              <strong>{{ formatPrice(total) }}</strong>
            </div>
            <p v-if="orderError" class="alert alert-danger py-2" role="alert">{{ orderError }}</p>
            <button
              class="btn btn-primary w-100"
              type="submit"
              form="shipping-form"
              :disabled="isSubmitting"
            >
              {{ isSubmitting ? 'Enviando pedido...' : 'Confirmar pedido' }}
            </button>
            <p class="small text-body-secondary text-center mt-3 mb-0">Pago al recibir · Pedido de demostración</p>
          </div>
        </div>
      </aside>
    </div>
  </main>
</template>
