"""P3 gate — command-line skeleton (tasks/plans/2026-11-06_p3_cli.md).

Synthetic files only, built in each test's temporary folder; the data folder is the temporary one the
shared conftest sets. Imports of the packet's modules sit inside the tests, so each test fails on its own
before the code exists. Written before the code; never edited to make it pass (CLAUDE.md section 6).
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import sqlalchemy as sa

from bizwave_preloi import config
from bizwave_preloi.config import REPO_ROOT, settings

DEAL_ID = re.compile(r"[a-z0-9][a-z0-9-]{2,40}")
CIM_PAGES = ["Confidential Information Memorandum\nProject Falcon, a synthetic HVAC services business",
             "Business overview and history of the synthetic company\nCustomers, employees and locations",
             "Summary financials (synthetic): revenue, gross profit, EBITDA by year"]
PNL_PAGES = ["Profit and Loss, synthetic company\nRevenue 1,000,000  Cost of sales 600,000",
             "Operating expenses 250,000  Net income 150,000 (synthetic figures)"]


# --------------------------------------------------------------------------- helpers

@pytest.fixture(autouse=True)
def database():
    """The data folder's database, migrated (the temporary data folder from conftest)."""
    from bizwave_preloi.db.migrate import upgrade
    upgrade()


def _bw(*args):
    from typer.testing import CliRunner

    from bizwave_preloi.cli import app
    return CliRunner().invoke(app, [str(a) for a in args])


def _pdf(path: Path, pages):
    pytest.importorskip("reportlab")
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=letter)
    for text in pages:
        for i, line in enumerate(text.split("\n")):
            c.drawString(72, 720 - 14 * i, line)
        c.showPage()
    c.save()
    return path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _buyer_folder(tmp_path: Path) -> Path:
    folder = tmp_path / "from buyer"
    _pdf(folder / "Project Falcon CIM.pdf", CIM_PAGES)
    _pdf(folder / "Profit and Loss 2023-2024.pdf", PNL_PAGES)
    (folder / "notes.xlsx").write_bytes(b"PK\x03\x04 synthetic spreadsheet bytes")
    (folder / "Thumbs.db").write_bytes(b"windows thumbnail cache")
    (folder / ".hidden").write_bytes(b"hidden file")
    return folder


def _new_deal(code="acme-hvac", *extra):
    r = _bw("new-deal", "--customer", "Pat@Example.com", "--name", "Pat Buyer", "--tier", "flash",
            "--code", code, *extra)
    assert r.exit_code == 0, r.output
    return code


def _deal(code="acme-hvac"):
    from bizwave_preloi.db import repo
    from bizwave_preloi.db.session import session_scope
    with session_scope() as s:
        deal = s.get(repo.Deal, code)
        return None if deal is None else (deal.status, deal.package_complete_at)


def _documents(code="acme-hvac"):
    from bizwave_preloi.db.models import Document, Page
    from bizwave_preloi.db.session import session_scope
    with session_scope() as s:
        docs = s.scalars(sa.select(Document).where(Document.deal_id == code).order_by(Document.id)).all()
        out = {}
        for d in docs:
            pages = s.scalars(sa.select(Page).where(Page.document_id == d.id).order_by(Page.page_no)).all()
            out[d.stored_path] = {"kind": d.kind, "sha256": d.sha256, "size": d.size_bytes,
                                  "page_count": d.page_count, "chars": [p.chars for p in pages]}
        return out


def _inputs(code="acme-hvac"):
    folder = settings().deals_dir / code / "inputs"
    return sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()) if folder.exists() else []


@pytest.fixture
def fake_repo(tmp_path, monkeypatch):
    repo_dir = tmp_path / "fake-repo"
    repo_dir.mkdir()
    (repo_dir / "pyproject.toml").write_text("[project]\nname = 'fake'\n")
    monkeypatch.setattr(config, "REPO_ROOT", repo_dir)
    return repo_dir


# --------------------------------------------------------------------------- new-deal and paid

