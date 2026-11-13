<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { setSession } from '../data/restaurant'
import { registerUser } from '../services/api'

const nombre = ref('')
const correo = ref('')
const direccion = ref('')
const password = ref('')
const confirmPassword = ref('')
const errorMessage = ref('')
const router = useRouter()

async function register() {
  errorMessage.value = ''

  if (!nombre.value.trim() || !correo.value.trim() || !password.value || !direccion.value.trim()) {
    errorMessage.value = 'Completa todos los campos obligatorios.'
    return
  }

  if (password.value.length < 6) {
    errorMessage.value = 'La contraseña debe tener al menos 6 caracteres.'
    return
  }

  if (password.value !== confirmPassword.value) {
    errorMessage.value = 'Las contraseñas no coinciden.'
    return
  }

  try {
    const response = await registerUser({
      nombre: nombre.value.trim(),
      correo: correo.value.trim().toLowerCase(),
      direccion: direccion.value.trim(),
      password: password.value,
    })
    setSession(response.usuario, response.token)
    router.push({ name: 'catalogo' })
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'No se pudo crear la cuenta.'
  }
}
</script>

<template>
  <main class="container py-5">
    <div class="row justify-content-center">
      <div class="col-sm-10 col-md-8 col-lg-6">
        <div class="card shadow-sm">
          <div class="card-body p-4">
            <RouterLink class="navbar-brand fw-bold text-danger" to="/">Mesa Roja</RouterLink>
            <h1 class="h3 mt-4">Crear cuenta</h1>
            <p class="text-body-secondary">Regístrate para hacer pedidos y administrar tu perfil.</p>

            <form class="mt-4" novalidate @submit.prevent="register">
              <div class="mb-3">
                <label class="form-label" for="nombre">Nombre</label>
                <input id="nombre" v-model="nombre" class="form-control" type="text" placeholder="Tu nombre" required />
              </div>

              <div class="mb-3">
                <label class="form-label" for="correo">Correo electrónico</label>
                <input id="correo" v-model="correo" class="form-control" type="email" placeholder="correo@ejemplo.com" required />
              </div>

              <div class="mb-3">
                <label class="form-label" for="direccion">Dirección</label>
                <input id="direccion" v-model="direccion" class="form-control" type="text" placeholder="Tu dirección" required />
              </div>

              <div class="mb-3">
                <label class="form-label" for="password">Contraseña</label>
                <input id="password" v-model="password" class="form-control" type="password" placeholder="Mínimo 6 caracteres" required />
              </div>

              <div class="mb-3">
                <label class="form-label" for="confirmPassword">Confirmar contraseña</label>
                <input id="confirmPassword" v-model="confirmPassword" class="form-control" type="password" placeholder="Repite tu contraseña" required />
              </div>

              <p v-if="errorMessage" class="alert alert-danger py-2 mb-3" role="alert">
                {{ errorMessage }}
              </p>

              <button class="btn btn-primary w-100" type="submit">Registrarse</button>
              <p class="mt-3 mb-0 text-center">
                <RouterLink to="/">Ya tengo cuenta</RouterLink>
              </p>
            </form>
          </div>
        </div>
      </div>
    </div>
  </main>
</template>
