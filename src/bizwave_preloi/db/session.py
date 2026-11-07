"""Engines and sessions. Every connection to SQLite gets foreign keys, WAL and a busy timeout, and
transactions that SQLAlchemy controls (BEGIN is sent explicitly), so schema changes roll back with
everything else when a migration fails.

    with session_scope() as s:      # commits on success, rolls back on any exception
        ...

Never open a raw sqlite3 connection: it would skip the pragmas below.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Dict, Iterator, Optional

import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from ..config import check_database_location, database_file, ensure_data_dirs

_ENGINES: Dict[str, Engine] = {}


def _sqlite_pragmas(dbapi_connection, _record) -> None:
    # pysqlite would otherwise start transactions itself and leave DDL outside them; with
    # isolation_level None it starts none, and _sqlite_begin sends BEGIN when SQLAlchemy begins.
    dbapi_connection.isolation_level = None
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def _sqlite_begin(connection) -> None:
    connection.exec_driver_sql("BEGIN")


def get_engine(url: Optional[str] = None) -> Engine:
    """One engine per URL. The default URL (settings().database_url) goes through ensure_data_dirs()
    first, so the data folder and database location are checked; any other SQLite file location is
    checked here (refused inside the repository, warned in a synced folder) before it can be created."""
    checked = url is None
    if url is None:
        url = ensure_data_dirs().database_url
    if url in _ENGINES:
        return _ENGINES[url]
    path = database_file(url)
    if path is not None:
        if not checked:
            check_database_location(path)
        path.parent.mkdir(parents=True, exist_ok=True)
    engine = sa.create_engine(url)
    if engine.dialect.name == "sqlite":
        event.listen(engine, "connect", _sqlite_pragmas)
        event.listen(engine, "begin", _sqlite_begin)
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
