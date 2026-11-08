from pydantic import BaseModel, Field

from app.models.enums import Category, Priority


class ClassificationResult(BaseModel):
    """Structured output the LLM must return."""

    category: Category
    priority: Priority
    confidence: float = Field(ge=0.0, le=1.0, description="0-1 certainty in the category")
    reason: str = Field(max_length=300, description="One sentence explaining the choice")
