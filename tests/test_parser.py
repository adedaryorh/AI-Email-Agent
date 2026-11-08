import base64

from app.integrations.gmail.parser import html_to_text, parse_message, strip_quoted_reply


def b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")


def test_parse_multipart_prefers_plain_and_strips_quotes():
    raw = {
        "id": "m1",
        "threadId": "t1",
        "internalDate": "1700000000000",
        "labelIds": ["INBOX"],
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": [
                {"name": "From", "value": "Ann <ann@x.com>"},
                {"name": "Subject", "value": "Hi"},
                {"name": "List-Unsubscribe", "value": "<mailto:u@x.com>"},
            ],
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {"data": b64("Thanks!\n\nOn Mon, Bob wrote:\n> old")},
                },
                {"mimeType": "text/html", "body": {"data": b64("<p>ignored</p>")}},
            ],
        },
    }
    email = parse_message(raw)
    assert email.sender == "Ann <ann@x.com>"
    assert email.body_text == "Thanks!"
    assert email.has_unsubscribe is True
    assert email.label_ids == ["INBOX"]


def test_html_fallback_skips_scripts():
    assert html_to_text("<style>x{}</style><p>Hello</p><script>bad()</script>") == "Hello"


def test_strip_quoted_lines():
    assert strip_quoted_reply("hi\n> quoted\nbye") == "hi\nbye"
