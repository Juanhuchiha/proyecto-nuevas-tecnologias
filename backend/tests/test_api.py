import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import jwt
from pymongo.errors import PyMongoError
from werkzeug.security import check_password_hash, generate_password_hash

from backend.app import create_app
from backend.database.mongo_connection import create_mongo_store
from backend.database.persistence import SQLiteStore
from backend.models.errors import RequestError
from backend.services.events import publish_pending_events


class FakeMongo:
    def __init__(self):
        self.activities = {}
        self.system_logs = []
        self.history = []
        self.outbox_documents = set()
        self.client = SimpleNamespace(
            admin=SimpleNamespace(command=lambda _operation: {"ok": 1})
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
        self.admin, _ = self.sqlite.create_or_update_user(
            "Administradora",
            "admin@example.com",
            "Calle 1",
            generate_password_hash("admin-pass-123"),
            "admin",
        )
        self.mongo = FakeMongo()
        self.app = create_app(
            {"TESTING": True},
            sqlite_store=self.sqlite,
            mongo=self.mongo,
        )
        self.client = self.app.test_client()
        login = self.client.post(
            "/auth/login",
            json={"correo": "admin@example.com", "password": "admin-pass-123"},
        )
        self.assertEqual(login.status_code, 200)
        self.admin_token = login.json["token"]
        self.client.environ_base["HTTP_AUTHORIZATION"] = (
            f"Bearer {self.admin_token}"
        )

    def tearDown(self):
        self.temp_directory.cleanup()

    def test_auth_registration_login_and_token_protection(self):
        register = self.client.post(
            "/auth/registro",
            json={
                "nombre": "Laura",
                "correo": "laura@example.com",
                "direccion": "Calle 9",
                "password": "secreto123",
                "rol": "admin",
            },
        )
        self.assertEqual(register.status_code, 201)
        self.assertIn("token", register.json)
        self.assertNotIn("password_hash", register.json["usuario"])
        self.assertEqual(register.json["usuario"]["rol"], "cliente")

        duplicate = self.client.post(
            "/auth/registro",
            json={
                "nombre": "Laura 2",
                "correo": "laura@example.com",
                "direccion": "Calle 10",
                "password": "secreto321",
            },
        )
        self.assertEqual(duplicate.status_code, 409)

        token = register.json["token"]
        profile = self.client.get(
            "/auth/perfil",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.json["usuario"]["rol"], "cliente")

        app = create_app(
            {
                "TESTING": False,
                "JWT_SECRET_KEY": self.app.config["JWT_SECRET_KEY"],
            },
            sqlite_store=self.sqlite,
            mongo=self.mongo,
        )
        client = app.test_client()
        protected_without_token = client.get("/pedidos")
        self.assertEqual(protected_without_token.status_code, 401)

        invalid_token = client.get(
            "/pedidos",
            headers={"Authorization": "Bearer este-token-es-invalido"},
        )
        self.assertEqual(invalid_token.status_code, 401)

        expired_token = jwt.encode(
            {
                "sub": str(self.admin["id"]),
                "ver": self.admin["token_version"],
                "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
            },
            self.app.config["JWT_SECRET_KEY"],
            algorithm="HS256",
        )
        expired = client.get(
            "/pedidos",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        self.assertEqual(expired.status_code, 401)

        login = self.client.post(
            "/auth/login",
            json={"correo": "laura@example.com", "password": "secreto123"},
        )
        self.assertEqual(login.status_code, 200)
        self.assertIn("token", login.json)
        self.assertNotIn("password_hash", login.json["usuario"])
        wrong_password = self.client.post(
            "/auth/login",
            json={"correo": "laura@example.com", "password": "incorrecta"},
        )
        self.assertEqual(wrong_password.status_code, 401)

        with self.sqlite.connect() as connection:
            row = connection.execute(
                "SELECT password_hash FROM usuarios WHERE correo = ?",
                ("laura@example.com",),
            ).fetchone()
            self.assertIsNotNone(row)
            self.assertNotEqual(row["password_hash"], "secreto123")

        logout = self.client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {login.json['token']}"},
        )
        self.assertEqual(logout.status_code, 200)
        profile_after_logout = self.client.get(
            "/auth/perfil",
            headers={"Authorization": f"Bearer {login.json['token']}"},
        )
        self.assertEqual(profile_after_logout.status_code, 401)

    def create_order(self):
        user_response = self.client.post(
            "/usuarios",
            json={
                "nombre": "Ana",
                "correo": "ana@example.com",
                "direccion": "Calle 1",
                "password": "cliente-123",
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

    def register_customer(self, email):
        response = self.client.post(
            "/auth/registro",
            json={
                "nombre": "Cliente",
                "correo": email,
                "direccion": "Calle 2",
                "password": "cliente-123",
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.json["usuario"], {
            "Authorization": f"Bearer {response.json['token']}"
        }

    def test_demo_accounts_are_explicit_idempotent_and_hashed(self):
        emails = (
            "jcamilogrimaldoperez@admin.com",
            "jcamilogrimaldoperez@cliente.com",
            "jcamilogrimaldoperez@repartidor.com",
            "jcamilogrimaldoperez@auditor.com",
        )
        with self.sqlite.connect() as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM usuarios WHERE lower(correo) IN (?, ?, ?, ?)",
                    emails,
                ).fetchone()[0],
                0,
            )
            original_admin = connection.execute(
                "SELECT rol, password_hash, token_version FROM usuarios WHERE id = ?",
                (self.admin["id"],),
            ).fetchone()

        self.assertEqual(
            self.sqlite.seed_demo_users("123456"),
            {"created": 4, "updated": 0, "unchanged": 0},
        )
        with self.sqlite.connect() as connection:
            rows = connection.execute(
                """
                SELECT correo, rol, password_hash
                FROM usuarios
                WHERE lower(correo) IN (?, ?, ?, ?)
                """,
                emails,
            ).fetchall()
            admin_after = connection.execute(
                "SELECT rol, password_hash, token_version FROM usuarios WHERE id = ?",
                (self.admin["id"],),
            ).fetchone()
        self.assertEqual(len(rows), 4)
        self.assertEqual(tuple(admin_after), tuple(original_admin))
        expected_roles = {
            emails[0]: "admin",
            emails[1]: "cliente",
            emails[2]: "repartidor",
            emails[3]: "auditor",
        }
        for row in rows:
            self.assertEqual(row["rol"], expected_roles[row["correo"]])
            self.assertNotEqual(row["password_hash"], "123456")
            self.assertTrue(check_password_hash(row["password_hash"], "123456"))
            login = self.app.test_client().post(
                "/auth/login",
                json={"correo": row["correo"], "password": "123456"},
            )
            self.assertEqual(login.status_code, 200)
            self.assertEqual(login.json["usuario"]["rol"], row["rol"])

        self.assertEqual(
            self.sqlite.seed_demo_users("123456"),
            {"created": 0, "updated": 0, "unchanged": 4},
        )

    def test_customer_can_create_order_for_authenticated_account_only(self):
        customer = self.sqlite.create_user(
            "Cliente de prueba",
            "cliente-pedido@example.com",
            "",
            generate_password_hash("cliente-password"),
            "cliente",
        )
        customer_client = self.app.test_client()
        login = customer_client.post(
            "/auth/login",
            json={
                "correo": "cliente-pedido@example.com",
                "password": "cliente-password",
            },
        )
        self.assertEqual(login.status_code, 200)
        headers = {"Authorization": f"Bearer {login.json['token']}"}

        order = customer_client.post(
            "/pedidos",
            json={
                "usuario_id": customer["id"],
                "direccion": "Calle 1, Chapinero",
                "productos": [{"producto_id": 1, "cantidad": 1}],
            },
            headers=headers,
        )
        self.assertEqual(order.status_code, 201)
        self.assertEqual(order.json["pedido"]["usuario_id"], customer["id"])
        self.assertEqual(order.json["pedido"]["direccion"], "Calle 1, Chapinero")

        forbidden_order = customer_client.post(
            "/pedidos",
            json={
                "usuario_id": self.admin["id"],
                "productos": [{"producto_id": 1, "cantidad": 1}],
            },
            headers=headers,
        )
        self.assertEqual(forbidden_order.status_code, 403)

    def test_auditor_can_read_reports_orders_and_activities_only(self):
        order = self.create_order()
        activity = self.client.post(
            "/actividades",
            json={
                "tipo": "nota",
                "descripcion": "Actividad para consulta de auditoría.",
                "pedido_id": order["id"],
            },
        )
        self.assertEqual(activity.status_code, 201)
        activity_id = activity.json["actividad"]["id"]
        created_auditor = self.client.post(
            "/usuarios",
            json={
                "nombre": "Auditor",
                "correo": "auditor-test@example.com",
                "password": "role-test-password",
                "rol": "auditor",
            },
        )
        self.assertEqual(created_auditor.status_code, 201)
        auditor_client = self.app.test_client()
        login = auditor_client.post(
            "/auth/login",
            json={
                "correo": "auditor-test@example.com",
                "password": "role-test-password",
            },
        )
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.json["usuario"]["rol"], "auditor")
        auditor_headers = {"Authorization": "Bearer " + login.json["token"]}
        self.assertEqual(
            auditor_client.get("/auth/perfil", headers=auditor_headers).status_code,
            200,
        )

        sales = auditor_client.get("/reportes/ventas", headers=auditor_headers)
        inventory = auditor_client.get(
            "/reportes/inventario", headers=auditor_headers
        )
        self.assertEqual(sales.status_code, 200)
        self.assertEqual(sales.json["cantidad_pedidos"], 1)
        self.assertEqual(inventory.status_code, 200)
        self.assertEqual(
            inventory.json["cantidad_productos"], len(self.sqlite.list_products())
        )
        self.assertEqual(
            auditor_client.get("/pedidos", headers=auditor_headers).status_code, 200
        )
        self.assertEqual(
            auditor_client.get(
                f"/pedidos/{order['id']}", headers=auditor_headers
            ).status_code,
            200,
        )
        self.assertEqual(
            auditor_client.get(
                f"/pedidos/{order['id']}/historial", headers=auditor_headers
            ).status_code,
            200,
        )
        self.assertEqual(
            auditor_client.get("/actividades", headers=auditor_headers).status_code,
            200,
        )
        self.assertEqual(
            auditor_client.get(
                f"/actividades/{activity_id}", headers=auditor_headers
            ).status_code,
            200,
        )

        original_stock = self.sqlite.list_products()[0]["stock"]
        with self.sqlite.connect() as connection:
            original_user_count = connection.execute(
                "SELECT COUNT(*) FROM usuarios"
            ).fetchone()[0]
            original_order_count = connection.execute(
                "SELECT COUNT(*) FROM pedidos"
            ).fetchone()[0]
        product = {
            "nombre": "No permitido",
            "precio": 1,
            "stock": 1,
            "categoria": "Pruebas",
        }
        self.assertEqual(
            auditor_client.post(
                "/productos", json=product, headers=auditor_headers
            ).status_code,
            403,
        )
        self.assertEqual(
            auditor_client.patch(
                "/productos/1", json={"stock": 0}, headers=auditor_headers
            ).status_code,
            403,
        )
        self.assertEqual(
            auditor_client.delete(
                "/productos/1", headers=auditor_headers
            ).status_code,
            403,
        )
        self.assertEqual(
            auditor_client.post(
                "/usuarios",
                json={
                    "nombre": "No permitido",
                    "correo": "no-permitido@example.com",
                    "password": "password",
                    "rol": "admin",
                },
                headers=auditor_headers,
            ).status_code,
            403,
        )
        self.assertEqual(
            auditor_client.post(
                "/pedidos",
                json={"productos": [{"producto_id": 1, "cantidad": 1}]},
                headers=auditor_headers,
            ).status_code,
            403,
        )
        self.assertEqual(
            auditor_client.patch(
                f"/pedidos/{order['id']}/estado",
                json={"estado": "En camino"},
                headers=auditor_headers,
            ).status_code,
            403,
        )
        self.assertEqual(
            auditor_client.post(
                "/actividades",
                json={"tipo": "nota", "descripcion": "No permitido"},
                headers=auditor_headers,
            ).status_code,
            403,
        )
        self.assertEqual(
            auditor_client.patch(
                f"/actividades/{activity_id}",
                json={"descripcion": "No permitido"},
                headers=auditor_headers,
            ).status_code,
            403,
        )
        self.assertEqual(
            auditor_client.delete(
                f"/actividades/{activity_id}", headers=auditor_headers
            ).status_code,
            403,
        )
        self.assertEqual(
            auditor_client.post(
                "/eventos/pendientes/reintentar", headers=auditor_headers
            ).status_code,
            403,
        )
        self.assertEqual(
            auditor_client.patch(
                "/reportes/inventario",
                json={"stock": 0},
                headers=auditor_headers,
            ).status_code,
            405,
        )
        self.assertEqual(self.sqlite.list_products()[0]["stock"], original_stock)
        with self.sqlite.connect() as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0],
                original_user_count,
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM pedidos").fetchone()[0],
                original_order_count,
            )

    def test_sales_report_date_filters_and_inventory_summary(self):
        self.create_order()
        today = datetime.now(timezone.utc).date().isoformat()
        report = self.client.get(f"/reportes/ventas?desde={today}&hasta={today}")
        self.assertEqual(report.status_code, 200)
        self.assertEqual(report.json["cantidad_pedidos"], 1)
        self.assertEqual(report.json["desde"], today)
        self.assertEqual(report.json["hasta"], today)
        self.assertEqual(
            self.client.get("/reportes/ventas?desde=invalid").status_code, 400
        )
        self.assertEqual(
            self.client.get(
                "/reportes/ventas?desde=2026-12-31&hasta=2026-01-01"
            ).status_code,
            400,
        )
        inventory = self.sqlite.inventory_report()
        products = self.sqlite.list_products()
        self.assertEqual(inventory["cantidad_productos"], len(products))
        self.assertEqual(
            inventory["unidades_disponibles"],
            sum(product["stock"] for product in products if product["activo"]),
        )

    def test_delivery_role_can_update_order_status(self):
        order = self.create_order()
        self.sqlite.create_user(
            "Repartidor",
            "repartidor-test@example.com",
            "",
            generate_password_hash("role-test-password"),
            "repartidor",
        )
        delivery_client = self.app.test_client()
        login = delivery_client.post(
            "/auth/login",
            json={
                "correo": "repartidor-test@example.com",
                "password": "role-test-password",
            },
        )
        self.assertEqual(login.status_code, 200)
        response = delivery_client.patch(
            f"/pedidos/{order['id']}/estado",
            json={"estado": "En camino"},
            headers={"Authorization": "Bearer " + login.json["token"]},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["pedido"]["estado"], "En camino")
        self.assertEqual(
            delivery_client.get(
                "/reportes/ventas",
                headers={"Authorization": "Bearer " + login.json["token"]},
            ).status_code,
            403,
        )
        self.assertEqual(
            delivery_client.post(
                "/usuarios",
                json={
                    "nombre": "No permitido",
                    "correo": "no-permitido-repartidor@example.com",
                    "password": "password",
                    "rol": "admin",
                },
                headers={"Authorization": "Bearer " + login.json["token"]},
            ).status_code,
            403,
        )

    def test_existing_role_constraint_migrates_without_breaking_order_links(self):
        temporary = tempfile.TemporaryDirectory()
        database_path = Path(temporary.name) / "legacy.db"
        schema_path = Path(__file__).resolve().parents[1] / "database" / "schema.sql"
        legacy_schema = schema_path.read_text(encoding="utf-8").replace(
            "'repartidor', 'auditor'", "'repartidor'"
        )
        connection = sqlite3.connect(database_path)
        try:
            connection.executescript(legacy_schema)
            connection.execute(
                """
                INSERT INTO usuarios (nombre, correo, direccion, rol)
                VALUES ('Cliente existente', 'existente@example.com', '', 'cliente')
                """
            )
            connection.execute(
                """
                INSERT INTO pedidos
                    (usuario_id, direccion, subtotal, envio, total, moneda, estado, creado_en)
                VALUES (1, '', 1000, 0, 1000, 'COP', 'Pendiente', '2026-01-01T10:00:00+00:00')
                """
            )
            connection.commit()
        finally:
            connection.close()

        legacy_store = SQLiteStore(database_path)
        legacy_store.initialize()
        with legacy_store.connect(write=True) as migrated:
            migrated.execute(
                """
                INSERT INTO usuarios (nombre, correo, direccion, rol)
                VALUES ('Auditor', 'auditor@example.com', '', 'auditor')
                """
            )
            self.assertEqual(
                migrated.execute("SELECT COUNT(*) FROM pedidos").fetchone()[0], 1
            )
            self.assertEqual(
                migrated.execute("PRAGMA foreign_key_check").fetchall(), []
            )
        existing = legacy_store.get_user_by_email("existente@example.com")
        self.assertEqual(existing["rol"], "cliente")
        self.assertIsNone(existing["password_hash"])
        temporary.cleanup()

    def test_legacy_users_without_role_columns_migrate_to_auditor_capable_schema(self):
        temporary = tempfile.TemporaryDirectory()
        database_path = Path(temporary.name) / "legacy-users.db"
        connection = sqlite3.connect(database_path)
        try:
            connection.execute(
                """
                CREATE TABLE usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT NOT NULL,
                    correo TEXT NOT NULL UNIQUE,
                    direccion TEXT NOT NULL DEFAULT ''
                )
                """
            )
            connection.execute(
                """
                INSERT INTO usuarios (nombre, correo, direccion)
                VALUES ('Cliente existente', 'existente@example.com', 'Calle 1')
                """
            )
            connection.commit()
        finally:
            connection.close()

        legacy_store = SQLiteStore(database_path)
        legacy_store.initialize()
        existing = legacy_store.get_user_by_email("existente@example.com")
        self.assertEqual(existing["rol"], "cliente")
        self.assertIsNone(existing["password_hash"])
        self.assertEqual(existing["token_version"], 0)
        with legacy_store.connect(write=True) as migrated:
            migrated.execute(
                """
                INSERT INTO usuarios (nombre, correo, direccion, rol)
                VALUES ('Auditor', 'auditor@example.com', '', 'auditor')
                """
            )
            self.assertEqual(migrated.execute("PRAGMA foreign_key_check").fetchall(), [])
        temporary.cleanup()

    def test_role_permissions_and_customer_order_isolation(self):
        unauthenticated = self.app.test_client()
        self.assertEqual(unauthenticated.get("/pedidos").status_code, 401)
        self.assertEqual(
            unauthenticated.get(
                "/pedidos", headers={"Authorization": "Bearer token-invalido"}
            ).status_code,
            401,
        )
        self.assertEqual(
            unauthenticated.post(
                "/usuarios",
                json={
                    "nombre": "Atacante",
                    "correo": "atacante@example.com",
                    "password": "cliente-123",
                    "rol": "admin",
                },
            ).status_code,
            401,
        )

        first_user, first_headers = self.register_customer("primero@example.com")
        second_user, second_headers = self.register_customer("segundo@example.com")

        first_order = unauthenticated.post(
            "/pedidos",
            json={"productos": [{"producto_id": 1, "cantidad": 1}]},
            headers=first_headers,
        )
        second_order = unauthenticated.post(
            "/pedidos",
            json={"productos": [{"producto_id": 2, "cantidad": 1}]},
            headers=second_headers,
        )
        self.assertEqual(first_order.status_code, 201)
        self.assertEqual(second_order.status_code, 201)
        self.assertEqual(first_order.json["pedido"]["usuario_id"], first_user["id"])
        self.assertEqual(second_order.json["pedido"]["usuario_id"], second_user["id"])

        self.assertEqual(
            len(unauthenticated.get("/pedidos", headers=first_headers).json["pedidos"]),
            1,
        )
        self.assertEqual(
            unauthenticated.get(
                f"/pedidos/{first_order.json['pedido']['id']}",
                headers=second_headers,
            ).status_code,
            404,
        )
        self.assertEqual(
            unauthenticated.get(
                f"/pedidos/{first_order.json['pedido']['id']}/historial",
                headers=second_headers,
            ).status_code,
            404,
        )
        self.assertEqual(
            unauthenticated.patch(
                f"/pedidos/{first_order.json['pedido']['id']}/estado",
                json={"estado": "En camino"},
                headers=first_headers,
            ).status_code,
            403,
        )
        self.assertEqual(
            unauthenticated.get(
                "/reportes/ventas", headers=first_headers
            ).status_code,
            403,
        )
        self.assertEqual(
            unauthenticated.get("/actividades", headers=first_headers).status_code,
            403,
        )
        self.assertEqual(
            unauthenticated.post(
                "/actividades",
                json={"tipo": "nota", "descripcion": "No autorizado"},
                headers=first_headers,
            ).status_code,
            403,
        )
        self.assertEqual(len(self.client.get("/pedidos").json["pedidos"]), 2)

    def test_product_crud_is_admin_only(self):
        _, customer_headers = self.register_customer("producto@example.com")
        unauthenticated = self.app.test_client()
        product = {
            "nombre": "Producto de prueba",
            "precio": 7000,
            "stock": 5,
            "categoria": "Pruebas",
        }
        self.assertEqual(
            unauthenticated.post("/productos", json=product).status_code, 401
        )
        self.assertEqual(
            unauthenticated.post(
                "/productos", json=product, headers=customer_headers
            ).status_code,
            403,
        )

        created = self.client.post("/productos", json=product)
        self.assertEqual(created.status_code, 201)
        product_id = created.json["producto"]["id"]
        updated = self.client.patch(
            f"/productos/{product_id}", json={"stock": 9, "precio": 8000}
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json["producto"]["stock"], 9)
        self.assertEqual(updated.json["producto"]["precio"], 8000)
        deleted = self.client.delete(f"/productos/{product_id}")
        self.assertEqual(deleted.status_code, 200)
        self.assertFalse(deleted.json["producto"]["activo"])

    def test_register_prevents_case_insensitive_duplicate_emails(self):
        first = self.client.post(
            "/auth/registro",
            json={
                "nombre": "Primera",
                "correo": "Persona@example.com",
                "password": "secreto123",
            },
        )
        second = self.client.post(
            "/auth/registro",
            json={
                "nombre": "Segunda",
                "correo": " persona@EXAMPLE.com ",
                "password": "secreto456",
            },
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 409)

    def test_admin_role_changes_revoke_existing_tokens(self):
        user, old_headers = self.register_customer("promocion@example.com")
        updated = self.client.post(
            "/usuarios",
            json={
                "nombre": user["nombre"],
                "correo": user["correo"],
                "direccion": user["direccion"],
                "password": "admin-updated-pass",
                "rol": "admin",
            },
        )
        self.assertEqual(updated.status_code, 200)

        unauthenticated = self.app.test_client()
        self.assertEqual(
            unauthenticated.get("/auth/perfil", headers=old_headers).status_code,
            401,
        )
        new_login = unauthenticated.post(
            "/auth/login",
            json={
                "correo": "promocion@example.com",
                "password": "admin-updated-pass",
            },
        )
        self.assertEqual(new_login.status_code, 200)
        self.assertEqual(new_login.json["usuario"]["rol"], "admin")

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
                "password": "cliente-123",
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
                    "password": "cliente-123",
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
                self, _action, _actor, _description, _data, _order_id=None
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
                headers={"Authorization": f"Bearer {self.admin_token}"},
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

    def test_health_reports_mongo_failure_without_exposing_credentials(self):
        uri = "mongodb+srv://test-user:<db_password>@cluster.example"
        with self.assertLogs("backend.app", level="ERROR") as captured:
            with patch.object(
                self.mongo.client.admin,
                "command",
                side_effect=PyMongoError(f"Connection failed for {uri}"),
            ):
                response = self.client.get("/salud")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json["estado"], "error")
        self.assertEqual(response.json["sqlite"], "conectado")
        self.assertEqual(response.json["mongodb"], "error")
        self.assertNotIn("<db_password>", response.get_data(as_text=True))
        self.assertNotIn("<db_password>", "\n".join(captured.output))

    def test_app_requires_mongo_uri_only(self):
        with patch.dict(
            os.environ,
            {
                "MONGODB_URI": "",
                "JWT_SECRET_KEY": "test-key-for-mongo-setup-and-configuration",
            },
        ):
            with self.assertRaisesRegex(RuntimeError, "MONGODB_URI"):
                create_app()

    def test_app_requires_a_configured_jwt_secret_outside_testing(self):
        with patch.dict(os.environ, {"JWT_SECRET_KEY": ""}):
            with self.assertRaisesRegex(RuntimeError, "JWT_SECRET_KEY"):
                create_app(
                    {"TESTING": False},
                    sqlite_store=self.sqlite,
                    mongo=self.mongo,
                )

    def test_connection_module_requires_atlas_uri_without_exposing_credentials(self):
        with patch.dict(os.environ, {"MONGODB_URI": ""}):
            with self.assertRaisesRegex(
                RuntimeError, "Cluster0 > Connect > Drivers"
            ):
                create_mongo_store()


