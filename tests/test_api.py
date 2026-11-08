from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_healthz_open():
    assert client.get("/api/v1/healthz").json() == {"status": "ok"}


def test_protected_routes_need_api_key():
    assert client.get("/api/v1/review").status_code == 401
    assert client.get("/api/v1/messages").status_code == 401


def test_draft_api_approval_versions_and_send(db, message):
    from types import SimpleNamespace
    from app.api.deps import get_services
    from tests.test_automation import draft_service

    app.dependency_overrides[get_services] = lambda: SimpleNamespace(drafts=draft_service(db))
    headers = {"X-API-Key": "test-key"}
    try:
        response = client.post(f"/api/v1/drafts/for-message/{message.id}", headers=headers)
        assert response.status_code == 200
        draft = response.json()
        draft_id = draft["id"]
        assert client.post(f"/api/v1/drafts/{draft_id}/send", headers=headers, json={"version": 1}).status_code == 409
        approved = client.post(f"/api/v1/drafts/{draft_id}/approve", headers=headers, json={"version": 1})
        assert approved.json()["version"] == 2
        assert client.patch(f"/api/v1/drafts/{draft_id}", headers=headers, json={"version": 1, "body": "stale edit"}).status_code == 409
        sent = client.post(f"/api/v1/drafts/{draft_id}/send", headers=headers, json={"version": 2})
        assert sent.json()["status"] == "sent"
        assert client.post(f"/api/v1/drafts/{draft_id}/send", headers=headers, json={"version": 2}).json()["status"] == "sent"
    finally:
        app.dependency_overrides.clear()


def test_rules_api_crud_dry_run_and_validation(db, message):
    from types import SimpleNamespace
    from app.api.deps import get_services
    from app.models.classification import Classification
    from app.repositories.automation_repo import AutomationRepository
    from app.repositories.message_repo import MessageRepository
    from app.repositories.action_log_repo import ActionLogRepository
    from app.services.message_service import MessageService
    from app.services.rule_service import RuleService
    from tests.test_automation import rule_input

    message.entities = {"invoice_numbers": ["INV-1"]}
    db.commit()
    classification = SimpleNamespace(latest=lambda _: Classification(category="billing", priority="normal"))
    service = RuleService(db, AutomationRepository(db), MessageService(MessageRepository(db)), classification, ActionLogRepository(db))
    app.dependency_overrides[get_services] = lambda: SimpleNamespace(rules=service)
    headers = {"X-API-Key": "test-key"}
    try:
        created = client.post("/api/v1/rules", json=rule_input().model_dump(), headers=headers)
        assert created.status_code == 201
        rule_id = created.json()["id"]
        dry_run = client.post(f"/api/v1/rules/{rule_id}/test", headers=headers, json={"message_id": message.id})
        assert dry_run.json()["matched"] is True
        assert message.action_plan is None
        assert client.get("/api/v1/rules", headers=headers).json()[0]["id"] == rule_id
        assert client.put("/api/v1/rules/0", json=rule_input().model_dump(), headers=headers).status_code == 404
        assert client.delete(f"/api/v1/rules/{rule_id}", headers=headers).status_code == 204
        assert client.get(f"/api/v1/rules/{rule_id}", headers=headers).status_code == 404
        invalid = rule_input().model_dump()
        invalid["definition"]["actions"] = [{"type": "send"}]
        assert client.post("/api/v1/rules", json=invalid, headers=headers).status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_all_mutating_routes_require_auth():
    requests = [
        ("post", "/api/v1/drafts/1/send", {"version": 1}),
        ("post", "/api/v1/drafts/1/approve", {"version": 1}),
        ("post", "/api/v1/messages/1/retry", {}),
        ("delete", "/api/v1/rules/1", None),
    ]
    for method, path, body in requests:
        kwargs = {"json": body} if body is not None else {}
        assert client.request(method, path, **kwargs).status_code == 401


def test_agent_management_api_and_auth(db, message):
    from app.core.database import get_db
    from tests.test_automation import draft_service
    app.dependency_overrides[get_db] = lambda: db
    headers = {"X-API-Key": "test-key"}
    try:
        for path in ("/knowledge", "/preferences", "/agent/runs", "/agent/runs/1"):
            assert client.get("/api/v1" + path).status_code == 401
        payload = {"title": "Login", "content": "Ask for an error code", "version": 1}
        created = client.post("/api/v1/knowledge", headers=headers, json=payload)
        assert created.status_code == 200
        key = created.json()["id"]
        assert client.put(f"/api/v1/knowledge/{key}", headers=headers, json=payload).json()["version"] == 2
        assert client.put(f"/api/v1/knowledge/{key}", headers=headers, json=payload).status_code == 409
        assert client.delete(f"/api/v1/knowledge/{key}?version=1", headers=headers).status_code == 409
        assert client.get("/api/v1/preferences", headers=headers).json()["version"] == 0
        assert client.put("/api/v1/preferences", headers=headers, json={"instructions": "Be concise", "version": 0}).json()["version"] == 1
        draft = draft_service(db).generate(message.id)
        runs = client.get("/api/v1/agent/runs", headers=headers).json()
        assert runs[0]["id"] == draft.agent_run_id
        assert "events" not in runs[0]
        assert client.get(f"/api/v1/agent/runs/{draft.agent_run_id}", headers=headers).json()["events"]
        assert client.delete(f"/api/v1/knowledge/{key}?version=2", headers=headers).status_code == 204
    finally:
        app.dependency_overrides.clear()
