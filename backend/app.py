from itertools import count

from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(
    app,
    resources={
        r"/*": {
            "origins": [
                "http://localhost:5173",
                "http://127.0.0.1:5173",
            ]
        }
    },
)

productos = [
    {
        "id": 1,
        "nombre": "Burger La Konrad",
        "precio": 18900,
        "stock": 18,
        "categoria": "Hamburguesas",
        "descripcion": "Carne, queso, lechuga y tomate.",
        "imagen": "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=500",
        "activo": True,
    },
    {
        "id": 2,
        "nombre": "Hamburguesa Doble Carne",
        "precio": 24500,
        "stock": 12,
        "categoria": "Hamburguesas",
        "descripcion": "Doble carne, doble queso y salsa de la casa.",
        "imagen": "https://images.unsplash.com/photo-1586190848861-99aa4a171e90?w=500",
        "activo": True,
    },
    {
        "id": 3,
        "nombre": "Hamburguesa de Pollo",
        "precio": 21900,
        "stock": 10,
        "categoria": "Hamburguesas",
        "descripcion": "Pollo crujiente, lechuga y mayonesa.",
        "imagen": "https://images.unsplash.com/photo-1606755962773-d324e0a13086?w=500",
        "activo": True,
    },
    {
        "id": 4,
        "nombre": "Papas Agrandadas",
        "precio": 6500,
        "stock": 24,
        "categoria": "Acompañamientos",
        "descripcion": "Porción grande de papas fritas.",
        "imagen": "https://images.unsplash.com/photo-1573080496219-bb080dd4f877?w=500",
        "activo": True,
    },
    {
        "id": 5,
        "nombre": "Nuggets x6",
        "precio": 10500,
        "stock": 16,
        "categoria": "Acompañamientos",
        "descripcion": "Seis nuggets de pollo con salsa.",
        "imagen": "https://images.unsplash.com/photo-1562967914-608f82629710?w=500",
        "activo": True,
    },
    {
        "id": 6,
        "nombre": "Gaseosa 400ml",
        "precio": 4000,
        "stock": 30,
        "categoria": "Bebidas",
        "descripcion": "Gaseosa fría de 400 ml.",
        "imagen": "https://images.unsplash.com/photo-1622483767028-3f66f32aef97?w=500",
        "activo": True,
    },
    {
        "id": 7,
        "nombre": "Agua 600ml",
        "precio": 3500,
        "stock": 22,
        "categoria": "Bebidas",
        "descripcion": "Agua embotellada de 600 ml.",
        "imagen": "https://images.unsplash.com/photo-1534616042650-80f5c9b61f09?w=500",
        "activo": True,
    },
    {
        "id": 8,
        "nombre": "Cono de Helado",
        "precio": 5000,
        "stock": 14,
        "categoria": "Postres",
        "descripcion": "Cono con helado de vainilla.",
        "imagen": "https://images.unsplash.com/photo-1560008581-09826d1de69e?w=500",
        "activo": True,
    },
]

usuarios = []
pedidos = []
ids_usuario = count(1)
ids_pedido = count(1)
ENVIO_COP = 5000


def json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, (jsonify({"error": "El cuerpo debe ser un objeto JSON válido."}), 400)
    return data, None


@app.get("/productos")
def obtener_productos():
    return jsonify({"productos": productos})


@app.post("/usuarios")
def crear_usuario():
    data, error = json_body()
    if error:
        return error

    nombre = data.get("nombre")
    correo = data.get("correo")
    if not isinstance(nombre, str) or not nombre.strip():
        return jsonify({"error": "El campo 'nombre' es obligatorio."}), 400
    if not isinstance(correo, str) or "@" not in correo:
        return jsonify({"error": "Ingresa un correo válido en el campo 'correo'."}), 400

    correo = correo.strip().lower()
    usuario = next((item for item in usuarios if item["correo"] == correo), None)
    if usuario is None:
        usuario = {
            "id": next(ids_usuario),
            "nombre": nombre.strip(),
            "correo": correo,
            "direccion": data.get("direccion", ""),
        }
        usuarios.append(usuario)
        status_code = 201
    else:
        usuario["nombre"] = nombre.strip()
        usuario["direccion"] = data.get("direccion", usuario["direccion"])
        status_code = 200

    return jsonify({"usuario": usuario}), status_code


