# Sistema de Gestión de Pedidos en Línea para Restaurante

Aplicación universitaria para consultar un catálogo, crear pedidos y hacer seguimiento de sus estados. El frontend usa Vue 3 y Vite; la API está construida con Flask. La persistencia combina PostgreSQL para los datos relacionales y MongoDB para los eventos y las actividades.

## Arquitectura de persistencia políglota

La copia de partida de este repositorio tenía una API Flask con listas en memoria: no incluía conexión ni esquema de PostgreSQL. Esta entrega conserva sus endpoints y flujo de pedidos, migra sus datos estructurados a PostgreSQL y añade MongoDB para los registros dinámicos.

- **PostgreSQL** guarda usuarios, catálogo, pedidos, detalles, existencias y una cola transaccional de eventos pendientes. Las relaciones, las restricciones y la transacción de compra protegen la integridad del inventario y los pedidos.
- **MongoDB** guarda actividades de usuarios, historial de estados y registros del sistema. Los documentos aceptan un campo `datos` dinámico para información adicional.
- Los eventos del pedido se insertan primero en `cola_eventos` dentro de la misma transacción PostgreSQL que crea el pedido o modifica su estado. Después se publican en MongoDB con un identificador idempotente. Si MongoDB no responde, el pedido SQL permanece confirmado y el evento queda pendiente para reintentarse; no se presenta el pedido como perdido ni se duplica al reintentar.
- `GET /pedidos/<id>/historial` reúne los datos del pedido de PostgreSQL con los eventos de MongoDB en una respuesta JSON.

### Esquema relacional

`backend/schema.sql` crea estas tablas:

- `usuarios`: nombre, correo único y dirección.
- `productos`: catálogo y existencias.
- `pedidos`: cliente, fecha, dirección, total y estado actual.
- `detalles_pedido`: productos, cantidades, precios y existencias posteriores a la compra.
- `cola_eventos`: eventos JSON pendientes de publicar en MongoDB, con intentos y error más reciente.

El backend crea el esquema al iniciar y añade los ocho productos de demostración únicamente si aún no existen. Las compras bloquean las filas de producto durante la comprobación y el descuento del stock.

### Colecciones MongoDB

- `actividades_usuarios`: `usuario_id`, `pedido_id`, `tipo`, `descripcion`, `fecha`, `responsable` y `datos`.
- `historial_pedidos`: `pedido_id`, `estado_anterior`, `estado_nuevo`, `usuario`, `tipo`, `fecha` y `datos`.
- `registros_sistema`: `pedido_id` cuando aplica, tipo de acción, usuario responsable, descripción, fecha y datos de la operación.

MongoDB mantiene índices por pedido y fecha para consultar con rapidez las actividades e historial. Los IDs SQL se guardan como números en `pedido_id` y `usuario_id`; el campo `id` de una actividad es el ObjectId de MongoDB convertido a texto.

## Tecnologías

- Vue 3, Vue Router, Bootstrap 5 y Vite.
- Flask y Flask-CORS.
- PostgreSQL con Psycopg 3.
- MongoDB con PyMongo.
- `python-dotenv` para cargar la configuración local desde `.env`.
- `unittest` y el cliente de pruebas de Flask para las pruebas automatizadas.

## Preparación en Windows

### 1. Crear las bases de datos

Puedes usar PostgreSQL instalado localmente o un servicio administrado. Crea una base `mesa_roja` y un usuario con permisos sobre ella. MongoDB puede ser local o un clúster de MongoDB Atlas; en Atlas crea una base y un usuario de base de datos y autoriza en Network Access la IP desde la que se conecta Flask.

La aplicación **no** puede conectarse hasta tener ambos servicios disponibles y sus variables configuradas. No publiques contraseñas, tokens ni el archivo `.env`.

Para una instalación local de PostgreSQL, entra a `psql` como administrador y crea una base y un usuario propios para la aplicación (reemplaza el marcador por una contraseña tuya):

```sql
CREATE USER mesa_app WITH PASSWORD 'REEMPLAZA_ESTA_CONTRASENA';
CREATE DATABASE mesa_roja OWNER mesa_app;
```

En MongoDB Atlas, crea un clúster, un usuario de base de datos y una regla de Network Access para tu IP. Copia la URI de conexión del clúster; la base `mesa_roja` se especifica con `MONGODB_DATABASE`.

### 2. Configurar variables de entorno

Desde la carpeta del proyecto:

```powershell
Copy-Item .env.example .env
```

Edita `.env` con tus valores privados:

```dotenv
DATABASE_URL=postgresql://USUARIO:CONTRASENA@localhost:5432/mesa_roja
MONGODB_URI=mongodb+srv://USUARIO:CONTRASENA@cluster.example.mongodb.net/?retryWrites=true&w=majority
MONGODB_DATABASE=mesa_roja
```

La dirección de MongoDB es solo un ejemplo de formato: reemplázala por la URI que proporciona Atlas o por tu URI local. Si la contraseña contiene caracteres reservados de URL, codifícalos antes de incorporarla. `.env` está excluido de Git; `.env.example` no contiene credenciales reales.

### 3. Instalar y ejecutar el backend

