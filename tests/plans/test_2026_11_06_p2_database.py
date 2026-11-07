"""P2 gate — database core (tasks/plans/2026-11-06_p2_database.md).

Written before the code; never edited to make it pass (CLAUDE.md section 6). The package under test is
imported inside each test, so the first run shows every test failing on its own rather than one
collection error.
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
import sqlalchemy as sa

from bizwave_preloi import config
from bizwave_preloi.config import REPO_ROOT, settings

CORE = {"customers", "deals", "deal_events", "documents", "pages", "pipeline_runs"}
PT = timezone(timedelta(hours=-8))
UTC = timezone.utc
T0 = datetime(2026, 11, 9, 17, 0, tzinfo=UTC)


@pytest.fixture
def url(tmp_path):
    return "sqlite:///" + (tmp_path / "gate.db").as_posix()


@pytest.fixture
def migrated(url):
    from bizwave_preloi.db.migrate import upgrade
    upgrade(url)
    return url


def _tables(url):
    engine = sa.create_engine(url)
    try:
        return set(sa.inspect(engine).get_table_names())
    finally:
        engine.dispose()


def _new_deal(s, deal_id="acme-hvac", **kwargs):
    from bizwave_preloi.db import repo
    customer = repo.get_or_create_customer(s, name="Test Buyer", email="buyer@example.com")
    s.flush()
    return repo.create_deal(s, deal_id=deal_id, customer_id=customer.id, tier="flash", by="chan", **kwargs)


def _walk(s, deal_id, statuses, start=T0):
    from bizwave_preloi.db import repo
    times = []
    for k, status in enumerate(statuses, start=1):
        at = start + timedelta(minutes=k)
        repo.transition(s, deal_id, status, by="chan", at=at)
        times.append(at)
    return times


# ------------------------------------------------------------------------- schema and migrations

def _head_and_history():
    """Spec amendment 2 (Chan 2026-11-06 18:23 PT): the newest revision grows with every migration
    packet, so tests compare with the folder's head and check that 0001_core is in its history."""
    from alembic.script import ScriptDirectory

    from bizwave_preloi.db import migrate
    script = ScriptDirectory.from_config(migrate._config())
    return script.get_current_head(), {rev.revision for rev in script.walk_revisions()}


def test_migration_round_trip(url):
    from bizwave_preloi.db.migrate import current_revision, downgrade, upgrade
    upgrade(url)
    assert CORE <= _tables(url)
    downgrade(url, "base")
    assert not (CORE & _tables(url))
    upgrade(url)
    assert CORE <= _tables(url)
    head, history = _head_and_history()                  # spec amendment 2 (was == "0001_core")
    assert current_revision(url) == head and "0001_core" in history


def test_models_match_migration(migrated):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from bizwave_preloi.db.models import Base
    engine = sa.create_engine(migrated)
    try:
        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn, opts={"compare_type": True})
            assert compare_metadata(ctx, Base.metadata) == []
    finally:
        engine.dispose()


def test_tables_compile_for_postgres():
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.schema import CreateTable

    from bizwave_preloi.db.models import Base
    compiled = {t.name: str(CreateTable(t).compile(dialect=postgresql.dialect()))
                for t in Base.metadata.sorted_tables}
    assert CORE <= set(compiled)
    assert "CHECK" in compiled["deals"] and "'delivered'" in compiled["deals"]


def test_pragmas_on_every_connection(migrated):
    from bizwave_preloi.db.session import get_engine
    engine = get_engine(migrated)
    with engine.connect() as first, engine.connect() as second:
        for conn in (first, second):
            assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
            assert conn.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"


def test_foreign_keys_enforced(migrated):
    from bizwave_preloi.db.models import Deal
    from bizwave_preloi.db.session import session_scope
    with pytest.raises(sa.exc.IntegrityError):
        with session_scope(migrated) as s:
            s.add(Deal(id="orphan-deal", customer_id=999, tier="flash"))


# ------------------------------------------------------------------------- types

