from sqlalchemy import select, or_
from datetime import UTC, datetime
from sqlalchemy.orm import Session

from app.models.message import Message


class MessageRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, message_id: int) -> Message | None:
        return self.db.get(Message, message_id)

    def get_by_gmail_id(self, mailbox_id: int, gmail_id: str) -> Message | None:
        return self.db.scalar(
            select(Message).where(Message.mailbox_id == mailbox_id, Message.gmail_id == gmail_id)
        )

    def list(
        self,
        *,
        status: str | None = None,
        mailbox_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Message]:
        stmt = select(Message).order_by(Message.received_at.desc(), Message.id.desc())
        if status:
            stmt = stmt.where(Message.status == status)
        if mailbox_id:
            stmt = stmt.where(Message.mailbox_id == mailbox_id)
        return list(self.db.scalars(stmt.limit(limit).offset(offset)))

    def add(self, message: Message) -> Message:
        self.db.add(message)
        self.db.flush()
        return message

    def runnable(self, max_attempts, limit=200):
        return list(self.db.scalars(select(Message).where(
            Message.status.in_(["new", "processing", "failed"]),
            or_(Message.status == "processing", Message.attempts < max_attempts),
            or_(Message.next_attempt_at.is_(None), Message.next_attempt_at <= datetime.now(UTC)),
        ).order_by(Message.id).limit(limit)))
