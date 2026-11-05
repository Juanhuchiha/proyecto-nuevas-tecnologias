import os

from pymongo.errors import PyMongoError

from backend.database.persistence import MongoStore


def create_mongo_store(uri=None, database_name=None):
    mongo_uri = uri or os.getenv("MONGODB_URI")
    if not mongo_uri:
        raise RuntimeError(
            "Falta MONGODB_URI. Cópiala desde MongoDB Atlas: "
            "Cluster0 > Connect > Drivers."
        )

    mongo_database = database_name or os.getenv("MONGODB_DATABASE", "mesa_roja")
    mongo_store = MongoStore(mongo_uri, mongo_database)
    try:
        mongo_store.check_connection()
    except PyMongoError:
        mongo_store.close()
        raise
    return mongo_store
