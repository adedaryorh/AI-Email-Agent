from datetime import UTC, datetime, timedelta
from sqlalchemy import delete
from app.models.automation import OAuthState

class OAuthRepository:
    def __init__(self, db):
        self.db = db

    def issue(self, nonce, lifetime):
        self.db.execute(delete(OAuthState).where(OAuthState.expires_at < datetime.now(UTC)))
        self.db.add(OAuthState(nonce=nonce, expires_at=datetime.now(UTC) + timedelta(seconds=lifetime)))

    def consume(self, nonce):
        result = self.db.execute(delete(OAuthState).where(OAuthState.nonce == nonce, OAuthState.expires_at >= datetime.now(UTC)))
        return result.rowcount == 1
