"""Polling + durable database work queue. Postgres is the queue; Redis is unnecessary."""
import logging
import signal
from threading import Event
from app.container import build_services
from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.exceptions import ConflictError
from app.core.logging import setup_logging
from app.repositories.message_repo import MessageRepository
from app.graph.checkpointer import close_checkpointer

log = logging.getLogger(__name__)
stop = Event()


def run_once():
    with get_session_factory()() as db:
        svc = build_services(db)
        try:
            mailbox_ids = [m.id for m in svc.mailboxes.list()]
            for mailbox_id in mailbox_ids:
                try:
                    svc.sync.sync_mailbox(mailbox_id)
                except ConflictError:
                    db.rollback()
                except Exception as exc:
                    db.rollback()
                    log.error("sync failed mailbox_id=%s error_type=%s", mailbox_id, type(exc).__name__)
            # Processing continues even when Gmail sync is temporarily unavailable.
            ids = [m.id for m in MessageRepository(db).runnable(get_settings().max_processing_attempts)]
            for message_id in ids:
                try:
                    svc.sorting.process(message_id)
                except ConflictError:
                    db.rollback()
                except Exception as exc:
                    db.rollback()
                    log.error("worker failed message_id=%s error_type=%s", message_id, type(exc).__name__)
        finally:
            svc.mailboxes.close()


def main():
    setup_logging()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    try:
        while not stop.is_set():
            try:
                run_once()
            except Exception as exc:
                log.error("poll cycle failed error_type=%s", type(exc).__name__)
            stop.wait(get_settings().poll_interval_seconds)
    finally:
        close_checkpointer()

if __name__ == "__main__":
    main()
