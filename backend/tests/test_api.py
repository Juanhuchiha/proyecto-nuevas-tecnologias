import os
import unittest
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

from pymongo.errors import PyMongoError

from backend.app import create_app
from backend.persistence import publish_pending_events


class FakePostgres:
    def __init__(self):
        self.users = {}
        self.orders = {}
        self.next_user_id = 1
        self.next_order_id = 1

    def connect(self):
        return nullcontext()

    def list_products(self):
        return [{"id": 1, "nombre": "Hamburguesa", "stock": 10, "activo": True}]

    def create_or_update_user(self, name, email, address):
        for user in self.users.values():
            if user["correo"] == email:
                user.update(nombre=name, direccion=address)
                return user, 200
        user = {
            "id": self.next_user_id,
            "nombre": name,
            "correo": email,
            "direccion": address,
        }
        self.users[user["id"]] = user
        self.next_user_id += 1
        return user, 201

    def user_exists(self, user_id):
        return user_id in self.users

    def create_order(self, user_id, address, quantities):
        user = self.users[user_id]
        order_id = self.next_order_id
        self.next_order_id += 1
        order = {
            "id": order_id,
            "usuario_id": user_id,
            "cliente": user,
            "direccion": address or user["direccion"],
            "productos": [
                {
                    "producto_id": product_id,
                    "nombre": "Hamburguesa",
                    "cantidad": quantity,
                    "precio_unitario": 10000,
                    "total": quantity * 10000,
                    "stock_restante": 10 - quantity,
                }
                for product_id, quantity in quantities.items()
            ],
            "subtotal": sum(10000 * quantity for quantity in quantities.values()),
            "envio": 5000,
            "total": sum(10000 * quantity for quantity in quantities.values()) + 5000,
            "moneda": "COP",
            "estado": "Listo para recoger",
            "creado_en": "2026-11-01T10:00:00+00:00",
        }
        self.orders[order_id] = order
        return order

    def get_order(self, order_id):
        return self.orders.get(order_id)

    def list_orders(self):
        return list(self.orders.values())

    def update_order_status(self, order_id, new_status, actor):
        order = self.orders.get(order_id)
        if order is None:
            from backend.persistence import RequestError

            raise RequestError("No se encontró el pedido.", 404)
        order["estado"] = new_status
        return order

    def pending_event_count(self, order_id=None):
        return 0

    def pending_events(self):
        return []

    def sales_report(self):
        return {
            "cantidad_pedidos": len(self.orders),
            "total_ventas": sum(order["total"] for order in self.orders.values()),
            "moneda": "COP",
        }


