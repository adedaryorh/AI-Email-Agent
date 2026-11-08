from urllib.parse import urlparse, parse_qs
import pytest
from app.core.config import get_settings, Settings
from app.core.security import Cipher
from app.core.rate_limit import RateLimiter
from app.core.privacy import redact
from app.core.exceptions import AppError, ConflictError
from app.core.locks import operation_lock
from app.repositories.mailbox_repo import MailboxRepository
from app.services.mailbox_service import MailboxService


def test_oauth_state_is_consumed_even_if_exchange_fails(db, monkeypatch):
    svc = MailboxService(db, MailboxRepository(db), Cipher(get_settings().encryption_key), get_settings())
    state = parse_qs(urlparse(svc.build_connect_url()).query)["state"][0]
    calls = []
    def exchange(**kwargs):
        calls.append(kwargs)
        raise RuntimeError("offline")
    monkeypatch.setattr("app.services.mailbox_service.oauth.exchange_code", exchange)
    with pytest.raises(RuntimeError):
        svc.connect_gmail(code="code", state=state)
    with pytest.raises(AppError):
        svc.connect_gmail(code="code", state=state)
    assert len(calls) == 1


def test_invalid_oauth_state_never_exchanges(db, monkeypatch):
    svc = MailboxService(db, MailboxRepository(db), Cipher(get_settings().encryption_key), get_settings())
    monkeypatch.setattr("app.services.mailbox_service.oauth.exchange_code", lambda **_: pytest.fail("invalid state exchanged"))
    with pytest.raises(AppError):
        svc.connect_gmail(code="code", state="bad")


def test_production_rejects_default_keys():
    with pytest.raises(ValueError):
        Settings(app_env="production", encryption_key=get_settings().encryption_key)


def test_lock_prevents_concurrent_message_work(db):
    with operation_lock(db, 1, 99):
        with pytest.raises(ConflictError):
            with operation_lock(db, 1, 99):
                pytest.fail("duplicate lock")
    with operation_lock(db, 1, 99):
        pass


def test_rate_limit_window():
    now = [0]
    limiter = RateLimiter(2, lambda: now[0])
    assert limiter.allow() and limiter.allow()
    assert not limiter.allow()
    now[0] = 61
    assert limiter.allow()


def test_redaction_masks_common_contacts():
    assert redact({"email": "me@example.com", "phone": "+43 123 456 7890"}) == {"email": "[EMAIL]", "phone": "[PHONE]"}
