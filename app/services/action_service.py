from collections.abc import Callable

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.integrations.gmail.client import GmailGateway
from app.models.classification import Classification
from app.models.enums import Category, Priority
from app.models.mailbox import Mailbox
from app.models.message import Message
from app.repositories.action_log_repo import ActionLogRepository
from app.repositories.mailbox_repo import MailboxRepository

LABEL_PREFIX = "AI/"
# Never delete: spam and newsletters are labeled and archived, so they stay recoverable.
ARCHIVE_CATEGORIES = {Category.NEWSLETTER.value, Category.SPAM.value}
STAR_PRIORITIES = {Priority.HIGH.value, Priority.URGENT.value}


class ActionService:
    """Applies the label/archive/star policy for a classification to Gmail."""

    def __init__(
        self,
        db: Session,
        mailboxes: MailboxRepository,
        action_log: ActionLogRepository,
        gmail_factory: Callable[[Mailbox], GmailGateway],
    ):
        self.db = db
        self.mailboxes = mailboxes
        self.action_log = action_log
        self.gmail_factory = gmail_factory

    def apply(self, message: Message, classification: Classification) -> list[str]:
        if message.actions_applied:
            return []
        mailbox = self.mailboxes.get(message.mailbox_id)
        if not mailbox:
            raise NotFoundError(f"Mailbox {message.mailbox_id} not found")
        gmail = self.gmail_factory(mailbox)

        label_name = f"{LABEL_PREFIX}{classification.category.title()}"
        add = [gmail.get_or_create_label(label_name)]
        remove: list[str] = []
        applied = ["label_applied"]
        detail = {"label": label_name}

        plan = message.action_plan or {}
        add.extend(gmail.get_or_create_label(name) for name in plan.get("labels", []))
        add = list(dict.fromkeys(add))
        if classification.category in ARCHIVE_CATEGORIES or plan.get("archive"):
            remove.append("INBOX")
            applied.append("archived")
        if plan.get("priority", classification.priority) in STAR_PRIORITIES:
            add.append("STARRED")
            applied.append("starred")

        gmail.modify_labels(message.gmail_id, add, remove)

        for action in applied:
            self.action_log.add(message.id, action, detail)
        message.label_ids = sorted((set(message.label_ids) | set(add)) - set(remove))
        message.actions_applied = True
        self.db.commit()
        return applied
