import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from fastapi import HTTPException
from app.core.passwords import verify_password
from app.repositories.session_repo import SessionRepository

SESSION_COOKIE = "email_session"
CSRF_COOKIE = "XSRF-TOKEN"

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

class SessionService:
    def __init__(self, db, settings):
        self.db, self.settings = db, settings
        self.repository = SessionRepository(db)

    def credential_version(self):
        return digest(self.settings.browser_username + ":" + self.settings.browser_password_hash)

    def login(self, username, password, old_token=None):
        if not self.settings.browser_password_hash:
            raise HTTPException(503, "Browser login is not configured. Run scripts/setup_login.py on the server.")
        valid = verify_password(password, self.settings.browser_password_hash)
        if not valid or not secrets.compare_digest(username.encode(), self.settings.browser_username.encode()):
            raise HTTPException(401, "Invalid username or password")
        if old_token:
            self.repository.delete(digest(old_token))
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        self.repository.create(token_hash=digest(token), csrf_hash=digest(csrf), username=username,
            credential_version=self.credential_version(),
            expires_at=datetime.now(UTC) + timedelta(seconds=self.settings.session_ttl_seconds))
        self.db.commit()
        return token, csrf

    def authenticate(self, token, csrf=None, mutation=False):
        if not token or len(token) > 128:
            raise HTTPException(401, "Sign in to continue")
        row = self.repository.get(digest(token))
        now = datetime.now(UTC)
        expires = row.expires_at if row else now
        expires = expires.replace(tzinfo=UTC) if expires.tzinfo is None else expires.astimezone(UTC)
        if not row or expires <= now or row.credential_version != self.credential_version():
            raise HTTPException(401, "Session expired. Sign in again")
        if mutation and (not csrf or not secrets.compare_digest(row.csrf_hash, digest(csrf))):
            raise HTTPException(403, "Invalid CSRF token. Sign in again to refresh your browser session")
        return row

    def logout(self, token):
        if token:
            self.repository.delete(digest(token))
            self.db.commit()
