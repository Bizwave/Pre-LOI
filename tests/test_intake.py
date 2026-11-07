"""ops/intake.py (P3), without the command line. Synthetic files only."""
import pytest

from bizwave_preloi.config import settings


@pytest.fixture
def deal():
    from bizwave_preloi.db import repo
    from bizwave_preloi.db.migrate import upgrade
    from bizwave_preloi.db.session import session_scope

    upgrade()
    with session_scope() as s:
        customer = repo.get_or_create_customer(s, name="Pat Buyer", email="pat@example.com")
        s.flush()
        repo.create_deal(s, deal_id="acme-hvac", customer_id=customer.id, tier="flash", by="chan")
        repo.transition(s, "acme-hvac", "awaiting_documents", by="chan")
    return "acme-hvac"


def _pdf(path, text):
    pytest.importorskip("reportlab")
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=letter)
    c.drawString(72, 720, text)
    c.showPage()
    c.save()


def test_an_interrupted_run_is_finished_without_copying_again(deal, tmp_path):
    from bizwave_preloi.ops.intake import intake

    folder = tmp_path / "in"
    _pdf(folder / "Project CIM.pdf", "Confidential information memorandum, synthetic company overview")
    copied = settings().deals_dir / deal / "inputs" / "Project CIM.pdf"
    copied.parent.mkdir(parents=True)
    copied.write_bytes((folder / "Project CIM.pdf").read_bytes())       # copied, never recorded
    result = intake(deal, folder, by="chan")
    assert [(f.action, f.stored_path, f.kind) for f in result.files] == [("recorded", "inputs/Project CIM.pdf", "cim")]
    assert result.status_after == "ready"


def test_kind_names_must_exist_and_be_unique(deal, tmp_path):
    from bizwave_preloi.ops.intake import intake

    folder = tmp_path / "in"
    _pdf(folder / "a" / "deck.pdf", "synthetic deck one")
    _pdf(folder / "b" / "deck.pdf", "synthetic deck two")
    with pytest.raises(ValueError, match="more than one file"):
        intake(deal, folder, by="chan", kinds={"deck.pdf": "cim"})
    with pytest.raises(ValueError, match="no such file"):
        intake(deal, folder, by="chan", kinds={"missing.pdf": "cim"})
    result = intake(deal, folder, by="chan", kinds={"a/deck.pdf": "cim"})
    assert {f.stored_path: f.kind for f in result.files} == {"inputs/a/deck.pdf": "cim", "inputs/b/deck.pdf": "other"}
    assert not list((settings().deals_dir / deal / "inputs").glob("*-v2*"))


def test_hidden_folders_and_links_are_skipped(deal, tmp_path):
    import os

    from bizwave_preloi.ops.intake import intake

    folder = tmp_path / "in"
    _pdf(folder / "Project CIM.pdf", "Confidential information memorandum, synthetic")
    _pdf(folder / ".sync" / "cache.pdf", "a sync client's hidden copy")
    outside = tmp_path / "outside.pdf"
    _pdf(outside, "a file outside the folder")
    try:
        os.symlink(outside, folder / "link.pdf")
    except (OSError, NotImplementedError):
        pass                                          # Windows without Developer Mode: no link to test
    result = intake(deal, folder, by="chan")
    assert [f.stored_path for f in result.files] == ["inputs/Project CIM.pdf"]


# --------------------------------------------------------------------------- P3 review round 1

@pytest.fixture
def fake_repo(tmp_path, monkeypatch):
    """A stand-in repository, so a broken refusal could never copy into the real one."""
    from bizwave_preloi import config
    repo_dir = tmp_path / "work" / "fake-repo"
    repo_dir.mkdir(parents=True)
    (repo_dir / "pyproject.toml").write_text("[project]\nname = 'fake'\n")
    monkeypatch.setattr(config, "REPO_ROOT", repo_dir)
    return repo_dir


def _nothing_taken_in(deal):
    from bizwave_preloi.db.models import Document
    from bizwave_preloi.db.session import session_scope
    import sqlalchemy as sa
    with session_scope() as s:
        assert s.scalar(sa.select(sa.func.count()).select_from(Document)) == 0
    assert not (settings().deals_dir / deal / "inputs").exists()


