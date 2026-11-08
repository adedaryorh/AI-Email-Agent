from datetime import UTC, datetime
from sqlalchemy import delete
from app.models.web_session import WebSession

class SessionRepository:
    def __init__(self, db):
        self.db = db

    def get(self, token_hash):
        return self.db.get(WebSession, token_hash)

    def create(self, **values):
        self.db.execute(delete(WebSession).where(WebSession.expires_at <= datetime.now(UTC)))
        row = WebSession(**values)
        self.db.add(row)
        return row

    def delete(self, token_hash):
        self.db.execute(delete(WebSession).where(WebSession.token_hash == token_hash))
