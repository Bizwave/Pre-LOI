"""Engines and sessions. Every connection to SQLite gets foreign keys, WAL and a busy timeout.

    with session_scope() as s:      # commits on success, rolls back on any exception
        ...

Never open a raw sqlite3 connection: it would skip the pragmas below.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Iterator, Optional

import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from ..config import ensure_data_dirs

_ENGINES: Dict[str, Engine] = {}


def sqlite_file(url: str) -> Optional[Path]:
    """The database file of a SQLite URL (absolute), or None for other databases and in-memory SQLite."""
    parsed = sa.engine.make_url(url)
    if not parsed.drivername.startswith("sqlite"):
        return None
    if not parsed.database or parsed.database == ":memory:":
        return None
    return Path(parsed.database).absolute()


def _sqlite_pragmas(dbapi_connection, _record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def get_engine(url: Optional[str] = None) -> Engine:
    """One engine per URL. The default URL (settings().database_url) goes through ensure_data_dirs()
    first, so the data folder exists and is checked."""
    if url is None:
        url = ensure_data_dirs().database_url
    if url in _ENGINES:
        return _ENGINES[url]
    path = sqlite_file(url)
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
    engine = sa.create_engine(url)
    if engine.dialect.name == "sqlite":
        event.listen(engine, "connect", _sqlite_pragmas)
    _ENGINES[url] = engine
    return engine


def dispose_engines() -> None:
    """Close every pooled connection (tests; lets Windows delete temporary database files)."""
    for engine in _ENGINES.values():
        engine.dispose()
    _ENGINES.clear()


@contextmanager
def session_scope(url: Optional[str] = None) -> Iterator[Session]:
    session = Session(bind=get_engine(url), expire_on_commit=False)
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()
