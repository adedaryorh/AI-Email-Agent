import os

from cryptography.fernet import Fernet

os.environ.setdefault("ENCRYPTION_KEY", Fernet.generate_key().decode())
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["API_KEY"] = "test-key"

from datetime import UTC, datetime  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import app.models  # noqa: E402,F401
from app.core.config import get_settings  # noqa: E402
from app.core.database import Base, make_engine  # noqa: E402
from app.models.mailbox import Mailbox  # noqa: E402
from app.models.message import Message  # noqa: E402
from app.schemas.classification import ClassificationResult  # noqa: E402


class FakeClassifier:
    model_name = "fake"
    prompt_version = "test"

    def __init__(self, result: ClassificationResult):
        self.result = result

    def classify(self, **_):
        return self.result


class FakeGmail:
    def __init__(self):
        self.labels: dict[str, str] = {}
        self.modified: list[tuple[str, list[str], list[str]]] = []

    def thread_context(self, thread_id, max_chars):
        return []

    def create_draft(self, draft, message):
        return {"id": "draft-1"}

    def update_draft(self, draft, message):
        return {"id": draft.gmail_draft_id}

    def send_draft(self, draft, message):
        return {"id": "sent-1"}

    def get_profile(self):
        return {"emailAddress": "me@example.com", "historyId": "100"}

    def list_message_ids(self, query, max_results):
        return []

    def get_message(self, message_id):
        raise NotImplementedError

    def list_history(self, start_history_id):
        return [], start_history_id

    def get_or_create_label(self, name):
        return self.labels.setdefault(name, f"Label_{len(self.labels) + 1}")

    def modify_labels(self, message_id, add, remove):
        self.modified.append((message_id, add, remove))


@pytest.fixture
def db():
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as session:
        yield session


@pytest.fixture
def message(db):
    mailbox = Mailbox(email="me@example.com", encrypted_refresh_token="x")
    db.add(mailbox)
    db.flush()
    msg = Message(
        mailbox_id=mailbox.id,
        gmail_id="g1",
        thread_id="t1",
        sender="a@b.com",
        subject="Help",
        body_text="my login is broken",
        received_at=datetime.now(UTC),
    )
    db.add(msg)
    db.commit()
    return msg


@pytest.fixture
def make_services(db):
    from app.container import build_services
    from langgraph.checkpoint.memory import InMemorySaver

    def _make(result: ClassificationResult, gmail: FakeGmail):
        return build_services(
            db,
            settings=get_settings(),
            classifier=FakeClassifier(result),
            gmail_factory=lambda _mb: gmail,
            checkpointer=InMemorySaver(),
            assistant=FakeAssistant(),
        )

    return _make


class FakeAssistant:
    def extract(self, message):
        return {"invoice_numbers": ["INV-100"], "requested_action": "Help with payment"}

    def draft(self, message, context, template):
        return "Thanks for your message. Could you share more details?"

    def plan(self, data):
        return {"tool": "finish", "query": ""}

    def compose(self, data):
        return {"body": "Thanks for your message. Could you share more details?", "citations": []}

    def verify(self, data):
        return {"passed": True, "findings": []}
