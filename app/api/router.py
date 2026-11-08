from fastapi import APIRouter

from app.api.v1 import health, mailboxes, messages, review, rules, drafts, analytics, auth, agent

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(mailboxes.router)
api_router.include_router(messages.router)
api_router.include_router(review.router)

api_router.include_router(rules.router)
api_router.include_router(drafts.router)
api_router.include_router(analytics.router)

api_router.include_router(auth.router)

api_router.include_router(agent.router)
