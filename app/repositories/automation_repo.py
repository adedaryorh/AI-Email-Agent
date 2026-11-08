from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.automation import Draft, Rule

class AutomationRepository:
    def __init__(self, db: Session):
        self.db = db

    def rules(self, enabled_only=False):
        query = select(Rule).order_by(Rule.position, Rule.id)
        if enabled_only:
            query = query.where(Rule.enabled.is_(True))
        return list(self.db.scalars(query))

    def rule(self, rule_id):
        return self.db.get(Rule, rule_id)

    def add(self, row):
        self.db.add(row)
        self.db.flush()
        return row

    def delete(self, row):
        self.db.delete(row)

    def draft(self, draft_id):
        return self.db.get(Draft, draft_id)

    def draft_for(self, message_id):
        return self.db.scalar(select(Draft).where(Draft.message_id == message_id))

    def drafts(self, status=None, limit=50, offset=0):
        query = select(Draft).order_by(Draft.id.desc())
        if status:
            query = query.where(Draft.status == status)
        return list(self.db.scalars(query.limit(limit).offset(offset)))
