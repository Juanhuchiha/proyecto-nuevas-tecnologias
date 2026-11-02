# Evidencias de la entrega

Fecha de las verificaciones locales: 1 de noviembre de 2026.

## Resultados ejecutados

- Backend: `python -m compileall -q backend` finalizó sin errores de sintaxis.
- Pruebas API: `python -m unittest discover -s backend\tests -t .` ejecutó 9 pruebas, todas aprobadas. El registro completo está en [`pruebas_backend.txt`](./pruebas_backend.txt).
- Frontend: `npm run build` finalizó correctamente. El registro está en [`pruebas_frontend.txt`](./pruebas_frontend.txt).
- Las pruebas unitarias inyectan adaptadores falsos; validan el contrato de rutas y el mecanismo de reintento, pero no constituyen una prueba de conexión a PostgreSQL o MongoDB.

## Verificación externa pendiente

En el entorno de trabajo no había `DATABASE_URL` ni `MONGODB_URI`; en la comprobación local los puertos PostgreSQL `5432` y MongoDB `27017` tampoco estaban disponibles. Por lo tanto:

- No se afirma que se haya establecido una conexión real a alguna de las bases.
- No se afirma que las operaciones CRUD se hayan ejecutado contra un clúster o servidor de base de datos real.
- No se generaron capturas de pantalla de una ejecución con bases reales.

La prueba [`backend/integration_smoke.py`](../backend/integration_smoke.py) realiza esa comprobación contra las dos bases configuradas y elimina los datos temporales que crea. Para obtener esa evidencia, configura `.env` con bases de prueba y ejecuta:

```powershell
python -m backend.integration_smoke
```

El informe relacionado directamente con esta implementación está en [`implementacion-mongodb.pdf`](./implementacion-mongodb.pdf).
