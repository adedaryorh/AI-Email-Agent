from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.classification import Classification


class ClassificationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, classification_id: int) -> Classification | None:
        return self.db.get(Classification, classification_id)

    def latest_for_message(self, message_id: int) -> Classification | None:
        return self.db.scalar(
            select(Classification)
            .where(Classification.message_id == message_id)
            .order_by(Classification.id.desc())
            .limit(1)
        )

    def add(self, classification: Classification) -> Classification:
        self.db.add(classification)
        self.db.flush()
        return classification