def test_new_deal_creates_customer_and_deal():
    from bizwave_preloi.db.models import Customer, DealEvent
    from bizwave_preloi.db.session import session_scope

    r = _bw("new-deal", "--customer", "Pat@Example.com", "--name", "Pat Buyer", "--tier", "flash",
            "--code", "acme-hvac")
    assert r.exit_code == 0, r.output
    assert r.stdout.strip().splitlines()[-1] == "acme-hvac"
    with session_scope() as s:
        customer = s.scalar(sa.select(Customer))
        assert (customer.email, customer.name) == ("pat@example.com", "Pat Buyer")
        events = s.scalars(sa.select(DealEvent).order_by(DealEvent.id)).all()
        assert [(e.from_status, e.to_status) for e in events] == [(None, "created"),
                                                                  ("created", "awaiting_payment")]
    assert _deal()[0] == "awaiting_payment"


def test_new_deal_pilot_skips_payment():
    from bizwave_preloi.db.models import DealEvent
    from bizwave_preloi.db.session import session_scope

    _new_deal("acme-hvac", "--pilot")
    assert _deal()[0] == "awaiting_documents"
    with session_scope() as s:
        assert [e.to_status for e in s.scalars(sa.select(DealEvent).order_by(DealEvent.id))] == \
            ["created", "awaiting_documents"]


def test_new_deal_generates_a_code_name():
    ids = []
    for _ in range(2):
        r = _bw("new-deal", "--customer", "pat@example.com", "--name", "Pat Buyer", "--tier", "flash")
        assert r.exit_code == 0, r.output
        ids.append(r.stdout.strip().splitlines()[-1])
    assert all(DEAL_ID.fullmatch(i) for i in ids), ids
    assert ids[0] != ids[1]
    assert not any(word in i for i in ids for word in ("pat", "buyer", "example"))
    assert all(_deal(i)[0] == "awaiting_payment" for i in ids)


@pytest.mark.parametrize("code", ["con", "NUL", "com1", "lpt9", "Acme", "acme-hvac\n"])
def test_reserved_and_bad_codes_refused(code):
    from bizwave_preloi.db.models import Deal
    from bizwave_preloi.db.session import session_scope

    r = _bw("new-deal", "--customer", "pat@example.com", "--name", "Pat Buyer", "--tier", "flash",
            "--code", code)
    assert r.exit_code == 1, r.output
    assert "Traceback" not in r.output
    with session_scope() as s:
        assert s.scalar(sa.select(sa.func.count()).select_from(Deal)) == 0


@pytest.mark.parametrize("code", ["con", "prn", "aux", "nul", "com9", "lpt1"])
def test_schema_refuses_reserved_names(code):
    from bizwave_preloi.schemas import Deal
    with pytest.raises(ValueError):
        Deal(id=code, name="x")


def test_paid_moves_to_awaiting_documents():
    _new_deal()
    r = _bw("paid", "acme-hvac")
    assert r.exit_code == 0, r.output
    assert _deal()[0] == "awaiting_documents"
    again = _bw("paid", "acme-hvac")
    assert again.exit_code == 1
    assert _deal()[0] == "awaiting_documents"


# --------------------------------------------------------------------------- intake

def test_intake_copies_hashes_classifies_and_records(tmp_path):
    from bizwave_preloi.ingest.inventory import inventory

    folder = _buyer_folder(tmp_path)
    _new_deal("acme-hvac", "--pilot")
    r = _bw("intake", "acme-hvac", "--from", folder)
    assert r.exit_code == 0, r.output
    assert _inputs() == ["Profit and Loss 2023-2024.pdf", "Project Falcon CIM.pdf", "notes.xlsx"]
    docs = _documents()
    cim, pnl, xlsx = (docs["inputs/Project Falcon CIM.pdf"], docs["inputs/Profit and Loss 2023-2024.pdf"],
                      docs["inputs/notes.xlsx"])
    assert (cim["kind"], pnl["kind"], xlsx["kind"]) == ("cim", "p_and_l", "other")
    for name, doc in (("Project Falcon CIM.pdf", cim), ("Profit and Loss 2023-2024.pdf", pnl),
                      ("notes.xlsx", xlsx)):
        assert doc["sha256"] == _sha(folder / name)
        assert doc["size"] == (folder / name).stat().st_size
    assert (cim["page_count"], pnl["page_count"], xlsx["page_count"]) == (3, 2, None)
    assert cim["chars"] == [p.chars for p in inventory(folder / "Project Falcon CIM.pdf")]
    assert pnl["chars"] == [p.chars for p in inventory(folder / "Profit and Loss 2023-2024.pdf")]
    assert len(cim["chars"]) + len(pnl["chars"]) == 5


