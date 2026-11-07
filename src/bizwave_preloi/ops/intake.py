"""Bringing a buyer's files into a deal (P3): copy, hash, classify, inventory, record, start the clock.

    result = intake("acme-hvac", Path("C:/Users/chan/OneDrive/Requests/acme"), by="chan")
    result = intake("acme-hvac", folder, by="chan", kinds={"deck.pdf": "cim"})   # correct a kind

Files land in <data folder>/deals/<deal>/inputs/, keeping subfolders. A file is never overwritten: content
the deal already has is not copied again, and a different file under a name already taken (on disk or in
the deal's records) is saved as "<name>-v2<suffix>" (then -v3 ...). Each copy is written under a hidden
temporary name and linked into place only when complete (ops/files.py), so a name never holds a partial or
replaced file. Names are compared as the disk compares them (case-insensitive on Windows and macOS).
Kinds come from rules/intake.yaml (file-name patterns) unless `kinds` names the file. PDFs are inventoried
page by page. A file that cannot be read, copied, recorded or inventoried is reported in `problem` and the
run goes on with the others.

Content the deal already has is checked against its stored copy: a copy missing from the deal folder is
put back from the buyer's identical file ("restored"); a copy that no longer matches its record (changed or
damaged since intake) is left untouched and reported.

The source folder must be the folder the buyer's files were delivered to: one inside, or containing, the
data folder, the backup folder, the database, the run log or the repository is refused before anything is
copied (it would bring the live database or another deal's files into this deal).

The SLA clock starts (status `ready`, P2) when a deal waiting for documents has at least one CIM whose
pages were read (Chan, P3 Q3). `start_clock_if_complete` is shared with `bw paid`.
"""
from __future__ import annotations

import os
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Set, Tuple

import sqlalchemy as sa
from sqlalchemy.orm import Session

from .. import config
from ..config import database_file, settings
from ..db import repo
from ..db.models import Deal, Document, Page
from ..db.session import session_scope
from ..db.status import CLOSED
from ..ingest.inventory import inventory
from ..rules import intake_rules
from . import files as filestore


@dataclass(frozen=True)
class IntakeFile:
    source: Path                 # as found under the source folder
    stored_path: Optional[str]   # relative to the deal folder, forward slashes: "inputs/cim.pdf"; None if failed
    action: str                  # "copied" | "copied_as_new_version" | "recorded" | "already_recorded"
                                 # | "restored" | "failed"
    kind: str
    pages: Optional[int]         # pages recorded; None for a non-PDF, an unreadable PDF or a failed file
    problem: Optional[str]


@dataclass(frozen=True)
class IntakeResult:
    deal_id: str
    files: List[IntakeFile]
    status_before: str
    status_after: str
    message: str


@dataclass(frozen=True)
class _Planned:
    source: Path
    relative: str                # under the source folder
    sha: Optional[str]
    action: str
    target: Optional[Path]
    problem: Optional[str]


def _name_key(relative: str) -> str:
    """A stored name as the disk compares it: case-insensitive on Windows (normcase); on macOS (APFS) also
    blind to Unicode normalization ("é" as one character or as e + accent)."""
    key = os.path.normcase(relative)
    return unicodedata.normalize("NFC", key).casefold() if sys.platform == "darwin" else key


def _source_files(source: Path) -> List[Tuple[Path, str]]:
    """(file, relative posix path) for every regular file under `source`, in path order; hidden files, links
    and the skip list in rules/intake.yaml are left out."""
    rules = intake_rules()
    found = []
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if path.is_symlink() or not path.is_file():
            continue
        if any(part.startswith(".") for part in relative.parts) or rules.skips(path.name):
            continue
        found.append((path, relative.as_posix()))
    return found


