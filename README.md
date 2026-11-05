# Sistema de Gestión de Pedidos en Línea para Restaurante

Este proyecto consiste en una aplicación web para administrar los pedidos de un restaurante. Permite consultar los productos disponibles, crear pedidos y revisar cómo va su estado. También cuenta con una parte de administración para manejar la información del restaurante.

El frontend está hecho con Vue 3, Vue Router, Bootstrap 5 y Vite. Para el backend se utiliza Python con Flask. Además, el proyecto trabaja con dos bases de datos: SQLite y MongoDB.

## ¿Cómo se utilizan las bases de datos?

Para esta entrega se decidió utilizar las dos bases de datos porque no toda la información del restaurante necesita guardarse de la misma manera.

- **SQLite:** se utiliza para guardar la información principal, como usuarios, productos, pedidos, detalles de los pedidos, existencias y ventas. Estos datos tienen una estructura definida y necesitan mantener sus relaciones.
- **MongoDB:** se utiliza para guardar actividades de los usuarios, cambios que se hacen en los pedidos y registros del sistema. Esta información puede tener datos diferentes dependiendo de lo que haya ocurrido.

En MongoDB se utiliza un campo llamado `datos`, donde se pueden guardar características adicionales sin tener que modificar las tablas de SQLite cada vez que se necesite agregar información.

Cuando se crea un pedido o se cambia su estado, primero se guarda la información en SQLite. Después, los eventos relacionados se envían a MongoDB. Si MongoDB no está disponible en ese momento, los eventos quedan guardados en una cola de SQLite para intentar enviarlos nuevamente.

También se implementó una ruta que permite consultar la información de un pedido junto con su historial. Para hacerlo, Flask consulta las dos bases de datos y reúne los resultados.

SQLite utiliza las siguientes tablas:

- `usuarios`
- `productos`
- `pedidos`
- `detalles_pedido`
- `cola_eventos`

Estas tablas están definidas en `backend/database/schema.sql` y se crean automáticamente cuando se inicia el backend.

En MongoDB se utilizan tres colecciones:

- `actividades_usuarios`: guarda las actividades realizadas, su descripción, fecha, usuario relacionado y otros datos.
- `historial_pedidos`: guarda la creación de los pedidos y los cambios que se realizan en sus estados.
- `registros_sistema`: guarda acciones que se realizan dentro de la aplicación.

Los documentos de MongoDB pueden tener información relacionada con los usuarios y pedidos de SQLite mediante sus identificadores. También se utilizan índices para facilitar las consultas por pedido, usuario y fecha.

## Tecnologías utilizadas

- Vue.js 3
- Vue Router
- Bootstrap 5
- Vite
- Python 3
- Flask
- Flask-CORS
- SQLite
- MongoDB
- PyMongo
- python-dotenv
- unittest

## Organización del proyecto

El proyecto está dividido en dos partes principales:

- `frontend/`: contiene la aplicación desarrollada en Vue. Aquí están las páginas, componentes, estilos, rutas y servicios que se comunican con el backend.
- `backend/`: contiene la API desarrollada con Flask y todo lo relacionado con las bases de datos.

Dentro del backend se encuentran algunos archivos importantes:

- `backend/app.py`: inicia la aplicación Flask.
- `backend/routes/`: contiene las rutas de la API.
- `backend/services/`: contiene la parte encargada de manejar los eventos.
- `backend/database/`: contiene la conexión con las bases de datos y el archivo con las tablas de SQLite.
- `backend/tests/`: contiene las pruebas del proyecto.
- `backend/config.py`: carga la configuración de la aplicación.

También se encuentra la carpeta `evidencias/`, donde se guardan los resultados de las pruebas y otros documentos relacionados con la entrega.

## Cómo configurar el proyecto en Windows

### 1. Configurar MongoDB

Para utilizar MongoDB se puede trabajar con una instalación local o con MongoDB Atlas. En este proyecto se utiliza Atlas.

Primero se debe tener creado el clúster, un usuario de base de datos y permitir la dirección IP desde la que se va a conectar la aplicación. Esto se configura desde las opciones de Network Access de MongoDB Atlas.

Después, desde la carpeta principal del proyecto, se crea el archivo `.env` usando el ejemplo que viene incluido:

```powershell
Copy-Item .env.example .env
```

Abre el archivo `.env` y coloca la información de conexión:

```dotenv
SQLITE_DATABASE_PATH=backend/data/mesa_roja.db
VITE_API_URL=http://127.0.0.1:5000
MONGODB_URI=mongodb+srv://<usuario>:<contraseña>@<cluster>.mongodb.net/?retryWrites=true&w=majority
MONGODB_DATABASE=mesa_roja
```

Se deben reemplazar los datos de ejemplo por los de la propia cuenta de MongoDB Atlas.

**Importante:** el archivo `.env` contiene información privada. No se debe subir a GitHub ni compartir la contraseña de MongoDB. Si la contraseña tiene caracteres especiales, puede ser necesario codificarlos para utilizarlos en la URI.

La base de datos de SQLite se crea automáticamente al iniciar Flask. No es necesario crear manualmente sus tablas.

### 2. Instalar y ejecutar el backend

