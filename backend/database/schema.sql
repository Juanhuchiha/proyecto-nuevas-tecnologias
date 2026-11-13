CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    correo TEXT NOT NULL UNIQUE,
    direccion TEXT NOT NULL DEFAULT '',
    rol TEXT NOT NULL DEFAULT 'cliente'
        CHECK (rol IN ('cliente', 'admin', 'repartidor', 'auditor')),
    password_hash TEXT,
    token_version INTEGER NOT NULL DEFAULT 0 CHECK (token_version >= 0)
);

CREATE TABLE IF NOT EXISTS productos (
    id INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL,
    precio INTEGER NOT NULL CHECK (precio >= 0),
    stock INTEGER NOT NULL CHECK (stock >= 0),
    categoria TEXT NOT NULL,
    descripcion TEXT NOT NULL DEFAULT '',
    imagen TEXT NOT NULL DEFAULT '',
    activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
);

CREATE TABLE IF NOT EXISTS pedidos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    direccion TEXT NOT NULL,
    subtotal INTEGER NOT NULL CHECK (subtotal >= 0),
    envio INTEGER NOT NULL CHECK (envio >= 0),
    total INTEGER NOT NULL CHECK (total >= 0),
    moneda TEXT NOT NULL DEFAULT 'COP',
    estado TEXT NOT NULL,
    creado_en TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS detalles_pedido (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id INTEGER NOT NULL REFERENCES pedidos(id) ON DELETE CASCADE,
    producto_id INTEGER NOT NULL REFERENCES productos(id),
    nombre TEXT NOT NULL,
    cantidad INTEGER NOT NULL CHECK (cantidad > 0),
    precio_unitario INTEGER NOT NULL CHECK (precio_unitario >= 0),
    total INTEGER NOT NULL CHECK (total >= 0),
    stock_restante INTEGER NOT NULL CHECK (stock_restante >= 0)
);

CREATE TABLE IF NOT EXISTS cola_eventos (
    id TEXT PRIMARY KEY,
    coleccion TEXT NOT NULL
        CHECK (coleccion IN ('historial_pedidos', 'registros_sistema')),
    documento TEXT NOT NULL CHECK (json_valid(documento)),
    intentos INTEGER NOT NULL DEFAULT 0 CHECK (intentos >= 0),
    error TEXT,
    fecha_creacion TEXT NOT NULL,
    publicado_en TEXT
);

CREATE INDEX IF NOT EXISTS idx_pedidos_usuario ON pedidos(usuario_id);
CREATE INDEX IF NOT EXISTS idx_detalles_pedido_pedido ON detalles_pedido(pedido_id);
CREATE INDEX IF NOT EXISTS idx_detalles_pedido_producto ON detalles_pedido(producto_id);
CREATE INDEX IF NOT EXISTS idx_pedidos_fecha ON pedidos(creado_en);
CREATE INDEX IF NOT EXISTS idx_cola_eventos_pendientes
    ON cola_eventos(fecha_creacion) WHERE publicado_en IS NULL;