def test_decimal_text_exact(migrated):
    from bizwave_preloi.db.models import Deal
    from bizwave_preloi.db.session import session_scope
    from bizwave_preloi.db.types import DecimalText
    values = {"dec-a": Decimal("1234567.89"), "dec-b": Decimal("-0.10"), "dec-c": Decimal("1E+3"),
              "dec-d": 1500000}
    with session_scope(migrated) as s:
        for deal_id, value in values.items():
            _new_deal(s, deal_id=deal_id, asking_price=value)
    with session_scope(migrated) as s:
        stored = dict(s.execute(sa.text("select id, asking_price from deals")).all())
        assert stored == {"dec-a": "1234567.89", "dec-b": "-0.10", "dec-c": "1E+3", "dec-d": "1500000"}
        read = {d.id: d.asking_price for d in s.scalars(sa.select(Deal))}
    assert read["dec-a"] == Decimal("1234567.89") and isinstance(read["dec-a"], Decimal)
    assert str(read["dec-b"]) == "-0.10" and str(read["dec-c"]) == "1E+3"
    assert read["dec-d"] == Decimal(1500000)
    with pytest.raises(TypeError):
        DecimalText().process_bind_param(1.5, None)
    assert DecimalText().process_bind_param(None, None) is None


def test_utc_datetime(migrated):
    from bizwave_preloi.db.models import Deal
    from bizwave_preloi.db.session import session_scope
    from bizwave_preloi.db.types import UTCDateTime
    with session_scope(migrated) as s:
        deal = _new_deal(s)
        deal.offer_deadline = datetime(2026, 11, 6, 16, 21, tzinfo=PT)
    with session_scope(migrated) as s:
        back = s.get(Deal, "acme-hvac").offer_deadline
    assert back == datetime(2026, 11, 7, 0, 21, tzinfo=UTC)
    assert back.tzinfo is not None and back.utcoffset() == timedelta(0)
    with pytest.raises(ValueError):
        UTCDateTime().process_bind_param(datetime(2026, 11, 6, 16, 21), None)


def test_money_cents_are_integers(migrated):
    from bizwave_preloi.db.models import Deal
    from bizwave_preloi.db.session import session_scope
    with session_scope(migrated) as s:
        _new_deal(s, list_price_cents=75000)
    with session_scope(migrated) as s:
        cents = s.get(Deal, "acme-hvac").list_price_cents
    assert cents == 75000 and type(cents) is int


# ------------------------------------------------------------------------- customers and deals

def test_deal_id_rules(migrated):
    from bizwave_preloi.db.session import session_scope
    with session_scope(migrated) as s:
        assert _new_deal(s, deal_id="acme-hvac").id == "acme-hvac"
        assert _new_deal(s, deal_id="a" * 41).id == "a" * 41
    for bad in ("Acme HVAC", "ab", "a" * 42, "-lead-dash"):
        with pytest.raises(ValueError):
            with session_scope(migrated) as s:
                _new_deal(s, deal_id=bad)
    with pytest.raises((ValueError, sa.exc.IntegrityError)):
        with session_scope(migrated) as s:
            _new_deal(s, deal_id="acme-hvac")


def test_customer_email_normalized_and_unique(migrated):
    from bizwave_preloi.db import repo
    from bizwave_preloi.db.models import Customer
    from bizwave_preloi.db.session import session_scope
    with session_scope(migrated) as s:
        first = repo.get_or_create_customer(s, name="Chan", email="  Chan@Example.COM ")
        s.flush()
        second = repo.get_or_create_customer(s, name="Someone Else", email="chan@example.com")
        s.flush()
        assert first.id == second.id
        assert first.email == "chan@example.com" and first.name == "Chan"
        assert s.scalar(sa.select(sa.func.count()).select_from(Customer)) == 1


# ------------------------------------------------------------------------- status flow

