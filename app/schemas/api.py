from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import Category, Priority


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MailboxOut(ORMModel):
    id: int
    email: str
    provider: str
    last_synced_at: datetime | None


class ClassificationOut(ORMModel):
    id: int
    category: str
    priority: str
    confidence: float
    reason: str
    source: str
    model: str
    prompt_version: str
    created_at: datetime


class ActionLogOut(ORMModel):
    id: int
    action: str
    detail: dict
    actor: str
    created_at: datetime


class MessageOut(ORMModel):
    id: int
    mailbox_id: int
    gmail_id: str
    thread_id: str
    sender: str
    subject: str
    status: str
    received_at: datetime


class MessageDetailOut(MessageOut):
    entities: dict | None
    action_plan: dict | None
    attempts: int
    body_text: str
    classifications: list[ClassificationOut]
    actions: list[ActionLogOut]


class ReviewItemOut(BaseModel):
    message: MessageOut
    suggestion: ClassificationOut | None


class ResolveReviewIn(BaseModel):
    category: Category
    priority: Priority | None = None


class ConnectUrlOut(BaseModel):
    auth_url: str


class SyncOut(BaseModel):
    mailbox_id: int
    new_messages: int
