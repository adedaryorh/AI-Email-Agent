from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.mailbox import Mailbox


class MailboxRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, mailbox_id: int) -> Mailbox | None:
        return self.db.get(Mailbox, mailbox_id)

    def get_by_email(self, email: str) -> Mailbox | None:
        return self.db.scalar(select(Mailbox).where(Mailbox.email == email))

    def list(self) -> list[Mailbox]:
        return list(self.db.scalars(select(Mailbox).order_by(Mailbox.id)))

    def add(self, mailbox: Mailbox) -> Mailbox:
        self.db.add(mailbox)
        self.db.flush()
        return mailbox
