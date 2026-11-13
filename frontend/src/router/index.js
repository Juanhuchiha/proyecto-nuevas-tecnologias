import { createRouter, createWebHistory } from 'vue-router'
import Login from '../views/Login.vue'
import Registro from '../views/Registro.vue'
import Catalogo from '../views/Catalogo.vue'
import Carrito from '../views/Carrito.vue'
import Admin from '../views/Admin.vue'
import Envios from '../views/Envios.vue'
import Auditor from '../views/Auditor.vue'
import { currentUser } from '../data/restaurant'

function currentSessionRole() {
  return currentUser.role || localStorage.getItem('restaurant-role') || null
}

function hasSessionToken() {
  return !!localStorage.getItem('restaurant-token')
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'login', component: Login, meta: { guestOnly: true } },
    { path: '/registro', name: 'registro', component: Registro, meta: { guestOnly: true } },
    {
      path: '/catalogo',
      name: 'catalogo',
      component: Catalogo,
      meta: { requiresAuth: true, roles: ['cliente', 'admin'] },
    },
    {
      path: '/carrito',
      name: 'carrito',
      component: Carrito,
      meta: { requiresAuth: true, role: 'cliente' },
    },
    {
      path: '/admin',
      name: 'admin',
      component: Admin,
      meta: { requiresAuth: true, role: 'admin' },
    },
    {
      path: '/envios',
      name: 'envios',
      component: Envios,
      meta: { requiresAuth: true, role: 'repartidor' },
    },
    {
      path: '/auditoria',
      name: 'auditoria',
      component: Auditor,
      meta: { requiresAuth: true, role: 'auditor' },
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

function homeForRole(role) {
  if (role === 'admin') return { name: 'admin' }
  if (role === 'repartidor') return { name: 'envios' }
  if (role === 'auditor') return { name: 'auditoria' }
  return { name: 'catalogo' }
}

router.beforeEach((to) => {
  const role = currentSessionRole()
  const isAuthenticated = hasSessionToken()

  if (to.meta.requiresAuth && !isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  if (to.meta.roles && role && !to.meta.roles.includes(role)) {
    return { name: 'login' }
  }

  if (to.meta.role && role && role !== to.meta.role) {
    return homeForRole(role)
  }

  if (to.meta.guestOnly && isAuthenticated) {
    return homeForRole(role)
  }

  return true
})

export default router
