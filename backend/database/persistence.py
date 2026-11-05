import json
import logging
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ASCENDING, DESCENDING, MongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError

from backend.data.catalog import PRODUCTS
from backend.models.errors import RequestError

logger = logging.getLogger(__name__)
ENVIO_COP = 5000


class SQLiteStore:
    def __init__(self, database_path=None):
        self.database_path = Path(
            database_path
            or Path(__file__).resolve().parents[1] / "data" / "mesa_roja.db"
        ).expanduser().resolve()

    @contextmanager
    def connect(self, write=False):
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(
            str(self.database_path),
            timeout=10,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        try:
            if write:
                connection.execute("BEGIN IMMEDIATE")
            yield connection
            if connection.in_transaction:
                connection.commit()
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self):
        schema_path = Path(__file__).with_name("schema.sql")
        with self.connect() as connection:
            connection.executescript(schema_path.read_text(encoding="utf-8"))
        with self.connect(write=True) as connection:
            connection.executemany(
                """
                INSERT INTO productos
                    (id, nombre, precio, stock, categoria, descripcion, imagen, activo)
                VALUES
                    (:id, :nombre, :precio, :stock, :categoria, :descripcion, :imagen,
                     :activo)
                ON CONFLICT (id) DO NOTHING
                """,
                [
                    {**product, "activo": int(product["activo"])}
                    for product in PRODUCTS
                ],
            )

    @staticmethod
    def _product(row):
        result = dict(row)
        result["activo"] = bool(result["activo"])
        return result

    def list_products(self):
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, nombre, precio, stock, categoria, descripcion, imagen, activo
                FROM productos ORDER BY id
                """
            ).fetchall()
        return [self._product(row) for row in rows]

    def create_or_update_user(self, name, email, address):
        with self.connect(write=True) as connection:
            existing = connection.execute(
                "SELECT id FROM usuarios WHERE correo = ?", (email,)
            ).fetchone()
            row = connection.execute(
                """
                INSERT INTO usuarios (nombre, correo, direccion)
                VALUES (?, ?, ?)
                ON CONFLICT (correo) DO UPDATE
                    SET nombre = excluded.nombre, direccion = excluded.direccion
                RETURNING id, nombre, correo, direccion
                """,
                (name, email, address),
            ).fetchone()
        return dict(row), 200 if existing else 201

    def user_exists(self, user_id):
        with self.connect() as connection:
            return connection.execute(
                "SELECT 1 FROM usuarios WHERE id = ?", (user_id,)
            ).fetchone() is not None

    def create_order(self, user_id, address, quantities):
        with self.connect(write=True) as connection:
            user = connection.execute(
                "SELECT id, nombre, correo, direccion FROM usuarios WHERE id = ?",
                (user_id,),
            ).fetchone()
            if user is None:
                raise RequestError("No existe el usuario indicado.", 404)

            products = connection.execute(
                """
                SELECT id, nombre, precio, stock, activo
                FROM productos WHERE id IN ({})
                ORDER BY id
                """.format(",".join("?" for _ in quantities)),
                tuple(quantities),
            ).fetchall()
            products_by_id = {row["id"]: self._product(row) for row in products}
            line_items = []
            subtotal = 0

            for product_id, quantity in quantities.items():
                product = products_by_id.get(product_id)
                if product is None:
                    raise RequestError(f"No existe el producto con id {product_id}.", 404)
                if not product["activo"]:
                    raise RequestError(
                        f"El producto '{product['nombre']}' no está disponible.", 409
                    )
                if quantity > product["stock"]:
                    raise RequestError(
                        f"Stock insuficiente para '{product['nombre']}'.",
                        409,
                        {"stock_disponible": product["stock"]},
                    )
                line_total = product["precio"] * quantity
                subtotal += line_total
                line_items.append(
                    {
                        "producto_id": product_id,
                        "nombre": product["nombre"],
                        "cantidad": quantity,
                        "precio_unitario": product["precio"],
                        "total": line_total,
                        "stock_restante": product["stock"] - quantity,
                    }
                )

            destination = address or user["direccion"]
            shipping = ENVIO_COP
            created_at = datetime.now(timezone.utc).isoformat()
            cursor = connection.execute(
                """
                INSERT INTO pedidos
                    (usuario_id, direccion, subtotal, envio, total, moneda, estado,
                     creado_en)
                VALUES (?, ?, ?, ?, ?, 'COP', 'Listo para recoger', ?)
                """,
                (user_id, destination, subtotal, shipping, subtotal + shipping, created_at),
            )
            order_id = cursor.lastrowid

            for item in line_items:
                connection.execute(
                    "UPDATE productos SET stock = ? WHERE id = ?",
                    (item["stock_restante"], item["producto_id"]),
                )
                connection.execute(
                    """
                    INSERT INTO detalles_pedido
                        (pedido_id, producto_id, nombre, cantidad, precio_unitario,
                         total, stock_restante)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        order_id,
                        item["producto_id"],
                        item["nombre"],
                        item["cantidad"],
                        item["precio_unitario"],
                        item["total"],
                        item["stock_restante"],
                    ),
                )

            initial_status = "Listo para recoger"
            self._enqueue(
                connection,
                "historial_pedidos",
                {
                    "pedido_id": order_id,
                    "usuario_id": user_id,
                    "estado_anterior": None,
                    "estado_nuevo": initial_status,
                    "usuario": {"id": user_id, "nombre": user["nombre"]},
                    "tipo": "pedido_creado",
                    "fecha": created_at,
                    "datos": {"total": subtotal + shipping, "moneda": "COP"},
                },
            )
            self._enqueue(
                connection,
                "registros_sistema",
                {
                    "pedido_id": order_id,
                    "usuario_id": user_id,
                    "tipo": "pedido_creado",
                    "usuario": {"id": user_id, "nombre": user["nombre"]},
                    "descripcion": f"Se creó el pedido {order_id}.",
                    "fecha": created_at,
                    "datos": {"pedido_id": order_id, "total": subtotal + shipping},
                },
            )

        return {
            "id": order_id,
            "usuario_id": user_id,
            "cliente": dict(user),
            "direccion": destination,
            "productos": line_items,
            "subtotal": subtotal,
            "envio": shipping,
            "total": subtotal + shipping,
            "moneda": "COP",
            "estado": initial_status,
            "creado_en": created_at,
        }

    @staticmethod
    def _enqueue(connection, collection, document):
        connection.execute(
            """
            INSERT INTO cola_eventos
                (id, coleccion, documento, fecha_creacion)
            VALUES (?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                collection,
                json.dumps(document, ensure_ascii=False),
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    def get_order(self, order_id):
        orders = self._get_orders("WHERE p.id = ?", (order_id,))
        return orders[0] if orders else None

    def list_orders(self):
        return self._get_orders("", ())

    def _get_orders(self, where, parameters):
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT p.id, p.usuario_id, p.direccion, p.subtotal, p.envio, p.total,
                       p.moneda, p.estado, p.creado_en,
                       u.nombre AS cliente_nombre, u.correo AS cliente_correo,
                       u.direccion AS cliente_direccion
                FROM pedidos AS p JOIN usuarios AS u ON u.id = p.usuario_id
                {where}
                ORDER BY p.creado_en DESC, p.id DESC
                """,
                parameters,
            ).fetchall()
            if not rows:
                return []

            order_ids = [row["id"] for row in rows]
            placeholders = ",".join("?" for _ in order_ids)
            details = connection.execute(
                f"""
                SELECT pedido_id, producto_id, nombre, cantidad, precio_unitario,
                       total, stock_restante
                FROM detalles_pedido WHERE pedido_id IN ({placeholders})
                ORDER BY id
                """,
                order_ids,
            ).fetchall()

        items_by_order = {order_id: [] for order_id in order_ids}
        for item in details:
            items_by_order[item["pedido_id"]].append(
                {
                    "producto_id": item["producto_id"],
                    "nombre": item["nombre"],
                    "cantidad": item["cantidad"],
                    "precio_unitario": item["precio_unitario"],
                    "total": item["total"],
                    "stock_restante": item["stock_restante"],
                }
            )

        result = []
        for row in rows:
            order = {
                key: row[key]
                for key in (
                    "id",
                    "usuario_id",
                    "direccion",
                    "subtotal",
                    "envio",
                    "total",
                    "moneda",
                    "estado",
                )
            }
            order["cliente"] = {
                "id": row["usuario_id"],
                "nombre": row["cliente_nombre"],
                "correo": row["cliente_correo"],
                "direccion": row["cliente_direccion"],
            }
            order["productos"] = items_by_order[row["id"]]
            order["creado_en"] = row["creado_en"]
            result.append(order)
        return result

    def update_order_status(self, order_id, new_status, actor):
        with self.connect(write=True) as connection:
            row = connection.execute(
                """
                SELECT p.estado, p.usuario_id, u.nombre AS cliente_nombre
                FROM pedidos AS p JOIN usuarios AS u ON u.id = p.usuario_id
                WHERE p.id = ?
                """,
                (order_id,),
            ).fetchone()
            if row is None:
                raise RequestError("No se encontró el pedido.", 404)

            if row["estado"] != new_status:
                event_time = datetime.now(timezone.utc).isoformat()
                event_user = actor or {
                    "id": row["usuario_id"],
                    "nombre": row["cliente_nombre"],
                }
                connection.execute(
                    "UPDATE pedidos SET estado = ? WHERE id = ?",
                    (new_status, order_id),
                )
                self._enqueue(
                    connection,
                    "historial_pedidos",
                    {
                        "pedido_id": order_id,
                        "usuario_id": row["usuario_id"],
                        "estado_anterior": row["estado"],
                        "estado_nuevo": new_status,
                        "usuario": event_user,
                        "tipo": "estado_pedido_actualizado",
                        "fecha": event_time,
                        "datos": {},
                    },
                )
                self._enqueue(
                    connection,
                    "registros_sistema",
                    {
                        "pedido_id": order_id,
                        "usuario_id": row["usuario_id"],
                        "tipo": "estado_pedido_actualizado",
                        "usuario": event_user,
                        "descripcion": (
                            f"El pedido {order_id} cambió de "
                            f"'{row['estado']}' a '{new_status}'."
                        ),
                        "fecha": event_time,
                        "datos": {
                            "estado_anterior": row["estado"],
                            "estado_nuevo": new_status,
                        },
                    },
                )

        return self.get_order(order_id)

    def pending_events(self, limit=100):
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, coleccion, documento FROM cola_eventos
                WHERE publicado_en IS NULL ORDER BY fecha_creacion
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "coleccion": row["coleccion"],
                "documento": json.loads(row["documento"]),
            }
            for row in rows
        ]

    def mark_event_published(self, event_id):
        with self.connect(write=True) as connection:
            connection.execute(
                """
                UPDATE cola_eventos
                SET publicado_en = ?, error = NULL
                WHERE id = ? AND publicado_en IS NULL
                """,
                (datetime.now(timezone.utc).isoformat(), str(event_id)),
            )

    def mark_event_failed(self, event_id, error):
        with self.connect(write=True) as connection:
            connection.execute(
                """
                UPDATE cola_eventos
                SET intentos = intentos + 1, error = ?
                WHERE id = ? AND publicado_en IS NULL
                """,
                (error[:1000], str(event_id)),
            )

    def pending_event_count(self, order_id=None):
        with self.connect() as connection:
            if order_id is None:
                row = connection.execute(
                    "SELECT COUNT(*) AS total FROM cola_eventos WHERE publicado_en IS NULL"
                ).fetchone()
                return row["total"]

            rows = connection.execute(
                """
                SELECT documento FROM cola_eventos
                WHERE publicado_en IS NULL
                """
            ).fetchall()
        return sum(
            json.loads(row["documento"]).get("pedido_id") == order_id for row in rows
        )

    def sales_report(self):
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS cantidad_pedidos,
                       COALESCE(SUM(total), 0) AS total_ventas
                FROM pedidos
                """
            ).fetchone()
        return {
            "cantidad_pedidos": row["cantidad_pedidos"],
            "total_ventas": row["total_ventas"],
            "moneda": "COP",
        }


class MongoStore:
    COLLECTIONS = {
        "actividades_usuarios",
        "historial_pedidos",
        "registros_sistema",
    }

    def __init__(self, uri, database_name):
        self.client = MongoClient(uri, serverSelectionTimeoutMS=5000, appname="MesaRoja")
        self.database = self.client[database_name]

    def check_connection(self):
        self.client.admin.command("ping")
        self.database["historial_pedidos"].create_index(
            [("pedido_id", ASCENDING), ("fecha", DESCENDING)]
        )
        self.database["actividades_usuarios"].create_index(
            [("pedido_id", ASCENDING), ("fecha", DESCENDING)]
        )
        self.database["actividades_usuarios"].create_index(
            [("usuario_id", ASCENDING), ("fecha", DESCENDING)]
        )
        self.database["registros_sistema"].create_index(
            [("pedido_id", ASCENDING), ("fecha", DESCENDING)]
        )

    def publish_outbox_event(self, event_id, collection_name, document):
        if collection_name not in self.COLLECTIONS:
            raise ValueError(f"Colección de eventos no permitida: {collection_name}")
        payload = dict(document)
        payload["_id"] = str(event_id)
        try:
            self.database[collection_name].insert_one(payload)
        except DuplicateKeyError:
            logger.info("Evento %s ya publicado; se confirma de forma idempotente.", event_id)

    @staticmethod
    def _serialize(document):
        if document is None:
            return None
        result = dict(document)
        result["id"] = str(result.pop("_id"))
        return result

    @staticmethod
    def _object_id(identifier):
        try:
            return ObjectId(identifier)
        except (InvalidId, TypeError):
            return None

    def create_activity(self, document):
        result = self.database["actividades_usuarios"].insert_one(dict(document))
        return {"id": str(result.inserted_id), **document}

    def list_activities(self, filters, limit):
        cursor = (
            self.database["actividades_usuarios"]
            .find(filters)
            .sort("fecha", DESCENDING)
            .limit(limit)
        )
        return [self._serialize(document) for document in cursor]

    def get_activity(self, identifier):
        object_id = self._object_id(identifier)
        if object_id is None:
            return None
        document = self.database["actividades_usuarios"].find_one({"_id": object_id})
        return self._serialize(document)

    def update_activity(self, identifier, updates):
        object_id = self._object_id(identifier)
        if object_id is None:
            return None
        document = self.database["actividades_usuarios"].find_one_and_update(
            {"_id": object_id},
            {"$set": updates},
            return_document=ReturnDocument.AFTER,
        )
        return self._serialize(document)

    def delete_activity(self, identifier):
        object_id = self._object_id(identifier)
        if object_id is None:
            return False
        return (
            self.database["actividades_usuarios"].delete_one({"_id": object_id}).deleted_count
            == 1
        )

    def log_system_action(self, action, actor, description, data, order_id=None):
        document = {
            "tipo": action,
            "usuario": {"nombre": actor or "No identificado"},
            "descripcion": description,
            "fecha": datetime.now(timezone.utc).isoformat(),
            "datos": data,
        }
        if order_id is not None:
            document["pedido_id"] = order_id
        self.database["registros_sistema"].insert_one(document)

    def order_history(self, order_id):
        query = {"pedido_id": order_id}
        history = self.database["historial_pedidos"].find(query).sort("fecha", ASCENDING)
        activities = self.database["actividades_usuarios"].find(query).sort(
            "fecha", ASCENDING
        )
        logs = self.database["registros_sistema"].find(query).sort("fecha", ASCENDING)
        return {
            "historial": [self._serialize(document) for document in history],
            "actividades": [self._serialize(document) for document in activities],
            "registros_sistema": [self._serialize(document) for document in logs],
        }

    def close(self):
        self.client.close()
