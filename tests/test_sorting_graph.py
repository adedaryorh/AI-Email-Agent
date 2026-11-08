from app.models.enums import Category, MessageStatus, Priority
from app.schemas.classification import ClassificationResult
from tests.conftest import FakeGmail


def result(category, confidence, priority=Priority.NORMAL):
    return ClassificationResult(
        category=category, priority=priority, confidence=confidence, reason="test"
    )


def test_confident_newsletter_is_labeled_and_archived(make_services, message):
    gmail = FakeGmail()
    svc = make_services(result(Category.NEWSLETTER, 0.95), gmail)

    assert svc.sorting.process(message.id) == MessageStatus.DONE.value
    assert gmail.modified == [("g1", ["Label_1"], ["INBOX"])]
    assert "AI/Newsletter" in gmail.labels


def test_urgent_support_is_starred_not_archived(make_services, message):
    gmail = FakeGmail()
    svc = make_services(result(Category.SUPPORT, 0.9, Priority.URGENT), gmail)
    svc.sorting.process(message.id)
    assert gmail.modified == [("g1", ["Label_1", "STARRED"], [])]


def test_low_confidence_pauses_then_resumes_with_human_decision(make_services, message):
    gmail = FakeGmail()
    svc = make_services(result(Category.OTHER, 0.4), gmail)

    assert svc.sorting.process(message.id) == MessageStatus.NEEDS_REVIEW.value
    assert gmail.modified == []  # nothing touched Gmail yet
    assert [m.id for m, _ in svc.review.pending()] == [message.id]

    svc.review.resolve(message.id, Category.BILLING, None)

    assert message.status == MessageStatus.DONE.value
    assert "AI/Billing" in gmail.labels
    latest = svc.classification.latest(message.id)
    assert (latest.source, latest.category) == ("human", "billing")
    actions = [a.action for a in message.actions]
    assert actions[:2] == ["classified", "queued_for_review"]
    assert "human_review" in actions and "label_applied" in actions


def test_process_is_idempotent_once_done(make_services, message):
    gmail = FakeGmail()
    svc = make_services(result(Category.SALES, 0.9), gmail)
    svc.sorting.process(message.id)
    svc.sorting.process(message.id)
    assert len(gmail.modified) == 1


def test_extraction_and_rule_generated_draft_are_wired(make_services, message):
    from app.schemas.automation import RuleIn
    gmail = FakeGmail()
    svc = make_services(result(Category.BILLING, 0.95), gmail)
    svc.rules.save(RuleIn.model_validate({
        "name": "Billing draft", "definition": {
            "conditions": [{"field": "category", "op": "eq", "value": "billing"}],
            "actions": [{"type": "draft"}],
        },
    }))
    assert svc.sorting.process(message.id) == "done"
    assert message.entities["invoice_numbers"] == ["INV-100"]
    drafts = svc.drafts.list()
    assert len(drafts) == 1 and drafts[0].status == "pending"
    assert drafts[0].gmail_draft_id == "draft-1"
    assert drafts[0].gmail_message_id is None
