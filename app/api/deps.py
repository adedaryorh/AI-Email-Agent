import secrets

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.container import build_services
from app.core.config import get_settings
from app.core.database import get_db


def require_api_key(request: Request, x_api_key: str = Header(default=""), db: Session = Depends(get_db)) -> None:
    # Existing automation clients retain API-key auth. Browser clients use revocable cookies.
    if x_api_key:
        if not secrets.compare_digest(x_api_key, get_settings().api_key):
            raise HTTPException(status_code=401, detail="Invalid API key")
        return
    from app.services.session_service import SessionService, SESSION_COOKIE
    SessionService(db, get_settings()).authenticate(
        request.cookies.get(SESSION_COOKIE), request.headers.get("X-XSRF-TOKEN"),
        mutation=request.method not in {"GET", "HEAD", "OPTIONS"},
    )


def get_services(db: Session = Depends(get_db)):
    svc = build_services(db)
    try:
        yield svc
    finally:
        svc.mailboxes.close()
