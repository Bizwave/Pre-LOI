"""Shared database fixture (P2.5): later packets' tests get a migrated temporary database from `db_url`."""
import pytest

from bizwave_preloi.db.migrate import current_revision


def test_db_url_fixture_is_migrated(db_url, tmp_path):
    assert db_url.endswith((tmp_path / "test.db").as_posix())
    assert current_revision(db_url) == "0001_core"


def test_migration_builds_exactly_the_models_schema(tmp_path):
    """Stronger than the gate's compare_metadata: the SQL the migration creates on SQLite is identical
    to what the models would create, constraint names included (naming convention applied by Alembic)."""
    import re

    import sqlalchemy as sa

    from bizwave_preloi.db.migrate import upgrade
    from bizwave_preloi.db.models import Base

    def ddl(engine):
        with engine.connect() as conn:
            rows = conn.exec_driver_sql("select name, sql from sqlite_master where sql is not null "
                                        "and name not like 'alembic%'").all()
        return {name: re.sub(r"\s+", " ", sql).strip() for name, sql in rows}

    migrated = "sqlite:///" + (tmp_path / "migrated.db").as_posix()
    upgrade(migrated)
    from_models = sa.create_engine("sqlite:///" + (tmp_path / "models.db").as_posix())
    Base.metadata.create_all(from_models)
    from_migration = sa.create_engine(migrated)
    try:
        assert ddl(from_migration) == ddl(from_models)
    finally:
        from_models.dispose()
        from_migration.dispose()


# --------------------------------------------------------------------------- migrations on a database with data
# Review round 1, should-fix 1: the round trip above runs on an empty database. These run a table-rebuilding
# ("batch recreate") migration over a database that holds a deal, its events, a document, pages and a run.

def _trial_scripts(tmp_path, body: str):
    """A copy of the shipped migrations plus a trial 0002 revision with the given upgrade() body."""
    import shutil
    from pathlib import Path

    import bizwave_preloi.db as db_pkg

    target = tmp_path / "scripts"
    shutil.copytree(Path(db_pkg.__file__).parent / "migrations", target,
                    ignore=shutil.ignore_patterns("__pycache__"))
    (target / "versions" / "0002_trial.py").write_text(
        "import sqlalchemy as sa\nfrom alembic import op\n\n"
        "revision = '0002_trial'\ndown_revision = '0001_core'\nbranch_labels = None\ndepends_on = None\n\n"
        "def upgrade():\n" + body + "\n\n"
        "def downgrade():\n    pass\n", encoding="utf-8")
    return str(target)


REBUILD_DEALS = ("    with op.batch_alter_table('deals', recreate='always') as b:\n"
                 "        b.alter_column('industry', type_=sa.String(200), existing_type=sa.String(120))")


def _seed(url):
    from datetime import datetime, timezone
    from types import SimpleNamespace

    from bizwave_preloi import config
    from bizwave_preloi.db import repo
    from bizwave_preloi.db.session import session_scope

    folder = config.settings().deals_dir / "acme-hvac" / "inputs"
    folder.mkdir(parents=True)
    (folder / "cim.pdf").write_bytes(b"synthetic cim\n")
    with session_scope(url) as s:
        customer = repo.get_or_create_customer(s, name="Pat Buyer", email="pat@example.com")
        s.flush()
        repo.create_deal(s, deal_id="acme-hvac", customer_id=customer.id, tier="flash", by="chan",
                         list_price_cents=75000, industry="HVAC")
        for status in ("awaiting_documents", "ready"):
            repo.transition(s, "acme-hvac", status, by="chan",
                            at=datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc))
        doc = repo.add_document(s, "acme-hvac", folder / "cim.pdf", kind="cim")
        s.flush()
        page = SimpleNamespace(page=1, chars=900, has_text_layer=True, tables_found=1, images=0)
        repo.record_pages(s, doc.id, [page])
        repo.start_run(s, "acme-hvac")


def _counts(url):
    from bizwave_preloi.db.session import get_engine
    with get_engine(url).connect() as conn:
        return {t: conn.exec_driver_sql(f"select count(*) from {t}").scalar()
                for t in ("customers", "deals", "deal_events", "documents", "pages", "pipeline_runs")}


def _tables(url):
    from bizwave_preloi.db.session import get_engine
    with get_engine(url).connect() as conn:
        return {r[0] for r in conn.exec_driver_sql("select name from sqlite_master where type='table'")}