def _check_source(source: Path) -> None:
    """Refuse a source folder that is, is inside or contains a folder or file intake must never read from."""
    s = settings()
    if not source.is_dir():
        raise ValueError(f"{source} is not a folder. Give the folder the buyer's files are in.")
    if config.REPO_ROOT is not None and config.is_inside(source, config.REPO_ROOT):
        raise ValueError(f"{source} is inside the repository {config.REPO_ROOT}; client files must never be "
                         f"there. Move them out first.")
    for label, folder in (("data folder", s.data_dir), ("backup folder", s.backup_dir)):
        if config.is_inside(source, folder):
            raise ValueError(f"{source} is inside the {label} {folder}; intake copies files into the data "
                             f"folder. Give the folder the buyer's files were delivered to.")
    protected = (("the data folder", s.data_dir), ("the backup folder", s.backup_dir),
                 ("the database", database_file(s.database_url)), ("the run log", s.runlog_path),
                 ("the repository", config.REPO_ROOT))
    for label, path in protected:
        if path is not None and config.is_inside(path, source):
            raise ValueError(f"{source} contains {label} ({path}); intake would copy it, and other deals' "
                             f"files, into this deal. Give the folder that holds only this buyer's files.")


def _kind_overrides(kinds: Optional[Dict[str, str]], files: List[Tuple[Path, str]]) -> Dict[str, str]:
    """{relative path: kind}. A key is a relative path or a file name that is unique in the folder."""
    if not kinds:
        return {}
    allowed = set(Document.__table__.c.kind.type.enums)
    by_path = {rel: rel for _, rel in files}
    by_name: Dict[str, List[str]] = {}
    for path, rel in files:
        by_name.setdefault(path.name, []).append(rel)
    resolved = {}
    for key, kind in kinds.items():
        if kind not in allowed:
            raise ValueError(f"--kind {key}={kind}: a kind must be one of {', '.join(sorted(allowed))}")
        if key in by_path:
            resolved[key] = kind
        elif len(by_name.get(key, [])) == 1:
            resolved[by_name[key][0]] = kind
        elif key in by_name:
            raise ValueError(f"--kind {key}: more than one file has that name; give its path, e.g. "
                             f"{by_name[key][0]}")
        else:
            raise ValueError(f"--kind {key}: no such file in the folder")
    return resolved


def _names(target: Path) -> Iterator[Path]:
    """The buyer's name, then "<stem>-v2<suffix>", "-v3" ..."""
    yield target
    n = 2
    while True:
        yield target.with_name(f"{target.stem}-v{n}{target.suffix}")
        n += 1


def _store(source: Path, sha: str, target: Path, deal_folder: Path, taken: Set[str]) -> Tuple[Path, str]:
    """Put `source` (content `sha`, not yet recorded for the deal) under the first free name. A name is taken
    when the deal's records use it (`taken` holds _name_key of each) or a different file is on disk there. A
    file already on disk with this content (an interrupted run copied it but never recorded it) is used as it
    is: action "recorded"."""
    temp = None
    try:
        for n, candidate in enumerate(_names(target)):
            if _name_key(candidate.relative_to(deal_folder).as_posix()) in taken:
                continue
            if candidate.exists() or candidate.is_symlink():
                if candidate.is_file() and not candidate.is_symlink() and filestore.sha256(candidate) == sha:
                    return candidate, "recorded"
                continue
            if temp is None:
                temp, copied = filestore.copy_to_temporary(source, candidate.parent)
                if copied != sha:
                    raise OSError(f"{source.name} changed while it was being copied; run intake again")
            if filestore.place(temp, candidate):
                temp = None
                return candidate, "copied" if n == 0 else "copied_as_new_version"
    finally:
        if temp is not None:
            filestore.discard(temp)
    raise AssertionError("unreachable: _names never ends")


def has_readable_cim(s: Session, deal_id: str) -> bool:
    return bool(s.scalar(sa.select(sa.func.count()).select_from(Document)
                         .where(Document.deal_id == deal_id, Document.kind == "cim", Document.page_count > 0)))


