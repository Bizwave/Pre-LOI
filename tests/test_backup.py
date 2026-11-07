"""ops/backup.py (P3): database snapshots and deal-file copies. Synthetic data, temporary folders."""
import warnings

import pytest
import sqlalchemy as sa

from bizwave_preloi.config import DataFolderError, settings


@pytest.fixture
def live():
    from bizwave_preloi.db import repo
    from bizwave_preloi.db.migrate import upgrade
    from bizwave_preloi.db.session import session_scope

    upgrade()
    with session_scope() as s:
        customer = repo.get_or_create_customer(s, name="Pat Buyer", email="pat@example.com")
        s.flush()
        repo.create_deal(s, deal_id="acme-hvac", customer_id=customer.id, tier="flash", by="chan")


def _deals_in(path):
    engine = sa.create_engine("sqlite:///" + path.as_posix())
    try:
        with engine.connect() as conn:
            return conn.exec_driver_sql("select id from deals").scalars().all()
    finally:
        engine.dispose()


def test_snapshots_open_on_their_own_and_never_collide(live, tmp_path):
    from bizwave_preloi.ops.backup import backup_database

    files = [backup_database(tmp_path / "b", label="x") for _ in range(3)]      # same second, same label
    assert len(set(files)) == 3 and all(f.name.endswith("-x.db") for f in files)
    assert all(_deals_in(f) == ["acme-hvac"] for f in files)


def test_backup_folder_inside_the_deals_folder_is_refused(live):
    from bizwave_preloi.ops.backup import backup

    with pytest.raises(DataFolderError, match="back itself up"):
        backup(settings().deals_dir / "backups")
    assert not (settings().deals_dir / "backups").exists()


def test_default_backup_folder_warns_same_disk(live):
    from bizwave_preloi.ops.backup import backup

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = backup()
    assert result.folder == settings().backup_dir
    assert any("same disk" in str(w.message) for w in caught)


def test_a_changed_deal_file_is_copied_again(live, tmp_path):
    from bizwave_preloi.ops.backup import backup

    folder = settings().deals_dir / "acme-hvac" / "outputs"
    folder.mkdir(parents=True)
    (folder / "memo.pdf").write_bytes(b"version 1")
    assert backup(tmp_path / "b").deal_files_copied == 1
    (folder / "memo.pdf").write_bytes(b"version 2, re-rendered")
    again = backup(tmp_path / "b")
    assert (again.deal_files_copied, again.deal_files_unchanged) == (1, 0)
    assert (tmp_path / "b" / "deals" / "acme-hvac" / "outputs" / "memo.pdf").read_bytes() == b"version 2, re-rendered"
    assert not list((tmp_path / "b").rglob("*.partial"))


def test_only_sqlite_is_backed_up(live, tmp_path):
    from bizwave_preloi.ops.backup import backup_database
    with pytest.raises(NotImplementedError):
        backup_database(tmp_path / "b", url="postgresql://localhost/bizwave")
