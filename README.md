Sistema de Gestión de Pedidos en Línea para Restaurante -- Mesa Roja
Usuarios para ingresar al sistema Estas son las cuentas de prueba para
entrar a los diferentes módulos. Las cuatro utilizan la misma
contraseña: 123456.
  Rol                     Correo                                  Contraseña
  Administrador           jcamilogrimaldoperez@admin.com        123456

  Cliente                 jcamilogrimaldoperez@cliente.com      123456

  Repartidor              jcamilogrimaldoperez@repartidor.com   123456
Auditor                 jcamilogrimaldoperez@auditor.com      123456
Importante: las cuentas se deben crear primero con el comando explicado
en la sección Preparar las cuentas de demostración. En otro computador
también hay que ejecutar ese paso. Son cuentas para pruebas académicas,
no para un entorno real. 1. ¿De qué trata el proyecto? Mesa Roja es una
aplicación web para gestionar los pedidos de un restaurante. Los
clientes pueden consultar los productos disponibles, realizar pedidos y
revisar su estado. También cuenta con opciones para administrar
productos, inventario, entregas y reportes.

El proyecto tiene dos partes: una página desarrollada con Vue y una API
desarrollada con Flask. Para guardar la información se utilizan SQLite y
MongoDB, cada una para manejar datos diferentes. 2. Tecnologías
utilizadas - Frontend: Vue 3, Vue Router, Bootstrap 5 y Vite. - Backend:
Python 3 y Flask. - Bases de datos: SQLite y MongoDB Atlas. - Conexión
con MongoDB: PyMongo. - Autenticación: JWT. - Protección de contraseñas:
Werkzeug. - Pruebas de rutas: Postman. 3. ¿Qué información guarda cada
base de datos? SQLite guarda la información principal del restaurante:
usuarios, roles, productos, existencias, pedidos y detalles de cada
pedido. Estos datos se organizan en tablas.

MongoDB guarda información relacionada con las actividades del sistema,
como el historial de pedidos, las actividades de los usuarios y los
registros del sistema. Utiliza las siguientes colecciones: -
actividades_usuarios - historial_pedidos - registros_sistema Cuando se
crea un pedido o se cambia su estado, la operación principal se guarda
en SQLite y también se registra un evento para enviarlo a MongoDB. Si
MongoDB no está disponible, el evento queda pendiente para intentar
enviarlo nuevamente.

La ruta GET /pedidos/`<id>`{=html}/historial permite consultar
información del pedido junto con su historial. 4. Requisitos para
ejecutar el proyecto Para ejecutar el proyecto en Windows se necesita: -
Python 3.10 o superior, con pip. - Node.js LTS, que incluye npm. - Una
cuenta de MongoDB Atlas con un clúster, un usuario de base de datos y la
dirección IP del computador autorizada en Network Access. - Conexión a
internet para instalar las dependencias y conectarse a MongoDB Atlas. -
Git, solamente si se va a descargar el proyecto directamente desde
GitHub. Si se recibe el proyecto en un archivo ZIP, no hace falta
instalar Git. SQLite se crea en el propio computador. MongoDB funciona
mediante Atlas, por lo que se necesita configurar una conexión válida
para poder utilizar las funciones que guardan o consultan historiales y
actividades. 5. Descargar y preparar el proyecto El proyecto se puede
obtener de estas dos formas: 1. Descargar el archivo ZIP y extraerlo por
completo. 2. Clonar el repositorio de GitHub:
https://github.com/Juanhuchiha/proyecto-nuevas-tecnologias Después de
extraerlo, abre la carpeta mi-proyecto-vue. Esta es la carpeta principal
del proyecto, donde se encuentran las carpetas backend y frontend,
además del archivo .env.example.

