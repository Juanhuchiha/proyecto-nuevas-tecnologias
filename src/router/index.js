import { createRouter, createWebHistory } from 'vue-router'
import Login from '../views/Login.vue'
import Catalogo from '../views/Catalogo.vue'
import Carrito from '../views/Carrito.vue'
import Admin from '../views/Admin.vue'
import Envios from '../views/Envios.vue'
import { currentUser } from '../data/restaurant'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'login', component: Login, meta: { guestOnly: true } },
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
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

function homeForRole(role) {
  if (role === 'admin') return { name: 'admin' }
  if (role === 'repartidor') return { name: 'envios' }
  return { name: 'catalogo' }
}

router.beforeEach((to) => {
  const role = currentUser.role

  if (to.meta.requiresAuth && !role) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  if (to.meta.roles && !to.meta.roles.includes(role)) {
    return { name: 'login' }
  }

  if (to.meta.role && role !== to.meta.role) {
    return homeForRole(role)
  }

  if (to.meta.guestOnly && role) {
    return homeForRole(role)
  }

  return true
})

export default router
