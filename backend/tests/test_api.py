import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pymongo.errors import PyMongoError

from backend.app import create_app
from backend.persistence import SQLiteStore, publish_pending_events


class FakeMongo:
    def __init__(self):
        self.activities = {}
        self.system_logs = []
        self.history = []
        self.outbox_documents = set()
        self.client = SimpleNamespace(
            admin=SimpleNamespace(command=lambda operation: {"ok": 1})
        )

    def list_activities(self, filters, limit):
        items = list(self.activities.values())
        return [
            item
            for item in items
            if all(item.get(key) == value for key, value in filters.items())
        ][:limit]

    def create_activity(self, document):
        identifier = "507f1f77bcf86cd799439011"
        result = {"id": identifier, **document}
        self.activities[identifier] = result
        return result

    def get_activity(self, identifier):
        return self.activities.get(identifier)

    def update_activity(self, identifier, updates):
        activity = self.activities.get(identifier)
        if activity is None:
            return None
        activity.update(updates)
        return activity

    def delete_activity(self, identifier):
        return self.activities.pop(identifier, None) is not None

    def log_system_action(self, action, actor, description, data, order_id=None):
        self.system_logs.append(
            {
                "tipo": action,
                "usuario": actor,
                "descripcion": description,
                "datos": data,
                "pedido_id": order_id,
            }
        )

    def publish_outbox_event(self, event_id, collection, document):
        identifier = str(event_id)
        if identifier in self.outbox_documents:
            return
        self.outbox_documents.add(identifier)
        record = {"id": identifier, **document}
        if collection == "historial_pedidos":
            self.history.append(record)
        else:
            self.system_logs.append(record)

    def order_history(self, order_id):
        return {
            "historial": [
                item for item in self.history if item["pedido_id"] == order_id
            ],
            "actividades": [
                item
                for item in self.activities.values()
                if item.get("pedido_id") == order_id
            ],
            "registros_sistema": [
                item for item in self.system_logs if item.get("pedido_id") == order_id
            ],
        }


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_directory.name) / "mesa_roja.db"
        self.sqlite = SQLiteStore(self.database_path)
        self.sqlite.initialize()
        self.mongo = FakeMongo()
        self.app = create_app(
            {"TESTING": True},
            sqlite_store=self.sqlite,
            mongo=self.mongo,
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_directory.cleanup()

    def create_order(self):
        user_response = self.client.post(
            "/usuarios",
            json={
                "nombre": "Ana",
                "correo": "ana@example.com",
                "direccion": "Calle 1",
            },
        )
        self.assertEqual(user_response.status_code, 201)
        user_id = user_response.json["usuario"]["id"]
        order_response = self.client.post(
            "/pedidos",
            json={
                "usuario_id": user_id,
                "productos": [{"producto_id": 1, "cantidad": 2}],
            },
        )
        self.assertEqual(order_response.status_code, 201)
        return order_response.json["pedido"]

    def test_sqlite_creates_schema_relations_and_demo_catalog(self):
        self.assertTrue(self.database_path.exists())
        with self.sqlite.connect() as connection:
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            self.assertTrue(
                {
                    "usuarios",
                    "productos",
                    "pedidos",
                    "detalles_pedido",
                    "cola_eventos",
                }.issubset(tables)
            )
            self.assertEqual(
                connection.execute("PRAGMA foreign_keys").fetchone()[0], 1
            )
            foreign_keys = connection.execute(
                "PRAGMA foreign_key_list(detalles_pedido)"
            ).fetchall()
            self.assertEqual(
                {row["table"] for row in foreign_keys},
                {"pedidos", "productos"},
            )

        self.assertEqual(len(self.sqlite.list_products()), 8)
        with self.sqlite.connect(write=True) as connection:
            connection.execute("UPDATE productos SET stock = 7 WHERE id = 1")
        self.sqlite.initialize()
        self.assertEqual(self.sqlite.list_products()[0]["stock"], 7)

    def test_product_user_order_inventory_outbox_and_sales(self):
        self.assertEqual(self.client.get("/productos").json["productos"][0]["id"], 1)

        user_response = self.client.post(
            "/usuarios",
            json={
                "nombre": "Ana",
                "correo": "ana@example.com",
                "direccion": "Calle 1",
            },
        )
        self.assertEqual(user_response.status_code, 201)
        user_id = user_response.json["usuario"]["id"]
        self.assertEqual(
            self.client.post(
                "/usuarios",
                json={
                    "nombre": "Ana actualizada",
                    "correo": "ana@example.com",
                    "direccion": "Calle 2",
                },
            ).status_code,
            200,
        )

        initial_stock = self.sqlite.list_products()[0]["stock"]
        order_response = self.client.post(
            "/pedidos",
            json={
                "usuario_id": user_id,
                "productos": [{"producto_id": 1, "cantidad": 2}],
            },
        )
        self.assertEqual(order_response.status_code, 201)
        order = order_response.json["pedido"]
        self.assertEqual(order["productos"][0]["stock_restante"], initial_stock - 2)
        self.assertEqual(
            self.sqlite.list_products()[0]["stock"], initial_stock - 2
        )
        self.assertEqual(
            self.client.get(f"/pedidos/{order['id']}").json["pedido"]["id"],
            order["id"],
        )
        self.assertEqual(
            len(self.client.get("/pedidos").json["pedidos"]), 1
        )

        with self.sqlite.connect() as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM cola_eventos"
                ).fetchone()[0],
                2,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM detalles_pedido WHERE pedido_id = ?",
                    (order["id"],),
                ).fetchone()[0],
                1,
            )

        report = self.client.get("/reportes/ventas").json
        self.assertEqual(report["cantidad_pedidos"], 1)
        self.assertEqual(report["total_ventas"], order["total"])

    def test_order_transaction_rolls_back_on_invalid_product(self):
        user, status = self.sqlite.create_or_update_user(
            "Ana", "ana@example.com", "Calle 1"
        )
        self.assertEqual(status, 201)
        initial_stock = self.sqlite.list_products()[0]["stock"]

        response = self.client.post(
            "/pedidos",
            json={
                "usuario_id": user["id"],
                "productos": [
                    {"producto_id": 1, "cantidad": 1},
                    {"producto_id": 999, "cantidad": 1},
                ],
            },
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.sqlite.list_products()[0]["stock"], initial_stock)
        self.assertEqual(self.client.get("/pedidos").json["pedidos"], [])
        self.assertEqual(self.sqlite.pending_event_count(), 0)

    def test_activity_crud_and_audit_logs(self):
        order = self.create_order()
        created = self.client.post(
            "/actividades",
            json={
                "tipo": "nota",
                "descripcion": "Cliente confirmó la dirección.",
                "pedido_id": order["id"],
                "datos": {"canal": "telefono"},
                "responsable": "Operador",
            },
        )
        self.assertEqual(created.status_code, 201)
        activity_id = created.json["actividad"]["id"]
        self.assertEqual(
            self.client.get(f"/actividades/{activity_id}").json["actividad"]["tipo"],
            "nota",
        )
        self.assertEqual(
            len(
                self.client.get("/actividades?pedido_id=1").json["actividades"]
            ),
            1,
        )

        updated = self.client.patch(
            f"/actividades/{activity_id}",
            json={"descripcion": "Dirección verificada.", "responsable": "Admin"},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(
            updated.json["actividad"]["descripcion"], "Dirección verificada."
        )
        self.assertEqual(len(self.mongo.system_logs), 3)

        deleted = self.client.delete(f"/actividades/{activity_id}")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(len(self.mongo.system_logs), 4)
        self.assertEqual(self.client.get(f"/actividades/{activity_id}").status_code, 404)

    def test_activity_validation_and_missing_references(self):
        self.assertEqual(
            self.client.post(
                "/actividades",
                json={"tipo": "nota", "descripcion": "Sin usuario", "usuario_id": 99},
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                "/actividades",
                json={"tipo": "", "descripcion": "Texto"},
            ).status_code,
            400,
        )
        self.assertEqual(self.client.get("/actividades?limite=1000").status_code, 400)

    def test_activity_is_returned_when_audit_write_fails(self):
        class FailingAuditMongo(FakeMongo):
            def log_system_action(
                self, action, actor, description, data, order_id=None
            ):
                raise PyMongoError("test audit failure")

        mongo = FailingAuditMongo()
        client = create_app(
            {"TESTING": True},
            sqlite_store=self.sqlite,
            mongo=mongo,
        ).test_client()

        with self.assertLogs("backend.app", level="ERROR"):
            response = client.post(
                "/actividades",
                json={"tipo": "nota", "descripcion": "Actividad guardada."},
            )

        self.assertEqual(response.status_code, 503)
        self.assertIn("actividad", response.json)
        self.assertIn(response.json["actividad"]["id"], mongo.activities)

    def test_combined_order_history_and_status_update(self):
        order = self.create_order()
        updated = self.client.patch(
            f"/pedidos/{order['id']}/estado",
            json={"estado": "En camino", "usuario": {"nombre": "Repartidor"}},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json["pedido"]["estado"], "En camino")

        with self.sqlite.connect() as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM cola_eventos WHERE publicado_en IS NULL"
                ).fetchone()[0],
                0,
            )

        result = self.client.get(f"/pedidos/{order['id']}/historial")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json["pedido"]["id"], order["id"])
        self.assertEqual(len(result.json["historial"]), 2)
        self.assertIn("actividades", result.json)
        self.assertIn("registros_sistema", result.json)

    def test_invalid_status_missing_order_health_and_manual_retry(self):
        order = self.create_order()
        self.assertEqual(
            self.client.patch(
                f"/pedidos/{order['id']}/estado", json={"estado": []}
            ).status_code,
            400,
        )
        self.assertEqual(self.client.get("/pedidos/999/historial").status_code, 404)
        health = self.client.get("/salud")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json["sqlite"], "conectado")
        self.assertEqual(health.json["mongodb"], "conectado")
        retry = self.client.post("/eventos/pendientes/reintentar")
        self.assertEqual(retry.json["pendientes"], 0)

    def test_app_requires_mongo_uri_only(self):
        with patch.dict(os.environ, {"MONGODB_URI": ""}):
            with self.assertRaisesRegex(RuntimeError, "MONGODB_URI"):
                create_app()


