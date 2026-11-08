"""Offline agent safety evaluations use fake model decisions, never live email."""
import pytest
from sqlalchemy import select
from app.core.config import get_settings
from app.core.exceptions import ConflictError
from app.models.agent import AgentRun
from app.schemas.agent import DocumentIn, PreferencesIn
from app.services.agent_service import AgentService
from app.services.knowledge_service import KnowledgeService
from tests.conftest import FakeAssistant
from tests.test_automation import draft_service


def test_retrieval_versioning_and_owner_preferences(db):
    service = KnowledgeService(db)
    doc = service.save(DocumentIn(title="Refund policy", content="Refund requests require an order number."))
    sources = service.search("refund order")
    assert sources[0]["document_id"] == doc.id
    assert service.sources_current(sources)
    service.save(DocumentIn(title=doc.title, content="Refund requests require a receipt.", version=1), doc.id)
    assert not service.sources_current(sources)
    with pytest.raises(ConflictError):
        service.save(DocumentIn(title="Old edit", content="Old", version=1), doc.id)
    assert service.set_preferences(PreferencesIn(instructions="Use concise English"))["version"] == 1
    with pytest.raises(ConflictError):
        service.set_preferences(PreferencesIn(instructions="Stale edit"))
    service.set_preferences(PreferencesIn(instructions="", version=1))
    assert service.preferences()["instructions"] == ""
    service.delete(doc.id, 2)
    assert service.search("refund") == []


def test_bounded_tools_grounding_and_execution_record(db, message):
    KnowledgeService(db).save(DocumentIn(title="Login help", content="Ask for the error code when login is broken."))
    class Assistant(FakeAssistant):
        def plan(self, data):
            return {"tool": "finish" if data["completed_tools"] else "read_thread"}
        def compose(self, data):
            assert data["thread"] == "Previous context"
            return {"body": "Could you share the error code?", "citations": [data["sources"][0]["id"]]}
    agent = AgentService(db, Assistant(), get_settings())
    body, sources, report, run_id = agent.generate(message, lambda: "Previous context")
    assert sources and report["passed"] and body
    run = db.get(AgentRun, run_id)
    assert run.status == "completed" and run.input_chars > 0
    assert [e["tool"] for e in run.events] == ["search_knowledge", "plan", "read_thread", "plan", "compose", "verify"]
    assert "Previous context" not in str(run.events)


@pytest.mark.parametrize("tool", ["send", "execute", "fetch_url"])
def test_disallowed_tools_fail_closed(db, message, tool):
    class Assistant(FakeAssistant):
        def plan(self, data):
            return {"tool": tool}
    with pytest.raises(ValueError):
        AgentService(db, Assistant(), get_settings()).generate(message, lambda: pytest.fail("No tools should execute"))
    assert db.scalar(select(AgentRun)).status == "failed"


def test_unknown_citations_are_rejected(db, message):
    class Assistant(FakeAssistant):
        def compose(self, data):
            return {"body": "Refund guaranteed", "citations": ["999:1:0"]}
    with pytest.raises(ConflictError, match="unknown source"):
        AgentService(db, Assistant(), get_settings()).generate(message, lambda: [])


@pytest.mark.parametrize("mode", ["repeat", "steps", "input", "time"])
def test_budget_failures_are_durable(db, message, mode, monkeypatch):
    settings = get_settings().model_copy()
    class Assistant(FakeAssistant):
        calls = 0
        def plan(self, data):
            self.calls += 1
            return {"tool": "search_knowledge", "query": str(self.calls) if mode == "steps" else "same"}
    if mode == "input":
        settings.agent_max_input_chars = 1
    if mode == "time":
        ticks = iter(range(0, 10000, 1000))
        monkeypatch.setattr("app.services.agent_service.time.monotonic", lambda: next(ticks))
    with pytest.raises(ConflictError):
        AgentService(db, Assistant(), settings).generate(message, lambda: [])
    assert db.scalar(select(AgentRun)).status == "failed"


def test_failed_verification_blocks_approval_and_send(db, message):
    service = draft_service(db)
    service.agent.assistant.verify = lambda data: {"passed": False, "findings": ["Unsupported refund guarantee"]}
    draft = service.generate(message.id)
    assert not draft.verification["passed"]
    with pytest.raises(ConflictError, match="verification"):
        service.decide(draft.id, draft.version, True)
    assert draft.status == "pending"