def test_a_source_containing_a_protected_folder_is_refused(deal, tmp_path, monkeypatch, fake_repo):
    """A folder that CONTAINS the data folder, the backup folder, the database, the run log or the repository
    is refused before anything is copied (should-fix 1: it copied the live database and another deal's CIM)."""
    from bizwave_preloi.ops.intake import intake

    _pdf(settings().deals_dir / "other-deal" / "inputs" / "Other Seller CIM.pdf", "another client's CIM")
    with pytest.raises(ValueError, match="contains the data folder"):
        intake(deal, tmp_path, by="chan")                       # tmp_path holds data/
    cases = {"BIZWAVE_BACKUP_DIR": ("backups-home", "backups-home/backups", "the backup folder"),
             "BIZWAVE_DATABASE_URL": ("db-home", "db-home/live.db", "the database"),
             "BIZWAVE_RUNLOG": ("log-home", "log-home/runlog.jsonl", "the run log")}
    for variable, (home, target, label) in cases.items():
        source = tmp_path / home
        _pdf(source / "cim.pdf", "a synthetic CIM")
        value = str(tmp_path / target)
        monkeypatch.setenv(variable, "sqlite:///" + (tmp_path / target).as_posix() if variable.endswith("URL")
                           else value)
        with pytest.raises(ValueError, match=f"contains {label}"):
            intake(deal, source, by="chan")
        monkeypatch.delenv(variable)
    _pdf(tmp_path / "work" / "cim.pdf", "a synthetic CIM")
    with pytest.raises(ValueError, match="contains the repository"):
        intake(deal, tmp_path / "work", by="chan")
    _nothing_taken_in(deal)


def test_a_source_inside_the_backup_folder_is_refused(deal, tmp_path, monkeypatch):
    from bizwave_preloi.ops.intake import intake

    monkeypatch.setenv("BIZWAVE_BACKUP_DIR", str(tmp_path / "backups"))
    _pdf(tmp_path / "backups" / "deals" / "other-deal" / "inputs" / "cim.pdf", "a backed-up CIM")
    with pytest.raises(ValueError, match="inside the backup folder"):
        intake(deal, tmp_path / "backups" / "deals", by="chan")
    _nothing_taken_in(deal)


def test_a_recorded_name_is_never_reused(deal, tmp_path):
    """A name the deal's records use stays taken even if its file went missing (should-fix 3)."""
    from bizwave_preloi.db.models import Document
    from bizwave_preloi.db.session import session_scope
    from bizwave_preloi.ops.intake import intake
    import sqlalchemy as sa

    folder = tmp_path / "in"
    _pdf(folder / "cim.pdf", "Confidential information memorandum, first version")
    intake(deal, folder, by="chan")
    stored = settings().deals_dir / deal / "inputs"
    with session_scope() as s:
        first_sha = s.scalar(sa.select(Document.sha256).where(Document.stored_path == "inputs/cim.pdf"))
    (stored / "cim.pdf").unlink()                                 # lost from disk; still recorded
    _pdf(folder / "cim.pdf", "Confidential information memorandum, a different file")
    result = intake(deal, folder, by="chan")
    assert [(f.stored_path, f.action) for f in result.files] == [("inputs/cim-v2.pdf", "copied_as_new_version")]
    assert not (stored / "cim.pdf").exists()                      # the recorded name was not written again
    with session_scope() as s:
        rows = dict(s.execute(sa.select(Document.stored_path, Document.sha256)).all())
    assert rows["inputs/cim.pdf"] == first_sha and len(rows) == 2


