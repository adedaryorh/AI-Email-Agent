"""Thin Gmail REST client plus the Protocol the services depend on."""

from collections.abc import Callable
from typing import Protocol

import httpx
import time
import random
from app.integrations.gmail.mime import reply_raw
from app.integrations.gmail.parser import parse_message

from app.core.exceptions import ExternalServiceError

BASE_URL = "https://gmail.googleapis.com/gmail/v1/users/me"


class GmailNotFound(ExternalServiceError):
    status_code = 404


class HistoryExpired(ExternalServiceError):
    """startHistoryId is too old; caller must do a full resync."""


class GmailGateway(Protocol):
    def get_profile(self) -> dict: ...
    def list_message_ids(self, query: str, max_results: int) -> list[str]: ...
    def get_message(self, message_id: str) -> dict: ...
    def list_history(self, start_history_id: str) -> tuple[list[str], str]: ...
    def get_or_create_label(self, name: str) -> str: ...
    def modify_labels(self, message_id: str, add: list[str], remove: list[str]) -> None: ...
    def thread_context(self, thread_id: str, max_chars: int) -> list[dict]: ...
    def create_draft(self, draft, message) -> dict: ...
    def update_draft(self, draft, message) -> dict: ...
    def get_draft(self, draft_id: str) -> dict: ...
    def send_draft(self, draft, message) -> dict: ...


class GmailClient:
    def __init__(self, token_provider: Callable[[], str], http: httpx.Client | None = None):
        self._token = token_provider
        self._http = http or httpx.Client(timeout=20)
        self._label_cache: dict[str, str] | None = None

    def close(self):
        self._http.close()

    def _request(self, method: str, path: str, **kwargs) -> dict:
        # Never retry create/send POSTs: their outcome can be ambiguous.
        retryable = method in {"GET", "PUT", "DELETE"} or path.endswith("/modify")
        attempts = 4 if retryable else 1
        for attempt in range(attempts):
            try:
                resp = self._http.request(
                    method, f"{BASE_URL}{path}",
                    headers={"Authorization": f"Bearer {self._token()}"}, **kwargs,
                )
            except httpx.TransportError as exc:
                if attempt + 1 == attempts:
                    raise ExternalServiceError("Gmail transport failure") from exc
                time.sleep(2 ** attempt + random.random())
                continue
            if resp.status_code == 404:
                raise GmailNotFound(f"Gmail 404 on {path}")
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt + 1 < attempts:
                    try:
                        delay = min(30, max(0, float(resp.headers.get("Retry-After", 2 ** attempt))))
                    except ValueError:
                        delay = 2 ** attempt
                    time.sleep(delay + random.random())
                    continue
            if resp.status_code >= 400:
                raise ExternalServiceError(f"Gmail error {resp.status_code}")
            return resp.json() if resp.content else {}
        raise ExternalServiceError("Gmail request exhausted retries")

    def get_profile(self) -> dict:
        return self._request("GET", "/profile")

    def list_message_ids(self, query: str, max_results: int) -> list[str]:
        ids: list[str] = []
        page_token: str | None = None
        while max_results == 0 or len(ids) < max_results:
            params = {"q": query, "maxResults": min(100, max_results - len(ids)) if max_results else 100}
            if page_token:
                params["pageToken"] = page_token
            data = self._request("GET", "/messages", params=params)
            ids += [m["id"] for m in data.get("messages", [])]
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        return ids

    def get_message(self, message_id: str) -> dict:
        return self._request("GET", f"/messages/{message_id}", params={"format": "full"})

    def list_history(self, start_history_id: str) -> tuple[list[str], str]:
        ids: list[str] = []
        latest = start_history_id
        page_token: str | None = None
        while True:
            params = {
                "startHistoryId": start_history_id,
                "historyTypes": "messageAdded",
                "labelId": "INBOX",
            }
            if page_token:
                params["pageToken"] = page_token
            try:
                data = self._request("GET", "/history", params=params)
            except GmailNotFound as exc:
                raise HistoryExpired("history id expired") from exc
            for h in data.get("history", []):
                for added in h.get("messagesAdded", []):
                    ids.append(added["message"]["id"])
            latest = data.get("historyId", latest)
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        return list(dict.fromkeys(ids)), latest

    def get_or_create_label(self, name: str) -> str:
        if self._label_cache is None:
            data = self._request("GET", "/labels")
            self._label_cache = {lbl["name"]: lbl["id"] for lbl in data.get("labels", [])}
        if name not in self._label_cache:
            created = self._request(
                "POST",
                "/labels",
                json={
                    "name": name,
                    "labelListVisibility": "labelShow",
                    "messageListVisibility": "show",
                },
            )
            self._label_cache[name] = created["id"]
        return self._label_cache[name]

    def modify_labels(self, message_id: str, add: list[str], remove: list[str]) -> None:
        self._request(
            "POST",
            f"/messages/{message_id}/modify",
            json={"addLabelIds": add, "removeLabelIds": remove},
        )

    def thread_context(self, thread_id, max_chars):
        raw = self._request("GET", f"/threads/{thread_id}", params={"format": "full"})
        context = []
        remaining = max_chars
        for item in reversed(raw.get("messages", [])[-10:]):
            if "DRAFT" in item.get("labelIds", []):
                continue
            parsed = parse_message(item)
            body = parsed.body_text[:remaining]
            context.append({"sender": parsed.sender, "body": body})
            remaining -= len(body)
            if remaining <= 0:
                break
        return list(reversed(context))

    def create_draft(self, draft, message):
        return self._request("POST", "/drafts", json={"message": {"raw": reply_raw(draft, message), "threadId": message.thread_id}})

    def update_draft(self, draft, message):
        return self._request("PUT", f"/drafts/{draft.gmail_draft_id}", json={"id": draft.gmail_draft_id, "message": {"raw": reply_raw(draft, message), "threadId": message.thread_id}})

    def get_draft(self, draft_id):
        return self._request("GET", f"/drafts/{draft_id}", params={"format": "full"})

    def send_draft(self, draft, message):
        # Supply approved raw content so edits made externally in Gmail cannot change this send.
        return self._request("POST", "/drafts/send", json={"id": draft.gmail_draft_id, "message": {"raw": reply_raw(draft, message), "threadId": message.thread_id}})