class SQLiteMigrationTests(unittest.TestCase):
    def test_existing_user_rows_receive_auth_columns_without_data_loss(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "legacy.db"
            connection = sqlite3.connect(database_path)
            connection.execute(
                """
                CREATE TABLE usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT NOT NULL,
                    correo TEXT NOT NULL UNIQUE,
                    direccion TEXT NOT NULL DEFAULT ''
                )
                """
            )
            connection.execute(
                "INSERT INTO usuarios (nombre, correo, direccion) VALUES (?, ?, ?)",
                ("Cliente anterior", "anterior@example.com", "Calle 5"),
            )
            connection.commit()
            connection.close()

            store = SQLiteStore(database_path)
            store.initialize()
            user = store.get_user_by_email("ANTERIOR@example.com")
            self.assertEqual(user["nombre"], "Cliente anterior")
            self.assertEqual(user["direccion"], "Calle 5")
            self.assertEqual(user["rol"], "cliente")
            self.assertIsNone(user["password_hash"])
            self.assertEqual(user["token_version"], 0)

            with self.assertRaisesRegex(RequestError, "correo ya está registrado"):
                store.create_user(
                    "Duplicado",
                    " ANTERIOR@example.com ",
                    "Calle 6",
                    generate_password_hash("password"),
                )


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

                def publish_outbox_event(
                    self, event_id, _collection, _document
                ):
                    if self.fail_once:
                        self.fail_once = False
                        raise PyMongoError(
                            "test connection failure for "
                            "mongodb+srv://test-user:<db_password>@cluster.example"
                        )
                    self.documents.add(str(event_id))

            mongo = FailOnceMongo()
            with self.assertLogs("backend.services.events", level="ERROR"):
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
            self.assertNotIn("<db_password>", error["error"])

            self.assertEqual(publish_pending_events(store, mongo), 1)
            self.assertEqual(publish_pending_events(store, mongo), 0)
            self.assertEqual(store.pending_event_count(), 0)
            self.assertEqual(len(mongo.documents), 1)


if __name__ == "__main__":
    unittest.main()
