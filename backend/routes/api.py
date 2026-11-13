import logging
import sqlite3
from datetime import date, datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import current_app, g, jsonify, request
from pymongo.errors import PyMongoError
from werkzeug.security import check_password_hash, generate_password_hash

from backend.database.mongo_connection import sanitize_mongo_error
from backend.models.errors import RequestError
from backend.services.events import publish_pending_events

ORDER_STATUSES = {"Listo para recoger", "En camino", "Entregado"}
MAX_PAGE_SIZE = 100


def json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, (jsonify({"error": "El cuerpo debe ser un objeto JSON válido."}), 400)
    return data, None


def valid_email(value):
    if not isinstance(value, str):
        return False
    email = value.strip()
    if not email or any(character.isspace() for character in email):
        return False
    local, separator, domain = email.partition("@")
    return bool(
        separator
        and local
        and domain
        and "." in domain
        and not domain.startswith(".")
        and not domain.endswith(".")
    )


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


def product_fields(data, partial=False):
    allowed = {
        "nombre",
        "precio",
        "stock",
        "categoria",
        "descripcion",
        "imagen",
        "activo",
    }
    unknown = set(data) - allowed
    if unknown:
        raise RequestError(
            "La solicitud contiene campos que no se pueden modificar.",
            400,
            {"campos": sorted(unknown)},
        )

    fields = {}
    for key in ("nombre", "categoria"):
        if key in data:
            value = data[key]
            if not isinstance(value, str) or not value.strip():
                raise RequestError(f"El campo '{key}' debe ser texto no vacío.", 400)
            fields[key] = value.strip()
        elif not partial:
            raise RequestError(f"El campo '{key}' es obligatorio.", 400)

    for key in ("precio", "stock"):
        if key in data:
            value = data[key]
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise RequestError(f"El campo '{key}' debe ser un entero no negativo.", 400)
            fields[key] = value
        elif not partial:
            raise RequestError(f"El campo '{key}' es obligatorio.", 400)

    for key in ("descripcion", "imagen"):
        if key in data:
            if not isinstance(data[key], str):
                raise RequestError(f"El campo '{key}' debe ser texto.", 400)
            fields[key] = data[key].strip()
        elif not partial:
            fields[key] = ""

    if "activo" in data:
        if not isinstance(data["activo"], bool):
            raise RequestError("El campo 'activo' debe ser booleano.", 400)
        fields["activo"] = data["activo"]
    elif not partial:
        fields["activo"] = True

    return fields


def validate_references(sqlite_store, fields):
    user_id = fields.get("usuario_id")
    if user_id is not None and not sqlite_store.user_exists(user_id):
        raise RequestError("No existe el usuario indicado.", 404)
    order_id = fields.get("pedido_id")
    if order_id is not None and sqlite_store.get_order(order_id) is None:
        raise RequestError("No existe el pedido indicado.", 404)


def _sanitize_user(user):
    if user is None:
        return None
    payload = dict(user)
    payload.pop("password_hash", None)
    payload.pop("token_version", None)
    return payload


def _issue_token(user):
    expiry = datetime.now(timezone.utc) + timedelta(
        hours=current_app.config["JWT_ACCESS_TOKEN_EXPIRES_HOURS"]
    )
    return jwt.encode(
        {
            "sub": str(user["id"]),
            "email": user["correo"],
            "ver": user["token_version"],
            "exp": expiry,
        },
        current_app.config["JWT_SECRET_KEY"],
        algorithm="HS256",
    )