Abre PowerShell desde esa carpeta. Los comandos de esta guía se deben
ejecutar desde la carpeta principal, no desde la carpeta externa que
contiene el ZIP. Crear el entorno virtual e instalar las dependencias de
Python py -m venv backend.venv
.`\backend`{=tex}.venv`\Scripts`{=tex}`\Activate`{=tex}.ps1 python -m
pip install -r backend`\requirements`{=tex}.txt Si PowerShell no permite
activar el entorno virtual, puedes ejecutar primero este comando en la
misma ventana: Set-ExecutionPolicy -Scope Process -ExecutionPolicy
Bypass Después vuelve a ejecutar el comando de activación. 6. Configurar
las bases de datos Desde la carpeta principal, crea el archivo .env
usando el archivo de ejemplo: Copy-Item .env.example .env Abre .env y
completa los datos de configuración. El contenido debe tener esta
estructura: SQLITE_DATABASE_PATH=backend/data/mesa_roja.db
VITE_API_URL=http://127.0.0.1:5000 JWT_SECRET_KEY=
JWT_ACCESS_TOKEN_EXPIRES_HOURS=8 MONGODB_URI= MONGODB_DATABASE=mesa_roja
En MONGODB_URI debes colocar la dirección de conexión de tu propio
clúster de MongoDB Atlas. También debes crear un usuario de base de
datos y autorizar la IP del computador desde Network Access en Atlas.

La clave JWT_SECRET_KEY debe ser privada y tener al menos 32 caracteres.
Puedes generar una desde PowerShell con: python -c "import secrets;
print(secrets.token_urlsafe(48))" Copia el resultado en JWT_SECRET_KEY.

No compartas el archivo .env ni lo subas a GitHub, porque contiene la
conexión a MongoDB y la clave utilizada para firmar los tokens. El
archivo .env.example sí se puede compartir porque contiene valores de
ejemplo.

Las tablas de SQLite se preparan cuando se inicia el backend. No es
necesario crearlas manualmente. 7. Preparar las cuentas de demostración
Las cuentas de prueba que aparecen al principio de este README no se
crean automáticamente al iniciar Flask. Para crearlas, abre PowerShell
desde la carpeta principal y ejecuta:
Env: Mesa Roja Env = "development"Env: Mesa Roja Demo Mode = "true"
.`\backend`{=tex}.venv`\Scripts`{=tex}`\python`{=tex}.exe -m
backend.seed_demo_users El programa te pedirá una contraseña y luego
solicitará que la confirmes. Escribe 123456 en las dos ocasiones para
preparar las cuatro cuentas que aparecen al principio de este README. La
contraseña no se muestra mientras la escribes.

Al terminar, puedes quitar las variables de la terminal: Remove-Item
Env:`\MESA`{=tex}_ROJA_ENV, Env:`\MESA`{=tex}_ROJA_DEMO_MODE Las
contraseñas se guardan con hashing de Werkzeug, no como texto normal. Si
vuelves a ejecutar el comando, no se crean cuentas duplicadas. 8.
Iniciar el backend Desde PowerShell, ubicado en la carpeta principal y
con el entorno virtual activado, ejecuta: python -m backend.app Flask
quedará disponible en: http://127.0.0.1:5000 Para revisar el estado de
las conexiones con las bases de datos, abre esta dirección en el
navegador: http://127.0.0.1:5000/salud Si una conexión falla, la ruta
responde con HTTP 503 e indica por separado el estado de SQLite y
MongoDB, sin incluir la contraseña de Atlas. Deja abierta esta ventana
de PowerShell mientras utilizas el programa. 9. Iniciar el frontend Abre
una segunda ventana de PowerShell desde la carpeta principal del
proyecto y ejecuta: npm --prefix frontend ci npm --prefix frontend run
dev Vite mostrará una dirección local, normalmente:
http://localhost:5173 Abre esa dirección en el navegador. Mantén
abiertas las dos ventanas de PowerShell: una ejecutando Flask y la otra
ejecutando Vite. 10. Ingresar y utilizar el sistema Cuando los dos
servidores estén funcionando, entra a http://localhost:5173. Aparecerá
la pantalla de inicio de sesión. Escribe el correo y la contraseña de
alguna de las cuentas de prueba.

Cada cuenta tiene permisos diferentes: Rol Funciones principales
Administrador Gestiona productos, inventario y usuarios; consulta y
administra pedidos; revisa reportes y actividades. Cliente Consulta el
catálogo, realiza pedidos y revisa sus propios pedidos y estados.
Repartidor Consulta los pedidos relacionados con las entregas y
actualiza su estado. Auditor Consulta pedidos, historiales, actividades
y reportes de ventas e inventario. Tiene permisos de consulta.

