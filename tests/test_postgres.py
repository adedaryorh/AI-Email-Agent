"""Run with TEST_POSTGRES_URL set to a disposable local/CI PostgreSQL database."""
import os
import uuid
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from app.core.config import Settings, get_settings
from app.models.mailbox import Mailbox
from app.models.message import Message
from app.schemas.classification import ClassificationResult
from app.models.enums import Category, Priority
from datetime import UTC, datetime
from tests.conftest import FakeAssistant, FakeClassifier, FakeGmail

pytestmark = [pytest.mark.postgres, pytest.mark.skipif(not os.getenv("TEST_POSTGRES_URL"), reason="TEST_POSTGRES_URL not configured")]


def test_postgres_migrations_and_review_across_connections(monkeypatch):
    from alembic import command
    from alembic.config import Config
    from langgraph.checkpoint.postgres import PostgresSaver
    from app.container import build_services
    base = os.environ["TEST_POSTGRES_URL"]
    schema = "test_" + uuid.uuid4().hex
    admin = create_engine(base, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    url = make_url(base).update_query_dict({"options": f"-csearch_path={schema}"}).render_as_string(hide_password=False)
    settings = Settings(database_url=url, encryption_key=get_settings().encryption_key)
    engine = create_engine(url)
    try:
        monkeypatch.setenv("DATABASE_URL", url)
        get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")
        classifier = FakeClassifier(ClassificationResult(category=Category.OTHER, priority=Priority.NORMAL, confidence=0.2, reason="ambiguous"))
        gmail = FakeGmail()
        with sessionmaker(engine, expire_on_commit=False)() as db:
            mailbox = Mailbox(email="test@example.test", encrypted_refresh_token="fake")
            db.add(mailbox)
            db.flush()
            message = Message(mailbox_id=mailbox.id, gmail_id="g1", thread_id="t1", sender="a@example.test", body_text="Help", received_at=datetime.now(UTC))
            db.add(message)
            db.commit()
            message_id = message.id
            with PostgresSaver.from_conn_string(settings.psycopg_conninfo) as saver:
                saver.setup()
                svc = build_services(db, settings=settings, classifier=classifier, gmail_factory=lambda _: gmail, assistant=FakeAssistant(), checkpointer=saver)
                assert svc.sorting.process(message_id) == "needs_review"
        with sessionmaker(engine, expire_on_commit=False)() as db:
            with PostgresSaver.from_conn_string(settings.psycopg_conninfo) as saver:
                svc = build_services(db, settings=settings, classifier=classifier, gmail_factory=lambda _: gmail, assistant=FakeAssistant(), checkpointer=saver)
                assert svc.review.resolve(message_id, Category.BILLING, None).status == "done"
                assert gmail.modified == [("g1", ["Label_1"], [])]
    finally:
        get_settings.cache_clear()
        engine.dispose()
        with admin.connect() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def test_advisory_lock_survives_commit_and_excludes_other_processes():
    import subprocess
    import sys

    from app.core.locks import operation_lock

    url = os.environ["TEST_POSTGRES_URL"]
    engine = create_engine(url)
    identity = uuid.uuid4().int % (2**31 - 1)
    child = """
import os
from sqlalchemy import create_engine, text
engine = create_engine(os.environ['TEST_LOCK_URL'], isolation_level='AUTOCOMMIT')
with engine.connect() as connection:
    args = {'identity': int(os.environ['TEST_LOCK_ID'])}
    acquired = connection.scalar(text('SELECT pg_try_advisory_lock(1, :identity)'), args)
    print('acquired' if acquired else 'blocked')
    if acquired:
        connection.execute(text('SELECT pg_advisory_unlock(1, :identity)'), args)
engine.dispose()
"""

    def check_child():
        result = subprocess.run(
            [sys.executable, "-c", child], capture_output=True, text=True, timeout=15,
            env={**os.environ, "TEST_LOCK_URL": url, "TEST_LOCK_ID": str(identity)},
        )
        assert result.returncode == 0, "Postgres lock probe failed"
        return result.stdout.strip()

    try:
        with sessionmaker(engine)() as db:
            with operation_lock(db, 1, identity):
                db.execute(text("SELECT 1"))
                db.commit()
                assert check_child() == "blocked"
            assert check_child() == "acquired"
    finally:
        engine.dispose()
