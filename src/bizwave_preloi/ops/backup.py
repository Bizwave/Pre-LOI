"""Backups (P3): a snapshot of the database plus a copy of the deal files.

    backup()                        # into settings().backup_dir (BIZWAVE_BACKUP_DIR)
    backup(Path("E:/Backups/BizWave"))
    backup_database(label="before-upgrade")     # the database only (db/migrate.py calls this)

The database is copied with SQLite's backup API through SQLAlchemy, never as a file copy: an open SQLite
file in WAL mode cannot be copied safely. Each snapshot is a new file
(<folder>/database/bizwave-<UTC YYYYMMDD-HHMMSS>[-n][-label].db) that opens on its own. Deal files are
copied into <folder>/deals/ when missing there or different; nothing in the backup folder is ever deleted.
"""
from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import sqlalchemy as sa

from ..config import check_backup_location, database_file, settings
from ..db.session import get_engine
from ..db.types import utcnow


@dataclass(frozen=True)
class BackupResult:
    folder: Path
    database: Path
    deal_files_copied: int
    deal_files_unchanged: int


def _new_snapshot_file(folder: Path, label: str) -> Path:
    """Reserve a new, unique snapshot file (created exclusively, so two backups never collide)."""
    folder.mkdir(parents=True, exist_ok=True)
    stamp = utcnow().strftime("%Y%m%d-%H%M%S")
    suffix = f"-{label}" if label else ""
    n = 1
    while True:
        name = f"bizwave-{stamp}{'' if n == 1 else f'-{n}'}{suffix}.db"
        try:
            with open(folder / name, "xb"):
                return folder / name
        except FileExistsError:
            n += 1


def backup_database(dest: Optional[Path] = None, *, url: Optional[str] = None, label: str = "") -> Path:
    """Snapshot the database (default: the data folder's) into <dest>/database/. Returns the new file."""
    s = settings()
    folder = Path(dest) if dest is not None else s.backup_dir
    check_backup_location(folder, s)
    if database_file(url if url is not None else s.database_url) is None:
        raise NotImplementedError("Only SQLite databases can be backed up here (Postgres: use pg_dump).")
    target = _new_snapshot_file(folder / "database", label)
    source = get_engine(url).raw_connection()
    copy_engine = sa.create_engine("sqlite:///" + target.as_posix(), poolclass=sa.pool.NullPool)
    copy = copy_engine.raw_connection()
    try:
        source.driver_connection.backup(copy.driver_connection)
    finally:
        copy.close()
        copy_engine.dispose()
        source.close()
    return target


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _same(a: Path, b: Path) -> bool:
    return a.stat().st_size == b.stat().st_size and _sha256(a) == _sha256(b)


def backup(dest: Optional[Path] = None) -> BackupResult:
    """A database snapshot plus the deal files, into `dest` (default settings().backup_dir)."""
    s = settings()
    folder = Path(dest) if dest is not None else s.backup_dir
    check_backup_location(folder, s)
    snapshot = backup_database(folder)
    copied = unchanged = 0
    if s.deals_dir.exists():
        for source in sorted(s.deals_dir.rglob("*")):
            if source.is_symlink() or not source.is_file():
                continue
            target = folder / "deals" / source.relative_to(s.deals_dir)
            if target.is_file() and _same(source, target):
                unchanged += 1
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            partial = target.with_name(target.name + ".partial")
            shutil.copy2(source, partial)
            os.replace(partial, target)        # never a half-written file under the real name
            copied += 1
    return BackupResult(folder=folder, database=snapshot, deal_files_copied=copied, deal_files_unchanged=unchanged)
