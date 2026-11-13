<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { setSession } from '../data/restaurant'
import { loginUser } from '../services/api'

const email = ref('')
const password = ref('')
const errorMessage = ref('')
const router = useRouter()

async function login() {
  errorMessage.value = ''

  if (!email.value.trim() || !password.value) {
    errorMessage.value = 'Completa el correo y la contraseña para continuar.'
    return
  }

  try {
    const response = await loginUser({
      correo: email.value.trim().toLowerCase(),
      password: password.value,
    })
    setSession(response.usuario, response.token)
    const destination = {
      cliente: { name: 'catalogo' },
      admin: { name: 'admin' },
      repartidor: { name: 'envios' },
      auditor: { name: 'auditoria' },
    }[response.usuario.rol] || { name: 'catalogo' }
    router.push(destination)
  } catch (error) {
    errorMessage.value =
      error instanceof Error
        ? error.message
        : 'No se pudo iniciar sesión. Inténtalo de nuevo.'
  }
}
</script>

<template>
  <main class="container py-5">
    <div class="row justify-content-center">
      <div class="col-sm-10 col-md-7 col-lg-5">
        <div class="card shadow-sm">
          <div class="card-body p-4">
            <RouterLink class="navbar-brand fw-bold text-danger" to="/">Mesa Roja</RouterLink>
            <h1 class="h3 mt-4">Iniciar sesión</h1>
            <p class="text-body-secondary">Ingresa con tu correo y contraseña.</p>

            <form class="mt-4" novalidate @submit.prevent="login">
              <div class="mb-3">
                <label class="form-label" for="email">Correo electrónico</label>
                <input
                  id="email"
                  v-model="email"
                  class="form-control"
                  type="email"
                  placeholder="correo@ejemplo.com"
                  autocomplete="email"
                  required
                />
              </div>

              <div class="mb-3">
                <label class="form-label" for="password">Contraseña</label>
                <input
                  id="password"
                  v-model="password"
                  class="form-control"
                  type="password"
                  placeholder="Ingresa tu contraseña"
                  autocomplete="current-password"
                  required
                />
              </div>

              <p v-if="errorMessage" class="alert alert-danger py-2 mb-3" role="alert">
                {{ errorMessage }}
              </p>

              <button class="btn btn-primary w-100" type="submit">Ingresar</button>
              <p class="mt-3 mb-0 text-center">
                <RouterLink to="/registro">Crear cuenta</RouterLink>
              </p>
            </form>
          </div>
        </div>
      </div>
    </div>
  </main>
</template>
