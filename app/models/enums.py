from enum import StrEnum


class Category(StrEnum):
    SUPPORT = "support"
    BILLING = "billing"
    SALES = "sales"
    NEWSLETTER = "newsletter"
    PERSONAL = "personal"
    SPAM = "spam"
    OTHER = "other"


class Priority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class MessageStatus(StrEnum):
    NEW = "new"
    PROCESSING = "processing"
    NEEDS_REVIEW = "needs_review"
    DONE = "done"
    FAILED = "failed"


class ClassificationSource(StrEnum):
    AI = "ai"
    HUMAN = "human"
