from datetime import UTC, datetime, timedelta
from sqlalchemy import select, update
from app.models.message import Message
from app.models.automation import Draft

class RetentionRepository:
    def __init__(self, db):
        self.db = db

    def purge(self, days):
        cutoff = datetime.now(UTC) - timedelta(days=days)
        pending = select(Draft.message_id).where(Draft.status.not_in(["sent", "rejected"]))
        rows = list(self.db.scalars(select(Message).where(
            Message.status == "done", Message.received_at < cutoff,
            Message.id.not_in(pending), Message.body_text != "",
        )))
        for row in rows:
            row.body_text = ""
            row.entities = {}
            row.headers = {}
        self.db.execute(update(Draft).where(Draft.status.in_(["sent", "rejected"]), Draft.updated_at < cutoff).values(body="", sources=[], verification={}))
        return len(rows)
