# Evidencias de la entrega SQLite + MongoDB

Fecha de las verificaciones locales: 1 de noviembre de 2026.

## Resultados ejecutados

- Python: `python -m compileall -q backend` finalizó sin errores de sintaxis.
- Pruebas API: `python -m unittest discover -s backend\tests -t . -v` ejecutó 10 pruebas. SQLite se probó usando archivos de base temporales reales; los adaptadores de MongoDB para las rutas se simularon. Consulta el registro [`pruebas_backend.txt`](./pruebas_backend.txt).
- Frontend: `npm run build` finalizó correctamente. Consulta [`pruebas_frontend.txt`](./pruebas_frontend.txt).
- Las pruebas SQLite verifican la creación de tablas, claves foráneas, datos de demostración, registro y actualización de usuarios, pedidos, descuento de inventario, rollback, reportes y cola de eventos.
- Las pruebas MongoDB simuladas verifican el CRUD de actividades, el historial combinado, los registros de auditoría y los reintentos; no son pruebas contra un servidor MongoDB real.

## Integración con MongoDB real pendiente

No había `MONGODB_URI` configurada ni un servidor local disponible en el puerto `27017`. Por lo tanto:

- No se afirma que la conexión a MongoDB, la creación de índices o el CRUD se haya comprobado contra un clúster o servidor real.
- No se generaron capturas de una ejecución con MongoDB real.
- La base SQLite y sus tablas sí fueron creadas y probadas con archivos temporales reales durante las pruebas unitarias.

Para verificar la conexión y todas las operaciones con tu MongoDB, configura `MONGODB_URI` en un `.env` local y ejecuta:

```powershell
python -m backend.integration_smoke
```

La prueba usa una SQLite temporal y limpia los documentos temporales que agrega a MongoDB. Ejecútala contra una base de pruebas, no contra una base con datos de producción.

El informe actualizado y relacionado con esta rama está en [`implementacion-mongodb.pdf`](./implementacion-mongodb.pdf).
