import os
import re

from pymongo.errors import PyMongoError

from backend.database.persistence import MongoStore


def sanitize_mongo_error(error, mongo_uri=None):
    message = str(error)
    configured_uri = mongo_uri or os.getenv("MONGODB_URI")
    if configured_uri:
        scheme, separator, remainder = configured_uri.partition("://")
        credentials, delimiter, host = remainder.rpartition("@")
        if separator and delimiter and ":" in credentials:
            username = credentials.split(":", 1)[0]
            redacted_uri = f"{scheme}://{username}:***@{host}"
            message = message.replace(configured_uri, redacted_uri)
    return re.sub(
        r"(?i)(mongodb(?:\+srv)?://[^:/@\s]+:)[^@\s]*@",
        r"\1***@",
        message,
    )


def create_mongo_store(uri=None, database_name=None):
    mongo_uri = uri or os.getenv("MONGODB_URI")
    if not mongo_uri:
        raise RuntimeError(
            "Falta MONGODB_URI. Cópiala desde MongoDB Atlas: "
            "Cluster0 > Connect > Drivers."
        )

    mongo_database = database_name or os.getenv("MONGODB_DATABASE", "mesa_roja")
    mongo_store = None
    try:
        mongo_store = MongoStore(mongo_uri, mongo_database)
        mongo_store.check_connection()
    except PyMongoError as error:
        if mongo_store is not None:
            mongo_store.close()
        raise RuntimeError(
            "No se pudo conectar con MongoDB: "
            f"{sanitize_mongo_error(error, mongo_uri)}"
        ) from None
    return mongo_store
