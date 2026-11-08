import logging
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.locks import operation_lock
from app.core.exceptions import NotFoundError
from app.integrations.gmail.client import GmailGateway, GmailNotFound, HistoryExpired
from app.integrations.gmail.parser import parse_message
from app.models.mailbox import Mailbox
from app.models.message import Message
from app.repositories.mailbox_repo import MailboxRepository
from app.repositories.message_repo import MessageRepository
from app.schemas.email import ParsedEmail

log = logging.getLogger(__name__)


class SyncService:
    """Pulls new inbox mail from Gmail into the messages table (idempotent)."""

    def __init__(
        self,
        db: Session,
        mailboxes: MailboxRepository,
        messages: MessageRepository,
        gmail_factory: Callable[[Mailbox], GmailGateway],
        settings: Settings,
    ):
        self.db = db
        self.mailboxes = mailboxes
        self.messages = messages
        self.gmail_factory = gmail_factory
        self.settings = settings

    def sync_mailbox(self, mailbox_id: int) -> list[int]:
        with operation_lock(self.db, 2, mailbox_id):
            self.db.expire_all()
            return self._sync_mailbox(mailbox_id)

    def _sync_mailbox(self, mailbox_id: int) -> list[int]:
        """Returns the internal ids of newly stored messages."""
        mailbox = self.mailboxes.get(mailbox_id)
        if not mailbox:
            raise NotFoundError(f"Mailbox {mailbox_id} not found")

        gmail = self.gmail_factory(mailbox)
        gmail_ids, new_history_id = self._discover(gmail, mailbox)

        new_ids: list[int] = []
        for gmail_id in gmail_ids:
            if self.messages.get_by_gmail_id(mailbox.id, gmail_id):
                continue
            try:
                parsed = parse_message(gmail.get_message(gmail_id))
            except GmailNotFound:
                continue  # deleted between listing and fetch
            if not self._is_inbound(parsed):
                continue
            stored = self.messages.add(
                Message(
                    mailbox_id=mailbox.id,
                    gmail_id=parsed.gmail_id,
                    thread_id=parsed.thread_id,
                    sender=parsed.sender,
                    subject=parsed.subject,
                    body_text=parsed.body_text,
                    has_unsubscribe=parsed.has_unsubscribe,
                    label_ids=parsed.label_ids,
                    headers=parsed.headers,
                    received_at=parsed.received_at,
                )
            )
            new_ids.append(stored.id)

        mailbox.history_id = new_history_id
        mailbox.last_synced_at = datetime.now(UTC)
        self.db.commit()
        log.info("synced mailbox=%s new_messages=%d", mailbox.email, len(new_ids))
        return new_ids

    def _discover(self, gmail: GmailGateway, mailbox: Mailbox) -> tuple[list[str], str]:
        if mailbox.history_id:
            try:
                return gmail.list_history(mailbox.history_id)
            except HistoryExpired:
                log.warning("history expired for %s, doing full resync", mailbox.email)
        # Capture the cursor BEFORE listing so nothing arriving mid-sync is missed.
        history_id = str(gmail.get_profile()["historyId"])
        query = f"in:inbox newer_than:{self.settings.sync_initial_days}d"
        return gmail.list_message_ids(query, 0), history_id

    @staticmethod
    def _is_inbound(email: ParsedEmail) -> bool:
        labels = set(email.label_ids)
        return "INBOX" in labels and not labels & {"SENT", "DRAFT"}
