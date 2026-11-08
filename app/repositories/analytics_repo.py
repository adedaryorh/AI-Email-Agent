from sqlalchemy import select, func
from app.models.message import Message
from app.models.automation import Draft
from app.models.classification import Classification

class AnalyticsRepository:
    def __init__(self, db):
        self.db = db

    def overview(self):
        messages = dict(self.db.execute(select(Message.status, func.count()).group_by(Message.status)).all())
        drafts = dict(self.db.execute(select(Draft.status, func.count()).group_by(Draft.status)).all())
        latest = select(func.max(Classification.id).label("id")).group_by(Classification.message_id).subquery()
        categories = dict(self.db.execute(select(Classification.category, func.count()).where(Classification.id.in_(select(latest.c.id))).group_by(Classification.category)).all())
        return {"messages_by_status": messages, "drafts_by_status": drafts, "categories": categories}
