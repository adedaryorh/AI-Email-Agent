from fastapi import APIRouter, Depends, Query
from app.api.deps import get_services, require_api_key
from app.container import Services
from app.schemas.automation import DraftOut, DraftEditIn, DraftReconcileIn, VersionIn

router = APIRouter(prefix="/drafts", tags=["drafts"], dependencies=[Depends(require_api_key)])

@router.get("", response_model=list[DraftOut])
def list_drafts(status: str | None = None, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), svc: Services = Depends(get_services)):
    return svc.drafts.list(status=status, limit=limit, offset=offset)

@router.post("/for-message/{message_id}", response_model=DraftOut)
def generate(message_id: int, svc: Services = Depends(get_services)):
    return svc.drafts.generate(message_id)

@router.get("/{draft_id}", response_model=DraftOut)
def get_draft(draft_id: int, svc: Services = Depends(get_services)):
    return svc.drafts.get(draft_id)

@router.patch("/{draft_id}", response_model=DraftOut)
def edit(draft_id: int, body: DraftEditIn, svc: Services = Depends(get_services)):
    return svc.drafts.edit(draft_id, body.version, body.body)

@router.post("/{draft_id}/regenerate", response_model=DraftOut)
def regenerate(draft_id: int, body: VersionIn, svc: Services = Depends(get_services)):
    return svc.drafts.edit(draft_id, body.version, regenerate=True)

@router.post("/{draft_id}/approve", response_model=DraftOut)
def approve(draft_id: int, body: VersionIn, svc: Services = Depends(get_services)):
    return svc.drafts.decide(draft_id, body.version, True)

@router.post("/{draft_id}/reject", response_model=DraftOut)
def reject(draft_id: int, body: VersionIn, svc: Services = Depends(get_services)):
    return svc.drafts.decide(draft_id, body.version, False)

@router.post("/{draft_id}/send", response_model=DraftOut)
def send(draft_id: int, body: VersionIn, svc: Services = Depends(get_services)):
    return svc.drafts.send(draft_id, body.version)

@router.post("/{draft_id}/reconcile", response_model=DraftOut)
def reconcile(draft_id: int, body: DraftReconcileIn, svc: Services = Depends(get_services)):
    return svc.drafts.reconcile(draft_id, body)
