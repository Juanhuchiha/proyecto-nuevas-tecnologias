# Sistema de Gestión de Pedidos en Línea para Restaurante

Aplicación universitaria para consultar un catálogo, crear pedidos y hacer seguimiento a sus estados. El frontend usa Vue 3, Vue Router, Bootstrap 5 y Vite; la API utiliza Python y Flask. La persistencia combina SQLite para datos relacionales y MongoDB para actividades y eventos flexibles.

## Arquitectura de persistencia políglota

- **SQLite** guarda usuarios, catálogo, pedidos, detalles, existencias, ventas y la cola transaccional de eventos. Las tablas y relaciones se crean automáticamente al arrancar Flask. Por defecto, la base se encuentra en `backend/data/mesa_roja.db`.
- **MongoDB** guarda actividades, historial de estados y registros del sistema. Los documentos contienen campos dinámicos en `datos`.
- Cuando se crea un pedido o cambia su estado, SQLite guarda el pedido, el inventario y los eventos pendientes en una misma transacción. Después, la API publica los eventos en MongoDB. Si MongoDB está temporalmente indisponible, los eventos permanecen en la cola SQLite y se pueden reintentar sin duplicar documentos.
- `GET /pedidos/<id>/historial` combina la información del pedido consultada en SQLite con los eventos encontrados en MongoDB.

SQLite conserva las tablas `usuarios`, `productos`, `pedidos`, `detalles_pedido` y `cola_eventos`, definidas en `backend/schema.sql`. Se activan las claves foráneas en cada conexión; las operaciones de escritura usan transacciones y un tiempo de espera para bloqueos. El catálogo de demostración se inserta si no existe; no se sobrescriben las existencias existentes.

Las colecciones MongoDB son:

- `actividades_usuarios`: `usuario_id`, `pedido_id`, `tipo`, `descripcion`, `fecha`, `responsable` y `datos`.
- `historial_pedidos`: pedido, estados anterior y nuevo, usuario responsable, fecha y datos.
- `registros_sistema`: acciones de la aplicación, responsable, descripción, fecha y datos.

Los IDs de pedidos y usuarios de SQLite se guardan como números en los documentos MongoDB. Las actividades tienen su propio ObjectId. PyMongo crea índices para consultar por pedido, usuario y fecha.

## Tecnologías

- Vue.js 3, Vue Router, Bootstrap 5 y Vite.
- Python 3 y Flask, con Flask-CORS.
- SQLite mediante el módulo `sqlite3` incluido en Python.
- MongoDB mediante PyMongo.
- `python-dotenv` para cargar la configuración local.
- `unittest` y el cliente de prueba de Flask.

## Configuración en Windows

### 1. Configurar MongoDB

MongoDB puede ejecutarse localmente o en MongoDB Atlas. Para Atlas, crea un clúster, un usuario de base de datos y autoriza la IP desde la que se conectará Flask en Network Access. Copia la URI de conexión del clúster. La base utilizada por el proyecto se llama `mesa_roja`.

No pegues la URI en el frontend, en el repositorio ni en mensajes públicos. Si la contraseña contiene caracteres reservados de URL, codifícalos correctamente.

Desde PowerShell, en la carpeta `mi-proyecto-vue`, crea la configuración local:

```powershell
Copy-Item .env.example .env
```

Edita `.env` con tu URI privada:

```dotenv
SQLITE_DATABASE_PATH=backend/data/mesa_roja.db
MONGODB_URI=mongodb+srv://USUARIO:CONTRASENA@TU-CLUSTER.mongodb.net/?retryWrites=true&w=majority
MONGODB_DATABASE=mesa_roja
```

Si MongoDB está instalado localmente, puedes usar `mongodb://localhost:27017/`. `SQLITE_DATABASE_PATH` es opcional: si no se define, se usa `backend/data/mesa_roja.db`. La base SQLite y sus tablas se crean al iniciar la API. `.env`, los archivos `.db`, los entornos virtuales y los archivos generados están excluidos de Git.

### 2. Instalar y arrancar Flask

```powershell
py -m venv backend\.venv
.\backend\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
python -m backend.app
```

Si PowerShell bloquea la activación del entorno:

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\backend\.venv\Scripts\python.exe -m backend.app
```

Flask queda disponible en `http://127.0.0.1:5000`. Al arrancar, se crea el archivo SQLite, se inicializan las tablas y el catálogo, se comprueba la conexión MongoDB y se preparan los índices. `GET /salud` permite comprobar ambas conexiones.

### 3. Arrancar Vue

En otra terminal, desde la carpeta `mi-proyecto-vue`:

```powershell
npm ci
npm run dev
```

Por defecto, Vue llama a `http://127.0.0.1:5000`. Para utilizar otra dirección, configura `VITE_API_URL` antes de iniciar Vite y añade el origen del frontend a la variable `CORS_ORIGINS` del backend.

## Endpoints

Las rutas de actividades no están protegidas por autenticación de servidor. El login actual es una demostración local; no expongas la API a Internet ni la utilices con datos reales hasta implementar autenticación y autorización.

