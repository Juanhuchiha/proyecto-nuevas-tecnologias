<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { cartCount, clearUserRole, currentUser } from '../data/restaurant'

const isMenuOpen = ref(false)
const router = useRouter()

function logout() {
  clearUserRole()
  isMenuOpen.value = false
  router.push('/')
}
</script>

<template>
  <nav class="navbar navbar-expand-lg navbar-dark restaurant-navbar fixed-top">
    <div class="container">
      <RouterLink
        class="navbar-brand fw-bold text-white"
        :to="currentUser.role === 'admin' ? '/admin' : '/catalogo'"
        @click="isMenuOpen = false"
      >
        Mesa Roja
      </RouterLink>

      <button
        class="navbar-toggler"
        type="button"
        :aria-expanded="isMenuOpen"
        aria-label="Abrir navegación"
        @click="isMenuOpen = !isMenuOpen"
      >
        <span class="navbar-toggler-icon"></span>
      </button>

      <div class="collapse navbar-collapse" :class="{ show: isMenuOpen }">
        <div class="navbar-nav ms-auto align-items-lg-center">
          <template v-if="currentUser.role === 'cliente' || currentUser.role === 'admin'">
            <RouterLink class="nav-link" to="/catalogo" @click="isMenuOpen = false">
              Menú
            </RouterLink>
          </template>
          <template v-if="currentUser.role === 'repartidor'">
            <RouterLink class="nav-link" to="/envios" @click="isMenuOpen = false">
              Envíos
            </RouterLink>
          </template>
          <template v-if="currentUser.role === 'admin'">
            <RouterLink
              class="nav-link fw-bold"
              to="/admin"
              @click="isMenuOpen = false"
            >
              Inventario / Admin
            </RouterLink>
          </template>
          <template v-if="currentUser.role === 'cliente'">
            <RouterLink class="nav-link" to="/carrito" @click="isMenuOpen = false">
              Carrito
              <span class="badge text-bg-danger">{{ cartCount }}</span>
            </RouterLink>
          </template>
          <button class="btn btn-outline-light btn-sm ms-lg-3 my-2 my-lg-0" type="button" @click="logout">
            Cerrar Sesión
          </button>
        </div>
      </div>
    </div>
  </nav>
</template>
