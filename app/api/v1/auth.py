from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.database import get_db
from app.core.rate_limit import RateLimiter
from app.services.session_service import SessionService, SESSION_COOKIE, CSRF_COOKIE

router = APIRouter(prefix="/auth", tags=["authentication"])
login_limiter = RateLimiter(5)

class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=1024)

def service(db: Session = Depends(get_db)):
    return SessionService(db, get_settings())

@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, svc: SessionService = Depends(service)):
    if request.headers.get("X-Requested-With") != "EmailAgent":
        raise HTTPException(403, "Browser request header required")
    origin = request.headers.get("origin")
    if origin and origin != svc.settings.frontend_origin:
        raise HTTPException(403, "Untrusted login origin")
    if not login_limiter.allow():
        raise HTTPException(429, "Too many sign-in attempts. Try again in a minute", headers={"Retry-After": "60"})
    token, csrf = svc.login(body.username, body.password, request.cookies.get(SESSION_COOKIE))
    secure = svc.settings.app_env not in {"dev", "test"}
    response.set_cookie(SESSION_COOKIE, token, httponly=True, secure=secure, samesite="lax", path="/api", max_age=svc.settings.session_ttl_seconds)
    response.set_cookie(CSRF_COOKIE, csrf, httponly=False, secure=secure, samesite="lax", path="/", max_age=svc.settings.session_ttl_seconds)
    response.headers["Cache-Control"] = "no-store"
    return {"username": svc.settings.browser_username}

@router.get("/session")
def session(request: Request, response: Response, svc: SessionService = Depends(service)):
    row = svc.authenticate(request.cookies.get(SESSION_COOKIE))
    response.headers["Cache-Control"] = "no-store"
    return {"username": row.username}

@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, svc: SessionService = Depends(service)):
    token = request.cookies.get(SESSION_COOKIE)
    svc.authenticate(token, request.headers.get("X-XSRF-TOKEN"), mutation=True)
    svc.logout(token)
    response.delete_cookie(SESSION_COOKIE, path="/api")
    response.delete_cookie(CSRF_COOKIE, path="/")
