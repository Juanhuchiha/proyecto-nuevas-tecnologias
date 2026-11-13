import logging

from pymongo.errors import PyMongoError

from backend.database.mongo_connection import sanitize_mongo_error

logger = logging.getLogger(__name__)


def publish_pending_events(sqlite_store, mongo):
    published = 0
    for event in sqlite_store.pending_events():
        event_id = event["id"]
        try:
            mongo.publish_outbox_event(
                event_id, event["coleccion"], event["documento"]
            )
        except PyMongoError as error:
            safe_error = sanitize_mongo_error(error)
            sqlite_store.mark_event_failed(event_id, safe_error)
            logger.error(
                "No se pudo publicar el evento %s en MongoDB; queda pendiente de reintento: %s",
                event_id,
                safe_error,
            )
            continue
        sqlite_store.mark_event_published(event_id)
        published += 1
    return published
