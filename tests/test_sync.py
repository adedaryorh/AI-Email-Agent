from app.core.config import get_settings
from app.core.exceptions import ExternalServiceError
from app.integrations.gmail.client import HistoryExpired
from app.repositories.mailbox_repo import MailboxRepository
from app.repositories.message_repo import MessageRepository
from app.services.sync_service import SyncService
from tests.test_parser import b64
from tests.conftest import FakeGmail
import pytest

class SyncGmail(FakeGmail):
    def list_message_ids(self, query, max_results):
        assert max_results == 0  # initial sync must exhaust pagination
        return [f"new-{i}" for i in range(105)]

    def get_message(self, message_id):
        return {"id": message_id, "threadId": message_id, "labelIds": ["INBOX"], "internalDate": "1700000000000", "payload": {"mimeType": "text/plain", "body": {"data": b64("hello")}, "headers": [{"name": "From", "value": "a@b.com"}]}}

    def list_history(self, cursor):
        return ["new-1"], "101"


def service(db, gmail):
    return SyncService(db, MailboxRepository(db), MessageRepository(db), lambda _: gmail, get_settings())


def test_sync_imports_all_initial_pages_and_deduplicates(db, message):
    svc = service(db, SyncGmail())
    assert len(svc.sync_mailbox(message.mailbox_id)) == 105
    assert svc.sync_mailbox(message.mailbox_id) == []
    assert message.mailbox.history_id == "101"


def test_history_expiry_falls_back_to_initial_sync(db, message):
    class Gmail(SyncGmail):
        def list_history(self, cursor):
            raise HistoryExpired("expired")
    message.mailbox.history_id = "old"
    db.commit()
    assert len(service(db, Gmail()).sync_mailbox(message.mailbox_id)) == 105
    assert message.mailbox.history_id == "100"


def test_sync_failure_does_not_advance_cursor(db, message):
    class Gmail(SyncGmail):
        def get_message(self, message_id):
            raise ExternalServiceError("failure")
    with pytest.raises(ExternalServiceError):
        service(db, Gmail()).sync_mailbox(message.mailbox_id)
    db.rollback()
    assert message.mailbox.history_id is None
