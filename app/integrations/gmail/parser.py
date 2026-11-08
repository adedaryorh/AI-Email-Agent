"""Gmail API message resource -> ParsedEmail. Pure functions, no I/O."""

import base64
import re
from datetime import UTC, datetime
from html.parser import HTMLParser

from app.schemas.email import ParsedEmail

MAX_STORED_BODY = 50_000

_QUOTE_HEADER = re.compile(r"^(On .+ wrote:|-{3,}\s*Original Message\s*-{3,}|From: .+)\s*$", re.I)


def _b64decode(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")


class _TextExtractor(HTMLParser):
    _SKIP = {"script", "style", "head"}
    _BREAK = {"br", "p", "div", "tr", "li", "h1", "h2", "h3", "h4"}

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1
        elif tag in self._BREAK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if not self._skip_depth:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    extractor = _TextExtractor()
    extractor.feed(html)
    text = "".join(extractor.parts)
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", text).strip()


def strip_quoted_reply(text: str) -> str:
    """Drop '> quoted' lines and everything after an 'On ... wrote:' marker."""
    kept: list[str] = []
    for line in text.splitlines():
        if _QUOTE_HEADER.match(line.strip()) and kept:
            break
        if line.lstrip().startswith(">"):
            continue
        kept.append(line)
    return "\n".join(kept).strip()


def _walk(part: dict, plain: list[str], html: list[str]) -> None:
    data = part.get("body", {}).get("data")
    if data and not part.get("filename"):
        mime = part.get("mimeType", "")
        if mime == "text/plain":
            plain.append(_b64decode(data))
        elif mime == "text/html":
            html.append(_b64decode(data))
    for sub in part.get("parts") or []:
        _walk(sub, plain, html)


def parse_message(raw: dict) -> ParsedEmail:
    payload = raw.get("payload", {})
    headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}

    plain: list[str] = []
    html: list[str] = []
    _walk(payload, plain, html)
    body = "\n".join(plain).strip() or html_to_text("\n".join(html))
    body = strip_quoted_reply(body)[:MAX_STORED_BODY]

    received = datetime.fromtimestamp(int(raw.get("internalDate", "0")) / 1000, tz=UTC)
    return ParsedEmail(
        gmail_id=raw["id"],
        thread_id=raw.get("threadId", raw["id"]),
        headers={k: headers[k] for k in ("message-id", "references", "in-reply-to") if k in headers},
        sender=headers.get("from", ""),
        subject=headers.get("subject", ""),
        body_text=body,
        has_unsubscribe="list-unsubscribe" in headers,
        label_ids=raw.get("labelIds", []),
        received_at=received,
    )
