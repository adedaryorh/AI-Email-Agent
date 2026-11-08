from pathlib import Path
import json
from app.core.privacy import redact
from typing import Protocol


from app.core.config import Settings
from app.integrations.llm.factory import get_chat_model
from app.schemas.classification import ClassificationResult

PROMPT_VERSION = "v2"
_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / f"classify_{PROMPT_VERSION}.txt"


class Classifier(Protocol):
    model_name: str
    prompt_version: str

    def classify(
        self, *, sender: str, subject: str, body_text: str, has_unsubscribe: bool
    ) -> ClassificationResult: ...


class LLMClassifier:
    """Structured-output classifier. The model is built lazily on first use."""

    prompt_version = PROMPT_VERSION

    def __init__(self, settings: Settings):
        self._settings = settings
        self.model_name = settings.llm_model
        self._chain = None
        self._system_prompt = _PROMPT_PATH.read_text()

    def _get_chain(self):
        if self._chain is None:
            self._chain = get_chat_model(self._settings).with_structured_output(
                ClassificationResult
            )
        return self._chain

    def _render(self, sender: str, subject: str, body_text: str, has_unsubscribe: bool) -> str:
        data = {"sender": sender, "subject": subject, "has_unsubscribe": has_unsubscribe,
                "body": body_text[:self._settings.max_body_chars]}
        if self._settings.redact_pii:
            data = redact(data)
        return json.dumps(data, ensure_ascii=False)

    def classify(
        self, *, sender: str, subject: str, body_text: str, has_unsubscribe: bool
    ) -> ClassificationResult:
        from langchain_core.messages import HumanMessage, SystemMessage

        messages = [
            SystemMessage(self._system_prompt),
            HumanMessage(self._render(sender, subject, body_text, has_unsubscribe)),
        ]
        result = self._get_chain().invoke(messages)
        if isinstance(result, dict):
            result = ClassificationResult.model_validate(result)
        return result
