"""Session-level advisory locks survive service commits; released on crash/disconnect.
SQLite fallback is for single-process tests only, not multi-worker deployment.
"""
from contextlib import contextmanager
from threading import Lock
from sqlalchemy import text
from app.core.exceptions import ConflictError

_guard = Lock()
_locks = {}

@contextmanager
def operation_lock(db, namespace: int, identity: int):
    engine = db.get_bind()
    if engine.dialect.name == "postgresql":
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            params = {"namespace": namespace, "identity": identity}
            acquired = conn.scalar(text("SELECT pg_try_advisory_lock(:namespace, :identity)"), params)
            if not acquired:
                raise ConflictError("Operation already in progress")
            try:
                yield
            finally:
                conn.execute(text("SELECT pg_advisory_unlock(:namespace, :identity)"), params)
    else:
        with _guard:
            lock = _locks.setdefault((namespace, identity), Lock())
        if not lock.acquire(blocking=False):
            raise ConflictError("Operation already in progress")
        try:
            yield
        finally:
            lock.release()
