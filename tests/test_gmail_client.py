import httpx
import pytest
from app.integrations.gmail.client import GmailClient
from app.core.exceptions import ExternalServiceError
from app.integrations.gmail.mime import reply_raw
from email import message_from_bytes
import base64
from types import SimpleNamespace


def test_reads_retry_but_sends_do_not(monkeypatch):
    monkeypatch.setattr("app.integrations.gmail.client.time.sleep", lambda _: None)
    calls = []
    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(503)
    client = GmailClient(lambda: "token", httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(ExternalServiceError):
        client.get_profile()
    assert len(calls) == 4
    calls.clear()
    with pytest.raises(ExternalServiceError):
        client._request("POST", "/drafts/send", json={})
    assert len(calls) == 1


def test_initial_list_paginates_all_results():
    calls = []
    def handler(request):
        calls.append(request)
        if request.url.params.get("pageToken"):
            return httpx.Response(200, json={"messages": [{"id": "b"}]})
        return httpx.Response(200, json={"messages": [{"id": "a"}], "nextPageToken": "page2"})
    client = GmailClient(lambda: "token", httpx.Client(transport=httpx.MockTransport(handler)))
    assert client.list_message_ids("in:inbox", 0) == ["a", "b"]
    assert len(calls) == 2


def test_reply_mime_threads_and_approved_content(message):
    message.headers = {"message-id": "<parent@example.com>"}
    draft = SimpleNamespace(id=12, version=3, recipient="a@example.com", subject="Re: Help", body="Approved text")
    mail = message_from_bytes(base64.urlsafe_b64decode(reply_raw(draft, message)))
    assert mail["To"] == "a@example.com"
    assert mail["In-Reply-To"] == "<parent@example.com>"
    assert mail["Message-ID"] == "<ai-email-agent-12-v3@local.invalid>"
    assert "Approved text" in mail.get_payload(decode=True).decode()