def test_status_happy_path(migrated):
    from bizwave_preloi.db.models import Deal, DealEvent
    from bizwave_preloi.db.session import session_scope
    path = ["awaiting_payment", "awaiting_documents", "ready", "processing", "in_review", "approved",
            "delivered"]
    with session_scope(migrated) as s:
        _new_deal(s)
        times = _walk(s, "acme-hvac", path)
    with session_scope(migrated) as s:
        deal = s.get(Deal, "acme-hvac")
        events = s.scalars(sa.select(DealEvent).where(DealEvent.deal_id == "acme-hvac")
                           .order_by(DealEvent.id)).all()
        assert deal.status == "delivered"
        assert deal.package_complete_at == times[2]          # entered "ready"
        assert deal.delivered_at == times[6]
        assert len(events) == 8
        assert [(e.from_status, e.to_status) for e in events] == list(zip([None, "created"] + path[:-1],
                                                                         ["created"] + path))
        assert {e.kind for e in events} == {"status_change"}
        assert {e.by for e in events} == {"chan"}


def test_direct_path_without_payment(migrated):
    from bizwave_preloi.db.session import session_scope
    with session_scope(migrated) as s:
        _new_deal(s)
        _walk(s, "acme-hvac", ["awaiting_documents", "ready"])


def test_invalid_transitions_refused(migrated):
    from bizwave_preloi.db import repo
    from bizwave_preloi.db.models import Deal, DealEvent
    from bizwave_preloi.db.session import session_scope
    from bizwave_preloi.db.status import InvalidTransition
    with session_scope(migrated) as s:
        _new_deal(s, deal_id="deal-one")
        _new_deal(s, deal_id="deal-two")
        _walk(s, "deal-two", ["awaiting_documents", "ready", "processing", "in_review", "approved",
                              "delivered"])

    def count(s, deal_id):
        return s.scalar(sa.select(sa.func.count()).select_from(DealEvent).where(DealEvent.deal_id == deal_id))

    for deal_id, target in (("deal-one", "delivered"), ("deal-one", "paid"), ("deal-two", "in_review")):
        with session_scope(migrated) as s:
            before = (s.get(Deal, deal_id).status, count(s, deal_id))
            with pytest.raises(InvalidTransition):
                repo.transition(s, deal_id, target, by="chan")
            assert (s.get(Deal, deal_id).status, count(s, deal_id)) == before
    with session_scope(migrated) as s:
        repo.transition(s, "deal-one", "cancelled", by="chan")
    with session_scope(migrated) as s:
        with pytest.raises(InvalidTransition):
            repo.transition(s, "deal-one", "ready", by="chan")
    assert issubclass(InvalidTransition, ValueError)


def test_on_hold_keeps_first_ready_time(migrated):
    from bizwave_preloi.db.models import Deal
    from bizwave_preloi.db.session import session_scope
    with session_scope(migrated) as s:
        _new_deal(s)
        times = _walk(s, "acme-hvac", ["awaiting_documents", "ready", "on_hold", "ready"])
    with session_scope(migrated) as s:
        assert s.get(Deal, "acme-hvac").package_complete_at == times[1]


# ------------------------------------------------------------------------- documents and pages

def _deal_file(name, data, deal_id="acme-hvac"):
    path = settings().deals_dir / deal_id / "inputs" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_add_document_hash_size_relative_path(migrated):
    from bizwave_preloi.db import repo
    from bizwave_preloi.db.models import Document
    from bizwave_preloi.db.session import session_scope
    data = b"%PDF-1.4 synthetic test document\n" * 10
    path = _deal_file("cim.pdf", data)
    with session_scope(migrated) as s:
        _new_deal(s)
        s.flush()
        doc = repo.add_document(s, "acme-hvac", path, kind="cim")
        s.flush()
        again = repo.add_document(s, "acme-hvac", path, kind="cim")
        s.flush()
        assert again.id == doc.id
        assert doc.sha256 == hashlib.sha256(data).hexdigest()
        assert doc.size_bytes == len(data) == 330  # spec amendment, Chan 2026-11-06 17:29 PT
        assert doc.stored_path == "inputs/cim.pdf"
        assert doc.filename == "cim.pdf" and doc.kind == "cim"
        assert doc.received_at.tzinfo is not None
        assert s.scalar(sa.select(sa.func.count()).select_from(Document)) == 1


