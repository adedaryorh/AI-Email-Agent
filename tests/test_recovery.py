from types import SimpleNamespace
from datetime import UTC, datetime, timedelta
from app.core.config import get_settings
from app.models.classification import Classification
from app.models.automation import Draft
from app.repositories.message_repo import MessageRepository
from app.repositories.mailbox_repo import MailboxRepository
from app.repositories.action_log_repo import ActionLogRepository
from app.repositories.retention_repo import RetentionRepository
from app.services.sorting_service import SortingService
from app.services.action_service import ActionService
from app.services.retention_service import RetentionService
from tests.conftest import FakeGmail


def test_failed_graph_resumes_existing_checkpoint(db, message):
    class Graph:
        inputs = []
        def get_state(self, config):
            return SimpleNamespace(next=("extract",), tasks=())
        def invoke(self, data, config):
            self.inputs.append(data)
            raise TimeoutError("sensitive provider payload")
    graph = Graph()
    service = SortingService(db, graph, MessageRepository(db), ActionLogRepository(db), get_settings())
    assert service.process(message.id) == "failed"
    assert graph.inputs == [None]
    assert message.attempts == 1
    assert message.next_attempt_at is not None
    assert message.actions[-1].detail == {"error_type": "TimeoutError"}
    assert MessageRepository(db).runnable(5) == []


def test_crash_on_final_attempt_becomes_terminal_failure(db, message):
    message.status = "processing"
    message.attempts = get_settings().max_processing_attempts
    db.commit()
    repo = MessageRepository(db)
    assert repo.runnable(message.attempts) == [message]
    service = SortingService(db, None, repo, ActionLogRepository(db), get_settings())
    assert service.process(message.id) == "failed"
    assert repo.runnable(message.attempts) == []


def test_actions_replay_skips_remote_effects_and_audit_duplicates(db, message):
    gmail = FakeGmail()
    service = ActionService(db, MailboxRepository(db), ActionLogRepository(db), lambda _: gmail)
    message.action_plan = {"labels": ["AI/Custom"], "archive": True, "priority": "high"}
    classification = Classification(category="support", priority="normal")
    service.apply(message, classification)
    count = len(message.actions)
    service.apply(message, classification)
    assert len(gmail.modified) == 1
    assert gmail.modified[0][2] == ["INBOX"]
    assert "STARRED" in gmail.modified[0][1]
    assert len(message.actions) == count


def test_retention_preserves_pending_review_content(db, message):
    message.received_at = datetime.now(UTC) - timedelta(days=90)
    message.status = "needs_review"
    db.commit()
    service = RetentionService(db, RetentionRepository(db))
    assert service.purge(30) == 0
    message.status = "done"
    db.add(Draft(message_id=message.id, recipient="a@b.com", subject="Reply", body="Keep", status="pending"))
    db.commit()
    assert service.purge(30) == 0
    draft = db.query(Draft).one()
    draft.status = "sent"
    db.commit()
    assert service.purge(30) == 1
    assert message.body_text == ""


def test_recording_human_decision_leaves_message_recoverable(db, message):
    from app.services.classification_service import ClassificationService
    from app.repositories.classification_repo import ClassificationRepository
    from app.models.enums import Category

    message.status = "needs_review"
    db.commit()
    service = ClassificationService(db, None, ClassificationRepository(db), ActionLogRepository(db), get_settings())
    decision = service.record_human_decision(message, Category.BILLING, None)
    assert message.status == "processing"
    assert message in MessageRepository(db).runnable(5)
    assert service.record_human_decision(message, Category.BILLING, None).id == decision.id
