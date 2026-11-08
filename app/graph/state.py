from typing import TypedDict


class SortingState(TypedDict, total=False):
    """Kept tiny on purpose: it is checkpointed, so it holds ids, not email bodies."""

    message_id: int
    classification_id: int
    needs_review: bool
    status: str
