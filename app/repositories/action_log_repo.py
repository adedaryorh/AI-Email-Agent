from sqlalchemy.orm import Session

from app.models.action_log import ActionLog


class ActionLogRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(
        self, message_id: int, action: str, detail: dict | None = None, actor: str = "agent"
    ) -> ActionLog:
        row = ActionLog(message_id=message_id, action=action, detail=detail or {}, actor=actor)
        self.db.add(row)
        self.db.flush()
        return row
