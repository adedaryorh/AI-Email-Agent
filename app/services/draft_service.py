from email.utils import parseaddr
from app.core.exceptions import ConflictError, NotFoundError
from app.core.locks import operation_lock
from app.models.automation import Draft

class DraftService:
    """Durable approval gate. Unknown remote outcomes require explicit reconciliation.

    Creation locks share the message workflow lock; mutations use a draft lock.
    No worker calls send. Approval is tied to an immutable version until send.
    """
    def __init__(self, db, repository, messages, mailboxes, gmail_factory, assistant, audit, settings):
        self.db, self.repository, self.messages = db, repository, messages
        self.mailboxes, self.gmail_factory = mailboxes, gmail_factory
        self.assistant, self.audit, self.settings = assistant, audit, settings
        from app.services.agent_service import AgentService
        self.agent = AgentService(db, assistant, settings)

    def list(self, **kwargs):
        return self.repository.drafts(**kwargs)

    def get(self, draft_id):
        row = self.repository.draft(draft_id)
        if not row:
            raise NotFoundError("Draft not found")
        return row

    def _gmail(self, message):
        return self.gmail_factory(self.mailboxes.get(message.mailbox_id))

    def _content(self, message):
        if not message.body_text:
            raise ConflictError("Message content is empty or has been removed by retention")
        gmail = self._gmail(message)
        return self.agent.generate(message, lambda: gmail.thread_context(message.thread_id, self.settings.max_body_chars))

    def generate(self, message_id):
        with operation_lock(self.db, 1, message_id):
            return self.ensure(self.messages.get(message_id))

    def ensure(self, message):
        """Caller holds the message lock; graph replay must never create duplicate drafts."""
        row = self.repository.draft_for(message.id)
        if row:
            return row
        _, recipient = parseaddr(message.sender)
        if not recipient or "@" not in recipient or any(c in message.sender for c in "\r\n"):
            raise ConflictError("Sender has no safe reply address")
        body, sources, verification, run_id = self._content(message)
        row = self.repository.add(Draft(
            message_id=message.id, recipient=recipient,
            subject=message.subject if message.subject.lower().startswith("re:") else f"Re: {message.subject}",
            body=body, status="creating", sources=sources, verification=verification, agent_run_id=run_id,
        ))
        self.audit.add(message.id, "draft_creation_started", {"draft_id": row.id})
        self.db.commit()  # intent precedes remote side effect
        try:
            remote = self._gmail(message).create_draft(row, message)
        except Exception:
            row.status = "creation_unknown"
            self.audit.add(message.id, "draft_creation_unknown", {"draft_id": row.id})
            self.db.commit()
            return row
        row.gmail_draft_id = remote["id"]
        row.status = "pending"
        self.audit.add(message.id, "draft_created", {"draft_id": row.id, "prompt_version": "v1"})
        self.db.commit()
        return row

    def _checked(self, draft_id, version, allowed):
        row = self.get(draft_id)
        self.db.refresh(row)
        if row.version != version:
            raise ConflictError("Draft changed; reload before proceeding")
        if row.status not in allowed:
            raise ConflictError(f"Cannot perform action while draft is {row.status}")
        return row

    def edit(self, draft_id, version, body=None, regenerate=False):
        with operation_lock(self.db, 3, draft_id):
            row = self._checked(draft_id, version, {"pending", "approved", "rejected"})
            message = self.messages.get(row.message_id)
            if regenerate:
                content, sources, verification, run_id = self._content(message)
            else:
                content, sources, run_id = body, row.sources, row.agent_run_id
                verification, run_id = self.agent.verify_edit(message, body, sources)
            row.body, row.sources, row.verification, row.agent_run_id = content, sources, verification, run_id
            row.version += 1
            row.status = "updating"
            self.audit.add(message.id, "draft_edited", {"draft_id": row.id, "version": row.version}, actor="human")
            self.db.commit()  # revoke approval before remote update
            try:
                self._gmail(message).update_draft(row, message)
            except Exception:
                row.status = "update_unknown"
                self.db.commit()
                return row
            row.status = "pending"
            self.db.commit()
            return row

    def decide(self, draft_id, version, approve):
        with operation_lock(self.db, 3, draft_id), operation_lock(self.db, 5, 0), operation_lock(self.db, 6, 1):
            row = self._checked(draft_id, version, {"pending", "approved"})
            if approve:
                self.agent.require_verified(row)
            row.status = "approved" if approve else "rejected"
            row.version += 1
            self.audit.add(row.message_id, f"draft_{row.status}", {"draft_id": row.id, "version": row.version}, actor="human")
            self.db.commit()
            return row

    def send(self, draft_id, version):
        with operation_lock(self.db, 3, draft_id), operation_lock(self.db, 5, 0), operation_lock(self.db, 6, 1):
            row = self.get(draft_id)
            self.db.refresh(row)
            if row.status == "sent":
                return row  # a repeated HTTP request must not resend
            row = self._checked(draft_id, version, {"approved"})
            self.agent.require_verified(row)
            message = self.messages.get(row.message_id)
            row.status = "sending"
            self.audit.add(row.message_id, "send_started", {"draft_id": row.id, "version": row.version}, actor="human")
            self.db.commit()
            try:
                remote = self._gmail(message).send_draft(row, message)
            except Exception:
                row.status = "send_unknown"
                self.audit.add(row.message_id, "send_unknown", {"draft_id": row.id})
                self.db.commit()
                return row
            row.gmail_message_id = remote["id"]
            row.status = "sent"
            self.audit.add(row.message_id, "sent", {"draft_id": row.id, "gmail_message_id": row.gmail_message_id}, actor="human")
            self.db.commit()
            return row

    def reconcile(self, draft_id, data):
        with operation_lock(self.db, 3, draft_id):
            row = self._checked(draft_id, data.version, {"creating", "creation_unknown", "updating", "update_unknown", "sending", "send_unknown"})
            message = self.messages.get(row.message_id)
            gmail = self._gmail(message)
            if row.status in {"sending", "send_unknown"}:
                if not data.gmail_message_id:
                    raise ConflictError("Uncertain sends require a verified sent message ID; resending is disabled")
                remote = gmail.get_message(data.gmail_message_id)
                if "SENT" not in remote.get("labelIds", []) or remote.get("threadId") != message.thread_id:
                    raise ConflictError("Sent message does not belong to this thread")
                expected = f"<ai-email-agent-{row.id}-v{row.version}@local.invalid>"
                headers = {h["name"].lower(): h["value"] for h in remote.get("payload", {}).get("headers", [])}
                if headers.get("message-id") != expected:
                    raise ConflictError("Sent message does not match this draft version")
                row.gmail_message_id = data.gmail_message_id
                row.status = "sent"
            else:
                if not data.gmail_draft_id:
                    raise ConflictError("Provide the existing Gmail draft ID")
                remote = gmail.get_draft(data.gmail_draft_id)
                if remote.get("message", {}).get("threadId") != message.thread_id:
                    raise ConflictError("Draft does not belong to this thread")
                row.gmail_draft_id = data.gmail_draft_id
                # PUT is idempotent; write the local reviewed content back to Gmail.
                gmail.update_draft(row, message)
                row.status = "pending"
            row.version += 1
            self.audit.add(row.message_id, "draft_reconciled", {"draft_id": row.id, "status": row.status}, actor="human")
            self.db.commit()
            return row
