"""Shared database fixture (P2.5): later packets' tests get a migrated temporary database from `db_url`."""
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
