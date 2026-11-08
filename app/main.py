from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import setup_logging
from app.core.rate_limit import RateLimiter
from app.graph.checkpointer import close_checkpointer


def create_app():
    @asynccontextmanager
    async def lifespan(app):
        get_settings()  # Fail fast on invalid configuration.
        yield
        close_checkpointer()

    setup_logging()
    app = FastAPI(title="AI Email Agent", version="0.2.0", lifespan=lifespan)
    limiter = None

    @app.middleware("http")
    async def rate_limit(request: Request, call_next):
        nonlocal limiter
        if request.url.path not in {"/api/v1/healthz", "/api/v1/readyz"}:
            if limiter is None:
                limiter = RateLimiter(get_settings().api_requests_per_minute)
            if not limiter.allow():
                return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"}, headers={"Retry-After": "60"})
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    app.include_router(api_router)
    return app

app = create_app()