| Método | Ruta | Base y uso |
|---|---|---|
| `GET` | `/salud` | Comprueba SQLite, MongoDB y eventos pendientes. |
| `GET` | `/productos` | Consulta catálogo y existencias en SQLite. |
| `POST` | `/usuarios` | Crea o actualiza el cliente por correo en SQLite. |
| `POST` | `/pedidos` | Crea pedido, detalles, actualiza stock y encola eventos en SQLite. |
| `GET` | `/pedidos` | Lista pedidos desde SQLite. |
| `GET` | `/pedidos/<id>` | Consulta pedido, cliente y productos desde SQLite. |
| `PATCH` | `/pedidos/<id>/estado` | Cambia estado en SQLite y encola el evento. |
| `GET` | `/pedidos/<id>/historial` | Combina el pedido de SQLite con historial y actividades de MongoDB. |
| `POST` | `/actividades` | Crea actividad en MongoDB. |
| `GET` | `/actividades` | Lista actividades; admite `usuario_id`, `pedido_id` y `limite` (1-100). |
| `GET` | `/actividades/<id>` | Consulta actividad por ObjectId de MongoDB. |
| `PATCH` | `/actividades/<id>` | Actualiza los campos permitidos en MongoDB. |
| `DELETE` | `/actividades/<id>` | Elimina actividad y registra la acción en MongoDB. |
| `POST` | `/eventos/pendientes/reintentar` | Reintenta publicar eventos pendientes de SQLite. |
| `GET` | `/reportes/ventas` | Genera el reporte de pedidos y ventas en SQLite. |

### Ejemplos

Crear una actividad con referencias existentes:

```http
POST /actividades
Content-Type: application/json
```

```json
{
  "usuario_id": 1,
  "pedido_id": 1,
  "tipo": "nota",
  "descripcion": "El cliente confirmó la dirección.",
  "responsable": "Operador",
  "datos": {
    "canal": "telefono",
    "requiere_confirmacion": false
  }
}
```

Cambiar el estado de un pedido:

```http
PATCH /pedidos/1/estado
Content-Type: application/json
```

```json
{
  "estado": "En camino",
  "usuario": {
    "id": 1,
    "nombre": "Repartidor"
  }
}
```

Consultar la persistencia políglota:

```http
GET /pedidos/1/historial
```

La respuesta contiene `pedido` desde SQLite y `historial`, `actividades` y `registros_sistema` desde MongoDB. Si hay eventos de ese pedido que no se pudieron publicar, el endpoint devuelve `503` en vez de presentar un historial incompleto como definitivo.

Errores de validación devuelven JSON y estado `400`; recursos inexistentes, `404`; conflictos de inventario, `409`; y fallos de base de datos, `503`.

## Datos anteriores y migración

La rama anterior usaba PostgreSQL y guardaba su información en un servidor externo; este entorno no dispone de ese servidor ni de sus credenciales. La rama SQLite no modifica ni elimina ese PostgreSQL. Tampoco copia automáticamente sus datos a SQLite. Si necesitas conservar pedidos reales de una instalación PostgreSQL anterior, exporta y migra los datos explícitamente antes de cambiar de versión; el catálogo de demostración de esta aplicación se mantiene.

## Pruebas y evidencias

Con el entorno virtual activado, ejecuta desde la raíz del proyecto:

```powershell
python -m unittest discover -s backend\tests -t .
npm run build
```

Las pruebas unitarias utilizan SQLite real en una base temporal y adaptadores falsos para MongoDB. Verifican esquema, claves foráneas, datos de prueba, compras transaccionales, descuento de inventario, cola, CRUD de API, historial combinado y validaciones. **No demuestran una conexión real a MongoDB.**

Con MongoDB configurado en `.env`, ejecuta:

```powershell
python -m backend.integration_smoke
```

La prueba usa SQLite temporal y tu MongoDB configurado, verifica las conexiones, el CRUD y los eventos reales, y limpia los datos temporales que crea. Usa una base de pruebas; no ejecutes la prueba de integración contra una base de producción. No se afirma que la integración con MongoDB haya sido probada hasta ejecutar este comando con credenciales válidas.

Los registros verificables se encuentran en [`evidencias/pruebas.md`](./evidencias/pruebas.md), [`evidencias/pruebas_backend.txt`](./evidencias/pruebas_backend.txt) y [`evidencias/pruebas_frontend.txt`](./evidencias/pruebas_frontend.txt). El informe actualizado está en [`evidencias/implementacion-mongodb.pdf`](./evidencias/implementacion-mongodb.pdf).

## PDF

El informe se puede regenerar con las dependencias opcionales:

```powershell
python -m pip install -r backend\requirements-docs.txt
python -m backend.generate_report
```

## Login de demostración

Usa `cliente@example.com`, `admin@example.com` o `repartidor@example.com` con la contraseña `123456`. Son credenciales públicas solo para la demostración del frontend, no autentican las rutas del backend y no deben usarse en producción.
