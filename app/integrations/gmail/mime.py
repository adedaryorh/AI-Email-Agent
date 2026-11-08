import base64
from email.message import EmailMessage
from email.policy import SMTP


def reply_raw(draft, message):
    mail = EmailMessage(policy=SMTP)
    mail["To"] = draft.recipient
    mail["Subject"] = draft.subject.replace("\r", " ").replace("\n", " ")
    mail["Message-ID"] = f"<ai-email-agent-{draft.id}-v{draft.version}@local.invalid>"
    headers = message.headers or {}
    parent = headers.get("message-id", "")
    if parent and not any(c in parent for c in "\r\n"):
        mail["In-Reply-To"] = parent
        refs = headers.get("references", "").replace("\r", " ").replace("\n", " ")
        mail["References"] = f"{refs} {parent}".strip()[-900:]
    mail.set_content(draft.body)
    return base64.urlsafe_b64encode(mail.as_bytes()).decode()
