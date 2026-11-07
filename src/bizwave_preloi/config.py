"""Settings: where things live and how Claude is switched. Every module reads these through
`settings()`; none reads `os.environ` for them directly. (The Anthropic SDK reads the API key value
from the environment itself; `Settings` only records whether one is present.)

    from bizwave_preloi.config import settings, ensure_data_dirs
    s = ensure_data_dirs()          # settings, with the data folders created and checked
    s.deals_dir, s.runlog_path, s.database_url, s.no_llm, s.llm_model ...

Client files, the run log and the database live in a data folder OUTSIDE the repository, by default
`~/BizWaveData` (`C:\\Users\\<you>\\BizWaveData` on Windows). A data folder or run log inside the
repository is refused (paths are compared after following links); a data folder inside a OneDrive,
Dropbox, Google Drive or iCloud folder is allowed with a warning, because a sync client can corrupt
an open SQLite database (docs/tech-plan.md section 3). Relative paths are taken from the folder the
command runs in, so prefer absolute paths in `.env`.

A `.env` file in the repository folder is read once per process. It never overrides a variable
already set in the environment, and it is not read at all when BIZWAVE_LOAD_DOTENV is off IN THE
ENVIRONMENT (the test suite turns it off so a developer's API key can never reach a real call).
Setting BIZWAVE_LOAD_DOTENV inside `.env` itself has no effect: the file is already being read.

Plan: tasks/plans/2026-11-06_p1_settings.md
"""
from __future__ import annotations

import os
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import FrozenSet, Mapping, Optional, Set

APP_DIR_NAME = "BizWaveData"
DEFAULT_MODEL = "claude-sonnet-5-5"
# Folder-name fragments of common sync clients (matched case-insensitively against each folder name
# in the path). A data folder under one of these gets a warning.
SYNC_FOLDER_MARKERS = ("onedrive", "dropbox", "google drive", "googledrive", "my drive", "icloud",
                       "mobile documents", "clouddocs", "cloudstorage")

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


class DataFolderError(ValueError):
    """The configured data folder is not allowed (inside the repository)."""