class OutboxTests(unittest.TestCase):
    def test_failed_mongo_publish_is_retryable_and_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "outbox.db")
            store.initialize()
            with store.connect(write=True) as connection:
                store._enqueue(
                    connection,
                    "historial_pedidos",
                    {"pedido_id": 1, "estado_nuevo": "En camino"},
                )

            class FailOnceMongo:
                fail_once = True
                documents = set()

                def publish_outbox_event(self, event_id, collection, document):
                    if self.fail_once:
                        self.fail_once = False
                        raise PyMongoError("test connection failure")
                    self.documents.add(str(event_id))

            mongo = FailOnceMongo()
            with self.assertLogs("backend.persistence", level="ERROR"):
                self.assertEqual(publish_pending_events(store, mongo), 0)
            failed = store.pending_events()
            self.assertEqual(len(failed), 1)
            with store.connect() as connection:
                error = connection.execute(
                    "SELECT intentos, error FROM cola_eventos WHERE id = ?",
                    (failed[0]["id"],),
                ).fetchone()
            self.assertEqual(error["intentos"], 1)
            self.assertIn("test connection failure", error["error"])

            self.assertEqual(publish_pending_events(store, mongo), 1)
            self.assertEqual(publish_pending_events(store, mongo), 0)
            self.assertEqual(store.pending_event_count(), 0)
            self.assertEqual(len(mongo.documents), 1)


if __name__ == "__main__":
    unittest.main()