def test_add_document_outside_deal_folder_refused(migrated, tmp_path):
    from bizwave_preloi.db import repo
    from bizwave_preloi.db.models import Document
    from bizwave_preloi.db.session import session_scope
    elsewhere = tmp_path / "elsewhere.pdf"
    elsewhere.write_bytes(b"%PDF-1.4 x")
    other_deal = _deal_file("x.pdf", b"%PDF-1.4 y", deal_id="other-deal")
    with session_scope(migrated) as s:
        _new_deal(s)
        s.flush()
        for path in (elsewhere, other_deal):
            with pytest.raises(ValueError):
                repo.add_document(s, "acme-hvac", path, kind="cim")
        assert s.scalar(sa.select(sa.func.count()).select_from(Document)) == 0


def _two_page_pdf(path):
    pytest.importorskip("reportlab")
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(path), pagesize=letter)
    c.drawString(72, 720, "Synthetic Co. Income Statement for the years ended December 31, 2024 and 2023")
    c.drawString(72, 700, "Revenue 1,000,000 1,200,000")
    c.showPage()
    c.rect(72, 300, 400, 300, fill=1)
    c.showPage()
    c.save()


def test_record_pages_from_inventory(migrated):
    from bizwave_preloi.db import repo
    from bizwave_preloi.db.models import Document, Page
    from bizwave_preloi.db.session import session_scope
    from bizwave_preloi.ingest import inventory
    path = settings().deals_dir / "acme-hvac" / "inputs" / "cim.pdf"
    path.parent.mkdir(parents=True, exist_ok=True)
    _two_page_pdf(path)
    with session_scope(migrated) as s:
        _new_deal(s)
        s.flush()
        doc = repo.add_document(s, "acme-hvac", path, kind="cim")
        s.flush()
        rows = repo.record_pages(s, doc.id, inventory(path))
        s.flush()
        assert [r.page_no for r in rows] == [1, 2]
        assert [r.has_text_layer for r in rows] == [True, False]
        assert {r.read_status for r in rows} == {"pending"}
        assert s.get(Document, doc.id).page_count == 2
        with pytest.raises(ValueError):
            repo.record_pages(s, doc.id, inventory(path))
        assert s.scalar(sa.select(sa.func.count()).select_from(Page)) == 2


# ------------------------------------------------------------------------- pipeline runs

def _rules_hash(folder):
    h = hashlib.sha256()
    for f in sorted(folder.glob("*.yaml"), key=lambda p: p.name):
        h.update(f.read_bytes())
    return h.hexdigest()


def test_pipeline_run_lifecycle(migrated, tmp_path, monkeypatch):
    from bizwave_preloi import rules
    from bizwave_preloi.db import repo
    from bizwave_preloi.db.session import session_scope
    with session_scope(migrated) as s:
        _new_deal(s)
        s.flush()
        run = repo.start_run(s, "acme-hvac")
        s.flush()
        assert run.status == "running" and run.llm_mode == "off"
        assert run.rules_hash == _rules_hash(rules.RULES_DIR)
        assert re.fullmatch(r"[0-9a-f]{64}", run.rules_hash)
        assert run.git_sha is None or re.fullmatch(r"[0-9a-f]{40}", run.git_sha)
        assert run.started_at.tzinfo is not None
        done = repo.finish_run(s, run.id, status="succeeded", stages={"inventory": {"pages": 2}})
        s.flush()
        assert done.status == "succeeded" and done.finished_at is not None
        run_id = run.id
    with session_scope(migrated) as s:
        from bizwave_preloi.db.models import PipelineRun
        assert s.get(PipelineRun, run_id).stages == {"inventory": {"pages": 2}}

    copy = tmp_path / "rules-copy"
    copy.mkdir()
    for f in rules.RULES_DIR.glob("*.yaml"):
        (copy / f.name).write_bytes(f.read_bytes())
    (copy / "flags.yaml").write_bytes((copy / "flags.yaml").read_bytes() + b"\n# changed\n")
    monkeypatch.setattr(rules, "RULES_DIR", copy)
    with session_scope(migrated) as s:
        changed = repo.start_run(s, "acme-hvac")
        s.flush()
        assert changed.rules_hash == _rules_hash(copy) != _rules_hash(copy.parent / "missing")
        assert changed.rules_hash != run.rules_hash


