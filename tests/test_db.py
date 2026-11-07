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
