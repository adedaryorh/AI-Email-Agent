import base64
import json
from email import message_from_bytes
from types import SimpleNamespace

import httpx
import pytest

from app.integrations.gmail.client import GmailClient, HistoryExpired


def test_send_request_uses_approved_local_content(message):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"id": "sent-id"})

    draft = SimpleNamespace(id=10, version=4, recipient="recipient@example.test", subject="Re: Help", body="Approved local body", gmail_draft_id="draft-id")
    client = GmailClient(lambda: "fake-token", httpx.Client(transport=httpx.MockTransport(handler)))
    assert client.send_draft(draft, message) == {"id": "sent-id"}
    request = requests[0]
    assert request.url.path.endswith("/drafts/send")
    assert request.headers["Authorization"] == "Bearer fake-token"
    payload = json.loads(request.content)
    assert payload["id"] == "draft-id"
    assert payload["message"]["threadId"] == message.thread_id
    mail = message_from_bytes(base64.urlsafe_b64decode(payload["message"]["raw"]))
    assert mail["To"] == "recipient@example.test"
    assert mail["Message-ID"] == "<ai-email-agent-10-v4@local.invalid>"
    assert mail.get_payload(decode=True).decode().strip() == "Approved local body"


def test_history_paginates_and_deduplicates():
    def handler(request):
        assert request.url.params["startHistoryId"] == "100"
        if request.url.params.get("pageToken"):
            return httpx.Response(200, json={"historyId": "103", "history": [{"messagesAdded": [{"message": {"id": "a"}}, {"message": {"id": "b"}}]}]})
        return httpx.Response(200, json={"historyId": "102", "nextPageToken": "next", "history": [{"messagesAdded": [{"message": {"id": "a"}}]}]})

    client = GmailClient(lambda: "token", httpx.Client(transport=httpx.MockTransport(handler)))
    assert client.list_history("100") == (["a", "b"], "103")


def test_expired_history_is_distinguished_from_empty_history():
    client = GmailClient(lambda: "token", httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(404))))
    with pytest.raises(HistoryExpired):
        client.list_history("expired")


def test_rate_limit_retry_after_is_bounded(monkeypatch):
    delays = []
    responses = [httpx.Response(429, headers={"Retry-After": "100000"}), httpx.Response(200, json={"historyId": "1"})]
    monkeypatch.setattr("app.integrations.gmail.client.time.sleep", delays.append)
    monkeypatch.setattr("app.integrations.gmail.client.random.random", lambda: 0)
    client = GmailClient(lambda: "token", httpx.Client(transport=httpx.MockTransport(lambda _: responses.pop(0))))
    assert client.get_profile() == {"historyId": "1"}
    assert delays == [30]
