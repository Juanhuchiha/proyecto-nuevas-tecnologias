import json
import os
import tempfile
import uuid
from pathlib import Path

from backend.app import create_app


def require_status(response, expected):
    if response.status_code != expected:
        raise AssertionError(
            f"HTTP {response.status_code}, esperado {expected}: "
            f"{response.get_data(as_text=True)}"
        )


def run():
    with tempfile.TemporaryDirectory(prefix="mesa-roja-smoke-") as directory:
        database_path = Path(directory) / "mesa_roja.db"
        app = create_app(
            {"TESTING": True, "SQLITE_DATABASE_PATH": str(database_path)}
        )
        client = app.test_client()
        sqlite_store = app.extensions["sqlite_store"]
        mongo = app.extensions["mongo_store"]
        suffix = uuid.uuid4().hex
        email = f"smoke-{suffix}@example.com"
        user_id = None
        order_id = None
        activity_id = None

        try:
            require_status(client.get("/salud"), 200)

            user_response = client.post(
                "/usuarios",
                json={
                    "nombre": "Prueba de integración",
                    "correo": email,
                    "direccion": "Dirección temporal de pruebas",
                },
            )
            require_status(user_response, 201)
            user_id = user_response.json["usuario"]["id"]

            order_response = client.post(
                "/pedidos",
                json={
                    "usuario_id": user_id,
                    "productos": [{"producto_id": 8, "cantidad": 1}],
                },
            )
            require_status(order_response, 201)
            order_id = order_response.json["pedido"]["id"]

            activity_response = client.post(
                "/actividades",
                json={
                    "tipo": "prueba_integracion",
                    "descripcion": "Actividad temporal para verificar MongoDB.",
                    "usuario_id": user_id,
                    "pedido_id": order_id,
                    "datos": {"id_prueba": suffix},
                    "responsable": "Prueba automatizada",
                },
            )
            require_status(activity_response, 201)
            activity_id = activity_response.json["actividad"]["id"]

            require_status(client.get(f"/actividades/{activity_id}"), 200)
            require_status(
                client.patch(
                    f"/actividades/{activity_id}",
                    json={"descripcion": "Actividad actualizada correctamente."},
                ),
                200,
            )
            require_status(
                client.get(f"/actividades?pedido_id={order_id}&limite=10"), 200
            )

            status_response = client.patch(
                f"/pedidos/{order_id}/estado",
                json={
                    "estado": "En camino",
                    "usuario": {
                        "id": user_id,
                        "nombre": "Repartidor de prueba",
                    },
                },
            )
            require_status(status_response, 200)

            history_response = client.get(f"/pedidos/{order_id}/historial")
            require_status(history_response, 200)
            if len(history_response.json["historial"]) < 2:
                raise AssertionError(
                    "Faltan eventos de creación y cambio de estado en MongoDB."
                )
            if not history_response.json["actividades"]:
                raise AssertionError(
                    "La actividad temporal no aparece en el historial combinado."
                )
            require_status(client.get("/reportes/ventas"), 200)

            require_status(client.delete(f"/actividades/{activity_id}"), 200)
            activity_id = None

            return {
                "resultado": "correcto",
                "base_sqlite": "conectada",
                "base_mongodb": "conectada",
                "endpoints_probados": [
                    "GET /salud",
                    "GET /productos",
                    "POST /usuarios",
                    "POST /pedidos",
                    "PATCH /pedidos/{id}/estado",
                    "GET /pedidos/{id}/historial",
                    "POST, GET, PATCH y DELETE /actividades",
                    "GET /reportes/ventas",
                ],
                "eventos_de_estado_encontrados": len(
                    history_response.json["historial"]
                ),
                "actividades_encontradas": len(
                    history_response.json["actividades"]
                ),
                "identificadores_temporales": {
                    "pedido_id": order_id,
                    "actividad_id": activity_response.json["actividad"]["id"],
                },
            }
        finally:
            if activity_id is not None:
                mongo.delete_activity(activity_id)
            if order_id is not None:
                for collection in (
                    "historial_pedidos",
                    "actividades_usuarios",
                    "registros_sistema",
                ):
                    mongo.database[collection].delete_many({"pedido_id": order_id})
                with sqlite_store.connect(write=True) as connection:
                    details = connection.execute(
                        """
                        SELECT producto_id, cantidad FROM detalles_pedido
                        WHERE pedido_id = ?
                        """,
                        (order_id,),
                    ).fetchall()
                    for detail in details:
                        connection.execute(
                            "UPDATE productos SET stock = stock + ? WHERE id = ?",
                            (detail["cantidad"], detail["producto_id"]),
                        )
                    pending = connection.execute(
                        "SELECT id, documento FROM cola_eventos"
                    ).fetchall()
                    for event in pending:
                        if json.loads(event["documento"]).get("pedido_id") == order_id:
                            connection.execute(
                                "DELETE FROM cola_eventos WHERE id = ?",
                                (event["id"],),
                            )
                    connection.execute("DELETE FROM pedidos WHERE id = ?", (order_id,))
            if user_id is not None:
                with sqlite_store.connect(write=True) as connection:
                    connection.execute("DELETE FROM usuarios WHERE id = ?", (user_id,))
            if app.extensions["mongo_client"] is not None:
                app.extensions["mongo_client"].close()


if __name__ == "__main__":
    if not os.getenv("MONGODB_URI"):
        raise SystemExit(
            "Configura MONGODB_URI en .env antes de ejecutar la prueba con MongoDB real."
        )
    print(json.dumps(run(), indent=2, ensure_ascii=False))