def test_intake_starts_the_clock_for_a_paid_deal_with_a_cim(tmp_path):
    _new_deal()
    assert _bw("paid", "acme-hvac").exit_code == 0
    r = _bw("intake", "acme-hvac", "--from", _buyer_folder(tmp_path))
    assert r.exit_code == 0, r.output
    status, started = _deal()
    assert status == "ready" and started is not None
    assert "clock" in r.output.lower()
    more = tmp_path / "later"
    _pdf(more / "Balance Sheet 2024.pdf", ["Balance sheet, synthetic company\nTotal assets 900,000"])
    assert _bw("intake", "acme-hvac", "--from", more).exit_code == 0
    assert _deal() == ("ready", started)                       # the clock started once only


def test_intake_before_payment_records_but_does_not_start_the_clock(tmp_path):
    _new_deal()
    r = _bw("intake", "acme-hvac", "--from", _buyer_folder(tmp_path))
    assert r.exit_code == 0, r.output
    assert len(_documents()) == 3
    assert _deal() == ("awaiting_payment", None)
    assert "bw paid" in r.output


def test_intake_without_a_cim_waits(tmp_path):
    folder = tmp_path / "partial"
    _pdf(folder / "deck.pdf", ["A synthetic slide deck without a recognisable name"])
    (folder / "notes.xlsx").write_bytes(b"PK\x03\x04 synthetic")
    _new_deal("acme-hvac", "--pilot")
    r = _bw("intake", "acme-hvac", "--from", folder)
    assert r.exit_code == 0, r.output
    assert _deal() == ("awaiting_documents", None)
    assert _documents()["inputs/deck.pdf"]["kind"] == "other"
    assert "--kind" in r.output and "=cim" in r.output


def test_intake_kind_override_and_correction(tmp_path):
    folder = tmp_path / "partial"
    _pdf(folder / "deck.pdf", ["A synthetic slide deck without a recognisable name"])
    _new_deal("acme-hvac", "--pilot")
    assert _bw("intake", "acme-hvac", "--from", folder).exit_code == 0
    assert _deal()[0] == "awaiting_documents"
    r = _bw("intake", "acme-hvac", "--from", folder, "--kind", "deck.pdf=cim")   # correct a recorded file
    assert r.exit_code == 0, r.output
    assert _documents()["inputs/deck.pdf"]["kind"] == "cim"
    assert _deal()[0] == "ready"
    _new_deal("beta-plumb", "--pilot")
    assert _bw("intake", "beta-plumb", "--from", folder, "--kind", "deck.pdf=cim").exit_code == 0   # new file
    assert _documents("beta-plumb")["inputs/deck.pdf"]["kind"] == "cim"
    assert _deal("beta-plumb")[0] == "ready"
    bad = _bw("intake", "beta-plumb", "--from", folder, "--kind", "deck.pdf=teaser")
    assert bad.exit_code == 1


def test_intake_is_idempotent(tmp_path):
    from bizwave_preloi.ops.intake import intake

    folder = _buyer_folder(tmp_path)
    _new_deal("acme-hvac", "--pilot")
    first = intake("acme-hvac", folder, by="chan")
    assert sorted(f.action for f in first.files) == ["copied", "copied", "copied"]
    files, docs = _inputs(), _documents()
    second = intake("acme-hvac", folder, by="chan")
    assert [f.action for f in second.files] == ["already_recorded"] * 3
    assert (_inputs(), _documents()) == (files, docs)