def test_a_failed_copy_leaves_no_file_under_a_real_name(deal, tmp_path, monkeypatch):
    """A copy that fails part-way leaves nothing behind, and the next run uses the buyer's own name
    (should-fix 6: a truncated file once took the name and pushed the real one to -v2)."""
    from bizwave_preloi.ops import files as filestore
    from bizwave_preloi.ops.intake import intake

    folder = tmp_path / "in"
    _pdf(folder / "Project CIM.pdf", "Confidential information memorandum, synthetic")

    real_fsync = filestore.os.fsync

    def disk_full(fd):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(filestore.os, "fsync", disk_full)
    result = intake(deal, folder, by="chan")
    assert [(f.action, f.stored_path) for f in result.files] == [("failed", None)]
    assert "No space left" in result.files[0].problem and result.status_after == "awaiting_documents"
    inputs = settings().deals_dir / deal / "inputs"
    assert [p.name for p in inputs.iterdir()] == []               # no partial file, not even a hidden one
    monkeypatch.setattr(filestore.os, "fsync", real_fsync)       # not undo(): that would undo conftest too
    again = intake(deal, folder, by="chan")
    assert [(f.action, f.stored_path) for f in again.files] == [("copied", "inputs/Project CIM.pdf")]


def test_a_leftover_temporary_file_is_ignored(deal, tmp_path):
    from bizwave_preloi.ops.intake import intake

    folder = tmp_path / "in"
    _pdf(folder / "Project CIM.pdf", "Confidential information memorandum, synthetic")
    inputs = settings().deals_dir / deal / "inputs"
    inputs.mkdir(parents=True)
    leftover = inputs / ".Project CIM.pdf.0123abcd.partial"       # a killed run's half copy
    leftover.write_bytes((folder / "Project CIM.pdf").read_bytes()[:500])
    result = intake(deal, folder, by="chan")
    assert [(f.action, f.stored_path) for f in result.files] == [("copied", "inputs/Project CIM.pdf")]


def test_one_unreadable_file_does_not_stop_the_others(deal, tmp_path, monkeypatch):
    """A file that cannot be read (e.g. a cloud-only OneDrive file) is that file's problem; the others are
    copied and recorded and the clock still starts (should-fix 7)."""
    from bizwave_preloi.ops import files as filestore
    from bizwave_preloi.ops.intake import intake

    folder = tmp_path / "in"
    _pdf(folder / "Project CIM.pdf", "Confidential information memorandum, synthetic")
    _pdf(folder / "cloud only.pdf", "not downloaded")
    real = filestore.sha256

    def unreadable(path):
        if path.name == "cloud only.pdf":
            raise OSError(22, "The cloud operation was unsuccessful")
        return real(path)
    monkeypatch.setattr(filestore, "sha256", unreadable)
    result = intake(deal, folder, by="chan")
    by_name = {f.source.name: f for f in result.files}
    assert by_name["cloud only.pdf"].action == "failed" and "cloud operation" in by_name["cloud only.pdf"].problem
    assert by_name["Project CIM.pdf"].action == "copied" and by_name["Project CIM.pdf"].pages == 1
    assert result.status_after == "ready"


def test_a_damaged_cim_alone_does_not_start_the_clock(deal, tmp_path):
    """Only a CIM with readable pages starts the clock (Q3; should-fix 10)."""
    from bizwave_preloi.ops.intake import intake

    folder = tmp_path / "in"
    folder.mkdir()
    (folder / "Project CIM.pdf").write_bytes(b"%PDF-1.4 damaged\n")
    result = intake(deal, folder, by="chan")
    assert [(f.kind, f.pages) for f in result.files] == [("cim", None)]
    assert result.status_after == "awaiting_documents"
    assert "no readable PDF pages" in result.message and "Project CIM.pdf" in result.message
    _pdf(folder / "Project CIM readable.pdf", "Confidential information memorandum, a readable copy")
    assert intake(deal, folder, by="chan").status_after == "ready"


def test_office_lock_files_are_skipped(deal, tmp_path):
    from bizwave_preloi.ops.intake import intake

    folder = tmp_path / "in"
    _pdf(folder / "Project CIM.pdf", "Confidential information memorandum, synthetic")
    (folder / "~$notes.xlsx").write_bytes(b"owner lock file")
    assert [f.source.name for f in intake(deal, folder, by="chan").files] == ["Project CIM.pdf"]
