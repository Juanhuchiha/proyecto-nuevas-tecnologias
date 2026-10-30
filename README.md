# Mesa Roja

Sistema de pedidos de demostración con Vue 3, Vite, Bootstrap 5 y una API REST en Flask.

## Estructura

- `backend/app.py`: API y datos de prueba en memoria.
- `backend/requirements.txt`: dependencias Python.
- `src/services/api.js`: cliente HTTP del frontend.
- `src/views/`: login, catálogo, carrito, administración y seguimiento de envíos.

## Preparar el backend en Windows PowerShell

Desde la carpeta del proyecto (`mi-proyecto-vue`):

```powershell
py -m venv backend\.venv
.\backend\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
python backend\app.py
```

Si PowerShell bloquea la activación del entorno, ejecuta el servidor directamente sin activarlo:

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\backend\.venv\Scripts\python.exe backend\app.py
```

El servidor queda en `http://127.0.0.1:5000`. En otra terminal, inicia Vue:

```powershell
npm run dev
```

Para cambiar la URL de la API, define `VITE_API_URL` antes de iniciar Vite. Por defecto se usa `http://127.0.0.1:5000`.

## Endpoints

- `GET /productos`: devuelve `{ "productos": [...] }`.
- `POST /usuarios`: recibe `{ "nombre": "...", "correo": "...", "direccion": "..." }`; devuelve `{ "usuario": {...} }`.
- `POST /pedidos`: recibe `{ "usuario_id": 1, "direccion": "...", "productos": [{ "producto_id": 1, "cantidad": 2 }] }`; valida stock, descuenta existencias y devuelve `{ "pedido": {...} }`.
- `GET /pedidos/<id_pedido>`: consulta un pedido por su identificador numérico.
- `GET /reportes/ventas`: devuelve el número de pedidos y el total vendido en COP.

Las solicitudes incorrectas devuelven un mensaje JSON en `error`. CORS permite el origen local de Vite (`localhost:5173` y `127.0.0.1:5173`).

## Frontend

`Catalogo.vue` obtiene los productos de `GET /productos` al cargar. `Carrito.vue` registra primero el usuario y luego crea el pedido con `POST /usuarios` y `POST /pedidos`. Si el servidor no está disponible, se muestra el error y el carrito se conserva para reintentar.

Los datos del backend son simulados en memoria: se reinician al detener el proceso Flask. El login del frontend también es una demostración y no se valida contra esta API; las credenciales frontend no sustituyen autenticación de servidor.

Para probar el login, usa `cliente@example.com`, `admin@example.com` o `repartidor@example.com` con la contraseña `123456`. Son credenciales públicas de demostración y no deben usarse en producción.
