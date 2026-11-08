from fastapi import APIRouter, Depends, Query

from app.api.deps import get_services, require_api_key
from app.container import Services
from app.schemas.api import MessageOut, ResolveReviewIn, ReviewItemOut

router = APIRouter(prefix="/review", tags=["review"], dependencies=[Depends(require_api_key)])


@router.get("", response_model=list[ReviewItemOut])
def pending_reviews(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), svc: Services = Depends(get_services)):
    return [{"message": m, "suggestion": c} for m, c in svc.review.pending(limit=limit, offset=offset)]


@router.post("/{message_id}/resolve", response_model=MessageOut)
def resolve_review(message_id: int, body: ResolveReviewIn, svc: Services = Depends(get_services)):
    return svc.review.resolve(message_id, body.category, body.priority)