def _waiting_message(s: Session, deal_id: str) -> str:
    documents = s.scalars(sa.select(Document).where(Document.deal_id == deal_id).order_by(Document.id)).all()
    if not documents:
        return (f"No files are recorded for this deal yet: run `bw intake {deal_id} --from FOLDER`. The SLA "
                f"clock starts when a readable CIM is in.")
    cims = [d.filename for d in documents if d.kind == "cim"]      # none of them has readable pages
    if cims:
        return (f"The CIM ({', '.join(cims)}) has no readable PDF pages (not a PDF, encrypted or damaged), "
                f"so the SLA clock has not started. Ask the buyer for a readable PDF, then run intake again.")
    return ("No file was recognized as the CIM, so the SLA clock has not started. If one of the files is the "
            "CIM, run intake again with --kind \"NAME=cim\".")


def start_clock_if_complete(s: Session, deal_id: str, *, by: str) -> Tuple[str, str]:
    """Move a deal waiting for documents to `ready` when its package is complete. Returns (status, message)."""
    deal = s.get(Deal, deal_id)
    if deal.status == "awaiting_documents":
        if has_readable_cim(s, deal_id):
            deal = repo.transition(s, deal_id, "ready", by=by, detail="package complete: a readable CIM")
            return deal.status, (f"Package complete: the SLA clock started at "
                                 f"{deal.package_complete_at:%Y-%m-%d %H:%M} UTC.")
        return deal.status, _waiting_message(s, deal_id)
    if deal.status in ("created", "awaiting_payment"):
        return deal.status, (f"Files recorded. Waiting for payment: run `bw paid {deal_id}` once paid; the "
                             f"clock starts then if a readable CIM is in.")
    return deal.status, f"Files added to a deal already in '{deal.status}'; the clock is unchanged."


def _matches(path: Path, sha: str) -> bool:
    return path.is_file() and not path.is_symlink() and filestore.sha256(path) == sha


def _known_content(source: Path, rel: str, sha: str, stored_path: str, deal_folder: Path) -> _Planned:
    """Content the deal already has: check its stored copy. Intact -> "already_recorded". Missing -> put
    back from the buyer's identical file -> "restored" (the name is free and the bytes equal the record, so
    nothing is replaced). Changed or damaged -> left as it is and reported."""
    stored = deal_folder / stored_path
    changed = (f"the recorded copy {stored_path} no longer matches its record (changed or damaged in the deal "
               f"folder since intake). The buyer's file still matches the record; nothing was changed. Check "
               f"the deal folder.")

    def checked() -> _Planned:
        try:
            intact = _matches(stored, sha)
        except OSError as exc:                       # the stored copy, not the buyer's file, could not be read
            return _Planned(source, rel, sha, "already_recorded", stored,
                            f"the recorded copy {stored_path} could not be read to check it: {exc}")
        return _Planned(source, rel, sha, "already_recorded", stored, None if intact else changed)

    if stored.exists() or stored.is_symlink():
        return checked()
    temp = None
    try:
        temp, copied = filestore.copy_to_temporary(source, stored.parent)
        if copied != sha:
            raise OSError(f"{source.name} changed while it was being copied; run intake again")
        if filestore.place(temp, stored):
            temp = None
            return _Planned(source, rel, sha, "restored", stored, None)
    except OSError as exc:
        return _Planned(source, rel, sha, "already_recorded", stored,
                        f"the recorded copy {stored_path} is missing from the deal folder and could not be "
                        f"restored: {exc}")
    finally:
        if temp is not None:                         # never leave the temporary copy behind
            filestore.discard(temp)
    return checked()                                 # something took the name meanwhile: look again


