from sqlalchemy import select
from app.models.agent import AgentPreferences, AgentRun, KnowledgeDocument


class AgentRepository:
    def __init__(self, db):
        self.db = db

    def documents(self):
        return list(self.db.scalars(select(KnowledgeDocument).order_by(KnowledgeDocument.id).limit(500)))

    def document(self, key):
        return self.db.get(KnowledgeDocument, key, populate_existing=True)

    def preferences(self):
        return self.db.get(AgentPreferences, 1, populate_existing=True)

    def runs(self, offset=0, message_id=None):
        query = select(AgentRun).order_by(AgentRun.id.desc()).offset(offset).limit(50)
        if message_id is not None:
            query = query.where(AgentRun.message_id == message_id)
        return list(self.db.scalars(query))

    def abandon_previous(self, message_id):
        # Caller holds the message/draft operation lock. A surviving running row
        # therefore belongs to an interrupted earlier attempt.
        for row in self.db.scalars(select(AgentRun).where(AgentRun.message_id == message_id, AgentRun.status == "running")):
            row.status = "interrupted"
            row.events = [*row.events, {"tool": "stopped", "summary": "Previous execution interrupted before completion", "elapsed_ms": row.elapsed_ms, "usage": None}]

    def run(self, key):
        return self.db.get(AgentRun, key)

    def add(self, row):
        self.db.add(row)
        self.db.flush()
        return row
