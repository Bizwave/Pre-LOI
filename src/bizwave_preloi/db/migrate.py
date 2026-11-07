"""Alembic, configured in code. Migrations ship inside the package (bizwave_preloi/db/migrations), so
these work from any folder and from an installed copy.

    upgrade()                      # the data folder's database, to the newest revision
    upgrade(url, "head")           # any database URL
    downgrade(url, "-1")           # one step back ("base" removes everything); url is required
    current_revision(url)          # e.g. "0001_core", or None for an empty database
    head_revision()                # the newest revision the code ships

Schema changes only ever go through a new revision file in migrations/versions/, tested
upgrade -> downgrade -> upgrade (CLAUDE.md §6 step 4).

Before an upgrade or downgrade of the data folder's (live) database, a snapshot is written with
ops.backup.backup_database into BIZWAVE_BACKUP_DIR (M11); an upgrade with nothing to apply makes none.

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

from .. import config
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
    # IMMEDIATE takes the write lock at the start, so busy_timeout makes the migration wait for another
    # writer instead of failing part-way.
    connection.exec_driver_sql("BEGIN IMMEDIATE")


def _require_existing(url: Optional[str]) -> None:
    path = database_file(url if url is not None else settings().database_url)
    if path is not None and not path.exists():
        raise FileNotFoundError(f"No database at {path}")


def _prepare_sqlite(connection) -> None:
    driver = connection.connection.driver_connection
    driver.isolation_level = None                    # pysqlite: no transactions of its own...
    event.listen(connection, "begin", _sqlite_begin)  # ...so BEGIN comes first and covers the DDL
    driver.execute("PRAGMA foreign_keys=OFF")          # only takes effect outside a transaction


def _run(command_fn, url: Optional[str], revision: str, *, script_location: str = SCRIPT_LOCATION) -> None:
    cfg = _config(script_location)
    engine = get_engine(url)
    sqlite = engine.dialect.name == "sqlite"
    with engine.connect() as connection:
        try:
            if sqlite:   # inside the try: if any of this fails, the connection is still discarded
                _prepare_sqlite(connection)
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


def _backup_live_database_first(url: Optional[str], action: str, revision: str) -> None:
    """Before changing the data folder's (live) database, snapshot it (M11, Chan 2026-11-06). Other
    databases (tests, scratch copies) are not backed up. An upgrade with nothing to apply makes no
    snapshot; a database file that does not exist yet has nothing to save."""
    live = database_file(settings().database_url)
    target = database_file(url if url is not None else settings().database_url)
    if live is None or target is None or not target.exists():
        return
    if config._real(target) != config._real(live):     # links followed, case folded: the same file counts
        return
    if action == "upgrade":
        wanted = head_revision() if revision == "head" else revision
        if current_revision(url) == wanted:
            return
    from ..ops.backup import backup_database        # here, not at the top: ops.backup imports the database layer
    backup_database(url=url, label=f"before-{action}")


def upgrade(url: Optional[str] = None, revision: str = "head") -> None:
    _backup_live_database_first(url, "upgrade", revision)
    _run(command.upgrade, url, revision)


def downgrade(url: Optional[str] = None, revision: str = "-1") -> None:
    """Step a database back. It removes tables and their data, so the database must be named: it never
    defaults to the data folder's (live) database (Chan, P2 review round 3, 2026-11-06)."""
    if url is None:
        raise ValueError("downgrade removes tables and their data: name the database explicitly "
                         "(downgrade(url, ...); on the command line, --url sqlite:///...)")
    _require_existing(url)
    _backup_live_database_first(url, "downgrade", revision)
    _run(command.downgrade, url, revision)


def head_revision() -> str:
    """The newest revision in migrations/versions (what `upgrade()` brings a database to)."""
    from alembic.script import ScriptDirectory
    return ScriptDirectory.from_config(_config()).get_current_head()


def current_revision(url: Optional[str] = None) -> Optional[str]:
    """The database's revision, or None for an empty database. A SQLite file that does not exist is
    FileNotFoundError: looking must not create an empty database (e.g. at a mistyped path)."""
    _require_existing(url)
    with get_engine(url).connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()
