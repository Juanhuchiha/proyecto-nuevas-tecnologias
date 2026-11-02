import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from pymongo.errors import PyMongoError

from backend.persistence import (
    MongoStore,
    RequestError,
    SQLiteStore,
    publish_pending_events,
)

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

ORDER_STATUSES = {"Listo para recoger", "En camino", "Entregado"}
MAX_PAGE_SIZE = 100


def json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, (jsonify({"error": "El cuerpo debe ser un objeto JSON válido."}), 400)
    return data, None


def optional_integer(value, field_name):
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise RequestError(f"El campo '{field_name}' debe ser un entero positivo.", 400)
    return value


def activity_fields(data, partial=False):
    allowed = {
        "tipo",
        "descripcion",
        "usuario_id",
        "pedido_id",
        "datos",
        "responsable",
    }
    unknown = set(data) - allowed
    if unknown:
        raise RequestError(
            "La solicitud contiene campos que no se pueden modificar.",
            400,
            {"campos": sorted(unknown)},
        )

    fields = {}
    for key in ("tipo", "descripcion"):
        if key in data:
            value = data[key]
            if not isinstance(value, str) or not value.strip():
                raise RequestError(f"El campo '{key}' debe ser texto no vacío.", 400)
            fields[key] = value.strip()
        elif not partial:
            raise RequestError(f"El campo '{key}' es obligatorio.", 400)

    for key in ("usuario_id", "pedido_id"):
        if key in data:
            fields[key] = optional_integer(data[key], key)
        elif not partial:
            fields[key] = None

    if "datos" in data:
        if not isinstance(data["datos"], dict):
            raise RequestError("El campo 'datos' debe ser un objeto JSON.", 400)
        fields["datos"] = data["datos"]
    elif not partial:
        fields["datos"] = {}

    if "responsable" in data:
        responsible = data["responsable"]
        if not isinstance(responsible, str) or not responsible.strip():
            raise RequestError("El campo 'responsable' debe ser texto no vacío.", 400)
        fields["responsable"] = responsible.strip()
    elif not partial:
        fields["responsable"] = "No identificado"

    return fields


def validate_references(sqlite_store, fields):
    user_id = fields.get("usuario_id")
    if user_id is not None and not sqlite_store.user_exists(user_id):
        raise RequestError("No existe el usuario indicado.", 404)
    order_id = fields.get("pedido_id")
    if order_id is not None and sqlite_store.get_order(order_id) is None:
        raise RequestError("No existe el pedido indicado.", 404)


