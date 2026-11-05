const apiBaseUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:5000'

async function request(path, options = {}) {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })

  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error(payload?.error || `Error del servidor (${response.status}).`)
  }
  if (!payload) {
    throw new Error('El servidor devolvió una respuesta JSON vacía o inválida.')
  }

  return payload
}

export async function fetchProducts() {
  const payload = await request('/productos')
  if (!Array.isArray(payload.productos)) {
    throw new Error('La respuesta de productos no tiene el formato esperado.')
  }
  return payload.productos
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