def test_intake_never_overwrites(tmp_path):
    from bizwave_preloi.ops.intake import intake

    folder = tmp_path / "from buyer"
    _pdf(folder / "cim.pdf", CIM_PAGES)
    original = _sha(folder / "cim.pdf")
    _new_deal("acme-hvac", "--pilot")
    intake("acme-hvac", folder, by="chan")
    _pdf(folder / "cim.pdf", CIM_PAGES + ["A revised page added by the broker (synthetic)"])
    second = intake("acme-hvac", folder, by="chan")
    assert [(f.stored_path, f.action) for f in second.files] == [("inputs/cim-v2.pdf", "copied_as_new_version")]
    stored = settings().deals_dir / "acme-hvac" / "inputs"
    assert _sha(stored / "cim.pdf") == original
    assert _sha(stored / "cim-v2.pdf") == _sha(folder / "cim.pdf")
    _pdf(folder / "cim.pdf", ["A third version (synthetic)"])
    third = intake("acme-hvac", folder, by="chan")
    assert third.files[0].stored_path == "inputs/cim-v3.pdf"
    assert sorted(_documents()) == ["inputs/cim-v2.pdf", "inputs/cim-v3.pdf", "inputs/cim.pdf"]
    assert _sha(stored / "cim.pdf") == original


def test_intake_same_content_under_another_name_is_not_copied(tmp_path):
    from bizwave_preloi.ops.intake import intake

    folder = tmp_path / "from buyer"
    _pdf(folder / "cim.pdf", CIM_PAGES)
    (folder / "cim copy.pdf").write_bytes((folder / "cim.pdf").read_bytes())
    _new_deal("acme-hvac", "--pilot")
    result = intake("acme-hvac", folder, by="chan")
    assert sorted(f.action for f in result.files) == ["already_recorded", "copied"]
    assert len(_inputs()) == 1 and len(_documents()) == 1


def test_intake_unreadable_pdf_is_recorded_and_reported(tmp_path):
    folder = tmp_path / "from buyer"
    _pdf(folder / "Project Falcon CIM.pdf", CIM_PAGES)
    (folder / "broken.pdf").write_bytes(b"%PDF-1.4 not really a pdf\n")
    _new_deal("acme-hvac", "--pilot")
    r = _bw("intake", "acme-hvac", "--from", folder)
    assert r.exit_code == 1
    assert "broken.pdf" in r.output and "unreadable" in r.output.lower()
    docs = _documents()
    assert docs["inputs/broken.pdf"]["page_count"] is None and docs["inputs/broken.pdf"]["chars"] == []
    assert docs["inputs/Project Falcon CIM.pdf"]["page_count"] == 3
    assert _deal()[0] == "ready"                                     # the readable CIM starts the clock


def test_intake_refusals(tmp_path, fake_repo):
    from bizwave_preloi.db import repo
    from bizwave_preloi.db.session import session_scope

    folder = _buyer_folder(tmp_path)
    assert _bw("intake", "no-such-deal", "--from", folder).exit_code == 1
    _new_deal("acme-hvac", "--pilot")
    _new_deal("beta-plumb", "--pilot")
    with session_scope() as s:
        repo.transition(s, "beta-plumb", "cancelled", by="chan")
    assert _bw("intake", "beta-plumb", "--from", folder).exit_code == 1
    assert _bw("intake", "acme-hvac", "--from", folder / "notes.xlsx").exit_code == 1      # not a folder
    inside_data = settings().data_dir / "incoming"
    _pdf(inside_data / "cim.pdf", CIM_PAGES)
    assert _bw("intake", "acme-hvac", "--from", inside_data).exit_code == 1
    inside_repo = fake_repo / "client files"
    _pdf(inside_repo / "cim.pdf", CIM_PAGES)
    assert _bw("intake", "acme-hvac", "--from", inside_repo).exit_code == 1
    assert _inputs("acme-hvac") == [] and _documents("acme-hvac") == {}
    assert _inputs("beta-plumb") == [] and _documents("beta-plumb") == {}