def test_rebuilding_migration_keeps_every_row(db_url, tmp_path):
    from alembic import command

    from bizwave_preloi.db import migrate
    from bizwave_preloi.db.session import get_engine

    _seed(db_url)
    before = _counts(db_url)
    assert before == {"customers": 1, "deals": 1, "deal_events": 3, "documents": 1, "pages": 1,
                      "pipeline_runs": 1}
    migrate._run(command.upgrade, db_url, "head", script_location=_trial_scripts(tmp_path, REBUILD_DEALS))
    assert migrate.current_revision(db_url) == "0002_trial"
    assert _counts(db_url) == before
    with get_engine(db_url).connect() as conn:
        assert conn.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1     # back on for normal use
        sql = conn.exec_driver_sql("select sql from sqlite_master where name='deals'").scalar()
    assert "VARCHAR(200)" in sql
    assert not any(t.startswith("_alembic_tmp") for t in _tables(db_url))


def test_failed_migration_rolls_back_schema_and_data(db_url, tmp_path):
    from alembic import command

    from bizwave_preloi.db import migrate

    _seed(db_url)
    before = _counts(db_url)
    failing = _trial_scripts(tmp_path, REBUILD_DEALS + "\n    raise RuntimeError('trial failure')")
    with pytest.raises(RuntimeError, match="trial failure"):
        migrate._run(command.upgrade, db_url, "head", script_location=failing)
    assert migrate.current_revision(db_url) == "0001_core"
    assert _counts(db_url) == before
    assert not any(t.startswith("_alembic_tmp") for t in _tables(db_url))   # nothing half-done to trip a retry


def test_migration_that_orphans_rows_is_refused(db_url, tmp_path):
    from alembic import command

    from bizwave_preloi.db import migrate

    _seed(db_url)
    before = _counts(db_url)
    orphaning = _trial_scripts(tmp_path, "    op.execute('DELETE FROM customers')")
    with pytest.raises(RuntimeError, match="foreign key points nowhere"):
        migrate._run(command.upgrade, db_url, "head", script_location=orphaning)
    assert migrate.current_revision(db_url) == "0001_core"
    assert _counts(db_url) == before


# --------------------------------------------------------------------------- inputs checked where they enter
# Review round 1, should-fixes 4, 5 and 7, and the untested paths in nit 12. Each refusal happens before
# anything is written, with the error type the contract names.

def _customer(s):
    from bizwave_preloi.db import repo
    customer = repo.get_or_create_customer(s, name="Pat Buyer", email="pat@example.com")
    s.flush()
    return customer


def _deal_count(url):
    from bizwave_preloi.db.session import get_engine
    with get_engine(url).connect() as conn:
        return conn.exec_driver_sql("select count(*) from deals").scalar()


@pytest.mark.parametrize("field, value, error", [
    ("list_price_cents", 750.5, TypeError),          # would be stored as REAL
    ("list_price_cents", True, TypeError),           # would be stored as 1
    ("asking_price", 2500000.0, TypeError),          # a float is never a figure read from a page
    ("asking_price", __import__("decimal").Decimal("1" * 41), ValueError),   # longer than the column
    ("by", "  ", ValueError),
])
def test_create_deal_refuses_bad_input_before_writing(db_url, field, value, error):
    from bizwave_preloi.db import repo
    from bizwave_preloi.db.session import session_scope

    with session_scope(db_url) as s:
        kwargs = dict(deal_id="acme-hvac", customer_id=_customer(s).id, tier="flash", by="chan")
        kwargs[field] = value
        with pytest.raises(error):
            repo.create_deal(s, **kwargs)
        assert not s.new                     # nothing added to the session
    assert _deal_count(db_url) == 0


@pytest.mark.parametrize("deal_id", ["acme-hvac\n", "Acme-hvac", "ab", "-acme"])
def test_deal_id_must_match_the_whole_pattern(db_url, deal_id):
    from bizwave_preloi.db import repo
    from bizwave_preloi.db.session import session_scope
    from bizwave_preloi.schemas import Deal

    with session_scope(db_url) as s:
        with pytest.raises(ValueError, match="Deal id"):
            repo.create_deal(s, deal_id=deal_id, customer_id=_customer(s).id, tier="flash", by="chan")
    with pytest.raises(ValueError):
        Deal(id=deal_id, name="x")           # the schema refuses the same ids
    assert _deal_count(db_url) == 0


