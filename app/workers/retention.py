from app.core.config import get_settings
from app.core.database import get_session_factory
from app.repositories.retention_repo import RetentionRepository
from app.services.retention_service import RetentionService

if __name__ == "__main__":
    with get_session_factory()() as db:
        count = RetentionService(db, RetentionRepository(db)).purge(get_settings().retention_days)
        print(f"Purged content for {count} completed messages")
