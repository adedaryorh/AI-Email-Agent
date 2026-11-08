from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.classification import Classification
from app.models.enums import Category, MessageStatus, Priority
from app.models.message import Message
from app.repositories.message_repo import MessageRepository
from app.services.classification_service import ClassificationService
from app.services.sorting_service import SortingService


class ReviewService:
    def __init__(
        self,
        db: Session,
        messages: MessageRepository,
        classification: ClassificationService,
        sorting: SortingService,
    ):
        self.db = db
        self.messages = messages
        self.classification = classification
        self.sorting = sorting

    def pending(self, limit: int = 50, offset: int = 0) -> list[tuple[Message, Classification | None]]:
        rows = self.messages.list(status=MessageStatus.NEEDS_REVIEW.value, limit=limit, offset=offset)
        return [(m, self.classification.latest(m.id)) for m in rows]

    def resolve(self, message_id: int, category: Category, priority: Priority | None) -> Message:
        message = self.messages.get(message_id)
        if not message:
            raise NotFoundError(f"Message {message_id} not found")
        self.sorting.resume(message_id, category, priority)
        self.db.refresh(message)
        return message