def _read_authorized_user(app, sqlite_store):
    token = request.headers.get("Authorization", "")
    if not token:
        raise RequestError("Se requiere un token JWT válido para esta operación.", 401)
    if not token.startswith("Bearer "):
        raise RequestError("El encabezado 'Authorization' debe usar el formato 'Bearer <token>'.", 401)
    jwt_token = token.split(" ", 1)[1].strip()
    if not jwt_token:
        raise RequestError("El token JWT está vacío.", 401)
    try:
        payload = jwt.decode(
            jwt_token,
            app.config["JWT_SECRET_KEY"],
            algorithms=["HS256"],
            options={"require": ["exp", "sub", "ver"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise RequestError("El token JWT ha expirado.", 401) from exc
    except jwt.InvalidTokenError as exc:
        raise RequestError("El token JWT es inválido.", 401) from exc

    raw_subject = payload.get("sub")
    user_id = None
    if isinstance(raw_subject, str) and raw_subject.isdigit():
        user_id = int(raw_subject)
    elif isinstance(raw_subject, int) and not isinstance(raw_subject, bool):
        user_id = raw_subject
    user = sqlite_store.get_user_by_id(user_id)
    if user is None:
        raise RequestError("El usuario asociado al token no existe.", 401)
    token_version = payload.get("ver")
    if (
        not isinstance(token_version, int)
        or isinstance(token_version, bool)
        or token_version != user["token_version"]
    ):
        raise RequestError("La sesión ya no es válida. Inicia sesión nuevamente.", 401)
    return user


def _require_roles(app, sqlite_store, *roles):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = _read_authorized_user(app, sqlite_store)
            if roles and user.get("rol") not in roles:
                raise RequestError("No tienes permisos para realizar esta acción.", 403)
            g.current_user = user
            return func(*args, **kwargs)
        return wrapper
    return decorator


def register_routes(app, sqlite_store, mongo):
    @app.post("/auth/registro")
    def auth_registro():
        data, error = json_body()
        if error:
            return error

        nombre = data.get("nombre")
        correo = data.get("correo")
        direccion = data.get("direccion", "")
        password = data.get("password")
        if not isinstance(nombre, str) or not nombre.strip():
            return jsonify({"error": "El campo 'nombre' es obligatorio."}), 400
        if not valid_email(correo):
            return jsonify({"error": "Ingresa un correo válido en el campo 'correo'."}), 400
        if not isinstance(direccion, str):
            return jsonify({"error": "El campo 'direccion' debe ser texto."}), 400
        if not isinstance(password, str) or len(password) < 6:
            return jsonify({"error": "La contraseña debe tener al menos 6 caracteres."}), 400
        if sqlite_store.get_user_by_email(correo.strip().lower()) is not None:
            return jsonify({"error": "El correo ya está registrado."}), 409

        user = sqlite_store.create_user(
            nombre.strip(),
            correo.strip().lower(),
            direccion,
            generate_password_hash(password),
            "cliente",
        )
        token = _issue_token(user)
        return jsonify({"usuario": _sanitize_user(user), "token": token}), 201

    @app.post("/auth/login")
    def auth_login():
        data, error = json_body()
        if error:
            return error

        correo = data.get("correo")
        password = data.get("password")
        if not valid_email(correo):
            return jsonify({"error": "Ingresa un correo válido en el campo 'correo'."}), 400
        if not isinstance(password, str) or not password:
            return jsonify({"error": "La contraseña es obligatoria."}), 400

        user = sqlite_store.get_user_by_email(correo.strip().lower())
        if user is None or not user.get("password_hash"):
            return jsonify({"error": "Credenciales inválidas."}), 401
        if not check_password_hash(user["password_hash"], password):
            return jsonify({"error": "Credenciales inválidas."}), 401

        token = _issue_token(user)
        return jsonify({"token": token, "usuario": _sanitize_user(user)})

    @app.get("/auth/perfil")
    @_require_roles(app, sqlite_store, "cliente", "admin", "repartidor", "auditor")
    def auth_perfil():
        return jsonify({"usuario": _sanitize_user(g.current_user)})

    @app.post("/auth/logout")
    @_require_roles(app, sqlite_store, "cliente", "admin", "repartidor", "auditor")
    def auth_logout():
        sqlite_store.revoke_user_tokens(g.current_user["id"])
        return jsonify({"mensaje": "Sesión cerrada correctamente."})

    @app.get("/salud")
    def health():
        sqlite_status = "conectado"
        mongo_status = "conectado"
        pending_events = None

        try:
            with sqlite_store.connect():
                pass
            pending_events = sqlite_store.pending_event_count()
        except sqlite3.Error as error:
            app.logger.error("Error al comprobar SQLite: %s", error)
            sqlite_status = "error"

        try:
            mongo.client.admin.command("ping")
        except PyMongoError as error:
            app.logger.error(
                "Error al comprobar MongoDB: %s", sanitize_mongo_error(error)
            )
            mongo_status = "error"

        response = {
            "estado": (
                "ok"
                if sqlite_status == "conectado" and mongo_status == "conectado"
                else "error"
            ),
            "sqlite": sqlite_status,
            "mongodb": mongo_status,
        }
        if pending_events is not None:
            response["eventos_pendientes"] = pending_events
        status_code = 200 if response["estado"] == "ok" else 503
        return jsonify(response), status_code

    @app.get("/productos")
    def obtener_productos():
        return jsonify({"productos": sqlite_store.list_products()})

    @app.post("/productos")
    @_require_roles(app, sqlite_store, "admin")
    def crear_producto():
        data, error = json_body()
        if error:
            return error
        product = sqlite_store.create_product(product_fields(data))
        return jsonify({"producto": product}), 201

    @app.patch("/productos/<int:product_id>")
    @_require_roles(app, sqlite_store, "admin")
    def actualizar_producto(product_id):
        data, error = json_body()
        if error:
            return error
        product = sqlite_store.update_product(
            product_id, product_fields(data, partial=True)
        )
        return jsonify({"producto": product})

    @app.delete("/productos/<int:product_id>")
    @_require_roles(app, sqlite_store, "admin")
    def eliminar_producto(product_id):
        product = sqlite_store.deactivate_product(product_id)
        return jsonify(
            {"mensaje": "Producto desactivado correctamente.", "producto": product}
        )

    @app.post("/usuarios")
    @_require_roles(app, sqlite_store, "admin")
    def crear_usuario():
        data, error = json_body()
        if error:
            return error

        name = data.get("nombre")
        email = data.get("correo")
        address = data.get("direccion", "")
        password = data.get("password")
        role = data.get("rol", "cliente")
        if not isinstance(name, str) or not name.strip():
            return jsonify({"error": "El campo 'nombre' es obligatorio."}), 400
        if not valid_email(email):
            return jsonify({"error": "Ingresa un correo válido en el campo 'correo'."}), 400
        if not isinstance(address, str):
            return jsonify({"error": "El campo 'direccion' debe ser texto."}), 400
        if not isinstance(role, str) or role not in {
            "cliente",
            "admin",
            "repartidor",
            "auditor",
        }:
            return jsonify(
                {
                    "error": (
                        "El rol debe ser 'cliente', 'admin', 'repartidor' o 'auditor'."
                    )
                }
            ), 400

        password_hash = None
        if password is not None:
            if not isinstance(password, str) or len(password) < 6:
                return jsonify(
                    {"error": "La contraseña debe tener al menos 6 caracteres."}
                ), 400
            password_hash = generate_password_hash(password)
        elif sqlite_store.get_user_by_email(email.strip().lower()) is None:
            return jsonify({"error": "La contraseña es obligatoria."}), 400

        user, status = sqlite_store.create_or_update_user(
            name.strip(),
            email.strip().lower(),
            address,
            password_hash,
            role,
        )
        return jsonify({"usuario": _sanitize_user(user)}), status

    @app.post("/pedidos")
    @_require_roles(app, sqlite_store, "cliente", "admin")
    def crear_pedido():
        data, error = json_body()
        if error:
            return error

        auth_user = g.current_user
        user_id = data.get("usuario_id")
        if auth_user["rol"] == "cliente":
            if user_id is not None and user_id != auth_user["id"]:
                return jsonify(
                    {"error": "Solo puedes crear pedidos para tu propia cuenta."}
                ), 403
            user_id = auth_user["id"]
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
    @_require_roles(app, sqlite_store, "cliente", "admin", "repartidor", "auditor")
    def listar_pedidos():
        auth_user = g.current_user
        if auth_user["rol"] == "cliente":
            orders = [
                order
                for order in sqlite_store.list_orders()
                if order["usuario_id"] == auth_user["id"]
            ]
            return jsonify({"pedidos": orders})
        return jsonify({"pedidos": sqlite_store.list_orders()})

    @app.get("/pedidos/<int:order_id>")
    @_require_roles(app, sqlite_store, "cliente", "admin", "repartidor", "auditor")
    def obtener_pedido(order_id):
        order = sqlite_store.get_order(order_id)
        if order is None:
            return jsonify({"error": "No se encontró el pedido."}), 404

        auth_user = g.current_user
        if auth_user["rol"] == "cliente" and order["usuario_id"] != auth_user["id"]:
            return jsonify({"error": "No se encontró el pedido."}), 404
        return jsonify({"pedido": order})

    @app.patch("/pedidos/<int:order_id>/estado")
    @_require_roles(app, sqlite_store, "admin", "repartidor")
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
        actor = {
            "id": g.current_user["id"],
            "nombre": g.current_user["nombre"],
        }

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
    @_require_roles(app, sqlite_store, "cliente", "admin", "repartidor", "auditor")
    def historial_pedido(order_id):
        order = sqlite_store.get_order(order_id)
        if order is None:
            return jsonify({"error": "No se encontró el pedido."}), 404

        auth_user = g.current_user
        if auth_user["rol"] == "cliente" and order["usuario_id"] != auth_user["id"]:
            return jsonify({"error": "No se encontró el pedido."}), 404

        if auth_user["rol"] == "auditor":
            pending = sqlite_store.pending_event_count(order_id=order_id) > 0
        else:
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
    @_require_roles(app, sqlite_store, "admin", "auditor")
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
    @_require_roles(app, sqlite_store, "admin")
    def crear_actividad():
        data, error = json_body()
        if error:
            return error
        fields = activity_fields(data)
        fields["responsable"] = g.current_user["nombre"]
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
        except PyMongoError as error:
            app.logger.error(
                "La actividad %s se guardó, pero falló su registro de auditoría: %s",
                result["id"],
                sanitize_mongo_error(error),
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
    @_require_roles(app, sqlite_store, "admin", "auditor")
    def obtener_actividad(activity_id):
        activity = mongo.get_activity(activity_id)
        if activity is None:
            return jsonify({"error": "No se encontró la actividad."}), 404
        return jsonify({"actividad": activity})

    @app.patch("/actividades/<activity_id>")
    @_require_roles(app, sqlite_store, "admin")
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
                g.current_user["nombre"],
                f"Se actualizó la actividad {activity_id}.",
                {"actividad_id": activity_id, "campos": sorted(updates)},
                activity.get("pedido_id"),
            )
        except PyMongoError as error:
            app.logger.error(
                "La actividad %s se actualizó, pero falló su registro de auditoría: %s",
                activity_id,
                sanitize_mongo_error(error),
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
    @_require_roles(app, sqlite_store, "admin")
    def eliminar_actividad(activity_id):
        activity = mongo.get_activity(activity_id)
        if activity is None:
            return jsonify({"error": "No se encontró la actividad."}), 404
        if not mongo.delete_activity(activity_id):
            return jsonify({"error": "No se encontró la actividad."}), 404
        try:
            mongo.log_system_action(
                "actividad_eliminada",
                g.current_user["nombre"],
                f"Se eliminó la actividad {activity_id}.",
                {"actividad_id": activity_id},
                activity.get("pedido_id"),
            )
        except PyMongoError as error:
            app.logger.error(
                "La actividad %s se eliminó, pero falló su registro de auditoría: %s",
                activity_id,
                sanitize_mongo_error(error),
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
    @_require_roles(app, sqlite_store, "admin")
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
    @_require_roles(app, sqlite_store, "admin", "auditor")
    def reporte_ventas():
        start_date = request.args.get("desde")
        end_date = request.args.get("hasta")
        for field_name, value in (("desde", start_date), ("hasta", end_date)):
            if value is not None:
                try:
                    parsed_date = date.fromisoformat(value)
                except ValueError as exc:
                    raise RequestError(
                        f"El filtro '{field_name}' debe usar el formato YYYY-MM-DD.",
                        400,
                    ) from exc
                if parsed_date.isoformat() != value:
                    raise RequestError(
                        f"El filtro '{field_name}' debe usar el formato YYYY-MM-DD.",
                        400,
                    )
        if start_date and end_date and start_date > end_date:
            raise RequestError(
                "El filtro 'desde' no puede ser posterior a 'hasta'.", 400
            )
        return jsonify(sqlite_store.sales_report(start_date, end_date))

    @app.get("/reportes/inventario")
    @_require_roles(app, sqlite_store, "admin", "auditor")
    def reporte_inventario():
        return jsonify(sqlite_store.inventory_report())



def _flush_events(sqlite_store, mongo):
    try:
        publish_pending_events(sqlite_store, mongo)
        return sqlite_store.pending_event_count() > 0
    except sqlite3.Error:
        logging.getLogger(__name__).exception(
            "No se pudo confirmar la publicación de eventos; quedan disponibles para reintento."
        )
        return True
