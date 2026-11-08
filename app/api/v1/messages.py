from fastapi import APIRouter, Depends, Query

from app.api.deps import get_services, require_api_key
from app.container import Services
from app.core.exceptions import NotFoundError
from app.schemas.api import MessageDetailOut, MessageOut

router = APIRouter(prefix="/messages", tags=["messages"], dependencies=[Depends(require_api_key)])


@router.get("", response_model=list[MessageOut])
def list_messages(
    status: str | None = None,
    mailbox_id: int | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    svc: Services = Depends(get_services),
):
    return svc.messages.list(status=status, mailbox_id=mailbox_id, limit=limit, offset=offset)


@router.get("/{message_id}", response_model=MessageDetailOut)
def get_message(message_id: int, svc: Services = Depends(get_services)):
    message = svc.messages.get(message_id)
    if not message:
        raise NotFoundError(f"Message {message_id} not found")
    return message

@router.post("/{message_id}/retry", response_model=MessageOut)
def retry_message(message_id: int, svc: Services = Depends(get_services)):
    svc.sorting.process(message_id, manual=True)
    return svc.messages.get(message_id)
