const apiBaseUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:5000'

function getAuthToken() {
  const token = typeof localStorage === 'undefined' ? '' : localStorage.getItem('restaurant-token') || ''
  return token
}

async function request(path, options = {}) {
  const token = getAuthToken()
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  })

  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    const error = new Error(payload?.error || `Error del servidor (${response.status}).`)
    error.status = response.status
    throw error
  }
  if (!payload) {
    throw new Error('El servidor devolvió una respuesta JSON vacía o inválida.')
  }

  return payload
}

export async function loginUser(credentials) {
  const payload = await request('/auth/login', {
    method: 'POST',
    body: JSON.stringify(credentials),
  })
  if (!payload.token || !payload.usuario) {
    throw new Error('El servidor no devolvió un token válido.')
  }
  return payload
}

export async function registerUser(user) {
  const payload = await request('/auth/registro', {
    method: 'POST',
    body: JSON.stringify(user),
  })
  if (!payload.usuario?.id) {
    throw new Error('El servidor no devolvió el usuario creado.')
  }
  return payload
}

export async function logoutUser() {
  return request('/auth/logout', { method: 'POST' })
}

export async function fetchProducts() {
  const payload = await request('/productos')
  if (!Array.isArray(payload.productos)) {
    throw new Error('La respuesta de productos no tiene el formato esperado.')
  }
  return payload.productos
}

export async function createProduct(product) {
  const payload = await request('/productos', {
    method: 'POST',
    body: JSON.stringify(product),
  })
  if (!payload.producto?.id) {
    throw new Error('El servidor no devolvió el producto creado.')
  }
  return payload.producto
}

export async function updateProduct(productId, updates) {
  const payload = await request(`/productos/${productId}`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  })
  if (!payload.producto?.id) {
    throw new Error('El servidor no devolvió el producto actualizado.')
  }
  return payload.producto
}

export async function deleteProduct(productId) {
  return request(`/productos/${productId}`, { method: 'DELETE' })
}

export async function createUser(user) {
  const payload = await request('/usuarios', {
    method: 'POST',
    body: JSON.stringify(user),
  })
  if (!payload.usuario?.id) {
    throw new Error('El servidor no devolvió el usuario creado.')
  }
  return payload.usuario
}

export async function createOrder(order) {
  const payload = await request('/pedidos', {
    method: 'POST',
    body: JSON.stringify(order),
  })
  if (!payload.pedido?.id) {
    throw new Error('El servidor no devolvió el pedido creado.')
  }
  if (payload.advertencia) {
    payload.pedido.eventWarning = payload.advertencia
  }
  return payload.pedido
}

export async function fetchOrders() {
  const payload = await request('/pedidos')
  if (!Array.isArray(payload.pedidos)) {
    throw new Error('La respuesta de pedidos no tiene el formato esperado.')
  }
  return payload.pedidos
}

export async function updateOrderStatus(orderId, status, actorName) {
  const payload = await request(`/pedidos/${orderId}/estado`, {
    method: 'PATCH',
    body: JSON.stringify({
      estado: status,
      ...(actorName?.trim() ? { usuario: { nombre: actorName.trim() } } : {}),
    }),
  })
  if (!payload.pedido?.id) {
    throw new Error('El servidor no devolvió el pedido actualizado.')
  }
  return {
    ...payload.pedido,
    eventWarning: payload.advertencia || '',
  }
}

export async function fetchOrderHistory(orderId) {
  const payload = await request(`/pedidos/${orderId}/historial`)
  if (!payload.pedido || !Array.isArray(payload.historial)) {
    throw new Error('La respuesta del historial no tiene el formato esperado.')
  }
  return payload
}

export async function fetchSalesReport(filters = {}) {
  const search = new URLSearchParams()
  if (filters.desde) search.set('desde', filters.desde)
  if (filters.hasta) search.set('hasta', filters.hasta)
  const query = search.size ? `?${search.toString()}` : ''
  const payload = await request(`/reportes/ventas${query}`)
  if (
    !Number.isInteger(payload.cantidad_pedidos) ||
    !Number.isInteger(payload.total_ventas)
  ) {
    throw new Error('El reporte de ventas no tiene el formato esperado.')
  }
  return payload
}

export async function fetchInventoryReport() {
  const payload = await request('/reportes/inventario')
  if (
    !Array.isArray(payload.productos) ||
    !Number.isInteger(payload.cantidad_productos) ||
    !Number.isInteger(payload.unidades_disponibles)
  ) {
    throw new Error('El reporte de inventario no tiene el formato esperado.')
  }
  return payload
}
