"""The only code that writes deals, documents, pages and pipeline runs. Each function takes an open
Session (from session_scope) and leaves committing to it.

    get_or_create_customer   customers are found by e-mail (trimmed, lower case)
    create_deal              deal ids are code names (schemas.Deal pattern); writes the first event
    transition               the status flow (db/status.py); every change is an event
    add_document             a file already inside the deal folder: hashed, de-duplicated, stored
                             relative to the deal folder so the data folder can move
    record_pages             one row per page from ingest.inventory()
    start_run / finish_run   pipeline runs with the code version and a hash of the rules files
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import sqlalchemy as sa
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from .. import config, rules
from ..schemas import DEAL_ID_PATTERN
from .models import Customer, Deal, DealEvent, Document, Page, PipelineRun
from .status import InvalidTransition, check
from .types import check_aware, check_cents, check_decimal, utcnow

DEAL_ID = re.compile(DEAL_ID_PATTERN)     # the same pattern as schemas.Deal.id; always use fullmatch


# Inputs are checked here, before anything is added to the session, so a bad value raises the error the
# contract names (TypeError, ValueError) instead of a database error at flush.

def _now(at: Optional[datetime]) -> datetime:
    return utcnow() if at is None else check_aware(at)


def _one_of(value: str, column, what: str) -> str:
    allowed = column.type.enums
    if value not in allowed:
        raise ValueError(f"{what} must be one of {', '.join(allowed)}; got {value!r}")
    return value


def _who(by: str) -> str:
    if not isinstance(by, str) or not by.strip():
        raise ValueError("'by' must name who made the change (e.g. 'chan')")
    return by.strip()


# --------------------------------------------------------------------------- customers and deals

def get_or_create_customer(s: Session, *, name: str, email: str, firm: Optional[str] = None,
                           referred_by: Optional[str] = None) -> Customer:
    email = email.strip().lower()
    if not email or "@" not in email:
        raise ValueError(f"Not an e-mail address: {email!r}")
    existing = s.scalar(sa.select(Customer).where(Customer.email == email))
    if existing is not None:
        return existing
    customer = Customer(name=name.strip(), email=email, firm=firm, referred_by=referred_by)
    s.add(customer)
    return customer


def create_deal(s: Session, *, deal_id: str, customer_id: int, tier: str, by: str,
                list_price_cents: Optional[int] = None, asking_price: Optional[Decimal] = None,
                proposed_price: Optional[Decimal] = None, industry: Optional[str] = None) -> Deal:
    if not isinstance(deal_id, str) or not DEAL_ID.fullmatch(deal_id):
        raise ValueError(f"Deal id {deal_id!r} must be 3-41 characters: lower-case letters, digits and "
                         f"hyphens, starting with a letter or digit (e.g. 'acme-hvac').")
    by = _who(by)
    _one_of(tier, Deal.__table__.c.tier, "tier")
    check_cents(list_price_cents)
    check_decimal(asking_price)
    check_decimal(proposed_price)
    if s.get(Deal, deal_id) is not None:
        raise ValueError(f"Deal {deal_id!r} already exists")
    now = utcnow()
    deal = Deal(id=deal_id, customer_id=customer_id, tier=tier, status="created",
                list_price_cents=list_price_cents, asking_price=asking_price,
                proposed_price=proposed_price, industry=industry, created_at=now, updated_at=now)
    s.add(deal)
    s.add(DealEvent(deal_id=deal_id, at=now, kind="status_change", from_status=None,
                    to_status="created", by=by))
    return deal


def transition(s: Session, deal_id: str, to_status: str, *, by: str, detail: Optional[str] = None,
               at: Optional[datetime] = None) -> Deal:
    deal = s.get(Deal, deal_id)
    if deal is None:
        raise ValueError(f"No deal {deal_id!r}")
    check(deal.status, to_status, held_from=_held_from(s, deal))   # InvalidTransition; nothing written
    by, when = _who(by), _now(at)
    s.add(DealEvent(deal_id=deal_id, at=when, kind="status_change", from_status=deal.status,
                    to_status=to_status, by=by, detail=detail))
    if to_status == "ready" and deal.package_complete_at is None:
        deal.package_complete_at = when        # the SLA clock starts the first time only
    if to_status == "delivered":
        deal.delivered_at = when
    read_status = deal.status
    deal.status = to_status
    deal.updated_at = when
    try:
        s.flush()     # the UPDATE matches only if the deal still has the status read (models.Deal)
    except StaleDataError:
        raise InvalidTransition(f"Deal {deal_id!r} was changed by someone else after it was read (it was "
                                f"'{read_status}'); nothing was written. Reload it and try again.") from None
    return deal


def _held_from(s: Session, deal: Deal) -> Optional[str]:
    """For a deal on hold, the status it had before the latest hold (from its events, in the order written)."""
    if deal.status != "on_hold":
        return None
    return s.scalar(sa.select(DealEvent.from_status)
                    .where(DealEvent.deal_id == deal.id, DealEvent.kind == "status_change",
                           DealEvent.to_status == "on_hold")
                    .order_by(DealEvent.id.desc()).limit(1))


# --------------------------------------------------------------------------- documents and pages

def _deal_folder(deal_id: str) -> Path:
    return config.settings().deals_dir / deal_id


def add_document(s: Session, deal_id: str, path: Path, *, kind: str,
                 received_at: Optional[datetime] = None) -> Document:
    if s.get(Deal, deal_id) is None:
        raise ValueError(f"No deal {deal_id!r}")
    _one_of(kind, Document.__table__.c.kind, "Document kind")
    received = _now(received_at)
    folder = _deal_folder(deal_id).resolve()
    file = Path(path).resolve()
    try:
        relative = file.relative_to(folder)
    except ValueError:
        raise ValueError(f"{path} is not inside the deal folder {folder}; copy it there first") from None
    if not file.is_file():
        raise ValueError(f"{path} is not a file")
    data = file.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    existing = s.scalar(sa.select(Document).where(Document.deal_id == deal_id, Document.sha256 == digest))
    if existing is not None:
        return existing
    stored_path = relative.as_posix()
    if s.scalar(sa.select(Document.id).where(Document.deal_id == deal_id, Document.stored_path == stored_path)):
        raise ValueError(f"{stored_path} is already recorded for deal {deal_id!r} with different content. "
                         f"Save the new file under a new name (e.g. {file.stem}-v2{file.suffix}) and add that; "
                         f"the recorded file must stay as it was, so figures read from it still trace.")
    document = Document(deal_id=deal_id, filename=file.name, kind=kind, sha256=digest, size_bytes=len(data),
                        stored_path=stored_path, received_at=received)
    s.add(document)
    return document


def record_pages(s: Session, document_id: int, pages: Iterable) -> List[Page]:
    document = s.get(Document, document_id)
    if document is None:
        raise ValueError(f"No document {document_id}")
    pages = list(pages)
    if not pages:
        raise ValueError(f"Document {document_id}: no pages to record (a PDF has at least one page)")
    if s.scalar(sa.select(sa.func.count()).select_from(Page).where(Page.document_id == document_id)):
        raise ValueError(f"Document {document_id} already has pages recorded")
    rows = [Page(document_id=document_id, page_no=p.page, chars=p.chars, has_text_layer=p.has_text_layer,
                 tables_found=p.tables_found, images=p.images, read_status="pending") for p in pages]
    s.add_all(rows)
    document.page_count = len(rows)
    return rows


# --------------------------------------------------------------------------- pipeline runs

def rules_hash() -> str:
    """sha256 over the rules/*.yaml files' bytes, in file-name order."""
    h = hashlib.sha256()
    for f in sorted(Path(rules.RULES_DIR).glob("*.yaml"), key=lambda p: p.name):
        h.update(f.read_bytes())
    return h.hexdigest()


def _git_sha() -> Optional[str]:
    root = config.REPO_ROOT
    if root is None:
        return None
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True,
                             timeout=10, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    except (OSError, subprocess.SubprocessError):
        return None
    sha = out.stdout.strip()
    return sha if out.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", sha) else None


def _llm_mode() -> str:
    """"off" in no-LLM mode or without an API key; otherwise "on". Switches for single uses
    (BIZWAVE_LLM_DISABLED_USES) still apply when each call is made; they do not make the whole run "off"."""
    s = config.settings()
    return "off" if s.no_llm or not s.has_api_key else "on"


def start_run(s: Session, deal_id: str) -> PipelineRun:
    if s.get(Deal, deal_id) is None:
        raise ValueError(f"No deal {deal_id!r}")
    run = PipelineRun(deal_id=deal_id, started_at=utcnow(), status="running", git_sha=_git_sha(),
                      rules_hash=rules_hash(), llm_mode=_llm_mode(), stages={})
    s.add(run)
    return run


def finish_run(s: Session, run_id: int, *, status: str, stages: Dict, error: Optional[str] = None) -> PipelineRun:
    if status not in ("succeeded", "failed"):
        raise ValueError(f"A run finishes as 'succeeded' or 'failed', not {status!r}")
    run = s.get(PipelineRun, run_id)
    if run is None:
        raise ValueError(f"No pipeline run {run_id}")
    if run.status != "running":
        raise ValueError(f"Pipeline run {run_id} already finished as {run.status!r}; its record is kept. "
                         f"Start a new run instead.")
    run.status, run.stages, run.error, run.finished_at = status, dict(stages), error, utcnow()
    return run
