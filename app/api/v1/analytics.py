from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from app.api.deps import require_api_key
from app.core.database import get_db
from app.repositories.analytics_repo import AnalyticsRepository
from app.services.analytics_service import AnalyticsService

router = APIRouter(tags=["analytics"], dependencies=[Depends(require_api_key)])

def get_analytics(db: Session = Depends(get_db)):
    return AnalyticsService(AnalyticsRepository(db))

@router.get("/analytics")
def analytics(svc: AnalyticsService = Depends(get_analytics)):
    return svc.overview()

@router.get("/metrics", response_class=PlainTextResponse)
def metrics(svc: AnalyticsService = Depends(get_analytics)):
    data = svc.overview()
    lines = []
    for key in ("messages_by_status", "drafts_by_status"):
        name = "email_agent_" + key
        lines.append(f"# TYPE {name} gauge")
        for status, count in sorted(data[key].items()):
            # Only enum/state-machine statuses are stored by the application.
            safe = status.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
            lines.append(f'{name}{{status="{safe}"}} {count}')
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")