def _plan(files: List[Tuple[Path, str]], deal_folder: Path, recorded: Dict[str, str]) -> List[_Planned]:
    """Copy what is new (never overwriting) and check what is known; one file's error is its problem, not the
    run's."""
    taken = {_name_key(stored) for stored in recorded.values()}
    planned = []
    for path, rel in files:
        try:
            sha = filestore.sha256(path)
            if sha in recorded:
                planned.append(_known_content(path, rel, sha, recorded[sha], deal_folder))
                continue
            target, action = _store(path, sha, deal_folder / "inputs" / rel, deal_folder, taken)
        except OSError as exc:                       # unreadable (e.g. a cloud-only file), disk full ...
            planned.append(_Planned(path, rel, None, "failed", None, f"could not be read or copied: {exc}"))
            continue
        stored = target.relative_to(deal_folder).as_posix()
        recorded[sha] = stored
        taken.add(_name_key(stored))
        planned.append(_Planned(path, rel, sha, action, target, None))
    return planned


def _record(s: Session, deal_id: str, item: _Planned, kind: str, override: Optional[str]) -> IntakeFile:
    """Record one planned file. Every repo call here checks its inputs before writing anything, so a refusal
    (ValueError) or a read error (OSError) leaves the session as it was and is this file's problem only."""
    def failed(problem: str) -> IntakeFile:
        return IntakeFile(source=item.source, stored_path=None, action="failed", kind=kind, pages=None,
                          problem=problem)
    action = item.action
    try:
        document = None
        if action in ("already_recorded", "restored"):              # the row exists: never re-read the file
            document = s.scalar(sa.select(Document).where(Document.deal_id == deal_id,
                                                          Document.sha256 == item.sha))
            if document is None:
                # No row after all: an identical file earlier in this run was copied to item.target but its
                # record failed. Record that copy now (add_document hashes it again), or fail this file too.
                action = "recorded"
        if document is None:
            document = repo.add_document(s, deal_id, item.target, kind=kind)
            s.flush()
        if override is not None and document.kind != override:
            repo.set_document_kind(s, document.id, override)
        problem = item.problem
        has_pages = s.scalar(sa.select(sa.func.count()).select_from(Page).where(Page.document_id == document.id))
        if problem is None and item.target.suffix.lower() == ".pdf" and not has_pages:
            try:
                pages = inventory(item.target)
            except Exception as exc:                 # encrypted, damaged or not a PDF
                problem = f"unreadable PDF (encrypted or damaged): {exc}"
            else:
                if pages:
                    repo.record_pages(s, document.id, pages)
                else:
                    problem = "unreadable PDF: no pages"
        s.flush()
    except OSError as exc:                           # the copy is on disk under its name; the next run records it
        return failed(f"copied but could not be read back: {exc}")
    except ValueError as exc:
        return failed(f"could not be recorded: {exc}")
    return IntakeFile(source=item.source, stored_path=document.stored_path, action=action,
                      kind=document.kind, pages=document.page_count, problem=problem)


def intake(deal_id: str, source: Path, *, by: str, kinds: Optional[Dict[str, str]] = None,
           url: Optional[str] = None) -> IntakeResult:
    source = Path(source)
    _check_source(source)
    files = _source_files(source)
    overrides = _kind_overrides(kinds, files)
    with session_scope(url) as s:
        deal = s.get(Deal, deal_id)
        if deal is None:
            raise ValueError(f"No deal {deal_id!r}")
        if deal.status in CLOSED:
            raise ValueError(f"Deal {deal_id!r} is {deal.status}; no files are taken in.")
        status_before = deal.status
        recorded = dict(s.execute(sa.select(Document.sha256, Document.stored_path)
                                  .where(Document.deal_id == deal_id)).all())

    rules = intake_rules()
    planned = _plan(files, settings().deals_dir / deal_id, recorded)
    results = []
    with session_scope(url) as s:
        for item in planned:
            kind = overrides.get(item.relative, rules.kind_for(item.source.name))
            if item.target is None:
                results.append(IntakeFile(source=item.source, stored_path=None, action="failed", kind=kind,
                                          pages=None, problem=item.problem))
                continue
            results.append(_record(s, deal_id, item, kind, overrides.get(item.relative)))
        status_after, message = start_clock_if_complete(s, deal_id, by=by)
    return IntakeResult(deal_id=deal_id, files=results, status_before=status_before,
                        status_after=status_after, message=message)
