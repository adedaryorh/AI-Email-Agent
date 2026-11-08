from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.deps import get_services, require_api_key
from app.container import Services
from app.schemas.api import ConnectUrlOut, MailboxOut, SyncOut

router = APIRouter(prefix="/mailboxes", tags=["mailboxes"])


@router.get("", response_model=list[MailboxOut], dependencies=[Depends(require_api_key)])
def list_mailboxes(svc: Services = Depends(get_services)):
    return svc.mailboxes.list()


@router.get("/connect/gmail", response_model=ConnectUrlOut, dependencies=[Depends(require_api_key)])
def connect_gmail(svc: Services = Depends(get_services)):
    return ConnectUrlOut(auth_url=svc.mailboxes.build_connect_url())


@router.get("/oauth/gmail/callback")
def gmail_callback(code: str, state: str, svc: Services = Depends(get_services)):
    # Browser redirect from Google: no API key, protected by the signed `state`.
    mailbox = svc.mailboxes.connect_gmail(code=code, state=state)
    return JSONResponse({"connected": mailbox.email, "mailbox_id": mailbox.id})


@router.post("/{mailbox_id}/sync", response_model=SyncOut, dependencies=[Depends(require_api_key)])
def sync_mailbox(
    mailbox_id: int, svc: Services = Depends(get_services)
):
    new_ids = svc.sync.sync_mailbox(mailbox_id)
    return SyncOut(mailbox_id=mailbox_id, new_messages=len(new_ids))