def test_source_and_preference_changes_invalidate_approval(db, message):
    knowledge = KnowledgeService(db)
    doc = knowledge.save(DocumentIn(title="Login", content="Ask for login error details."))
    service = draft_service(db)
    draft = service.generate(message.id)
    service.decide(draft.id, draft.version, True)
    knowledge.save(DocumentIn(title="Login", content="Ask for account type.", version=1), doc.id)
    with pytest.raises(ConflictError, match="sources changed"):
        service.send(draft.id, draft.version)
    service.edit(draft.id, draft.version, regenerate=True)
    service.decide(draft.id, draft.version, True)
    knowledge.set_preferences(PreferencesIn(instructions="Reply in French"))
    with pytest.raises(ConflictError, match="Preferences changed"):
        service.send(draft.id, draft.version)


def test_body_tampering_and_legacy_drafts_cannot_be_approved(db, message):
    service = draft_service(db)
    draft = service.generate(message.id)
    draft.body = "Different body"
    db.commit()
    with pytest.raises(ConflictError):
        service.decide(draft.id, draft.version, True)
    draft.verification = {}
    db.commit()
    with pytest.raises(ConflictError):
        service.decide(draft.id, draft.version, True)


def test_clarification_only_creates_draft(db, message):
    class Assistant(FakeAssistant):
        def plan(self, data):
            return {"tool": "request_clarification", "query": "What error appears?"}
        def compose(self, data):
            return {"body": data["clarification"], "citations": []}
    body, _, _, run_id = AgentService(db, Assistant(), get_settings()).generate(message, lambda: pytest.fail("Thread not needed"))
    assert body == "What error appears?"
    assert db.get(AgentRun, run_id).status == "completed"


def test_restart_records_interrupted_run_without_replaying_tools(db, message):
    previous = AgentRun(message_id=message.id, status="running", events=[])
    db.add(previous)
    db.commit()
    AgentService(db, FakeAssistant(), get_settings()).generate(message, lambda: pytest.fail("No thread read needed"))
    assert previous.status == "interrupted"
    assert previous.events[-1]["tool"] == "stopped"


def test_edit_with_failed_verification_revokes_approval(db, message):
    service = draft_service(db)
    draft = service.generate(message.id)
    service.decide(draft.id, draft.version, True)
    service.agent.assistant.verify = lambda data: {"passed": False, "findings": ["Unsupported commitment"]}
    service.edit(draft.id, draft.version, "We guarantee a refund")
    assert draft.status == "pending"
    with pytest.raises(ConflictError):
        service.decide(draft.id, draft.version, True)
    with pytest.raises(ConflictError):
        service.send(draft.id, draft.version)


def test_cost_budget_stops_before_call_and_records_actual_usage(db, message):
    settings = get_settings().model_copy(update={"llm_input_usd_per_million": 1.0,
        "llm_output_usd_per_million": 2.0, "agent_max_cost_usd": 0.000001})
    class Assistant(FakeAssistant):
        last_usage = {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}
        calls = 0
        def plan(self, data):
            self.calls += 1
            return super().plan(data)
    assistant = Assistant()
    with pytest.raises(ConflictError, match="cost budget"):
        AgentService(db, assistant, settings).generate(message, lambda: [])
    assert assistant.calls == 0
    settings.agent_max_cost_usd = 1.0
    _, _, _, run_id = AgentService(db, assistant, settings).generate(message, lambda: [])
    event = next(e for e in db.get(AgentRun, run_id).events if e["tool"] == "plan")
    assert event["estimated_cost_usd"] == pytest.approx(0.00014)
    assert event["usage"]["total_tokens"] == 120


def test_cost_budget_fails_closed_without_provider_usage(db, message):
    settings = get_settings().model_copy(update={"llm_input_usd_per_million": 1.0,
        "llm_output_usd_per_million": 2.0, "agent_max_cost_usd": 1.0})
    with pytest.raises(ConflictError, match="usage is unavailable"):
        AgentService(db, FakeAssistant(), settings).generate(message, lambda: [])
