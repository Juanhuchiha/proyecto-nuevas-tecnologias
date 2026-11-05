# Estructura del proyecto

La aplicación conserva Vue 3, Flask, SQLite y MongoDB. La organización por carpetas separa la interfaz, las rutas HTTP, la persistencia, la configuración y las pruebas sin cambiar los endpoints.

```text
frontend/
  src/
    components/
    views/
    router/
    services/
    data/
    assets/
backend/
  app.py
  config.py
  routes/
    api.py
  database/
    mongo_connection.py
    persistence.py
    schema.sql
  models/
    errors.py
  services/
    events.py
  data/
    catalog.py
  tests/
docs/
evidencias/
README.md
.env.example
```

- `frontend/src/components` contiene elementos Vue reutilizables; `views` las páginas; `router` las rutas del cliente; `services` el cliente HTTP; `data` el estado del restaurante.
- `backend/app.py` configura e inicia Flask; `backend/routes/api.py` registra los endpoints; `backend/services/events.py` publica los eventos de la cola transaccional.
- `backend/database` contiene las conexiones, el esquema y los adaptadores de persistencia; `backend/models/errors.py` define los errores de dominio usados por la API.
- SQLite conserva usuarios, productos, pedidos, inventario y la cola transaccional. MongoDB conserva actividades, historial de pedidos y registros del sistema.
- `backend/tests` contiene pruebas automatizadas. `evidencias` conserva los resultados y materiales de la entrega; este directorio documenta la arquitectura.

La reorganización no cambia la API ni habilita nuevas funcionalidades de autenticación o administración. La conexión real a MongoDB Atlas solo se puede validar después de configurar una URI válida en el `.env` local.
