"""Shared database fixture (P2.5): later packets' tests get a migrated temporary database from `db_url`."""
from bizwave_preloi.db.migrate import current_revision


def test_db_url_fixture_is_migrated(db_url, tmp_path):
    assert db_url.endswith((tmp_path / "test.db").as_posix())
    assert current_revision(db_url) == "0001_core"