def test_transition_refuses_a_naive_time_before_writing(db_url):
    from datetime import datetime

    from bizwave_preloi.db import repo
    from bizwave_preloi.db.models import DealEvent
    from bizwave_preloi.db.session import session_scope

    with session_scope(db_url) as s:
        repo.create_deal(s, deal_id="acme-hvac", customer_id=_customer(s).id, tier="flash", by="chan")
    with session_scope(db_url) as s:
        with pytest.raises(ValueError, match="timezone-aware"):
            repo.transition(s, "acme-hvac", "awaiting_documents", by="chan", at=datetime(2026, 11, 6, 9))
        with pytest.raises(ValueError, match="'by'"):
            repo.transition(s, "acme-hvac", "awaiting_documents", by="")
        assert not s.new
        assert s.get(repo.Deal, "acme-hvac").status == "created"
        assert s.query(DealEvent).count() == 1


def test_direct_path_without_payment_reaches_awaiting_documents(db_url):
    from bizwave_preloi.db import repo
    from bizwave_preloi.db.session import session_scope

    with session_scope(db_url) as s:
        repo.create_deal(s, deal_id="acme-hvac", customer_id=_customer(s).id, tier="flash", by="chan")
        deal = repo.transition(s, "acme-hvac", "awaiting_documents", by="chan")
        assert deal.status == "awaiting_documents" and deal.package_complete_at is None


@pytest.mark.parametrize("env, expected", [
    ({"ANTHROPIC_API_KEY": "test-key-not-real"}, "on"),
    ({"ANTHROPIC_API_KEY": "test-key-not-real", "BIZWAVE_LLM_DISABLED_USES": "addbacks.classify_unmatched"}, "on"),
    ({"ANTHROPIC_API_KEY": "test-key-not-real", "BIZWAVE_NO_LLM": "1"}, "off"),
    ({}, "off"),
])
def test_run_records_whether_claude_was_reachable(db_url, monkeypatch, env, expected):
    from bizwave_preloi.db import repo
    from bizwave_preloi.db.session import session_scope

    for name, value in env.items():
        monkeypatch.setenv(name, value)
    with session_scope(db_url) as s:
        repo.create_deal(s, deal_id="acme-hvac", customer_id=_customer(s).id, tier="flash", by="chan")
        assert repo.start_run(s, "acme-hvac").llm_mode == expected