Para probar las funciones de los diferentes roles, cierra la sesión y
vuelve a ingresar con otra cuenta. Ejemplo de uso 1. Ingresa como
administrador y revisa que existan productos con unidades disponibles.
Si hace falta, crea o actualiza un producto. 2. Cierra sesión e ingresa
como cliente. Consulta el catálogo y registra un pedido. 3. Ingresa como
administrador o repartidor para consultar el pedido y actualizar su
estado, de acuerdo con los permisos de cada rol. 4. Vuelve a ingresar
como cliente para revisar el estado del pedido. 5. Ingresa como auditor
o administrador para consultar los reportes y revisar el historial del
pedido. Cuando termines de utilizar el programa, presiona Ctrl + C en
cada ventana de PowerShell para detener Flask y Vite. 11. Autenticación
y permisos El sistema permite registrar nuevos usuarios desde el
formulario de registro. Las cuentas nuevas se crean con el rol de
cliente. Las contraseñas se guardan en SQLite después de aplicarles
hashing con Werkzeug; no se almacenan como texto normal.

Cuando un usuario inicia sesión correctamente, la API genera un token
JWT. Este token se envía en las solicitudes a las rutas protegidas
mediante el encabezado: Authorization: Bearer <token>{=html} El tiempo
de duración del token se configura en JWT_ACCESS_TOKEN_EXPIRES_HOURS.
Los permisos se comprueban desde el backend según el rol del usuario.
12. Rutas principales de la API Las rutas se pueden probar desde
Postman. Para utilizar las rutas protegidas, primero debes iniciar
sesión y enviar el token JWT en el encabezado Authorization. Método Ruta
Función Acceso GET /salud Revisa las conexiones con SQLite y MongoDB.
Público POST /auth/registro Registra una cuenta nueva de cliente.
Público POST /auth/login Comprueba los datos de ingreso y devuelve un
token. Público GET /auth/perfil Consulta los datos del usuario
conectado. Usuarios autenticados POST /auth/logout Cierra la sesión.
Usuarios autenticados GET /productos Consulta los productos y sus
existencias. Público POST /productos Crea un producto. Administrador
PATCH /productos/`<id>`{=html} Actualiza un producto o su inventario.
Administrador DELETE /productos/`<id>`{=html} Desactiva un producto.
Administrador POST /usuarios Crea o actualiza usuarios. Administrador
POST /pedidos Registra un pedido y descuenta las existencias. Cliente
GET /pedidos Consulta los pedidos permitidos para el usuario. Según el
rol y sus permisos GET /pedidos/`<id>`{=html} Consulta un pedido
específico. Según el rol y sus permisos PATCH
/pedidos/`<id>`{=html}/estado Actualiza el estado de entrega.
Administrador y repartidor GET /pedidos/`<id>`{=html}/historial Consulta
el pedido y su historial. Según el rol y sus permisos GET /actividades
Consulta las actividades registradas. Administrador y auditor GET
/actividades/`<id>`{=html} Consulta una actividad específica.
Administrador y auditor POST /actividades Registra una actividad.
Administrador PATCH /actividades/`<id>`{=html} Modifica una actividad.
Administrador DELETE /actividades/`<id>`{=html} Elimina una actividad.
Administrador POST /eventos/pendientes/reintentar Intenta enviar a
MongoDB los eventos pendientes. Administrador GET /reportes/ventas
Consulta las ventas y los pedidos por fechas. Administrador y auditor
GET /reportes/inventario Consulta los productos y sus existencias.
Administrador y auditor
13. Ejemplos para probar la API Iniciar sesión
Envía una solicitud POST a /auth/login con este contenido JSON: {
"correo": "jcamilogrimaldoperez@cliente.com", "password": "123456" } La
respuesta incluye los datos del usuario y el token que se utiliza en las
rutas protegidas.

Registrar un pedido

Envía una solicitud POST a /pedidos con un contenido parecido a este: {
"productos": \({ "producto_id": 1, "cantidad": 1 }\), "direccion":
"Dirección de entrega" } El producto indicado debe existir y tener
unidades disponibles.

Consultar las ventas de un periodo GET
/reportes/ventas?desde=2026-01-01&hasta=2026-01-31 14. Colección de
Postman El proyecto incluye una colección para probar las rutas de la
API: postman/mesa-roja.postman_collection.json Para utilizarla: 1. Abre
Postman. 2. Selecciona Import. 3. Busca y selecciona el archivo
mesa-roja.postman_collection.json dentro de la carpeta postman. 4.
Configura la dirección base de la API (baseUrl). 5. Inicia sesión para
obtener un token JWT. 6. Utiliza ese token en las solicitudes que
necesitan autenticación.
