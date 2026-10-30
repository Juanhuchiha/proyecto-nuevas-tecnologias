import { computed, reactive } from 'vue'

export const categories = [
  'Todos',
  'Hamburguesas',
  'Acompañamientos',
  'Bebidas',
  'Postres',
]

export const products = reactive([
  {
    id: 1,
    name: 'Burger La Konrad',
    category: 'Hamburguesas',
    description: 'Carne, queso, lechuga y tomate.',
    price: 18900,
    stock: 18,
    imagen: 'https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=500',
    icon: '🍔',
    tag: 'Favorita',
    active: true,
  },
  {
    id: 2,
    name: 'Hamburguesa Doble Carne',
    category: 'Hamburguesas',
    description: 'Doble carne, doble queso y salsa de la casa.',
    price: 24500,
    stock: 12,
    imagen: 'https://images.unsplash.com/photo-1586190848861-99aa4a171e90?w=500',
    icon: '🍔',
    tag: '',
    active: true,
  },
  {
    id: 3,
    name: 'Hamburguesa de Pollo',
    category: 'Hamburguesas',
    description: 'Pollo crujiente, lechuga y mayonesa.',
    price: 21900,
    stock: 10,
    imagen: 'https://images.unsplash.com/photo-1606755962773-d324e0a13086?w=500',
    icon: '🍗',
    tag: '',
    active: true,
  },
  {
    id: 4,
    name: 'Papas Agrandadas',
    category: 'Acompañamientos',
    description: 'Porción grande de papas fritas.',
    price: 6500,
    stock: 24,
    imagen: 'https://images.unsplash.com/photo-1573080496219-bb080dd4f877?w=500',
    icon: '🍟',
    tag: '',
    active: true,
  },
  {
    id: 5,
    name: 'Nuggets x6',
    category: 'Acompañamientos',
    description: 'Seis nuggets de pollo con salsa.',
    price: 10500,
    stock: 16,
    imagen: 'https://images.unsplash.com/photo-1562967914-608f82629710?w=500',
    icon: '🍗',
    tag: '',
    active: true,
  },
  {
    id: 6,
    name: 'Gaseosa 400ml',
    category: 'Bebidas',
    description: 'Gaseosa fría de 400 ml.',
    price: 4000,
    stock: 30,
    imagen: 'https://images.unsplash.com/photo-1622483767028-3f66f32aef97?w=500',
    icon: '🥤',
    tag: '',
    active: true,
  },
  {
    id: 7,
    name: 'Agua 600ml',
    category: 'Bebidas',
    description: 'Agua embotellada de 600 ml.',
    price: 3500,
    stock: 22,
    imagen: 'https://images.unsplash.com/photo-1534616042650-80f5c9b61f09?w=500',
    icon: '💧',
    tag: '',
    active: true,
  },
  {
    id: 8,
    name: 'Cono de Helado',
    category: 'Postres',
    description: 'Cono con helado de vainilla.',
    price: 5000,
    stock: 14,
    imagen: 'https://images.unsplash.com/photo-1560008581-09826d1de69e?w=500',
    icon: '🍦',
    tag: '',
    active: true,
  },
])

export const cart = reactive([])
const validRoles = ['cliente', 'admin', 'repartidor']
const storedRole =
  typeof localStorage === 'undefined' ? null : localStorage.getItem('restaurant-role')
export const currentUser = reactive({
  name: '',
  role: validRoles.includes(storedRole) ? storedRole : null,
})
export const deliveries = reactive([
  {
    id: 'PED-1042',
    customer: 'Laura Gómez',
    address: 'Cra. 7 # 72-41, Bogotá',
    items: 'Burger La Konrad x1, Papas Agrandadas x1',
    status: 'Listo para recoger',
  },
  {
    id: 'PED-1043',
    customer: 'Andrés Rojas',
    address: 'Calle 85 # 12-18, Bogotá',
    items: 'Hamburguesa Doble Carne x2',
    status: 'En camino',
  },
])
export const cartCount = computed(() =>
  cart.reduce((total, item) => total + item.quantity, 0),
)