def test_run_records_the_code_version(db_url):
    import shutil

    from bizwave_preloi import config
    from bizwave_preloi.db import repo
    from bizwave_preloi.db.session import session_scope

    if shutil.which("git") is None or not (config.REPO_ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    with session_scope(db_url) as s:
        repo.create_deal(s, deal_id="acme-hvac", customer_id=_customer(s).id, tier="flash", by="chan")
        sha = repo.start_run(s, "acme-hvac").git_sha
    assert sha is not None and len(sha) == 40 and set(sha) <= set("0123456789abcdef")


def test_refusals_for_missing_records(db_url, tmp_path):
    from bizwave_preloi import config
    from bizwave_preloi.db import repo
    from bizwave_preloi.db.session import session_scope

    with session_scope(db_url) as s:
        with pytest.raises(ValueError, match="No deal"):
            repo.add_document(s, "no-such-deal", tmp_path / "x.pdf", kind="cim")
        with pytest.raises(ValueError, match="No document"):
            repo.record_pages(s, 999, [])
        repo.create_deal(s, deal_id="acme-hvac", customer_id=_customer(s).id, tier="flash", by="chan")
        folder = config.settings().deals_dir / "acme-hvac" / "inputs"
        folder.mkdir(parents=True)
        with pytest.raises(ValueError, match="not a file"):
            repo.add_document(s, "acme-hvac", folder, kind="cim")
        run = repo.start_run(s, "acme-hvac")
        s.flush()
        with pytest.raises(ValueError, match="succeeded' or 'failed"):
            repo.finish_run(s, run.id, status="done", stages={})


def test_run_stages_edited_in_place_are_saved(db_url):
    from bizwave_preloi.db import repo
    from bizwave_preloi.db.models import PipelineRun
    from bizwave_preloi.db.session import session_scope

    with session_scope(db_url) as s:
        repo.create_deal(s, deal_id="acme-hvac", customer_id=_customer(s).id, tier="flash", by="chan")
        run = repo.start_run(s, "acme-hvac")
        s.flush()
        run_id = run.id
    with session_scope(db_url) as s:
        run = s.get(PipelineRun, run_id)
        run.stages["inventory"] = {"pages": 2}
    with session_scope(db_url) as s:
        assert s.get(PipelineRun, run_id).stages == {"inventory": {"pages": 2}}


# --------------------------------------------------------------------------- 0001's constraint names
# Review round 1, should-fix 8: 0001 takes its constraint names from the live naming convention. If the
# convention changed, new databases would get different names from existing ones and a later
# drop_constraint(name) would fail on one of them. Both are pinned here; change them only with a new
# migration that renames the constraints.

FIRST_MIGRATION_NAMES = {
    "ck_deal_events_event_kind", "ck_deals_deal_status", "ck_deals_tier", "ck_deals_verdict",
    "ck_documents_document_kind", "ck_pages_page_no_positive", "ck_pages_read_status",
    "ck_pipeline_runs_llm_mode", "ck_pipeline_runs_run_status",
    "fk_deal_events_deal_id_deals", "fk_deals_customer_id_customers", "fk_documents_deal_id_deals",
    "fk_pages_document_id_documents", "fk_pages_run_id_pipeline_runs", "fk_pipeline_runs_deal_id_deals",
    "ix_deal_events_deal_id_at",
    "pk_customers", "pk_deal_events", "pk_deals", "pk_documents", "pk_pages", "pk_pipeline_runs",
    "uq_customers_email", "uq_documents_deal_id", "uq_documents_deal_id_stored_path", "uq_pages_document_id",
}


def test_naming_convention_is_pinned():
    from bizwave_preloi.db.models import NAMING_CONVENTION
    assert NAMING_CONVENTION == {
        "ix": "ix_%(column_0_label)s", "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s", "pk": "pk_%(table_name)s"}


def test_first_migration_constraint_names_are_pinned(tmp_path):
    import re

    import sqlalchemy as sa

    from bizwave_preloi.db.migrate import upgrade

    url = "sqlite:///" + (tmp_path / "names.db").as_posix()
    upgrade(url, "0001_core")
    engine = sa.create_engine(url)
    try:
        with engine.connect() as conn:
            rows = conn.exec_driver_sql("select type, name, sql from sqlite_master where name not like "
                                        "'alembic%' and name not like 'sqlite_%'").all()
    finally:
        engine.dispose()
    names = {name for kind, name, _ in rows if kind == "index"}
    for _, _, sql in rows:
        names |= set(re.findall(r"CONSTRAINT (\w+)", sql or ""))
    assert names == FIRST_MIGRATION_NAMES


@pytest.mark.parametrize("name", ["bizwave.db", "bizwave.db-wal", "bizwave.db-shm", "bizwave.db-journal",
                                  "x.sqlite-wal", "x.sqlite3-shm"])
def test_git_ignores_database_files_and_their_companions(name):
    """Review round 1, should-fix 9: a safety net if a database ever lands in the repository (WAL on)."""
    import shutil
    import subprocess

    from bizwave_preloi import config

    if shutil.which("git") is None or not (config.REPO_ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    # At the repository root: everything under deals/ is ignored anyway.
    result = subprocess.run(["git", "check-ignore", "-q", "--no-index", name], cwd=config.REPO_ROOT)
    assert result.returncode == 0, f"{name} is not ignored by .gitignore"


def test_cli_takes_the_revision_as_written_in_the_plan(tmp_path, capsys):
    """Review round 1, should-fix 10: the plan's rollback command uses a positional revision."""
    from bizwave_preloi.db.__main__ import main
    from bizwave_preloi.db.migrate import current_revision

    url = "sqlite:///" + (tmp_path / "cli.db").as_posix()
    assert main(["upgrade", "--url", url]) == 0
    assert current_revision(url) == "0001_core"
    assert main(["downgrade", "--url", url, "base"]) == 0
    assert current_revision(url) is None
    assert main(["upgrade", "--url", url, "--revision", "0001_core"]) == 0
    assert current_revision(url) == "0001_core"
    with pytest.raises(SystemExit):
        main(["downgrade", "--url", url, "base", "--revision", "-1"])
    assert current_revision(url) == "0001_core"


# --------------------------------------------------------------------------- on_hold (P2.8, Chan 17:59)
# Review round 1, should-fix 2: on_hold must not be a shortcut past ready (the SLA clock and the pipeline
# run). From on_hold a deal goes back only to the status it had before the hold, or is cancelled.

def _deal_at(s, path):
    from bizwave_preloi.db import repo
    repo.create_deal(s, deal_id="acme-hvac", customer_id=_customer(s).id, tier="flash", by="chan")
    for status in path:
        repo.transition(s, "acme-hvac", status, by="chan")


@pytest.mark.parametrize("before, back, refused", [
    (["awaiting_documents"], "awaiting_documents", ["ready", "processing", "in_review"]),
    (["awaiting_documents", "ready"], "ready", ["awaiting_documents", "processing", "in_review"]),
    (["awaiting_documents", "ready", "processing"], "processing", ["ready", "in_review"]),
    (["awaiting_documents", "ready", "processing", "in_review"], "in_review", ["processing", "ready"]),
])
def test_on_hold_returns_only_to_where_it_came_from(db_url, before, back, refused):
    from bizwave_preloi.db import repo
    from bizwave_preloi.db.models import DealEvent
    from bizwave_preloi.db.session import session_scope
    from bizwave_preloi.db.status import InvalidTransition

    with session_scope(db_url) as s:
        _deal_at(s, before + ["on_hold"])
    with session_scope(db_url) as s:
        events = s.query(DealEvent).count()
        for target in refused:
            with pytest.raises(InvalidTransition, match=f"back to '{back}'"):
                repo.transition(s, "acme-hvac", target, by="chan")
        assert s.query(DealEvent).count() == events and not s.new          # nothing written
        assert repo.transition(s, "acme-hvac", back, by="chan").status == back


def test_on_hold_can_always_be_cancelled(db_url):
    from bizwave_preloi.db import repo
    from bizwave_preloi.db.session import session_scope

    with session_scope(db_url) as s:
        _deal_at(s, ["awaiting_documents", "on_hold"])
        assert repo.transition(s, "acme-hvac", "cancelled", by="chan").status == "cancelled"


def test_the_reviewers_shortcut_is_closed(db_url):
    """awaiting_documents -> on_hold -> in_review -> approved -> delivered reached delivery with no
    package_complete_at (no SLA clock, no pipeline run)."""
    from bizwave_preloi.db import repo
    from bizwave_preloi.db.session import session_scope
    from bizwave_preloi.db.status import InvalidTransition

    with session_scope(db_url) as s:
        _deal_at(s, ["awaiting_documents", "on_hold"])
        with pytest.raises(InvalidTransition):
            repo.transition(s, "acme-hvac", "in_review", by="chan")


def test_every_way_to_delivery_passes_ready():
    """Over the flow itself: walking every allowed move (with on_hold returning only where it came from),
    no path from created reaches delivered without passing ready."""
    from bizwave_preloi.db.status import ALLOWED, check

    def moves(state):
        status, held_from, seen_ready = state
        for target in ALLOWED[status]:
            try:
                check(status, target, held_from=held_from)
            except ValueError:
                continue
            yield (target, status if target == "on_hold" else None, seen_ready or target == "ready")

    start = ("created", None, False)
    seen, todo = {start}, [start]
    while todo:
        for nxt in moves(todo.pop()):
            if nxt not in seen:
                seen.add(nxt)
                todo.append(nxt)
    assert ("delivered", None, True) in seen
    assert not any(status == "delivered" and not ready for status, _, ready in seen)


# --------------------------------------------------------------------------- one file, one row (P2.9, Chan 17:59)
# Review round 1, should-fix 3: a file overwritten in place and added again gave two rows with one
# stored_path, so a source reference to the first row would open the new file (invariant 1).

def test_a_different_file_at_a_recorded_path_is_refused(db_url):
    from bizwave_preloi import config
    from bizwave_preloi.db import repo
    from bizwave_preloi.db.models import Document
    from bizwave_preloi.db.session import session_scope

    folder = config.settings().deals_dir / "acme-hvac" / "inputs"
    folder.mkdir(parents=True)
    cim = folder / "cim.pdf"
    cim.write_bytes(b"%PDF-1.4 first version\n")
    with session_scope(db_url) as s:
        repo.create_deal(s, deal_id="acme-hvac", customer_id=_customer(s).id, tier="flash", by="chan")
        first = repo.add_document(s, "acme-hvac", cim, kind="cim")
        s.flush()
        first_sha = first.sha256
    cim.write_bytes(b"%PDF-1.4 revised version, saved over the first\n")
    with session_scope(db_url) as s:
        with pytest.raises(ValueError, match="cim-v2.pdf|new name"):
            repo.add_document(s, "acme-hvac", cim, kind="cim")
        assert not s.new
    (folder / "cim-v2.pdf").write_bytes(b"%PDF-1.4 revised version, saved under a new name\n")
    with session_scope(db_url) as s:
        repo.add_document(s, "acme-hvac", folder / "cim-v2.pdf", kind="cim")
    with session_scope(db_url) as s:
        rows = {d.stored_path: d.sha256 for d in s.query(Document)}
    assert rows["inputs/cim.pdf"] == first_sha                 # the first record is untouched
    assert set(rows) == {"inputs/cim.pdf", "inputs/cim-v2.pdf"}


def test_the_database_refuses_two_rows_for_one_path(db_url):
    import sqlalchemy as sa

    from bizwave_preloi.db import repo
    from bizwave_preloi.db.models import Document
    from bizwave_preloi.db.session import session_scope
    from bizwave_preloi.db.types import utcnow

    with pytest.raises(sa.exc.IntegrityError, match="UNIQUE"):
        with session_scope(db_url) as s:
            repo.create_deal(s, deal_id="acme-hvac", customer_id=_customer(s).id, tier="flash", by="chan")
            for digest in ("a" * 64, "b" * 64):
                s.add(Document(deal_id="acme-hvac", filename="cim.pdf", kind="cim", sha256=digest,
                               size_bytes=1, stored_path="inputs/cim.pdf", received_at=utcnow()))
            s.flush()


# --------------------------------------------------------------------------- four refusals (P2.10, Chan 17:59)

def test_a_finished_run_keeps_its_record(db_url):
    from bizwave_preloi.db import repo
    from bizwave_preloi.db.session import session_scope

    with session_scope(db_url) as s:
        repo.create_deal(s, deal_id="acme-hvac", customer_id=_customer(s).id, tier="flash", by="chan")
        run = repo.start_run(s, "acme-hvac")
        s.flush()
        repo.finish_run(s, run.id, status="failed", stages={"inventory": {}}, error="page 3 unreadable")
        with pytest.raises(ValueError, match="already finished"):
            repo.finish_run(s, run.id, status="succeeded", stages={})
        assert (run.status, run.error) == ("failed", "page 3 unreadable")


@pytest.mark.parametrize("text", ["NaN", "-Infinity", "Infinity", "sNaN"])
def test_a_figure_must_be_a_finite_number(db_url, text):
    from decimal import Decimal

    from bizwave_preloi.db import repo
    from bizwave_preloi.db.session import session_scope

    with session_scope(db_url) as s:
        with pytest.raises(ValueError, match="finite"):
            repo.create_deal(s, deal_id="acme-hvac", customer_id=_customer(s).id, tier="flash", by="chan",
                             asking_price=Decimal(text))
    assert _deal_count(db_url) == 0


def test_zero_pages_are_refused(db_url):
    from bizwave_preloi import config
    from bizwave_preloi.db import repo
    from bizwave_preloi.db.session import session_scope

    folder = config.settings().deals_dir / "acme-hvac"
    folder.mkdir(parents=True)
    (folder / "cim.pdf").write_bytes(b"%PDF-1.4 synthetic\n")
    with session_scope(db_url) as s:
        repo.create_deal(s, deal_id="acme-hvac", customer_id=_customer(s).id, tier="flash", by="chan")
        doc = repo.add_document(s, "acme-hvac", folder / "cim.pdf", kind="cim")
        s.flush()
        with pytest.raises(ValueError, match="no pages"):
            repo.record_pages(s, doc.id, [])
        assert doc.page_count is None


def test_current_on_a_missing_database_creates_nothing(tmp_path, capsys):
    from bizwave_preloi.db.__main__ import main
    from bizwave_preloi.db.migrate import current_revision

    missing = tmp_path / "typo" / "bizwave.db"
    url = "sqlite:///" + missing.as_posix()
    with pytest.raises(FileNotFoundError, match="No database"):
        current_revision(url)
    assert main(["current", "--url", url]) == 1
    assert "No database" in capsys.readouterr().err
    assert not missing.exists() and not missing.parent.exists()