class FakeMongo:
    def __init__(self):
        self.activities = {}
        self.system_logs = []
        self.history = []
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
        result = {"id": "507f1f77bcf86cd799439011", **document}
        self.activities[result["id"]] = result
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

    def order_history(self, order_id):
        return {
            "historial": [item for item in self.history if item["pedido_id"] == order_id],
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
        self.postgres = FakePostgres()
        self.mongo = FakeMongo()
        self.app = create_app(
            {"TESTING": True},
            postgres=self.postgres,
            mongo=self.mongo,
        )
        self.client = self.app.test_client()

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

    def test_existing_product_user_order_and_report_endpoints(self):
        self.assertEqual(self.client.get("/productos").json["productos"][0]["id"], 1)
        user, status = self.postgres.create_or_update_user(
            "Ana", "ana@example.com", "Calle 1"
        )
        self.assertEqual(status, 201)
        order = self.client.post(
            "/pedidos",
            json={
                "usuario_id": user["id"],
                "productos": [{"producto_id": 1, "cantidad": 1}],
            },
        ).json["pedido"]

        self.assertEqual(self.client.get(f"/pedidos/{order['id']}").status_code, 200)
        self.assertEqual(len(self.client.get("/pedidos").json["pedidos"]), 1)
        self.assertEqual(
            self.client.get("/reportes/ventas").json["cantidad_pedidos"], 1
        )

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
        self.assertEqual(len(self.client.get("/actividades?pedido_id=1").json["actividades"]), 1)

        updated = self.client.patch(
            f"/actividades/{activity_id}",
            json={"descripcion": "Dirección verificada.", "responsable": "Admin"},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(
            updated.json["actividad"]["descripcion"], "Dirección verificada."
        )
        self.assertEqual(len(self.mongo.system_logs), 2)

        deleted = self.client.delete(f"/actividades/{activity_id}")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(len(self.mongo.system_logs), 3)
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
        self.assertEqual(
            self.client.get("/actividades?limite=1000").status_code, 400
        )

    def test_activity_is_returned_when_audit_write_fails(self):
        class FailingAuditMongo(FakeMongo):
            def log_system_action(self, action, actor, description, data, order_id=None):
                raise PyMongoError("test audit failure")

        mongo = FailingAuditMongo()
        client = create_app(
            {"TESTING": True},
            postgres=self.postgres,
            mongo=mongo,
        ).test_client()

        with self.assertLogs("backend.app", level="ERROR"):
            response = client.post(
                "/actividades",
                json={"tipo": "nota", "descripcion": "Actividad guardada."},
            )

        self.assertEqual(response.status_code, 503)
        self.assertIn("actividad", response.json)
        self.assertEqual(
            client.get(f"/actividades/{response.json['actividad']['id']}").status_code,
            200,
        )

    def test_combined_order_history_and_status_update(self):
        order = self.create_order()
        self.mongo.history.append(
            {
                "pedido_id": order["id"],
                "estado_anterior": None,
                "estado_nuevo": "Listo para recoger",
            }
        )
        updated = self.client.patch(
            f"/pedidos/{order['id']}/estado",
            json={"estado": "En camino", "usuario": {"nombre": "Repartidor"}},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json["pedido"]["estado"], "En camino")

        result = self.client.get(f"/pedidos/{order['id']}/historial")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json["pedido"]["id"], order["id"])
        self.assertEqual(len(result.json["historial"]), 1)
        self.assertIn("actividades", result.json)
        self.assertIn("registros_sistema", result.json)

    def test_invalid_status_and_missing_order(self):
        order = self.create_order()
        self.assertEqual(
            self.client.patch(
                f"/pedidos/{order['id']}/estado", json={"estado": []}
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.get("/pedidos/999/historial").status_code, 404
        )

    def test_health_and_outbox_retry_endpoints(self):
        health = self.client.get("/salud")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json["postgresql"], "conectado")
        self.assertEqual(health.json["mongodb"], "conectado")

        retry = self.client.post("/eventos/pendientes/reintentar")
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.json, {"publicados": 0, "pendientes": 0})


class OutboxTests(unittest.TestCase):
    def test_failed_mongo_publish_is_retryable_and_idempotent(self):
        class FakeOutboxPostgres:
            def __init__(self):
                self.events = [
                    {
                        "id": "event-1",
                        "coleccion": "historial_pedidos",
                        "documento": {"pedido_id": 1},
                    }
                ]
                self.errors = []

            def pending_events(self):
                return list(self.events)

            def mark_event_failed(self, event_id, error):
                self.errors.append((event_id, error))

            def mark_event_published(self, event_id):
                self.events = [item for item in self.events if item["id"] != event_id]

        class FakeOutboxMongo:
            fail_once = True

            def publish_outbox_event(self, event_id, collection, document):
                if self.fail_once:
                    self.fail_once = False
                    raise PyMongoError("test connection failure")

        postgres = FakeOutboxPostgres()
        mongo = FakeOutboxMongo()
        with self.assertLogs("backend.persistence", level="ERROR"):
            self.assertEqual(publish_pending_events(postgres, mongo), 0)
        self.assertEqual(postgres.errors[0][0], "event-1")

        self.assertEqual(publish_pending_events(postgres, mongo), 1)
        self.assertEqual(postgres.events, [])


class ConfigurationTests(unittest.TestCase):
    def test_app_requires_both_database_connections(self):
        with patch.dict(os.environ, {"DATABASE_URL": "", "MONGODB_URI": ""}):
            with self.assertRaisesRegex(RuntimeError, "DATABASE_URL, MONGODB_URI"):
                create_app()


if __name__ == "__main__":
    unittest.main()
