"""Alembic, configured in code. Migrations ship inside the package (bizwave_preloi/db/migrations), so
these work from any folder and from an installed copy.

    upgrade()                      # the data folder's database, to the newest revision
    upgrade(url, "head")           # any database URL
    downgrade(url, "-1")           # one step back ("base" removes everything)
    current_revision(url)          # e.g. "0001_core", or None for an empty database

Schema changes only ever go through a new revision file in migrations/versions/, tested
upgrade -> downgrade -> upgrade (CLAUDE.md §6 step 4).

On SQLite a migration runs on a connection of its own, with foreign keys switched off (a batch
"recreate" drops and rebuilds a parent table while child rows exist) and inside one transaction that
includes the DDL. Before it commits, PRAGMA foreign_key_check must come back empty; otherwise, or if any
step fails, everything rolls back, including the schema. That connection is then discarded, never
returned to the pool, so ordinary sessions keep pysqlite's default handling (which lets busy_timeout
make a second writer wait instead of failing).

Looking at, or stepping back, a SQLite database file that does not exist is refused (FileNotFoundError):
it would otherwise create an empty file, e.g. at a mistyped path. `upgrade` creates the file.
"""
from __future__ import annotations

from typing import Optional

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import event

from ..config import database_file, settings
from .session import get_engine

SCRIPT_LOCATION = "bizwave_preloi.db:migrations"


def _config(script_location: str = SCRIPT_LOCATION) -> Config:
    # P2's frozen gate (tests/plans/test_2026_11_06_p2_database.py) calls _config() to read the migration
    # head: keep this name and its default.
    cfg = Config()
    cfg.set_main_option("script_location", script_location)
    return cfg


def _sqlite_begin(connection) -> None:
    connection.exec_driver_sql("BEGIN")


def _require_existing(url: Optional[str]) -> None:
    path = database_file(url if url is not None else settings().database_url)
    if path is not None and not path.exists():
        raise FileNotFoundError(f"No database at {path}")


def _run(command_fn, url: Optional[str], revision: str, *, script_location: str = SCRIPT_LOCATION) -> None:
    cfg = _config(script_location)
    engine = get_engine(url)
    sqlite = engine.dialect.name == "sqlite"
    with engine.connect() as connection:
        if sqlite:
            driver = connection.connection.driver_connection
            driver.isolation_level = None                    # pysqlite: no transactions of its own...
            event.listen(connection, "begin", _sqlite_begin)  # ...so BEGIN comes first and covers the DDL
            driver.execute("PRAGMA foreign_keys=OFF")          # only takes effect outside a transaction
        try:
            with connection.begin():
                cfg.attributes["connection"] = connection
                command_fn(cfg, revision)
                if sqlite:
                    broken = connection.exec_driver_sql("PRAGMA foreign_key_check").all()
                    if broken:
                        raise RuntimeError(f"Migration to {revision!r} left {len(broken)} row(s) whose foreign "
                                           f"key points nowhere (first: {tuple(broken[0])}); rolled back.")
        finally:
            if sqlite:
                connection.invalidate()   # changed above: never back to the pool (foreign keys off)


def upgrade(url: Optional[str] = None, revision: str = "head") -> None:
    _run(command.upgrade, url, revision)


def downgrade(url: Optional[str] = None, revision: str = "-1") -> None:
    _require_existing(url)
    _run(command.downgrade, url, revision)


def current_revision(url: Optional[str] = None) -> Optional[str]:
    """The database's revision, or None for an empty database. A SQLite file that does not exist is
    FileNotFoundError: looking must not create an empty database (e.g. at a mistyped path)."""
    _require_existing(url)
    with get_engine(url).connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()
