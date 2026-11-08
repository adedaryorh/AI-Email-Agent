from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.models.enums import Priority

class Entities(BaseModel):
    invoice_numbers: list[str] = Field(default_factory=list, max_length=20)
    dates: list[str] = Field(default_factory=list, max_length=20)
    amounts: list[str] = Field(default_factory=list, max_length=20)
    order_ids: list[str] = Field(default_factory=list, max_length=20)
    requested_action: str = Field(default="", max_length=1000)

class ReplyContent(BaseModel):
    body: str = Field(min_length=1, max_length=20000)

class Condition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: Literal["category", "priority", "sender", "subject", "entities.invoice_numbers", "entities.order_ids", "entities.requested_action", "entities.amounts", "entities.dates"]
    op: Literal["eq", "contains", "exists"]
    value: str = Field(default="", max_length=500)

class RuleAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["label", "archive", "set_priority", "draft"]
    value: str = Field(default="", max_length=200)

    @model_validator(mode="after")
    def validate_value(self):
        if self.type == "label" and (not self.value.startswith("AI/") or len(self.value) < 4 or any(ord(c)<32 for c in self.value)):
            raise ValueError("Custom labels must start with AI/ and contain no control characters")
        if self.type == "set_priority":
            Priority(self.value)
        return self

class RuleDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conditions: list[Condition] = Field(min_length=1, max_length=20)
    actions: list[RuleAction] = Field(min_length=1, max_length=10)

class RuleIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    enabled: bool = True
    position: int = Field(default=100, ge=0, le=10000)
    definition: RuleDefinition

class RuleOut(RuleIn):
    model_config = ConfigDict(from_attributes=True)
    id: int

class RuleTestIn(BaseModel):
    message_id: int

class DraftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    message_id: int
    recipient: str
    subject: str
    body: str
    status: str
    version: int
    sources: list[dict] = Field(default_factory=list)
    verification: dict = Field(default_factory=dict)
    agent_run_id: int | None = None
    gmail_draft_id: str | None
    gmail_message_id: str | None
    created_at: datetime

class VersionIn(BaseModel):
    version: int = Field(ge=1)

class DraftEditIn(VersionIn):
    body: str = Field(min_length=1, max_length=20000)

class DraftReconcileIn(VersionIn):
    gmail_draft_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]+$", max_length=128)
    gmail_message_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]+$", max_length=128)

    @model_validator(mode="after")
    def exactly_one(self):
        if bool(self.gmail_draft_id) == bool(self.gmail_message_id):
            raise ValueError("Provide exactly one Gmail draft ID or sent message ID")
        return self