export function setUserRole(role, name) {
  if (!validRoles.includes(role)) {
    throw new Error('El rol seleccionado no es válido.')
  }

  localStorage.setItem('restaurant-role', role)
  currentUser.role = role
  currentUser.name = name
}

export function clearUserRole() {
  localStorage.removeItem('restaurant-role')
  currentUser.role = null
  currentUser.name = ''
}

export function formatPrice(price) {
  return `$ ${price.toLocaleString('es-CO')} COP`
}

export function syncProductsFromApi(apiProducts) {
  const syncedProducts = apiProducts.map((apiProduct) => {
    const existingProduct = products.find((product) => product.id === apiProduct.id)

    return {
      ...existingProduct,
      id: apiProduct.id,
      name: apiProduct.nombre,
      category: apiProduct.categoria,
      description: apiProduct.descripcion || existingProduct?.description || '',
      price: apiProduct.precio,
      stock: apiProduct.stock,
      imagen: apiProduct.imagen || existingProduct?.imagen || '',
      icon: existingProduct?.icon || '🍽️',
      tag: existingProduct?.tag || '',
      active: apiProduct.activo !== false,
    }
  })

  products.splice(0, products.length, ...syncedProducts)
}

export function clearCart() {
  cart.splice(0, cart.length)
}

export function registerDeliveryFromOrder(order) {
  const deliveryId = `PED-${order.id}`
  const existingDelivery = deliveries.find((delivery) => delivery.id === deliveryId)
  const delivery = {
    id: deliveryId,
    customer: order.cliente.nombre,
    address: order.direccion,
    items: order.productos
      .map((item) => `${item.nombre} x${item.cantidad}`)
      .join(', '),
    status: order.estado,
  }

  if (existingDelivery) Object.assign(existingDelivery, delivery)
  else deliveries.unshift(delivery)
}

export function updateDeliveryStatus(deliveryId, status) {
  const delivery = deliveries.find((entry) => entry.id === deliveryId)
  if (!delivery) {
    throw new Error('No se encontró el pedido de entrega.')
  }
  if (!['Listo para recoger', 'En camino', 'Entregado'].includes(status)) {
    throw new Error('El estado de entrega no es válido.')
  }

  delivery.status = status
}

export function addToCart(product) {
  if (!product.active) return false

  const item = cart.find((entry) => entry.id === product.id)
  const quantityInCart = item?.quantity ?? 0

  if (quantityInCart >= product.stock) return false

  if (item) item.quantity += 1
  else cart.push({ id: product.id, quantity: 1 })

  return true
}

export function changeCartQuantity(productId, change) {
  const item = cart.find((entry) => entry.id === productId)
  const product = products.find((entry) => entry.id === productId)

  if (!item || !product) return

  const nextQuantity = item.quantity + change
  if (nextQuantity <= 0) {
    removeFromCart(productId)
  } else if (nextQuantity <= product.stock) {
    item.quantity = nextQuantity
  }
}

export function removeFromCart(productId) {
  const itemIndex = cart.findIndex((entry) => entry.id === productId)
  if (itemIndex !== -1) cart.splice(itemIndex, 1)
}

export function placeOrder(customer) {
  if (cart.length === 0) {
    throw new Error('Agrega al menos un producto antes de confirmar el pedido.')
  }

  for (const item of cart) {
    const product = products.find((entry) => entry.id === item.id)
    if (!product || !product.active || item.quantity > product.stock) {
      throw new Error('El inventario cambió. Revisa los productos y cantidades de tu carrito.')
    }
  }

  for (const item of cart) {
    const product = products.find((entry) => entry.id === item.id)
    product.stock -= item.quantity
  }

  const orderId = `PED-${1044 + deliveries.length - 2}`
  deliveries.unshift({
    id: orderId,
    customer: customer.name,
    address: `${customer.address}, ${customer.city}`,
    items: cart
      .map((item) => `${productForCartItem(item).name} x${item.quantity}`)
      .join(', '),
    status: 'Listo para recoger',
  })
  cart.splice(0, cart.length)
}

export function productForCartItem(item) {
  return products.find((product) => product.id === item.id)
}
