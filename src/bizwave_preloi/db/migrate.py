"""Alembic, configured in code. Migrations ship inside the package (bizwave_preloi/db/migrations), so
these work from any folder and from an installed copy.

    upgrade()                      # the data folder's database, to the newest revision
    upgrade(url, "head")           # any database URL
    downgrade(url, "-1")           # one step back ("base" removes everything)
    current_revision(url)          # e.g. "0001_core", or None for an empty database

Schema changes only ever go through a new revision file in migrations/versions/, tested
upgrade -> downgrade -> upgrade (CLAUDE.md §6 step 4).

On SQLite a migration runs with foreign keys switched off (a batch "recreate" drops and rebuilds a parent
table while child rows exist) and inside one transaction. Before it commits, PRAGMA foreign_key_check
must come back empty; otherwise, or if any step fails, everything rolls back, including the schema.
"""
from __future__ import annotations

from typing import Optional

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext

from ..config import database_file, settings
from .session import get_engine

SCRIPT_LOCATION = "bizwave_preloi.db:migrations"


def _config(script_location: str = SCRIPT_LOCATION) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", script_location)
    return cfg


def _foreign_keys(connection, on: bool) -> None:
    """Switch SQLite foreign keys on or off. Only works outside a transaction, so it goes straight to the
    driver connection (which, see session.py, never opens a transaction by itself)."""
    connection.connection.driver_connection.execute(f"PRAGMA foreign_keys={'ON' if on else 'OFF'}")


def _run(command_fn, url: Optional[str], revision: str, *, script_location: str = SCRIPT_LOCATION) -> None:
    cfg = _config(script_location)
    engine = get_engine(url)
    sqlite = engine.dialect.name == "sqlite"
    with engine.connect() as connection:
        if sqlite:
            _foreign_keys(connection, on=False)
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
                _foreign_keys(connection, on=True)
                if connection.connection.driver_connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
                    connection.invalidate()        # never hand a connection without foreign keys back


def upgrade(url: Optional[str] = None, revision: str = "head") -> None:
    _run(command.upgrade, url, revision)


def downgrade(url: Optional[str] = None, revision: str = "-1") -> None:
    _run(command.downgrade, url, revision)


def current_revision(url: Optional[str] = None) -> Optional[str]:
    """The database's revision, or None for an empty database. A SQLite file that does not exist is
    FileNotFoundError: looking must not create an empty database (e.g. at a mistyped path)."""
    path = database_file(url if url is not None else settings().database_url)
    if path is not None and not path.exists():
        raise FileNotFoundError(f"No database at {path}")
    with get_engine(url).connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()