```powershell
py -m venv backend\.venv
.\backend\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
python -m backend.app
```

Al arrancar, Flask comprueba las conexiones, crea el esquema relacional, inserta el catálogo de demostración si hace falta y crea los índices de MongoDB. La API local queda en `http://127.0.0.1:5000`. `GET /salud` muestra el estado de ambas bases de datos.

Si PowerShell bloquea la activación del entorno:

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\backend\.venv\Scripts\python.exe -m backend.app
```

### 4. Ejecutar el frontend

En otra terminal, desde la carpeta del proyecto:

```powershell
npm ci
npm run dev
```

Por defecto, Vue usa la API local `http://127.0.0.1:5000`. Para apuntar a otra API, define `VITE_API_URL` antes de iniciar Vite y configura `CORS_ORIGINS` en el backend para el origen del frontend.

## API HTTP

Las rutas de consulta y escritura de actividades no están protegidas por autenticación de servidor: el login actual es una demostración local. No expongas esta API a Internet ni la uses con datos reales hasta implementar autenticación y autorización.

| Método | Ruta | Uso |
|---|---|---|
| `GET` | `/salud` | Comprueba PostgreSQL, MongoDB y eventos pendientes. |
| `GET` | `/productos` | Consulta el catálogo y el stock desde PostgreSQL. |
| `POST` | `/usuarios` | Crea o actualiza el cliente por correo. |
| `POST` | `/pedidos` | Valida stock y crea pedido, detalle y eventos transaccionalmente. |
| `GET` | `/pedidos` | Lista pedidos de PostgreSQL. |
| `GET` | `/pedidos/<id>` | Consulta pedido, cliente y productos. |
| `PATCH` | `/pedidos/<id>/estado` | Cambia a `Listo para recoger`, `En camino` o `Entregado`; registra el evento. |
| `GET` | `/pedidos/<id>/historial` | Combina el pedido de PostgreSQL con historial, actividades y registros MongoDB. |
| `POST` | `/actividades` | Registra una actividad en MongoDB. |
| `GET` | `/actividades` | Lista actividades; admite `usuario_id`, `pedido_id` y `limite` (1–100). |
| `GET` | `/actividades/<id>` | Consulta una actividad por ObjectId. |
| `PATCH` | `/actividades/<id>` | Actualiza los campos permitidos de una actividad. |
| `DELETE` | `/actividades/<id>` | Elimina una actividad y genera un registro del sistema. |
| `POST` | `/eventos/pendientes/reintentar` | Reintenta publicar en MongoDB eventos pendientes de PostgreSQL. |
| `GET` | `/reportes/ventas` | Consulta cantidad de pedidos y ventas desde PostgreSQL. |

### Ejemplos

Crear una actividad (el usuario y el pedido, si se incluyen, deben existir en PostgreSQL):

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

El servidor responde `201` con `{ "actividad": { "id": "<ObjectId>", ... } }`. Al crear, modificar o eliminar actividades también se añade una entrada a `registros_sistema`.

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

La respuesta contiene `pedido` (PostgreSQL), `historial`, `actividades` y `registros_sistema` (MongoDB). Si quedan eventos de ese pedido pendientes en la cola SQL, el endpoint devuelve `503` en vez de presentar un historial incompleto como si estuviera actualizado.

Los errores de validación devuelven JSON con `error` y estado `400`; los recursos inexistentes, `404`; los conflictos de inventario, `409`; y los fallos de base de datos, `503`.

## Pruebas y evidencias

### Pruebas locales sin bases externas

Con el entorno virtual activado:

```powershell
python -m unittest discover -s backend\tests -t .
npm run build
```

Las pruebas unitarias usan adaptadores falsos de almacenamiento: verifican validaciones, rutas existentes, CRUD, la respuesta combinada y el reintento idempotente del outbox, pero **no** demuestran una conexión real a PostgreSQL o MongoDB.

### Prueba de integración con ambas bases reales

Después de configurar `.env` y arrancar ambos servicios:

```powershell
python -m backend.integration_smoke
```

Esta prueba usa PostgreSQL y MongoDB configurados, crea datos temporales, comprueba los endpoints, valida el historial y limpia pedido, stock, usuario y documentos generados. No la ejecutes contra una base con datos de producción.

Las pruebas ejecutadas en esta entrega se registran en [`evidencias/pruebas.md`](./evidencias/pruebas.md). En el entorno de desarrollo usado para esta implementación no había URI configuradas y los puertos locales `5432` y `27017` no estaban disponibles; por eso la prueba con bases reales queda pendiente y no se reporta como exitosa.

## PDF de la entrega

El informe específico de la implementación está en [`evidencias/implementacion-mongodb.pdf`](./evidencias/implementacion-mongodb.pdf). Se puede regenerar instalando sus dependencias opcionales:

```powershell
python -m pip install -r backend\requirements-docs.txt
python -m backend.generate_report
```

## Login de demostración

Usa `cliente@example.com`, `admin@example.com` o `repartidor@example.com` con la contraseña `123456`. Estas credenciales son públicas, se validan solo en el frontend y no constituyen autenticación real del backend.