@app.post("/pedidos")
def crear_pedido():
    data, error = json_body()
    if error:
        return error

    usuario_id = data.get("usuario_id")
    lineas_recibidas = data.get("productos")
    if not isinstance(usuario_id, int) or isinstance(usuario_id, bool):
        return jsonify({"error": "El campo 'usuario_id' debe ser un entero."}), 400
    usuario = next((item for item in usuarios if item["id"] == usuario_id), None)
    if usuario is None:
        return jsonify({"error": "No existe el usuario indicado."}), 404
    if not isinstance(lineas_recibidas, list) or not lineas_recibidas:
        return jsonify({"error": "El pedido debe incluir al menos un producto."}), 400

    cantidades = {}
    for linea in lineas_recibidas:
        if not isinstance(linea, dict):
            return jsonify({"error": "Cada producto debe ser un objeto."}), 400
        producto_id = linea.get("producto_id")
        cantidad = linea.get("cantidad")
        if (
            not isinstance(producto_id, int)
            or isinstance(producto_id, bool)
            or not isinstance(cantidad, int)
            or isinstance(cantidad, bool)
            or cantidad < 1
        ):
            return jsonify(
                {"error": "Cada producto necesita 'producto_id' y una 'cantidad' entera mayor a cero."}
            ), 400
        cantidades[producto_id] = cantidades.get(producto_id, 0) + cantidad

    lineas_pedido = []
    subtotal = 0
    for producto_id, cantidad in cantidades.items():
        producto = next((item for item in productos if item["id"] == producto_id), None)
        if producto is None:
            return jsonify({"error": f"No existe el producto con id {producto_id}."}), 404
        if not producto["activo"]:
            return jsonify({"error": f"El producto '{producto['nombre']}' no está disponible."}), 409
        if cantidad > producto["stock"]:
            return jsonify(
                {
                    "error": f"Stock insuficiente para '{producto['nombre']}'.",
                    "stock_disponible": producto["stock"],
                }
            ), 409

        total_linea = producto["precio"] * cantidad
        subtotal += total_linea
        lineas_pedido.append(
            {
                "producto_id": producto_id,
                "nombre": producto["nombre"],
                "cantidad": cantidad,
                "precio_unitario": producto["precio"],
                "total": total_linea,
            }
        )

    direccion = data.get("direccion") or usuario["direccion"]
    envio = ENVIO_COP
    pedido = {
        "id": next(ids_pedido),
        "usuario_id": usuario_id,
        "cliente": usuario,
        "direccion": direccion,
        "productos": lineas_pedido,
        "subtotal": subtotal,
        "envio": envio,
        "total": subtotal + envio,
        "moneda": "COP",
        "estado": "Listo para recoger",
    }

    for linea in lineas_pedido:
        producto = next(item for item in productos if item["id"] == linea["producto_id"])
        producto["stock"] -= linea["cantidad"]
        linea["stock_restante"] = producto["stock"]

    pedidos.append(pedido)
    return jsonify({"pedido": pedido}), 201


@app.get("/pedidos/<int:id_pedido>")
def obtener_pedido(id_pedido):
    pedido = next((item for item in pedidos if item["id"] == id_pedido), None)
    if pedido is None:
        return jsonify({"error": "No se encontró el pedido."}), 404
    return jsonify({"pedido": pedido})


@app.get("/reportes/ventas")
def reporte_ventas():
    total_ventas = sum(pedido["total"] for pedido in pedidos)
    return jsonify(
        {
            "cantidad_pedidos": len(pedidos),
            "total_ventas": total_ventas,
            "moneda": "COP",
        }
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