def test_intake_keeps_subfolders(tmp_path):
    folder = tmp_path / "from buyer"
    _pdf(folder / "financials" / "2024 P&L.pdf", PNL_PAGES)
    _new_deal("acme-hvac", "--pilot")
    assert _bw("intake", "acme-hvac", "--from", folder).exit_code == 0
    assert _inputs() == ["financials/2024 P&L.pdf"]
    assert _documents()["inputs/financials/2024 P&L.pdf"]["kind"] == "p_and_l"


# --------------------------------------------------------------------------- status

def test_status_lists_open_deals(tmp_path):
    from bizwave_preloi.db import repo
    from bizwave_preloi.db.session import session_scope

    _new_deal("acme-hvac", "--pilot")
    assert _bw("intake", "acme-hvac", "--from", _buyer_folder(tmp_path)).exit_code == 0
    _new_deal("beta-plumb")
    _new_deal("gamma-roof", "--pilot")
    with session_scope() as s:
        repo.transition(s, "gamma-roof", "cancelled", by="chan")
    r = _bw("status")
    assert r.exit_code == 0, r.output
    lines = r.output.splitlines()
    assert any("acme-hvac" in ln and "ready" in ln for ln in lines)
    assert any("beta-plumb" in ln and "awaiting_payment" in ln for ln in lines)
    assert "gamma-roof" not in r.output
    started = _deal()[1]
    assert started.strftime("%Y-%m-%d") in next(ln for ln in lines if "acme-hvac" in ln)
    assert "gamma-roof" in _bw("status", "--all").output


def test_open_deals_and_hours_since():
    from bizwave_preloi.db import repo
    from bizwave_preloi.db.session import session_scope

    complete = datetime(2026, 11, 9, 13, 0, tzinfo=timezone.utc)
    with session_scope() as s:
        customer = repo.get_or_create_customer(s, name="Pat Buyer", email="pat@example.com")
        s.flush()
        for code in ("acme-hvac", "beta-plumb", "gamma-roof"):
            repo.create_deal(s, deal_id=code, customer_id=customer.id, tier="flash", by="chan")
            repo.transition(s, code, "awaiting_documents", by="chan")
        repo.transition(s, "acme-hvac", "ready", by="chan", at=complete)
        repo.transition(s, "gamma-roof", "cancelled", by="chan")
    with session_scope() as s:
        open_ids = [d.id for d in repo.open_deals(s)]
        assert sorted(open_ids) == ["acme-hvac", "beta-plumb"]
        acme = s.get(repo.Deal, "acme-hvac")
        assert repo.hours_since_package_complete(acme, complete + timedelta(hours=26, minutes=30)) == 26.5
        assert repo.hours_since_package_complete(s.get(repo.Deal, "beta-plumb"), complete) is None


# --------------------------------------------------------------------------- backup

def _snapshots(folder: Path):
    return sorted((folder / "database").glob("bizwave-*.db"))


def _count(db_file: Path, table: str) -> int:
    engine = sa.create_engine("sqlite:///" + db_file.as_posix())
    try:
        with engine.connect() as conn:
            return conn.exec_driver_sql(f"select count(*) from {table}").scalar()
    finally:
        engine.dispose()