def _find_repo_root() -> Optional[Path]:
    """The folder holding pyproject.toml and src/bizwave_preloi, or None when installed without it."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file() and (parent / "src" / "bizwave_preloi").is_dir():
            return parent
    return None


REPO_ROOT: Optional[Path] = _find_repo_root()


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    deals_dir: Path
    samples_dir: Path
    runlog_path: Path
    database_url: str
    no_llm: bool
    disabled_uses: FrozenSet[str]
    llm_model: str
    has_api_key: bool               # presence only: the key itself is never held here


# --------------------------------------------------------------------------- building settings

def _flag(value: Optional[str]) -> bool:
    return str(value or "").strip().lower() in _TRUE


def _path(raw: str, home: Path) -> Path:
    """`~` and `~/...` (or `~\\...`) against `home`; relative paths made absolute against the
    current folder. Symlinks are not resolved."""
    if raw == "~":
        return home
    if raw.startswith(("~/", "~\\")):
        return home / raw[2:]
    return Path(os.path.abspath(raw))


def load_settings(env: Optional[Mapping[str, str]] = None, home: Optional[Path] = None) -> Settings:
    """Settings from `env` (default: os.environ) and `home` (default: the user's home folder).
    Pure: reads nothing else and creates nothing."""
    env = os.environ if env is None else env
    home = Path.home() if home is None else Path(home)

    def text(name: str) -> str:
        return (env.get(name) or "").strip()

    data_dir = _path(text("BIZWAVE_DATA_DIR"), home) if text("BIZWAVE_DATA_DIR") else home / APP_DIR_NAME
    runlog = _path(text("BIZWAVE_RUNLOG"), home) if text("BIZWAVE_RUNLOG") else data_dir / "runlog.jsonl"
    database_url = text("BIZWAVE_DATABASE_URL") or "sqlite:///" + (data_dir / "bizwave.db").as_posix()
    disabled = frozenset(u.strip() for u in text("BIZWAVE_LLM_DISABLED_USES").split(",") if u.strip())
    return Settings(
        data_dir=data_dir,
        deals_dir=data_dir / "deals",
        samples_dir=data_dir / "samples",
        runlog_path=runlog,
        database_url=database_url,
        no_llm=_flag(env.get("BIZWAVE_NO_LLM")),
        disabled_uses=disabled,
        llm_model=text("BIZWAVE_LLM_MODEL") or DEFAULT_MODEL,
        has_api_key=bool(text("ANTHROPIC_API_KEY")),
    )


# --------------------------------------------------------------------------- .env

_dotenv_loaded: Set[Path] = set()


def _dotenv_enabled() -> bool:
    return os.environ.get("BIZWAVE_LOAD_DOTENV", "1").strip().lower() not in _FALSE


def _load_dotenv(path: Optional[Path]) -> None:
    """Read `path` into os.environ once per process, never overriding what is already set."""
    if path is None or not _dotenv_enabled():
        return
    path = Path(os.path.abspath(path))
    if path in _dotenv_loaded or not path.is_file():
        return
    from dotenv import load_dotenv
    load_dotenv(path, override=False)
    _dotenv_loaded.add(path)


def settings(dotenv_path: Optional[Path] = None) -> Settings:
    """Current settings: the .env file applied (see module doc), then built fresh from os.environ."""
    default = REPO_ROOT / ".env" if REPO_ROOT else None
    _load_dotenv(dotenv_path if dotenv_path is not None else default)
    return load_settings()


# --------------------------------------------------------------------------- data folders

def _real(path: Path) -> str:
    """Absolute, links followed (also for folders that do not exist yet), case-folded on Windows and
    macOS (both usually case-insensitive; folding there can only over-refuse, never miss)."""
    text = os.path.normcase(str(Path(path).resolve(strict=False)))
    return text.casefold() if sys.platform == "darwin" else text


def _synced_folder(path: Path) -> Optional[str]:
    """The first folder name in `path`, as written or with links followed, that looks like a sync
    client's folder; None otherwise."""
    for candidate in (Path(path), Path(path).resolve(strict=False)):
        for part in candidate.parts:
            if any(marker in part.lower() for marker in SYNC_FOLDER_MARKERS):
                return part
    return None


def _inside(child: Path, parent: Path) -> bool:
    c, p = _real(child), _real(parent)
    return c == p or c.startswith(p.rstrip(os.sep) + os.sep)


def database_file(url: str) -> Optional[Path]:
    """The file of a SQLite database URL (absolute), or None for other databases and in-memory SQLite."""
    from sqlalchemy.engine import make_url
    parsed = make_url(url)
    if not parsed.drivername.startswith("sqlite") or not parsed.database or parsed.database == ":memory:":
        return None
    return Path(os.path.abspath(parsed.database))


def check_database_location(path: Path, warn: bool = True) -> None:
    """Refuse a database file inside the repository (DataFolderError); warn when it sits in a synced
    folder. Called before the file can be created (P2.7; Chan, P2 Q1)."""
    if REPO_ROOT is not None and _inside(path, REPO_ROOT):
        raise DataFolderError(
            f"The database {path} is inside the repository {REPO_ROOT}. It holds client deals: set "
            f"BIZWAVE_DATABASE_URL to a file outside the repository, or leave it empty to use "
            f"<data folder>/bizwave.db.")
    synced = _synced_folder(path)
    if warn and synced:
        warnings.warn(
            f"The database {path} is inside a synced folder ('{synced}'). Sync can corrupt an open SQLite "
            f"file and its -wal/-shm companions; keep it outside and back it up into the synced folder "
            f"instead.", UserWarning, stacklevel=3)


def ensure_data_dirs(s: Optional[Settings] = None) -> Settings:
    """Check where the data folder, run log and SQLite database are, then create the data folder with
    deals/ and samples/ (safe to repeat). Raises DataFolderError, before creating anything, when any of
    them is inside the repository."""
    s = s or settings()
    if REPO_ROOT is not None:
        if _inside(s.data_dir, REPO_ROOT):
            raise DataFolderError(
                f"The data folder {s.data_dir} is inside the repository {REPO_ROOT}. Client files "
                f"must live outside it: set BIZWAVE_DATA_DIR to a folder outside the repository "
                f"(default ~/{APP_DIR_NAME}).")
        if _inside(s.runlog_path, REPO_ROOT):
            raise DataFolderError(
                f"The run log {s.runlog_path} is inside the repository {REPO_ROOT}. It holds model "
                f"outputs for client deals: set BIZWAVE_RUNLOG to a path outside the repository, or "
                f"leave it empty to use <data folder>/runlog.jsonl.")
    db_file = database_file(s.database_url)
    synced = _synced_folder(s.data_dir)
    if db_file is not None:
        check_database_location(db_file, warn=synced is None)   # one sync warning is enough
    if synced:
        warnings.warn(
            f"The data folder {s.data_dir} is inside a synced folder ('{synced}'). Keep the database "
            f"out of synced folders: sync can corrupt an open SQLite file. Back it up into the synced "
            f"folder instead.", UserWarning, stacklevel=2)
    for folder in (s.data_dir, s.deals_dir, s.samples_dir):
        folder.mkdir(parents=True, exist_ok=True)
    return s
