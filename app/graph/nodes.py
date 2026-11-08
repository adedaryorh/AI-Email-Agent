from dataclasses import dataclass
from langgraph.types import interrupt
from app.graph.state import SortingState
from app.models.enums import Category, MessageStatus, Priority
from app.services.message_service import MessageService
from app.services.action_service import ActionService
from app.services.classification_service import ClassificationService

@dataclass
class GraphDeps:
    messages: MessageService
    classification: ClassificationService
    actions: ActionService
    review_threshold: float
    enrichment: object
    rules: object
    drafts: object


def make_nodes(deps: GraphDeps):
    def classify(state: SortingState):
        message = deps.messages.get(state["message_id"])
        row = deps.classification.classify_and_store(message)
        return {"classification_id": row.id, "needs_review": row.confidence < deps.review_threshold}

    def human_review(state: SortingState):
        message = deps.messages.get(state["message_id"])
        suggestion = deps.classification.get(state["classification_id"])
        deps.classification.queue_for_review(message, suggestion)
        decision = interrupt({"message_id": message.id, "suggested_category": suggestion.category,
                              "suggested_priority": suggestion.priority, "confidence": suggestion.confidence})
        priority = Priority(decision["priority"]) if decision.get("priority") else None
        row = deps.classification.record_human_decision(message, Category(decision["category"]), priority)
        return {"classification_id": row.id, "needs_review": False}

    def extract(state: SortingState):
        deps.enrichment.extract(deps.messages.get(state["message_id"]))
        return {}

    def rules(state: SortingState):
        deps.rules.evaluate(deps.messages.get(state["message_id"]), deps.classification.get(state["classification_id"]))
        return {}

    def apply_actions(state: SortingState):
        deps.actions.apply(deps.messages.get(state["message_id"]), deps.classification.get(state["classification_id"]))
        return {}

    def draft(state: SortingState):
        message = deps.messages.get(state["message_id"])
        if (message.action_plan or {}).get("draft"):
            deps.drafts.ensure(message)
        deps.classification.finish(message)
        return {"status": MessageStatus.DONE.value}

    return {"classify": classify, "human_review": human_review, "extract": extract,
            "rules": rules, "apply_actions": apply_actions, "draft": draft}
