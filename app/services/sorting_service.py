import logging
from datetime import UTC, datetime, timedelta
from app.core.exceptions import ConflictError, NotFoundError
from app.core.locks import operation_lock
from app.models.enums import MessageStatus

log = logging.getLogger(__name__)


def _config(message_id):
    return {"configurable": {"thread_id": f"msg-{message_id}"}}

class SortingService:
    def __init__(self, db, graph, messages, action_log, settings):
        self.db, self.graph, self.messages, self.action_log, self.settings = db, graph, messages, action_log, settings

    def process(self, message_id, manual=False):
        with operation_lock(self.db, 1, message_id):
            message = self.messages.get(message_id)
            if not message:
                raise NotFoundError("Message not found")
            self.db.refresh(message)
            if message.status in ("done", "needs_review"):
                return message.status
            if not manual and message.attempts >= self.settings.max_processing_attempts:
                if message.status == "processing":
                    message.status = "failed"
                    self.action_log.add(message_id, "retry_exhausted")
                    self.db.commit()
                return message.status
            if manual:
                message.attempts = 0
                self.action_log.add(message_id, "retry_requested", actor="human")
            snapshot = self.graph.get_state(_config(message_id))
            # Crash after persisting the review status but before interrupt checkpoint:
            # a human resume can fall back to starting from persisted classification.
            if any(getattr(task, "interrupts", ()) for task in snapshot.tasks):
                message.status = "needs_review"
                self.db.commit()
                return message.status
            message.status = "processing"
            message.attempts += 1
            message.next_attempt_at = None
            self.db.commit()
            try:
                initial = None if snapshot.next else {"message_id": message_id}
                self.graph.invoke(initial, _config(message_id))
            except Exception as exc:
                self._mark_failed(message_id, exc)
                return "failed"
            self.db.refresh(message)
            return message.status

    def resume(self, message_id, category, priority):
        from langgraph.types import Command
        with operation_lock(self.db, 1, message_id):
            message = self.messages.get(message_id)
            if not message:
                raise NotFoundError("Message not found")
            self.db.refresh(message)
            if message.status != "needs_review":
                raise ConflictError("Message is not awaiting review")
            config = _config(message_id)
            decision = {"category": category.value, "priority": priority.value if priority else None}
            message.status = "processing"
            self.db.commit()
            try:
                snapshot = self.graph.get_state(config)
                if not any(getattr(task, "interrupts", ()) for task in snapshot.tasks):
                    self.graph.invoke(None if snapshot.next else {"message_id": message_id}, config)
                self.graph.invoke(Command(resume=decision), config)
            except Exception as exc:
                self._mark_failed(message_id, exc)
                return "failed"
            self.db.refresh(message)
            return message.status

    def _mark_failed(self, message_id, exc):
        # Never persist raw provider errors: they can contain email content or tokens.
        log.error("sorting failed message_id=%s error_type=%s", message_id, type(exc).__name__)
        self.db.rollback()
        message = self.messages.get(message_id)
        message.status = MessageStatus.FAILED.value
        delay = min(3600, self.settings.retry_base_seconds * 2 ** max(0, message.attempts - 1))
        message.next_attempt_at = datetime.now(UTC) + timedelta(seconds=delay)
        self.action_log.add(message_id, "failed", {"error_type": type(exc).__name__})
        self.db.commit()
