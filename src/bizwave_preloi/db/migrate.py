"""Alembic, configured in code. Migrations ship inside the package (bizwave_preloi/db/migrations), so
these work from any folder and from an installed copy.

    upgrade()                      # the data folder's database, to the newest revision
    upgrade(url, "head")           # any database URL
    downgrade(url, "-1")           # one step back ("base" removes everything)
    current_revision(url)          # e.g. "0001_core", or None for an empty database

Schema changes only ever go through a new revision file in migrations/versions/, tested
upgrade -> downgrade -> upgrade (CLAUDE.md §6 step 4).
"""
from __future__ import annotations

from typing import Optional

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext

from .session import get_engine

SCRIPT_LOCATION = "bizwave_preloi.db:migrations"


def _config() -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", SCRIPT_LOCATION)
    return cfg


def _run(command_fn, url: Optional[str], revision: str) -> None:
    cfg = _config()
    with get_engine(url).begin() as connection:
        cfg.attributes["connection"] = connection
        command_fn(cfg, revision)


def upgrade(url: Optional[str] = None, revision: str = "head") -> None:
    _run(command.upgrade, url, revision)


def downgrade(url: Optional[str] = None, revision: str = "-1") -> None:
    _run(command.downgrade, url, revision)


def current_revision(url: Optional[str] = None) -> Optional[str]:
    with get_engine(url).connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()
