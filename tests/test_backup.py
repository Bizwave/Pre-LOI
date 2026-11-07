"""ops/backup.py (P3): database snapshots and deal-file copies. Synthetic data, temporary folders."""
import re
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
    engine = sa.create_engine(sa.engine.URL.create("sqlite", database=str(path)))   # a %25 in a name stays
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


def test_a_changed_deal_file_is_kept_beside_the_old_copy(live, tmp_path):
    """Deal files are not meant to change; a different content may be damage, so the backup keeps the old
    copy and adds the new one under a dated name, and reports it (P3 review round 1, should-fix 4)."""
    from bizwave_preloi.ops.backup import backup

    folder = settings().deals_dir / "acme-hvac" / "outputs"
    folder.mkdir(parents=True)
    (folder / "memo.pdf").write_bytes(b"version 1")
    first = backup(tmp_path / "b")
    assert (first.deal_files_copied, first.deal_files_changed) == (1, ())
    (folder / "memo.pdf").write_bytes(b"version 2, re-rendered")
    again = backup(tmp_path / "b")
    assert (again.deal_files_copied, again.deal_files_unchanged) == (1, 0)
    assert again.deal_files_changed == ("acme-hvac/outputs/memo.pdf",)
    held = tmp_path / "b" / "deals" / "acme-hvac" / "outputs"
    assert (held / "memo.pdf").read_bytes() == b"version 1"
    changed = [p for p in held.iterdir() if p.name != "memo.pdf"]
    assert len(changed) == 1 and re.fullmatch(r"memo-changed-\d{8}-\d{6}\.pdf", changed[0].name)
    assert changed[0].read_bytes() == b"version 2, re-rendered"
    third = backup(tmp_path / "b")                                       # nothing new: both contents held
    assert (third.deal_files_copied, third.deal_files_unchanged, third.deal_files_changed) == (0, 1, ())
    (folder / "memo.pdf").write_bytes(b"version 1")                      # back to a content the backup holds
    assert backup(tmp_path / "b").deal_files_copied == 0
    assert not [p for p in (tmp_path / "b").rglob("*") if p.name.endswith(".partial")]


def test_only_sqlite_is_backed_up(live, tmp_path):
    from bizwave_preloi.ops.backup import backup_database
    with pytest.raises(NotImplementedError):
        backup_database(tmp_path / "b", url="postgresql://localhost/bizwave")


# --------------------------------------------------------------------------- P3 review round 1

def test_a_failed_snapshot_leaves_nothing_under_a_snapshot_name(live, tmp_path, monkeypatch):
    """A restore takes "the newest snapshot": a failed backup must never leave an empty file there
    (should-fix 5)."""
    from bizwave_preloi.ops import backup as backup_module

    def broken(url=None):
        raise RuntimeError("simulated failure while opening the database")
    monkeypatch.setattr(backup_module, "get_engine", broken)
    with pytest.raises(RuntimeError, match="simulated"):
        backup_module.backup_database(tmp_path / "b", label="before-upgrade")
    assert list((tmp_path / "b" / "database").iterdir()) == []


def test_snapshots_are_in_rollback_journal_mode(live, tmp_path):
    """Opening a snapshot in a synced folder must not create -wal/-shm files beside it (nit 16)."""
    from bizwave_preloi.ops.backup import backup_database

    snapshot = backup_database(tmp_path / "b")
    assert snapshot.read_bytes()[18:20] == b"\x01\x01"             # 1, 1: rollback journal, not WAL (2, 2)
    assert _deals_in(snapshot) == ["acme-hvac"]
    assert sorted(p.name for p in snapshot.parent.iterdir()) == [snapshot.name]


def test_backup_folder_names_and_files(live, tmp_path):
    """A folder name with % in it works; a file given as the folder is refused in one line (nit 15)."""
    from bizwave_preloi.ops.backup import backup

    odd = tmp_path / "Backups 100%25 safe"
    assert _deals_in(backup(odd).database) == ["acme-hvac"]
    not_a_folder = tmp_path / "backup.txt"
    not_a_folder.write_text("x")
    with pytest.raises(ValueError, match="is a file"):
        backup(not_a_folder)


def test_the_same_disk_warning_is_given_once(live):
    from bizwave_preloi.ops.backup import backup

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        backup()
    assert sum("same disk" in str(w.message) for w in caught) == 1


def test_temporary_files_are_not_backed_up_and_problems_do_not_stop_it(live, tmp_path, monkeypatch):
    from bizwave_preloi.ops import files as filestore
    from bizwave_preloi.ops.backup import backup

    inputs = settings().deals_dir / "acme-hvac" / "inputs"
    inputs.mkdir(parents=True)
    (inputs / ".bw-0123abcd.partial").write_bytes(b"half a copy")
    (inputs / "a.pdf").write_bytes(b"first")
    (inputs / "b.pdf").write_bytes(b"second")
    real = filestore.copy_to_temporary

    def unreadable(source, folder):
        if source.name == "a.pdf":
            raise OSError(5, "Input/output error")
        return real(source, folder)
    monkeypatch.setattr(filestore, "copy_to_temporary", unreadable)
    result = backup(tmp_path / "b")
    assert result.deal_files_copied == 1 and len(result.problems) == 1
    assert result.problems[0].startswith("acme-hvac/inputs/a.pdf") and "Input/output" in result.problems[0]
    held = tmp_path / "b" / "deals" / "acme-hvac" / "inputs"
    assert sorted(p.name for p in held.iterdir()) == ["b.pdf"]


def test_the_live_database_reached_through_a_link_is_backed_up_first(tmp_path):
    """The live database named through a link (or another spelling) is still the live database: a
    downgrade of it makes the M11 snapshot first (should-fix 8)."""
    import os

    from bizwave_preloi.db.migrate import downgrade, upgrade

    upgrade()
    link = tmp_path / "data-link"
    try:
        os.symlink(settings().data_dir, link, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("this system cannot create links (Windows without Developer Mode)")
    downgrade("sqlite:///" + (link / "bizwave.db").as_posix(), "base")
    snapshots = list((settings().backup_dir / "database").glob("*-before-downgrade.db"))
    assert len(snapshots) == 1


def test_a_backup_folder_containing_the_deals_folder_is_refused(live):
    """`--to` the data folder would make <backup>/deals the originals: nothing would be copied (P3 review
    round 2, should-fix 2)."""
    from bizwave_preloi.ops.backup import backup

    (settings().deals_dir / "acme-hvac" / "inputs").mkdir(parents=True)
    (settings().deals_dir / "acme-hvac" / "inputs" / "cim.pdf").write_bytes(b"synthetic")
    for folder in (settings().data_dir, settings().data_dir.parent):
        with pytest.raises(DataFolderError, match="contains the deals folder"):
            backup(folder)
    assert not (settings().data_dir / "database").exists()
    assert not (settings().data_dir.parent / "database").exists()
