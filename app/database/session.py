"""Engine and session management."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker


def create_db_engine(url: str) -> Engine:
    """Create an engine; SQLite gets foreign keys, WAL and a busy timeout."""
    parsed = make_url(url)
    kwargs: dict[str, object] = {}
    if parsed.get_backend_name() == "sqlite":
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
        if parsed.database and parsed.database != ":memory:":
            Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, **kwargs)

    if parsed.get_backend_name() == "sqlite":

        @event.listens_for(engine, "connect")
        def _pragmas(dbapi_conn, _record):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            if parsed.database and parsed.database != ":memory:":
                cur.execute("PRAGMA journal_mode=WAL")
            cur.close()

    return engine


class Database:
    """Owns the engine and hands out sessions."""

    def __init__(self, url: str) -> None:
        self.url = url
        self.engine = create_db_engine(url)
        self._factory = sessionmaker(self.engine, expire_on_commit=False)

    def session(self) -> Session:
        return self._factory()

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        session = self.session()
        try:
            yield session
            session.commit()
        except BaseException:
            session.rollback()
            raise
        finally:
            session.close()

    def dispose(self) -> None:
        self.engine.dispose()