Abre una terminal en la carpeta principal del proyecto y ejecuta:

```powershell
py -m venv backend\.venv
.\backend\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
python -m backend.app
```

Si Windows no permite activar el entorno virtual, también se pueden ejecutar los comandos directamente desde Python:

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\backend\.venv\Scripts\python.exe -m backend.app
```

Cuando Flask esté funcionando, la API estará disponible en:

`http://127.0.0.1:5000`

Para comprobar el estado de las bases de datos se puede consultar:

`http://127.0.0.1:5000/salud`

Esta ruta permite revisar el estado de SQLite y MongoDB.

### 3. Ejecutar el frontend

Abre otra terminal en la carpeta principal del proyecto y ejecuta:

```powershell
npm --prefix frontend ci
npm --prefix frontend run dev
```

Vite mostrará la dirección local donde se puede abrir la aplicación desde el navegador.

Por defecto, el frontend se comunica con el backend en `http://127.0.0.1:5000`.

## Rutas de la API

Estas son las principales rutas que tiene el proyecto:

| Método | Ruta | Función |
|---|---|---|
| GET | `/salud` | Comprueba el estado de las bases de datos. |
| GET | `/productos` | Consulta los productos disponibles. |
| POST | `/usuarios` | Crea o actualiza un usuario. |
| POST | `/pedidos` | Registra un pedido y actualiza las existencias. |
| GET | `/pedidos` | Consulta los pedidos registrados. |
| GET | `/pedidos/<id>` | Consulta un pedido específico. |
| PATCH | `/pedidos/<id>/estado` | Cambia el estado de un pedido. |
| GET | `/pedidos/<id>/historial` | Consulta el pedido y su información relacionada en ambas bases de datos. |
| POST | `/actividades` | Registra una actividad en MongoDB. |
| GET | `/actividades` | Consulta las actividades guardadas. |
| GET | `/actividades/<id>` | Consulta una actividad específica. |
| PATCH | `/actividades/<id>` | Actualiza una actividad. |
| DELETE | `/actividades/<id>` | Elimina una actividad. |
| POST | `/eventos/pendientes/reintentar` | Intenta enviar nuevamente los eventos pendientes. |
| GET | `/reportes/ventas` | Consulta el reporte de ventas. |

### Ejemplo de uso de MongoDB

Para registrar una actividad se puede utilizar la ruta:

`POST /actividades`

Con un cuerpo JSON como este:

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

También se puede cambiar el estado de un pedido utilizando:

`PATCH /pedidos/1/estado`

```json
{
  "estado": "En camino",
  "usuario": {
    "id": 1,
    "nombre": "Repartidor"
  }
}
```

Una de las rutas más importantes de esta entrega es:

`GET /pedidos/1/historial`

Esta consulta devuelve la información del pedido desde SQLite y su historial, actividades y registros relacionados desde MongoDB.

### Colección de Postman

El proyecto incluye una colección de Postman en:

`postman/mesa-roja.postman_collection.json`

Se puede importar desde Postman usando la opción **Import > File**.

Para probar el funcionamiento, primero se debe crear un usuario de prueba y después un pedido. La colección permite continuar con las demás solicitudes utilizando los identificadores que se guardan en las respuestas.

Las operaciones de actividades y el historial necesitan que MongoDB esté conectado.

## Datos anteriores del proyecto

En una versión anterior se había trabajado con PostgreSQL. Para esta versión se cambió la parte relacional a SQLite, manteniendo MongoDB para la información dinámica.

Este cambio no elimina automáticamente los datos que pudieran existir en una instalación anterior de PostgreSQL. Si se necesitan conservar, se deben exportar y migrar por separado.

## Pruebas del proyecto

Para ejecutar las pruebas del backend se utiliza:

```powershell
python -m unittest discover -s backend\tests -t .
```

Para comprobar que el frontend se puede compilar:

```powershell
npm --prefix frontend run build
```

Las pruebas unitarias revisan el funcionamiento de SQLite, la creación de pedidos, el manejo de existencias, las actividades y las consultas que utilizan las dos bases de datos. En estas pruebas MongoDB se reemplaza por una versión simulada, por lo que no sirven por sí solas para demostrar una conexión real con Atlas.

Para probar la conexión real con MongoDB se utiliza:

```powershell
python -m backend.integration_smoke
```

Este comando realiza pruebas de conexión, lectura y escritura utilizando la configuración de MongoDB que se encuentra en `.env`. Se recomienda ejecutarlo con una base de pruebas y no con información real del restaurante.

Los resultados y archivos relacionados con las pruebas se encuentran en la carpeta `evidencias/`.

## Informe en PDF

El proyecto también incluye un documento PDF con la explicación de la implementación de MongoDB y la forma en que se utilizan las dos bases de datos.

Si se necesita generar nuevamente, se pueden instalar las dependencias adicionales y ejecutar:

```powershell
python -m pip install -r backend\requirements-docs.txt
python -m backend.generate_report
```

## Usuarios de demostración

Para probar el inicio de sesión del frontend se encuentran estos usuarios de ejemplo:

- `cliente@example.com`
- `admin@example.com`
- `repartidor@example.com`

La contraseña para los tres es `123456`.