# ------------------------------------------------------------------------- sessions, defaults, CLI

def test_default_database_in_data_folder():
    from bizwave_preloi.db.migrate import current_revision, upgrade
    upgrade()
    assert (settings().data_dir / "bizwave.db").is_file()
    head, history = _head_and_history()                  # spec amendment 2 (was == "0001_core")
    assert current_revision() == head and "0001_core" in history


def test_session_scope_rolls_back(migrated):
    from bizwave_preloi.db import repo
    from bizwave_preloi.db.models import Customer
    from bizwave_preloi.db.session import session_scope
    with pytest.raises(RuntimeError):
        with session_scope(migrated) as s:
            repo.get_or_create_customer(s, name="Gone", email="gone@example.com")
            s.flush()
            raise RuntimeError("boom")
    with session_scope(migrated) as s:
        assert s.scalar(sa.select(sa.func.count()).select_from(Customer)) == 0


def test_cli_upgrade_and_current(url):
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src") + os.pathsep + os.environ.get("PYTHONPATH", "")}
    up = subprocess.run([sys.executable, "-m", "bizwave_preloi.db", "upgrade", "--url", url],
                        capture_output=True, text=True, env=env, timeout=120)
    assert up.returncode == 0, up.stderr
    cur = subprocess.run([sys.executable, "-m", "bizwave_preloi.db", "current", "--url", url],
                         capture_output=True, text=True, env=env, timeout=120)
    assert cur.returncode == 0, cur.stderr
    head, history = _head_and_history()                  # spec amendment 2 (was "0001_core" in stdout)
    assert cur.stdout.strip() == head and "0001_core" in history


# ------------------------------------------------------------------------- P2.7 database location

@pytest.fixture
def fake_repo(tmp_path, monkeypatch):
    """A stand-in repository (P1 lesson): a broken refusal can only write here, never in the real repo."""
    repo_dir = tmp_path / "fake-repo"
    (repo_dir / "src" / "bizwave_preloi").mkdir(parents=True)
    (repo_dir / "pyproject.toml").write_text("[project]\nname = 'fake'\n")
    monkeypatch.setattr(config, "REPO_ROOT", repo_dir)
    return repo_dir


def test_database_inside_repo_refused(fake_repo, tmp_path, monkeypatch):
    from bizwave_preloi.config import DataFolderError, ensure_data_dirs
    from bizwave_preloi.db.migrate import upgrade
    from bizwave_preloi.db.session import get_engine
    inside = "sqlite:///" + (fake_repo / "bizwave.db").as_posix()
    with pytest.raises(DataFolderError) as err:
        get_engine(inside)
    assert "database" in str(err.value).lower()
    with pytest.raises(DataFolderError):
        upgrade(inside)
    assert not (fake_repo / "bizwave.db").exists()

    monkeypatch.setenv("BIZWAVE_DATABASE_URL", inside)
    with pytest.raises(DataFolderError):
        ensure_data_dirs()

    synced = "sqlite:///" + (tmp_path / "OneDrive - BizWave" / "db" / "bizwave.db").as_posix()
    with pytest.warns(UserWarning, match="(?i)sync"):
        get_engine(synced)

    monkeypatch.setenv("BIZWAVE_DATABASE_URL", "postgresql://localhost/bizwave")
    ensure_data_dirs()          # not a SQLite file: not checked, no error
