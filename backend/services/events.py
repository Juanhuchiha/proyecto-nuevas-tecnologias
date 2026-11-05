import logging

from pymongo.errors import PyMongoError

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
            sqlite_store.mark_event_failed(event_id, str(error))
            logger.exception(
                "No se pudo publicar el evento %s en MongoDB; queda pendiente de reintento.",
                event_id,
            )
            continue
        sqlite_store.mark_event_published(event_id)
        published += 1
    return published
