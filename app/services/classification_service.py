from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import NotFoundError
from app.integrations.llm.classifier import Classifier
from app.models.classification import Classification
from app.models.enums import Category, ClassificationSource, MessageStatus, Priority
from app.models.message import Message
from app.repositories.action_log_repo import ActionLogRepository
from app.repositories.classification_repo import ClassificationRepository


class ClassificationService:
    def __init__(
        self,
        db: Session,
        classifier: Classifier,
        classifications: ClassificationRepository,
        action_log: ActionLogRepository,
        settings: Settings,
    ):
        self.db = db
        self.classifier = classifier
        self.classifications = classifications
        self.action_log = action_log
        self.settings = settings

    def get(self, classification_id: int) -> Classification:
        row = self.classifications.get(classification_id)
        if not row:
            raise NotFoundError(f"Classification {classification_id} not found")
        return row

    def latest(self, message_id: int) -> Classification | None:
        return self.classifications.latest_for_message(message_id)

    def classify_and_store(self, message: Message) -> Classification:
        existing = self.latest(message.id)
        if existing:
            return existing
        result = self.classifier.classify(
            sender=message.sender,
            subject=message.subject,
            body_text=message.body_text,
            has_unsubscribe=message.has_unsubscribe,
        )
        row = self.classifications.add(
            Classification(
                message_id=message.id,
                category=result.category.value,
                priority=result.priority.value,
                confidence=result.confidence,
                reason=result.reason,
                source=ClassificationSource.AI.value,
                model=self.classifier.model_name,
                prompt_version=self.classifier.prompt_version,
            )
        )
        self.action_log.add(
            message.id,
            "classified",
            {"category": row.category, "priority": row.priority, "confidence": row.confidence},
        )
        self.db.commit()
        return row

    def queue_for_review(self, message: Message, suggestion: Classification) -> None:
        """Idempotent: safe to call again when the graph node re-runs on resume."""
        if message.status == MessageStatus.NEEDS_REVIEW.value:
            return
        message.status = MessageStatus.NEEDS_REVIEW.value
        self.action_log.add(
            message.id,
            "queued_for_review",
            {"suggested_category": suggestion.category, "confidence": suggestion.confidence},
        )
        self.db.commit()

    def record_human_decision(
        self, message: Message, category: Category, priority: Priority | None
    ) -> Classification:
        previous = self.classifications.latest_for_message(message.id)
        if previous and previous.source == ClassificationSource.HUMAN.value:
            message.status = MessageStatus.PROCESSING.value
            self.db.commit()
            return previous
        row = self.classifications.add(
            Classification(
                message_id=message.id,
                category=category.value,
                priority=(
                    priority.value
                    if priority
                    else (previous.priority if previous else Priority.NORMAL.value)
                ),
                confidence=1.0,
                reason="Set by human reviewer",
                source=ClassificationSource.HUMAN.value,
            )
        )
        message.status = MessageStatus.PROCESSING.value
        self.action_log.add(
            message.id,
            "human_review",
            {
                "category": row.category,
                "priority": row.priority,
                "ai_category": previous.category if previous else None,
            },
            actor="human",
        )
        self.db.commit()
        return row

    def finish(self, message):
        message.status = MessageStatus.DONE.value
        message.next_attempt_at = None
        self.db.commit()
