"""Backups (P3): a snapshot of the database plus a copy of the deal files.

    backup()                        # into settings().backup_dir (BIZWAVE_BACKUP_DIR)
    backup(Path("E:/Backups/BizWave"))
    backup_database(label="before-upgrade")     # the database only (db/migrate.py calls this)

The database is copied with SQLite's backup API through SQLAlchemy, never as a file copy: an open SQLite
file in WAL mode cannot be copied safely. Each snapshot is a new file
(<folder>/database/bizwave-<UTC YYYYMMDD-HHMMSS>[-n][-label].db) that opens on its own, in rollback-journal
mode so opening it never creates -wal/-shm files next to it. It appears under that name only when complete.

Deal files are copied into <folder>/deals/<same path>. Nothing in the backup folder is ever replaced or
deleted: a deal file whose content differs from every copy the backup holds (deal files are not meant to
change, so this may be damage) is kept as a new copy "<stem>-changed-<UTC stamp>[-n]<suffix>" beside the
old one, and reported. A deal file that cannot be read is reported and the backup goes on with the rest.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import count
from pathlib import Path
from typing import List, Optional, Tuple

import sqlalchemy as sa
from sqlalchemy.pool import NullPool

from ..config import Settings, check_backup_location, database_file, settings
from ..db.session import get_engine
from ..db.types import utcnow
from . import files as filestore


@dataclass(frozen=True)
class BackupResult:
    folder: Path
    database: Path
    deal_files_copied: int                    # new copies written, including changed files
    deal_files_unchanged: int
    deal_files_changed: Tuple[str, ...] = ()  # paths under deals/ that differed from every copy: kept both
    problems: Tuple[str, ...] = ()            # deal files that could not be backed up, with the reason


def _backup_folder(dest: Optional[Path], s: Settings) -> Path:
    folder = Path(dest) if dest is not None else s.backup_dir
    if folder.exists() and not folder.is_dir():
        raise ValueError(f"{folder} is a file; give a folder for the backup.")
    check_backup_location(folder, s)
    return folder


def _snapshot(folder: Path, url: Optional[str], label: str, s: Settings) -> Path:
    if database_file(url if url is not None else s.database_url) is None:
        raise NotImplementedError("Only SQLite databases can be backed up here (Postgres: use pg_dump).")
    target_folder = folder / "database"
    temp = filestore.new_temporary(target_folder)
    try:
        source = get_engine(url).raw_connection()
        try:
            copy_engine = sa.create_engine(sa.engine.URL.create("sqlite", database=str(temp)), poolclass=NullPool)
            try:
                copy = copy_engine.raw_connection()
                try:
                    source.driver_connection.backup(copy.driver_connection)
                    copy.driver_connection.execute("PRAGMA journal_mode=DELETE")   # no -wal/-shm when opened
                finally:
                    copy.close()
            finally:
                copy_engine.dispose()
        finally:
            source.close()
    except BaseException:
        filestore.discard(temp)
        raise
    stamp = utcnow().strftime("%Y%m%d-%H%M%S")
    suffix = f"-{label}" if label else ""
    return filestore.place_first(temp, (target_folder / f"bizwave-{stamp}{'' if n == 1 else f'-{n}'}{suffix}.db"
                                        for n in count(1)))


def backup_database(dest: Optional[Path] = None, *, url: Optional[str] = None, label: str = "") -> Path:
    """Snapshot the database (default: the data folder's) into <dest>/database/. Returns the new file."""
    s = settings()
    return _snapshot(_backup_folder(dest, s), url, label, s)


def _copies(target: Path) -> List[Path]:
    """The copies the backup holds of one deal file: under its own name, then the "-changed-" copies."""
    found = [target] if target.is_file() else []
    if target.parent.is_dir():
        changed = re.compile(re.escape(target.stem) + r"-changed-\d{8}-\d{6}(?:-\d+)?" + re.escape(target.suffix))
        found += sorted(p for p in target.parent.iterdir() if p.is_file() and changed.fullmatch(p.name))
    return found


def _held(source: Path, copies: List[Path]) -> bool:
    size, digest = source.stat().st_size, None
    for copy in copies:
        if copy.stat().st_size == size:
            digest = digest or filestore.sha256(source)
            if filestore.sha256(copy) == digest:
                return True
    return False


def _names(target: Path, stamp: str):
    yield target
    for n in count(1):
        yield target.with_name(f"{target.stem}-changed-{stamp}{'' if n == 1 else f'-{n}'}{target.suffix}")


def backup(dest: Optional[Path] = None) -> BackupResult:
    """A database snapshot plus the deal files, into `dest` (default settings().backup_dir)."""
    s = settings()
    folder = _backup_folder(dest, s)
    snapshot = _snapshot(folder, None, "", s)
    stamp = utcnow().strftime("%Y%m%d-%H%M%S")
    copied = unchanged = 0
    changed: List[str] = []
    problems: List[str] = []
    sources = sorted(s.deals_dir.rglob("*")) if s.deals_dir.exists() else []
    for source in sources:
        if source.is_symlink() or not source.is_file() or filestore.is_temporary(source):
            continue
        relative = source.relative_to(s.deals_dir)
        target = folder / "deals" / relative
        try:
            copies = _copies(target)
            if _held(source, copies):
                unchanged += 1
                continue
            temp, _ = filestore.copy_to_temporary(source, target.parent)
            filestore.place_first(temp, _names(target, stamp))
        except OSError as exc:
            problems.append(f"{relative.as_posix()}: {exc}")
            continue
        copied += 1
        if copies:
            changed.append(relative.as_posix())
    return BackupResult(folder=folder, database=snapshot, deal_files_copied=copied, deal_files_unchanged=unchanged,
                        deal_files_changed=tuple(changed), problems=tuple(problems))
