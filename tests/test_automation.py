import pytest
from sqlalchemy import select
from app.core.config import get_settings
from app.core.exceptions import ConflictError
from app.models.action_log import ActionLog
from app.models.classification import Classification
from app.repositories.automation_repo import AutomationRepository
from app.repositories.message_repo import MessageRepository
from app.repositories.mailbox_repo import MailboxRepository
from app.repositories.action_log_repo import ActionLogRepository
from app.services.message_service import MessageService
from app.services.draft_service import DraftService
from app.services.rule_service import RuleService, matches
from app.schemas.automation import RuleIn, RuleDefinition, DraftReconcileIn
from tests.conftest import FakeGmail, FakeAssistant


def draft_service(db, gmail=None):
    return DraftService(db, AutomationRepository(db), MessageService(MessageRepository(db)),
        MailboxRepository(db), lambda _: gmail or FakeGmail(), FakeAssistant(),
        ActionLogRepository(db), get_settings())


def rule_input():
    return RuleIn(name="Invoice replies", definition=RuleDefinition.model_validate({
        "conditions": [{"field": "category", "op": "eq", "value": "billing"},
                       {"field": "entities.invoice_numbers", "op": "exists"}],
        "actions": [{"type": "label", "value": "AI/Invoice"}, {"type": "draft"},
                    {"type": "set_priority", "value": "high"}],
    }))


def test_rules_match_all_conditions_and_snapshot_plan(db, message):
    message.entities = {"invoice_numbers": ["INV-1"]}
    category = Classification(category="billing", priority="normal")
    service = RuleService(db, AutomationRepository(db), MessageService(MessageRepository(db)), None, ActionLogRepository(db))
    row = service.save(rule_input())
    plan = service.evaluate(message, category)
    assert plan == {"labels": ["AI/Invoice"], "archive": False, "priority": "high", "draft": True, "matched_rules": [row.id]}
    service.delete(row.id)
    assert service.evaluate(message, category) == plan
    assert not matches(rule_input().definition, message, Classification(category="sales", priority="normal"))


def test_rules_reject_unknown_fields_and_send_actions():
    for action in ({"type": "send"}, {"type": "label", "value": "INBOX"}, {"type": "set_priority", "value": "invalid"}):
        with pytest.raises(ValueError):
            RuleDefinition.model_validate({"conditions": [{"field": "category", "op": "eq", "value": "billing"}], "actions": [action]})


def test_draft_requires_approval_and_current_version(db, message):
    service = draft_service(db)
    draft = service.generate(message.id)
    assert service.generate(message.id).id == draft.id
    with pytest.raises(ConflictError):
        service.send(draft.id, draft.version)
    service.decide(draft.id, 1, True)
    assert draft.status == "approved" and draft.version == 2
    service.edit(draft.id, 2, "Revised reply")
    assert draft.status == "pending" and draft.version == 3
    with pytest.raises(ConflictError):
        service.decide(draft.id, 2, True)
    service.decide(draft.id, 3, True)
    service.send(draft.id, 4)
    assert draft.status == "sent"
    assert service.send(draft.id, 4).gmail_message_id == "sent-1"
    actions = list(db.scalars(select(ActionLog.action).where(ActionLog.message_id == message.id)))
    assert actions.count("send_started") == 1


def test_send_timeout_is_not_retried(db, message):
    class Gmail(FakeGmail):
        calls = 0
        def send_draft(self, draft, message):
            self.calls += 1
            raise TimeoutError()
    gmail = Gmail()
    service = draft_service(db, gmail)
    draft = service.generate(message.id)
    service.decide(draft.id, draft.version, True)
    service.send(draft.id, draft.version)
    assert draft.status == "send_unknown"
    with pytest.raises(ConflictError):
        service.send(draft.id, draft.version)
    with pytest.raises(ConflictError):
        service.reconcile(draft.id, DraftReconcileIn(version=draft.version, gmail_draft_id="d1"))
    assert gmail.calls == 1


def test_create_timeout_does_not_duplicate_draft(db, message):
    class Gmail(FakeGmail):
        calls = 0
        def create_draft(self, draft, message):
            self.calls += 1
            raise TimeoutError()
    gmail = Gmail()
    service = draft_service(db, gmail)
    draft = service.generate(message.id)
    assert draft.status == "creation_unknown"
    assert service.generate(message.id).id == draft.id
    assert gmail.calls == 1


def test_update_failure_revokes_approval(db, message):
    class Gmail(FakeGmail):
        def update_draft(self, draft, message):
            raise TimeoutError()
    service = draft_service(db, Gmail())
    draft = service.generate(message.id)
    service.decide(draft.id, draft.version, True)
    service.edit(draft.id, draft.version, "New version")
    assert draft.status == "update_unknown"
    with pytest.raises(ConflictError):
        service.send(draft.id, draft.version)


def test_draft_reconciliation_verifies_sent_message_identity(db, message):
    class Gmail(FakeGmail):
        def get_message(self, message_id):
            return {"id": message_id, "threadId": message.thread_id, "labelIds": ["SENT"], "payload": {"headers": [{"name": "Message-ID", "value": "wrong"}]}}
    service = draft_service(db, Gmail())
    draft = service.generate(message.id)
    draft.status = "send_unknown"
    db.commit()
    with pytest.raises(ConflictError):
        service.reconcile(draft.id, DraftReconcileIn(version=draft.version, gmail_message_id="s1"))


def test_verified_sent_message_reconciles_without_resending(db, message):
    class Gmail(FakeGmail):
        def get_message(self, message_id):
            return {"id": message_id, "threadId": message.thread_id, "labelIds": ["SENT"], "payload": {"headers": [{"name": "Message-ID", "value": expected}]}}

        def send_draft(self, draft, message):
            pytest.fail("reconciliation must never send")

    service = draft_service(db, Gmail())
    draft = service.generate(message.id)
    service.decide(draft.id, draft.version, True)
    expected = f"<ai-email-agent-{draft.id}-v{draft.version}@local.invalid>"
    draft.status = "send_unknown"
    db.commit()
    service.reconcile(draft.id, DraftReconcileIn(version=draft.version, gmail_message_id="sent-confirmed"))
    assert draft.status == "sent"
    assert draft.gmail_message_id == "sent-confirmed"


def test_rejected_draft_cannot_send(db, message):
    service = draft_service(db)
    draft = service.generate(message.id)
    service.decide(draft.id, draft.version, False)
    with pytest.raises(ConflictError):
        service.send(draft.id, draft.version)
