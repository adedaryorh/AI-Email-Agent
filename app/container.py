"""Composition root: wires repositories -> services -> graph for one DB session."""

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import Cipher
from app.graph.checkpointer import get_checkpointer
from app.integrations.gmail.client import GmailGateway
from app.integrations.llm.classifier import Classifier, LLMClassifier
from app.models.mailbox import Mailbox
from app.repositories.action_log_repo import ActionLogRepository
from app.repositories.classification_repo import ClassificationRepository
from app.repositories.mailbox_repo import MailboxRepository
from app.repositories.message_repo import MessageRepository
from app.services.action_service import ActionService
from app.services.classification_service import ClassificationService
from app.services.mailbox_service import MailboxService
from app.services.review_service import ReviewService
from app.services.sorting_service import SortingService
from app.services.sync_service import SyncService
from app.services.message_service import MessageService
from app.services.enrichment_service import EnrichmentService
from app.services.rule_service import RuleService
from app.services.draft_service import DraftService
from app.repositories.automation_repo import AutomationRepository
from app.integrations.llm.assistant import EmailAssistant


@dataclass
class Services:
    mailboxes: MailboxService
    sync: SyncService
    classification: ClassificationService
    actions: ActionService
    sorting: SortingService
    review: ReviewService
    messages: MessageService
    rules: RuleService
    drafts: DraftService


def build_services(
    db: Session,
    *,
    settings: Settings | None = None,
    classifier: Classifier | None = None,
    gmail_factory: Callable[[Mailbox], GmailGateway] | None = None,
    checkpointer=None,
    assistant=None,
) -> Services:
    """Overridable seams (classifier, gmail_factory, checkpointer) exist for tests."""
    from app.graph.builder import build_sorting_graph
    from app.graph.nodes import GraphDeps

    settings = settings or get_settings()

    mailbox_repo = MailboxRepository(db)
    message_repo = MessageRepository(db)
    classification_repo = ClassificationRepository(db)
    action_log = ActionLogRepository(db)

    mailbox_service = MailboxService(db, mailbox_repo, Cipher(settings.encryption_key), settings)
    gmail_factory = gmail_factory or mailbox_service.gmail_for
    classifier = classifier or LLMClassifier(settings)

    sync = SyncService(db, mailbox_repo, message_repo, gmail_factory, settings)
    classification = ClassificationService(
        db, classifier, classification_repo, action_log, settings
    )
    actions = ActionService(db, mailbox_repo, action_log, gmail_factory)

    messages = MessageService(message_repo)
    automation_repo = AutomationRepository(db)
    assistant = assistant or EmailAssistant(settings)
    enrichment = EnrichmentService(db, assistant, action_log)
    rules = RuleService(db, automation_repo, messages, classification, action_log)
    drafts = DraftService(db, automation_repo, messages, mailbox_repo, gmail_factory, assistant, action_log, settings)

    graph = build_sorting_graph(
        GraphDeps(messages, classification, actions, settings.review_confidence_threshold, enrichment, rules, drafts),
        checkpointer or get_checkpointer(settings),
    )
    sorting = SortingService(db, graph, message_repo, action_log, settings)
    review = ReviewService(db, message_repo, classification, sorting)

    return Services(mailbox_service, sync, classification, actions, sorting, review, messages, rules, drafts)
