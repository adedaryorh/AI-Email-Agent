from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.api.deps import require_api_key
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.schemas.agent import DocumentIn, DocumentOut, PreferencesIn
from app.services.knowledge_service import KnowledgeService
from app.repositories.agent_repo import AgentRepository

router = APIRouter(tags=["agent"], dependencies=[Depends(require_api_key)])


@router.get("/knowledge", response_model=list[DocumentOut])
def documents(db: Session = Depends(get_db)):
    return AgentRepository(db).documents()


@router.post("/knowledge", response_model=DocumentOut)
def create_document(data: DocumentIn, db: Session = Depends(get_db)):
    return KnowledgeService(db).save(data)


@router.put("/knowledge/{key}", response_model=DocumentOut)
def update_document(key: int, data: DocumentIn, db: Session = Depends(get_db)):
    return KnowledgeService(db).save(data, key)


@router.delete("/knowledge/{key}", status_code=204)
def delete_document(key: int, version: int = Query(ge=1), db: Session = Depends(get_db)):
    KnowledgeService(db).delete(key, version)


@router.get("/preferences", response_model=PreferencesIn)
def preferences(db: Session = Depends(get_db)):
    return KnowledgeService(db).preferences()


@router.put("/preferences", response_model=PreferencesIn)
def save_preferences(data: PreferencesIn, db: Session = Depends(get_db)):
    return KnowledgeService(db).set_preferences(data)


def run_summary(row):
    return {"id": row.id, "message_id": row.message_id, "status": row.status,
            "elapsed_ms": row.elapsed_ms, "input_chars": row.input_chars, "created_at": row.created_at}


@router.get("/agent/runs")
def runs(offset: int = Query(default=0, ge=0), message_id: int | None = None, db: Session = Depends(get_db)):
    return [run_summary(row) for row in AgentRepository(db).runs(offset, message_id)]


@router.get("/agent/runs/{key}")
def run(key: int, db: Session = Depends(get_db)):
    row = AgentRepository(db).run(key)
    if not row:
        raise NotFoundError("Agent run not found")
    return {**run_summary(row), "events": row.events}
