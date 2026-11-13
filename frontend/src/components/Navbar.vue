<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { cartCount, clearUserRole, currentUser } from '../data/restaurant'
import { logoutUser } from '../services/api'

const isMenuOpen = ref(false)
const logoutError = ref('')
const isLoggingOut = ref(false)
const router = useRouter()
const roleLabel = computed(
  () =>
    ({
      admin: 'Administrador',
      cliente: 'Cliente',
      repartidor: 'Repartidor',
      auditor: 'Auditor',
    })[currentUser.role] || '',
)
const homeRoute = computed(
  () =>
    ({
      admin: '/admin',
      cliente: '/catalogo',
      repartidor: '/envios',
      auditor: '/auditoria',
    })[currentUser.role] || '/',
)

async function logout() {
  logoutError.value = ''
  isLoggingOut.value = true
  try {
    await logoutUser()
  } catch (error) {
    if (error?.status === 401) {
      clearUserRole()
      isMenuOpen.value = false
      router.push('/')
      isLoggingOut.value = false
      return
    }
    logoutError.value =
      error instanceof Error ? error.message : 'No se pudo cerrar la sesión.'
    isLoggingOut.value = false
    return
  }
  clearUserRole()
  isMenuOpen.value = false
  isLoggingOut.value = false
  router.push('/')
}
</script>

<template>
  <nav class="navbar navbar-expand-lg navbar-dark restaurant-navbar fixed-top">
    <div class="container">
      <RouterLink
        class="navbar-brand fw-bold text-white"
        :to="homeRoute"
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
          <p v-if="logoutError" class="alert alert-danger py-1 px-2 mb-2" role="alert">
            {{ logoutError }}
          </p>
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
          <template v-if="currentUser.role === 'auditor'">
            <RouterLink class="nav-link" to="/auditoria" @click="isMenuOpen = false">
              Reportes
            </RouterLink>
          </template>
          <span
            v-if="roleLabel"
            class="navbar-text text-white-50 ms-lg-3"
            aria-label="Tipo de usuario"
          >
            {{ roleLabel }}
          </span>
          <button
            class="btn btn-outline-light btn-sm ms-lg-3 my-2 my-lg-0"
            type="button"
            :disabled="isLoggingOut"
            @click="logout"
          >
            {{ isLoggingOut ? 'Cerrando...' : 'Cerrar Sesión' }}
          </button>
        </div>
      </div>
    </div>
  </nav>
</template>