def test_backup_snapshot_opens_with_the_deal(tmp_path):
    from bizwave_preloi.ops.backup import backup

    _new_deal("acme-hvac", "--pilot")
    assert _bw("intake", "acme-hvac", "--from", _buyer_folder(tmp_path)).exit_code == 0
    target = tmp_path / "encrypted backups"
    r = _bw("backup", "--to", target)
    assert r.exit_code == 0, r.output
    [snapshot] = _snapshots(target)
    assert _count(snapshot, "deals") == 1 and _count(snapshot, "documents") == 3 and _count(snapshot, "pages") == 5
    deal_files = sorted(p.relative_to(settings().deals_dir).as_posix()
                        for p in settings().deals_dir.rglob("*") if p.is_file())
    backed = sorted(p.relative_to(target / "deals").as_posix() for p in (target / "deals").rglob("*") if p.is_file())
    assert backed == deal_files and len(deal_files) == 3
    second = backup(target)
    assert (second.deal_files_copied, second.deal_files_unchanged) == (0, 3)
    assert len(_snapshots(target)) == 2


def test_backup_never_deletes(tmp_path):
    from bizwave_preloi.ops.backup import backup

    _new_deal("acme-hvac", "--pilot")
    assert _bw("intake", "acme-hvac", "--from", _buyer_folder(tmp_path)).exit_code == 0
    target = tmp_path / "backups"
    backup(target)
    (settings().deals_dir / "acme-hvac" / "inputs" / "notes.xlsx").unlink()
    backup(target)
    assert (target / "deals" / "acme-hvac" / "inputs" / "notes.xlsx").is_file()


def test_backup_folder_inside_repository_refused(fake_repo, monkeypatch):
    from bizwave_preloi.config import DataFolderError
    from bizwave_preloi.ops.backup import backup

    monkeypatch.setenv("BIZWAVE_BACKUP_DIR", str(fake_repo / "backups"))
    with pytest.raises(DataFolderError):
        backup()
    assert _bw("backup").exit_code == 1
    assert not (fake_repo / "backups").exists()


def test_backup_before_upgrade_and_downgrade_of_the_live_database(tmp_path):
    from bizwave_preloi.db.migrate import downgrade, upgrade

    _new_deal("acme-hvac", "--pilot")
    backups = settings().backup_dir
    live = settings().database_url
    upgrade()                                                        # already at the newest revision
    assert _snapshots(backups) == []
    downgrade(live, "base")
    [before_down] = _snapshots(backups)
    assert before_down.name.endswith("-before-downgrade.db") and _count(before_down, "deals") == 1
    upgrade()
    snaps = _snapshots(backups)
    assert len(snaps) == 2 and any(p.name.endswith("-before-upgrade.db") for p in snaps)
    other = "sqlite:///" + (tmp_path / "elsewhere" / "other.db").as_posix()
    upgrade(other)
    downgrade(other, "base")
    assert len(_snapshots(backups)) == 2                              # no backup for other databases


# --------------------------------------------------------------------------- rules and entry point

def test_intake_rules_loader():
    import pydantic

    from bizwave_preloi.db.models import Document
    from bizwave_preloi.rules import IntakeRules, intake_rules

    rules = intake_rules()
    kinds = set(Document.__table__.c.kind.type.enums)
    assert {r.kind for r in rules.document_kinds} <= kinds and rules.unmatched_kind in kinds
    assert all(re.compile(p) for r in rules.document_kinds for p in r.patterns)
    good = rules.model_dump()
    for bad in ({**good, "unexpected": 1},
                {**good, "unmatched_kind": "teaser"},
                {**good, "document_kinds": [{"kind": "cim", "patterns": ["(unclosed"]}]}):
        with pytest.raises((pydantic.ValidationError, ValueError)):
            IntakeRules.model_validate(bad)


def test_cli_help_lists_the_commands():
    import tomllib

    r = _bw("--help")
    assert r.exit_code == 0, r.output
    for command in ("new-deal", "paid", "intake", "status", "backup"):
        assert command in r.output
    with open(REPO_ROOT / "pyproject.toml", "rb") as f:
        assert tomllib.load(f)["project"]["scripts"]["bw"] == "bizwave_preloi.cli:app"
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src") + os.pathsep + os.environ.get("PYTHONPATH", "")}
    module = subprocess.run([sys.executable, "-m", "bizwave_preloi.cli", "--help"], capture_output=True,
                            text=True, env=env, timeout=120)
    assert module.returncode == 0 and "intake" in module.stdout
