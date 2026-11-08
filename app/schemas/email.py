from datetime import datetime

from pydantic import BaseModel, Field


class ParsedEmail(BaseModel):
    """Provider-neutral email, as produced by an integration parser."""

    gmail_id: str
    thread_id: str
    sender: str
    subject: str = ""
    body_text: str = ""
    has_unsubscribe: bool = False
    headers: dict[str, str] = Field(default_factory=dict)
    label_ids: list[str] = Field(default_factory=list)
    received_at: datetime