def create_app(settings=None, sqlite_store=None, mongo=None):
    app = Flask(__name__)
    app.config.update(settings or {})
    CORS(
        app,
        resources={
            r"/*": {
                "origins": [
                    origin.strip()
                    for origin in os.getenv(
                        "CORS_ORIGINS",
                        "http://localhost:5173,http://127.0.0.1:5173",
                    ).split(",")
                    if origin.strip()
                ]
            }
        },
    )

    mongo_client = None
    if sqlite_store is None and mongo is None:
        mongodb_uri = os.getenv("MONGODB_URI")
        if not mongodb_uri:
            raise RuntimeError(
                "Falta la variable de entorno MONGODB_URI. "
                "Configúrala a partir de .env.example."
            )

        sqlite_store = SQLiteStore(
            app.config.get("SQLITE_DATABASE_PATH")
            or os.getenv("SQLITE_DATABASE_PATH")
        )
        mongo_client = MongoStore(
            mongodb_uri, os.getenv("MONGODB_DATABASE", "mesa_roja")
        )
        try:
            sqlite_store.initialize()
            mongo_client.check_connection()
        except (sqlite3.Error, PyMongoError):
            mongo_client.close()
            raise
        mongo = mongo_client
    elif sqlite_store is None or mongo is None:
        raise ValueError("Las dependencias de SQLite y MongoDB deben configurarse juntas.")

    app.extensions["sqlite_store"] = sqlite_store
    app.extensions["mongo_store"] = mongo
    app.extensions["mongo_client"] = mongo_client

    @app.errorhandler(RequestError)
    def handle_request_error(error):
        return jsonify({"error": error.message, **error.details}), error.status_code

    @app.errorhandler(sqlite3.Error)
    def handle_sqlite_error(error):
        app.logger.exception("Error al operar con SQLite")
        return jsonify({"error": "No se pudo completar la operación en SQLite."}), 503

    @app.errorhandler(PyMongoError)
    def handle_mongo_error(error):
        app.logger.exception("Error al operar con MongoDB")
        return jsonify({"error": "No se pudo completar la operación en MongoDB."}), 503

    @app.get("/salud")
    def health():
        with sqlite_store.connect():
            pass
        mongo.client.admin.command("ping")
        return jsonify(
            {
                "estado": "ok",
                "sqlite": "conectado",
                "mongodb": "conectado",
                "eventos_pendientes": sqlite_store.pending_event_count(),
            }
        )

    @app.get("/productos")
    def obtener_productos():
        return jsonify({"productos": sqlite_store.list_products()})

    @app.post("/usuarios")
    def crear_usuario():
        data, error = json_body()
        if error:
            return error

        name = data.get("nombre")
        email = data.get("correo")
        address = data.get("direccion", "")
        if not isinstance(name, str) or not name.strip():
            return jsonify({"error": "El campo 'nombre' es obligatorio."}), 400
        if not isinstance(email, str) or "@" not in email:
            return jsonify({"error": "Ingresa un correo válido en el campo 'correo'."}), 400
        if not isinstance(address, str):
            return jsonify({"error": "El campo 'direccion' debe ser texto."}), 400

        user, status = sqlite_store.create_or_update_user(
            name.strip(), email.strip().lower(), address
        )
        return jsonify({"usuario": user}), status

    @app.post("/pedidos")
    def crear_pedido():
        data, error = json_body()
        if error:
            return error

        user_id = data.get("usuario_id")
        if not isinstance(user_id, int) or isinstance(user_id, bool):
            return jsonify({"error": "El campo 'usuario_id' debe ser un entero."}), 400
        requested_items = data.get("productos")
        if not isinstance(requested_items, list) or not requested_items:
            return jsonify({"error": "El pedido debe incluir al menos un producto."}), 400

        quantities = {}
        for item in requested_items:
            if not isinstance(item, dict):
                return jsonify({"error": "Cada producto debe ser un objeto."}), 400
            product_id = item.get("producto_id")
            quantity = item.get("cantidad")
            if (
                not isinstance(product_id, int)
                or isinstance(product_id, bool)
                or not isinstance(quantity, int)
                or isinstance(quantity, bool)
                or quantity < 1
            ):
                return jsonify(
                    {
                        "error": (
                            "Cada producto necesita 'producto_id' y una 'cantidad' "
                            "entera mayor a cero."
                        )
                    }
                ), 400
            quantities[product_id] = quantities.get(product_id, 0) + quantity

        address = data.get("direccion", "")
        if not isinstance(address, str):
            return jsonify({"error": "El campo 'direccion' debe ser texto."}), 400
        order = sqlite_store.create_order(user_id, address, quantities)
        pending = _flush_events(sqlite_store, mongo)
        response = {"pedido": order}
        if pending:
            response["advertencia"] = (
                "El pedido quedó guardado en SQLite; sus eventos están en la "
                "cola de reintentos y se publicarán cuando MongoDB esté disponible."
            )
        return jsonify(response), 201

    @app.get("/pedidos")
    def listar_pedidos():
        return jsonify({"pedidos": sqlite_store.list_orders()})

    @app.get("/pedidos/<int:order_id>")
    def obtener_pedido(order_id):
        order = sqlite_store.get_order(order_id)
        if order is None:
            return jsonify({"error": "No se encontró el pedido."}), 404
        return jsonify({"pedido": order})

    @app.patch("/pedidos/<int:order_id>/estado")
    def actualizar_estado_pedido(order_id):
        data, error = json_body()
        if error:
            return error
        status = data.get("estado")
        if not isinstance(status, str) or status not in ORDER_STATUSES:
            return jsonify(
                {
                    "error": "El estado debe ser 'Listo para recoger', 'En camino' o 'Entregado'."
                }
            ), 400
        actor = data.get("usuario")
        if actor is not None and (
            not isinstance(actor, dict)
            or not isinstance(actor.get("nombre"), str)
            or not actor["nombre"].strip()
        ):
            return jsonify({"error": "El campo 'usuario' debe incluir un nombre válido."}), 400
        if actor is not None:
            actor_id = actor.get("id")
            if actor_id is not None and (
                not isinstance(actor_id, int) or isinstance(actor_id, bool) or actor_id < 1
            ):
                return jsonify({"error": "El identificador del usuario no es válido."}), 400
            if actor_id is not None and not sqlite_store.user_exists(actor_id):
                return jsonify({"error": "No existe el usuario responsable indicado."}), 404

        order = sqlite_store.update_order_status(order_id, status, actor)
        pending = _flush_events(sqlite_store, mongo)
        response = {"pedido": order}
        if pending:
            response["advertencia"] = (
                "El cambio quedó guardado en SQLite; el evento se reintentará "
                "cuando MongoDB esté disponible."
            )
        return jsonify(response)

    @app.get("/pedidos/<int:order_id>/historial")
    def historial_pedido(order_id):
        order = sqlite_store.get_order(order_id)
        if order is None:
            return jsonify({"error": "No se encontró el pedido."}), 404

        pending = _flush_events(sqlite_store, mongo)
        if pending and sqlite_store.pending_event_count(order_id=order_id):
            return jsonify(
                {
                    "error": (
                        "El pedido está en SQLite, pero sus eventos aún no se "
                        "han podido consultar en MongoDB."
                    )
                }
            ), 503
        events = mongo.order_history(order_id)
        return jsonify({"pedido": order, **events})

    @app.get("/actividades")
    def listar_actividades():
        filters = {}
        for parameter, field in (("usuario_id", "usuario_id"), ("pedido_id", "pedido_id")):
            value = request.args.get(parameter)
            if value is not None:
                try:
                    filters[field] = int(value)
                except ValueError:
                    raise RequestError(f"El filtro '{parameter}' debe ser un entero.", 400)
                if filters[field] < 1:
                    raise RequestError(f"El filtro '{parameter}' debe ser positivo.", 400)

        raw_limit = request.args.get("limite", "50")
        try:
            limit = int(raw_limit)
        except ValueError:
            raise RequestError("El filtro 'limite' debe ser un entero.", 400)
        if not 1 <= limit <= MAX_PAGE_SIZE:
            raise RequestError(
                f"El filtro 'limite' debe estar entre 1 y {MAX_PAGE_SIZE}.", 400
            )
        return jsonify({"actividades": mongo.list_activities(filters, limit)})

    @app.post("/actividades")
    def crear_actividad():
        data, error = json_body()
        if error:
            return error
        fields = activity_fields(data)
        validate_references(sqlite_store, fields)
        activity = {
            **fields,
            "fecha": datetime.now(timezone.utc).isoformat(),
        }
        result = mongo.create_activity(activity)
        try:
            mongo.log_system_action(
                "actividad_creada",
                fields["responsable"],
                f"Se registró la actividad {result['id']}.",
                {"actividad_id": result["id"], "tipo_actividad": fields["tipo"]},
                fields.get("pedido_id"),
            )
        except PyMongoError:
            app.logger.exception(
                "La actividad %s se guardó, pero falló su registro de auditoría.",
                result["id"],
            )
            return jsonify(
                {
                    "error": (
                        "La actividad se guardó, pero no se pudo registrar la auditoría. "
                        "Consulta la actividad antes de repetir la solicitud."
                    ),
                    "actividad": result,
                }
            ), 503
        return jsonify({"actividad": result}), 201

    @app.get("/actividades/<activity_id>")
    def obtener_actividad(activity_id):
        activity = mongo.get_activity(activity_id)
        if activity is None:
            return jsonify({"error": "No se encontró la actividad."}), 404
        return jsonify({"actividad": activity})

    @app.patch("/actividades/<activity_id>")
    def actualizar_actividad(activity_id):
        data, error = json_body()
        if error:
            return error
        updates = activity_fields(data, partial=True)
        if not updates:
            return jsonify({"error": "Incluye al menos un campo para actualizar."}), 400
        validate_references(sqlite_store, updates)
        activity = mongo.update_activity(activity_id, updates)
        if activity is None:
            return jsonify({"error": "No se encontró la actividad."}), 404
        try:
            mongo.log_system_action(
                "actividad_actualizada",
                updates.get("responsable", activity.get("responsable")),
                f"Se actualizó la actividad {activity_id}.",
                {"actividad_id": activity_id, "campos": sorted(updates)},
                activity.get("pedido_id"),
            )
        except PyMongoError:
            app.logger.exception(
                "La actividad %s se actualizó, pero falló su registro de auditoría.",
                activity_id,
            )
            return jsonify(
                {
                    "error": (
                        "La actividad se actualizó, pero no se pudo registrar la auditoría. "
                        "Consulta el recurso antes de repetir la solicitud."
                    ),
                    "actividad": activity,
                }
            ), 503
        return jsonify({"actividad": activity})

    @app.delete("/actividades/<activity_id>")
    def eliminar_actividad(activity_id):
        activity = mongo.get_activity(activity_id)
        if activity is None:
            return jsonify({"error": "No se encontró la actividad."}), 404
        if not mongo.delete_activity(activity_id):
            return jsonify({"error": "No se encontró la actividad."}), 404
        responsable = request.args.get("responsable", "No identificado").strip()
        try:
            mongo.log_system_action(
                "actividad_eliminada",
                responsable or "No identificado",
                f"Se eliminó la actividad {activity_id}.",
                {"actividad_id": activity_id},
                activity.get("pedido_id"),
            )
        except PyMongoError:
            app.logger.exception(
                "La actividad %s se eliminó, pero falló su registro de auditoría.",
                activity_id,
            )
            return jsonify(
                {
                    "error": (
                        "La actividad se eliminó, pero no se pudo registrar la auditoría."
                    )
                }
            ), 503
        return jsonify({"mensaje": "Actividad eliminada correctamente."})

    @app.post("/eventos/pendientes/reintentar")
    def reintentar_eventos():
        published = 0
        try:
            published = publish_pending_events(sqlite_store, mongo)
            pending_count = sqlite_store.pending_event_count()
        except sqlite3.Error:
            app.logger.exception("No se pudo procesar la cola de eventos.")
            return jsonify({"error": "No se pudo consultar la cola de eventos."}), 503
        return jsonify(
            {"publicados": published, "pendientes": pending_count}
        )

    @app.get("/reportes/ventas")
    def reporte_ventas():
        return jsonify(sqlite_store.sales_report())

    return app


def _flush_events(sqlite_store, mongo):
    try:
        publish_pending_events(sqlite_store, mongo)
        return sqlite_store.pending_event_count() > 0
    except sqlite3.Error:
        logging.getLogger(__name__).exception(
            "No se pudo confirmar la publicación de eventos; quedan disponibles para reintento."
        )
        return True


if __name__ == "__main__":
    create_app().run(
        host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=False
    )
