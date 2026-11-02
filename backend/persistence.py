import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pymongo import ASCENDING, DESCENDING, MongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError
from bson import ObjectId
from bson.errors import InvalidId

from backend.catalog import PRODUCTS

logger = logging.getLogger(__name__)
ENVIO_COP = 5000


class RequestError(Exception):
    def __init__(self, message, status_code, details=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class PostgresStore:
    def __init__(self, dsn):
        self.dsn = dsn

    def connect(self):
        return psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=5)

    def initialize(self):
        schema_path = Path(__file__).with_name("schema.sql")
        with self.connect() as connection:
            schema = schema_path.read_text(encoding="utf-8")
            for statement in schema.split(";"):
                if statement.strip():
                    connection.execute(statement)
            connection.executemany(
                """
                INSERT INTO productos
                    (id, nombre, precio, stock, categoria, descripcion, imagen, activo)
                VALUES
                    (%(id)s, %(nombre)s, %(precio)s, %(stock)s, %(categoria)s,
                     %(descripcion)s, %(imagen)s, %(activo)s)
                ON CONFLICT (id) DO NOTHING
                """,
                PRODUCTS,
            )

    def list_products(self):
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, nombre, precio, stock, categoria, descripcion, imagen, activo
                FROM productos ORDER BY id
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def create_or_update_user(self, name, email, address):
        with self.connect() as connection:
            row = connection.execute(
                """
                INSERT INTO usuarios (nombre, correo, direccion)
                VALUES (%s, %s, %s)
                ON CONFLICT (correo) DO UPDATE
                    SET nombre = EXCLUDED.nombre, direccion = EXCLUDED.direccion
                RETURNING id, nombre, correo, direccion, (xmax = 0) AS creado
                """,
                (name, email, address),
            ).fetchone()
        user = {key: row[key] for key in ("id", "nombre", "correo", "direccion")}
        return user, 201 if row["creado"] else 200

    def user_exists(self, user_id):
        with self.connect() as connection:
            return connection.execute(
                "SELECT 1 FROM usuarios WHERE id = %s", (user_id,)
            ).fetchone() is not None

    def create_order(self, user_id, address, quantities):
        with self.connect() as connection:
            user = connection.execute(
                "SELECT id, nombre, correo, direccion FROM usuarios WHERE id = %s FOR SHARE",
                (user_id,),
            ).fetchone()
            if user is None:
                raise RequestError("No existe el usuario indicado.", 404)

            products = connection.execute(
                """
                SELECT id, nombre, precio, stock, activo
                FROM productos WHERE id = ANY(%s) ORDER BY id FOR UPDATE
                """,
                (list(quantities),),
            ).fetchall()
            products_by_id = {row["id"]: row for row in products}
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
            order_row = connection.execute(
                """
                INSERT INTO pedidos
                    (usuario_id, direccion, subtotal, envio, total, moneda, estado)
                VALUES (%s, %s, %s, %s, %s, 'COP', 'Listo para recoger')
                RETURNING id, creado_en
                """,
                (user_id, destination, subtotal, shipping, subtotal + shipping),
            ).fetchone()
            order_id = order_row["id"]

            for item in line_items:
                connection.execute(
                    "UPDATE productos SET stock = %s WHERE id = %s",
                    (item["stock_restante"], item["producto_id"]),
                )
                connection.execute(
                    """
                    INSERT INTO detalles_pedido
                        (pedido_id, producto_id, nombre, cantidad, precio_unitario,
                         total, stock_restante)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
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

            created_at = order_row["creado_en"].isoformat()
            initial_status = "Listo para recoger"
            self._enqueue(
                connection,
                "historial_pedidos",
                {
                    "pedido_id": order_id,
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
            "INSERT INTO cola_eventos (id, coleccion, documento) VALUES (%s, %s, %s)",
            (uuid.uuid4(), collection, Jsonb(document)),
        )

    def get_order(self, order_id):
        orders = self._get_orders("WHERE p.id = %s", (order_id,))
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
            details = connection.execute(
                """
                SELECT pedido_id, producto_id, nombre, cantidad, precio_unitario,
                       total, stock_restante
                FROM detalles_pedido WHERE pedido_id = ANY(%s)
                ORDER BY id
                """,
                (order_ids,),
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
            order["creado_en"] = row["creado_en"].isoformat()
            result.append(order)
        return result

    def update_order_status(self, order_id, new_status, actor):
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT p.estado, p.usuario_id, u.nombre AS cliente_nombre
                FROM pedidos AS p JOIN usuarios AS u ON u.id = p.usuario_id
                WHERE p.id = %s FOR UPDATE OF p
                """,
                (order_id,),
            ).fetchone()
            if row is None:
                raise RequestError("No se encontró el pedido.", 404)

            if row["estado"] != new_status:
                updated = connection.execute(
                    """
                    UPDATE pedidos SET estado = %s
                    WHERE id = %s RETURNING NOW() AS actualizado_en
                    """,
                    (new_status, order_id),
                ).fetchone()
                event_time = updated["actualizado_en"].isoformat()
                event_user = actor
                self._enqueue(
                    connection,
                    "historial_pedidos",
                    {
                        "pedido_id": order_id,
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
                        "tipo": "estado_pedido_actualizado",
                        "usuario": event_user or {"nombre": "No identificado"},
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
            return connection.execute(
                """
                SELECT id, coleccion, documento FROM cola_eventos
                WHERE publicado_en IS NULL ORDER BY creado_en
                LIMIT %s
                """,
                (limit,),
            ).fetchall()

    def mark_event_published(self, event_id):
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE cola_eventos
                SET publicado_en = NOW(), ultimo_error = NULL
                WHERE id = %s AND publicado_en IS NULL
                """,
                (event_id,),
            )

    def mark_event_failed(self, event_id, error):
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE cola_eventos
                SET intentos = intentos + 1, ultimo_error = %s
                WHERE id = %s AND publicado_en IS NULL
                """,
                (error[:1000], event_id),
            )

    def pending_event_count(self, order_id=None):
        with self.connect() as connection:
            if order_id is None:
                row = connection.execute(
                    "SELECT COUNT(*) AS total FROM cola_eventos WHERE publicado_en IS NULL"
                ).fetchone()
            else:
                row = connection.execute(
                    """
                    SELECT COUNT(*) AS total FROM cola_eventos
                    WHERE publicado_en IS NULL
                      AND documento->>'pedido_id' = %s
                    """,
                    (str(order_id),),
                ).fetchone()
        return row["total"]

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
        result = self.database["actividades_usuarios"].insert_one(document)
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


def publish_pending_events(postgres, mongo):
    published = 0
    for event in postgres.pending_events():
        event_id = event["id"]
        try:
            mongo.publish_outbox_event(
                event_id, event["coleccion"], event["documento"]
            )
        except PyMongoError as error:
            postgres.mark_event_failed(event_id, str(error))
            logger.exception(
                "No se pudo publicar el evento %s en MongoDB; queda pendiente de reintento.",
                event_id,
            )
            continue
        postgres.mark_event_published(event_id)
        published += 1
    return published
