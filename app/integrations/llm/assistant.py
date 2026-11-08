import json
from pathlib import Path
from app.integrations.llm.factory import get_chat_model
from app.core.privacy import redact
from app.schemas.automation import Entities, ReplyContent

class EmailAssistant:
    def __init__(self, settings):
        self.settings = settings

    def _invoke(self, prompt, schema, data):
        from langchain_core.messages import HumanMessage, SystemMessage

        if self.settings.redact_pii:
            data = redact(data)
        text = (Path(__file__).resolve().parents[2] / "prompts" / prompt).read_text()
        agent_call = prompt.startswith("agent_")
        options = {"timeout": getattr(self, "call_timeout_seconds", 45), "max_retries": 0, "max_tokens": self.settings.agent_max_output_tokens} if agent_call else {}
        model = get_chat_model(self.settings, **options)
        self.last_usage = None
        result = model.with_structured_output(schema, include_raw=agent_call).invoke([
            SystemMessage(text), HumanMessage(json.dumps(data, ensure_ascii=False))
        ])
        if agent_call:
            if result.get("parsing_error") or result.get("parsed") is None:
                raise ValueError("Invalid structured agent response")
            usage = getattr(result.get("raw"), "usage_metadata", None)
            if usage:
                self.last_usage = {key: usage[key] for key in ("input_tokens", "output_tokens", "total_tokens") if key in usage}
            result = result["parsed"]
        return schema.model_validate(result) if isinstance(result, dict) else result

    def extract(self, message):
        return self._invoke("extract_v1.txt", Entities, {
            "sender": message.sender, "subject": message.subject,
            "body": message.body_text[:self.settings.max_body_chars]
        }).model_dump()

    def draft(self, message, context, template):
        return self._invoke("draft_v1.txt", ReplyContent, {
            "sender": message.sender, "subject": message.subject,
            "body": message.body_text[:self.settings.max_body_chars],
            "thread": context, "style_template": template,
        }).body

    def plan(self, data):
        from app.schemas.agent import Decision
        return self._invoke("agent_plan_v1.txt", Decision, data).model_dump()

    def compose(self, data):
        from app.schemas.agent import GroundedReply
        return self._invoke("agent_draft_v1.txt", GroundedReply, data).model_dump()

    def verify(self, data):
        from app.schemas.agent import Verification
        return self._invoke("agent_verify_v1.txt", Verification, data).model_dump()
