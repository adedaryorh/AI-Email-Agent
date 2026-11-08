from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class DocumentIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=50000)
    version: int = Field(default=1, ge=1)


class DocumentOut(DocumentIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class PreferencesIn(BaseModel):
    instructions: str = Field(default="", max_length=4000)
    version: int = Field(default=0, ge=0)


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool: Literal["search_knowledge", "read_thread", "request_clarification", "finish"]
    query: str = Field(default="", max_length=500)


class GroundedReply(BaseModel):
    body: str = Field(min_length=1, max_length=20000)
    citations: list[str] = Field(default_factory=list, max_length=12)


class Verification(BaseModel):
    passed: bool
    findings: list[str] = Field(default_factory=list, max_length=20)
