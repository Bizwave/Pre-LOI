"""Bringing a buyer's files into a deal (P3): copy, hash, classify, inventory, record, start the clock.

    result = intake("acme-hvac", Path("C:/Users/chan/OneDrive/Requests/acme"), by="chan")
    result = intake("acme-hvac", folder, by="chan", kinds={"deck.pdf": "cim"})   # correct a kind

Files land in <data folder>/deals/<deal>/inputs/, keeping subfolders. A file is never overwritten: content
the deal already has is not copied again, and a different file under a name already taken is saved as
"<name>-v2<suffix>" (then -v3 ...). Every copy is created exclusively, so an existing file is never touched.
Kinds come from rules/intake.yaml (file-name patterns) unless `kinds` names the file. PDFs are inventoried
page by page; a PDF that cannot be read is still recorded, with the reason in `problem`.

The SLA clock starts (status `ready`, P2) when a deal waiting for documents has at least one CIM whose
pages were read (Chan, P3 Q3). `start_clock_if_complete` is shared with `bw paid`.
"""
from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import sqlalchemy as sa
from sqlalchemy.orm import Session

from .. import config
from ..config import settings
from ..db import repo
from ..db.models import Deal, Document, Page
from ..db.session import session_scope
from ..ingest.inventory import inventory
from ..rules import intake_rules

CLOSED = ("delivered", "cancelled")


@dataclass(frozen=True)
class IntakeFile:
    source: Path               # as found under the source folder
    stored_path: str           # relative to the deal folder, forward slashes: "inputs/cim.pdf"
    action: str                # "copied" | "copied_as_new_version" | "recorded" | "already_recorded"
    kind: str
    pages: Optional[int]       # pages recorded; None for a non-PDF or an unreadable PDF
    problem: Optional[str]


@dataclass(frozen=True)
class IntakeResult:
    deal_id: str
    files: List[IntakeFile]
    status_before: str
    status_after: str
    message: str


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


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
    s = settings()
    if not source.is_dir():
        raise ValueError(f"{source} is not a folder. Give the folder the buyer's files are in.")
    if config._inside(source, s.data_dir):
        raise ValueError(f"{source} is inside the data folder {s.data_dir}; intake copies files INTO it. "
                         f"Give the folder the files were delivered to.")
    if config.REPO_ROOT is not None and config._inside(source, config.REPO_ROOT):
        raise ValueError(f"{source} is inside the repository {config.REPO_ROOT}; client files must never be "
                         f"there. Move them out first.")


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


def _free_version(target: Path) -> Path:
    n = 2
    while True:
        candidate = target.with_name(f"{target.stem}-v{n}{target.suffix}")
        if not candidate.exists():
            return candidate
        n += 1


def _copy_exclusively(source: Path, target: Path) -> Path:
    """Copy into a NEW file; if the name was taken meanwhile, take the next free version name."""
    target.parent.mkdir(parents=True, exist_ok=True)
    while True:
        try:
            with open(source, "rb") as src, open(target, "xb") as dst:
                shutil.copyfileobj(src, dst)
            return target
        except FileExistsError:
            target = _free_version(target)


def has_readable_cim(s: Session, deal_id: str) -> bool:
    return bool(s.scalar(sa.select(sa.func.count()).select_from(Document)
                         .where(Document.deal_id == deal_id, Document.kind == "cim", Document.page_count > 0)))


def start_clock_if_complete(s: Session, deal_id: str, *, by: str) -> Tuple[str, str]:
    """Move a deal waiting for documents to `ready` when its package is complete. Returns (status, message)."""
    deal = s.get(Deal, deal_id)
    if deal.status == "awaiting_documents":
        if has_readable_cim(s, deal_id):
            deal = repo.transition(s, deal_id, "ready", by=by, detail="package complete: a readable CIM")
            return deal.status, (f"Package complete: the SLA clock started at "
                                 f"{deal.package_complete_at:%Y-%m-%d %H:%M} UTC.")
        return deal.status, ("No CIM with readable pages yet, so the SLA clock has not started. If one of these "
                             "files is the CIM, run intake again with --kind \"NAME=cim\".")
    if deal.status in ("created", "awaiting_payment"):
        return deal.status, (f"Files recorded. Waiting for payment: run `bw paid {deal_id}` once paid; the "
                             f"clock starts then if a readable CIM is in.")
    return deal.status, f"Files added to a deal already in '{deal.status}'; the clock is unchanged."


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
    deal_folder = settings().deals_dir / deal_id
    inputs = deal_folder / "inputs"
    planned = []                                     # (source, relative, sha, action, target or None)
    for path, rel in files:
        sha = _sha256(path)
        if sha in recorded:
            planned.append((path, rel, sha, "already_recorded", deal_folder / recorded[sha]))
            continue
        target = inputs / rel
        if target.exists() and _sha256(target) == sha:
            action = "recorded"                      # copied by an earlier, interrupted run
        elif target.exists():
            target, action = _copy_exclusively(path, _free_version(target)), "copied_as_new_version"
        else:
            target, action = _copy_exclusively(path, target), "copied"
        recorded[sha] = target.relative_to(deal_folder).as_posix()
        planned.append((path, rel, sha, action, target))

    results = []
    with session_scope(url) as s:
        for path, rel, sha, action, target in planned:
            kind = overrides.get(rel, rules.kind_for(path.name))
            document = repo.add_document(s, deal_id, target, kind=kind)      # existing row for known content
            s.flush()
            if rel in overrides and document.kind != overrides[rel]:
                repo.set_document_kind(s, document.id, overrides[rel])
            problem = None
            has_pages = s.scalar(sa.select(sa.func.count()).select_from(Page).where(Page.document_id == document.id))
            if target.suffix.lower() == ".pdf" and not has_pages:
                try:
                    pages = inventory(target)
                except Exception as exc:                 # encrypted, damaged or not a PDF
                    problem = f"unreadable PDF (encrypted or damaged): {exc}"
                else:
                    if pages:
                        repo.record_pages(s, document.id, pages)
                    else:
                        problem = "unreadable PDF: no pages"
            s.flush()
            results.append(IntakeFile(source=path, stored_path=document.stored_path, action=action,
                                      kind=document.kind, pages=document.page_count, problem=problem))
        status_after, message = start_clock_if_complete(s, deal_id, by=by)
    return IntakeResult(deal_id=deal_id, files=results, status_before=status_before,
                        status_after=status_after, message=message)
