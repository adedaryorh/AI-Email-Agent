from threading import Lock

_saver = None
_pool = None
_lock = Lock()


def get_checkpointer(settings):
    global _saver, _pool
    with _lock:
        if _saver is None:
            if settings.database_url.startswith("sqlite"):
                from langgraph.checkpoint.memory import InMemorySaver
                _saver = InMemorySaver()
            else:
                from langgraph.checkpoint.postgres import PostgresSaver
                from psycopg_pool import ConnectionPool
                from psycopg.rows import dict_row
                _pool = ConnectionPool(settings.psycopg_conninfo, max_size=10,
                    kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row})
                _saver = PostgresSaver(_pool)
        return _saver


def setup_checkpointer():
    """Run once in the migration job, before API/worker startup."""
    from app.core.config import get_settings
    saver = get_checkpointer(get_settings())
    if hasattr(saver, "setup"):
        saver.setup()
    close_checkpointer()


def close_checkpointer():
    global _saver, _pool
    with _lock:
        if _pool:
            _pool.close()
        _pool, _saver = None, None

if __name__ == "__main__":
    setup_checkpointer()
