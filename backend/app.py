import os
import sqlite3
from pathlib import Path

from flask import Flask, jsonify
from flask_cors import CORS
from pymongo.errors import PyMongoError

from backend.config import load_environment
from backend.database.mongo_connection import create_mongo_store
from backend.database.persistence import SQLiteStore
from backend.models.errors import RequestError
from backend.routes.api import register_routes

load_environment()


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
        mongo_client = create_mongo_store()
        sqlite_store = SQLiteStore(
            app.config.get("SQLITE_DATABASE_PATH")
            or os.getenv("SQLITE_DATABASE_PATH")
        )
        try:
            sqlite_store.initialize()
        except sqlite3.Error:
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

    register_routes(app, sqlite_store, mongo)
    return app


if __name__ == "__main__":
    create_app().run(
        host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=False
    )
