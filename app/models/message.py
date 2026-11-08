from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import MessageStatus
from app.models.mailbox import utcnow


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("mailbox_id", "gmail_id", name="uq_message_mailbox_gmail"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    mailbox_id: Mapped[int] = mapped_column(
        ForeignKey("mailboxes.id", ondelete="CASCADE"), index=True
    )
    gmail_id: Mapped[str] = mapped_column(String(64))
    thread_id: Mapped[str] = mapped_column(String(64), index=True)
    sender: Mapped[str] = mapped_column(String(512))
    subject: Mapped[str] = mapped_column(Text, default="")
    body_text: Mapped[str] = mapped_column(Text, default="")
    has_unsubscribe: Mapped[bool] = mapped_column(default=False)
    label_ids: Mapped[list] = mapped_column(JSON, default=list)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default=MessageStatus.NEW.value, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    headers: Mapped[dict] = mapped_column(JSON, default=dict)
    entities: Mapped[dict | None] = mapped_column(JSON)
    action_plan: Mapped[dict | None] = mapped_column(JSON)
    actions_applied: Mapped[bool] = mapped_column(default=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    mailbox = relationship("Mailbox", back_populates="messages")
    classifications = relationship(
        "Classification",
        back_populates="message",
        order_by="Classification.id",
        cascade="all, delete-orphan",
    )
    actions = relationship(
        "ActionLog",
        back_populates="message",
        order_by="ActionLog.id",
        cascade="all, delete-orphan",
    )
