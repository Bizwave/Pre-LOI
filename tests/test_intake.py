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
    leftover = inputs / ".bw-0123abcd.partial"                    # a killed run's half copy
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


# --------------------------------------------------------------------------- P3 review round 2

def _documents(deal):
    from bizwave_preloi.db.models import Document
    from bizwave_preloi.db.session import session_scope
    import sqlalchemy as sa
    with session_scope() as s:
        return {d.stored_path: (d.sha256, d.page_count) for d in
                s.scalars(sa.select(Document).where(Document.deal_id == deal))}


def test_a_missing_recorded_copy_is_restored_and_the_run_goes_on(deal, tmp_path):
    """A recorded file deleted from the deal folder no longer stops intake: the buyer's identical file puts
    it back (the bytes equal the record) and new files are recorded (P3 review round 2, should-fix 1)."""
    from bizwave_preloi.ops import files as filestore
    from bizwave_preloi.ops.intake import intake

    folder = tmp_path / "in"
    _pdf(folder / "Project CIM.pdf", "Confidential information memorandum, synthetic")
    intake(deal, folder, by="chan")
    before = _documents(deal)
    stored = settings().deals_dir / deal / "inputs" / "Project CIM.pdf"
    stored.unlink()
    _pdf(folder / "Profit and Loss 2024.pdf", "Synthetic P&L")
    result = intake(deal, folder, by="chan")
    actions = {f.source.name: (f.action, f.problem) for f in result.files}
    assert actions == {"Project CIM.pdf": ("restored", None), "Profit and Loss 2024.pdf": ("copied", None)}
    assert filestore.sha256(stored) == before["inputs/Project CIM.pdf"][0]
    after = _documents(deal)
    assert after["inputs/Project CIM.pdf"] == before["inputs/Project CIM.pdf"] and len(after) == 2


def test_a_changed_recorded_copy_is_reported_and_left_alone(deal, tmp_path):
    """A recorded copy that no longer matches its record is possible damage: it is not touched, the file is
    reported (exit 1 at the command line) and the other files are still recorded (should-fix 1)."""
    from bizwave_preloi.ops.intake import intake

    folder = tmp_path / "in"
    _pdf(folder / "Project CIM.pdf", "Confidential information memorandum, synthetic")
    intake(deal, folder, by="chan")
    stored = settings().deals_dir / deal / "inputs" / "Project CIM.pdf"
    stored.write_bytes(b"damaged")
    _pdf(folder / "Profit and Loss 2024.pdf", "Synthetic P&L")
    result = intake(deal, folder, by="chan")
    by_name = {f.source.name: f for f in result.files}
    cim = by_name["Project CIM.pdf"]
    assert (cim.action, cim.stored_path, cim.pages) == ("already_recorded", "inputs/Project CIM.pdf", 1)
    assert "no longer matches its record" in cim.problem and "Save the new file" not in cim.problem
    assert stored.read_bytes() == b"damaged"                      # never overwritten
    assert by_name["Profit and Loss 2024.pdf"].action == "copied"
    assert len(_documents(deal)) == 2
    assert not list(stored.parent.glob("Project CIM-v*"))         # no second copy of known content


def test_a_refused_record_is_that_files_problem(deal, tmp_path, monkeypatch):
    """A ValueError from the repository for one file does not roll back the others (should-fix 1)."""
    from bizwave_preloi.db import repo
    from bizwave_preloi.ops.intake import intake

    folder = tmp_path / "in"
    _pdf(folder / "Project CIM.pdf", "Confidential information memorandum, synthetic")
    _pdf(folder / "odd.pdf", "a file the repository refuses (simulated)")
    real = repo.add_document

    def refuse_odd(s, deal_id, path, **kw):
        if path.name == "odd.pdf":
            raise ValueError("simulated refusal")
        return real(s, deal_id, path, **kw)
    monkeypatch.setattr(repo, "add_document", refuse_odd)
    result = intake(deal, folder, by="chan")
    by_name = {f.source.name: f for f in result.files}
    assert by_name["odd.pdf"].action == "failed" and "simulated refusal" in by_name["odd.pdf"].problem
    assert by_name["Project CIM.pdf"].action == "copied" and result.status_after == "ready"
    assert list(_documents(deal)) == ["inputs/Project CIM.pdf"]


def test_recorded_names_are_compared_as_the_disk_compares_them(deal, tmp_path, monkeypatch):
    """On Windows and macOS "CIM.pdf" and "cim.pdf" are one name: a recorded name stays taken in any case
    (P3 review round 2, nit 3; a case-insensitive disk is simulated through the key function)."""
    from bizwave_preloi.ops import intake as intake_module

    monkeypatch.setattr(intake_module, "_name_key", str.casefold)
    folder = tmp_path / "in"
    _pdf(folder / "CIM.pdf", "Confidential information memorandum, first")
    intake_module.intake(deal, folder, by="chan")
    (settings().deals_dir / deal / "inputs" / "CIM.pdf").unlink()           # lost from disk, still recorded
    (folder / "CIM.pdf").unlink()
    _pdf(folder / "cim.pdf", "Confidential information memorandum, a different file")
    result = intake_module.intake(deal, folder, by="chan")
    assert [(f.stored_path, f.action) for f in result.files] == [("inputs/cim-v2.pdf", "copied_as_new_version")]


# --------------------------------------------------------------------------- P3 review round 3

def _two_identical_cims_and_a_pnl(tmp_path):
    folder = tmp_path / "in"
    _pdf(folder / "a CIM.pdf", "Confidential information memorandum, synthetic")
    (folder / "b CIM.pdf").write_bytes((folder / "a CIM.pdf").read_bytes())
    _pdf(folder / "notes P&L.pdf", "Synthetic P&L")
    return folder


def test_identical_files_when_the_first_record_keeps_failing(deal, tmp_path, monkeypatch):
    """Two identical files and the first one's record is refused: both are that content's problem, the
    other files are still recorded, and nothing crashes (P3 review round 3, should-fix 1)."""
    from bizwave_preloi.db import repo
    from bizwave_preloi.ops.intake import intake

    folder = _two_identical_cims_and_a_pnl(tmp_path)
    real = repo.add_document

    def refuse(s, deal_id, path, **kw):
        if path.name == "a CIM.pdf":
            raise ValueError("simulated refusal")
        return real(s, deal_id, path, **kw)
    monkeypatch.setattr(repo, "add_document", refuse)
    result = intake(deal, folder, by="chan")
    by_name = {f.source.name: (f.action, f.stored_path) for f in result.files}
    assert by_name == {"a CIM.pdf": ("failed", None), "b CIM.pdf": ("failed", None),
                       "notes P&L.pdf": ("copied", "inputs/notes P&L.pdf")}
    assert list(_documents(deal)) == ["inputs/notes P&L.pdf"] and result.status_after == "awaiting_documents"


def test_identical_files_when_the_first_record_fails_once(deal, tmp_path, monkeypatch):
    """A one-off read error on the first copy: the identical second file records that copy instead."""
    from bizwave_preloi.db import repo
    from bizwave_preloi.ops.intake import intake

    folder = _two_identical_cims_and_a_pnl(tmp_path)
    real = repo.add_document
    calls = []

    def fail_once(s, deal_id, path, **kw):
        calls.append(path.name)
        if calls == ["a CIM.pdf"]:
            raise PermissionError(13, "The process cannot access the file", str(path))
        return real(s, deal_id, path, **kw)
    monkeypatch.setattr(repo, "add_document", fail_once)
    result = intake(deal, folder, by="chan")
    by_name = {f.source.name: (f.action, f.stored_path) for f in result.files}
    assert by_name["a CIM.pdf"] == ("failed", None)
    assert by_name["b CIM.pdf"] == ("recorded", "inputs/a CIM.pdf")
    assert sorted(_documents(deal)) == ["inputs/a CIM.pdf", "inputs/notes P&L.pdf"]
    assert result.status_after == "ready"


def test_a_hand_replaced_copy_is_never_read_in_place_of_the_record(deal, tmp_path):
    """Pages are read only from a stored copy that matches its record: a readable PDF put in place of an
    unreadable recorded one is reported, and the clock does not start on it (round 3, nit 2)."""
    from bizwave_preloi.ops.intake import intake

    folder = tmp_path / "in"
    folder.mkdir()
    (folder / "Project CIM.pdf").write_bytes(b"%PDF-1.4 damaged\n")
    intake(deal, folder, by="chan")
    _pdf(settings().deals_dir / deal / "inputs" / "Project CIM.pdf", "a readable PDF put there by hand")
    result = intake(deal, folder, by="chan")
    assert [(f.action, f.pages) for f in result.files] == [("already_recorded", None)]
    assert "no longer matches its record" in result.files[0].problem
    assert result.status_after == "awaiting_documents"
    assert list(_documents(deal).values())[0][1] is None                   # no pages recorded


def _file_changes_while_copied(monkeypatch):
    """copy_to_temporary as if the buyer's file changed while it was being copied."""
    from bizwave_preloi.ops import files as filestore
    real = filestore.copy_to_temporary

    def changed(source, folder):
        temp, _ = real(source, folder)
        return temp, "0" * 64
    monkeypatch.setattr(filestore, "copy_to_temporary", changed)


def test_a_file_changing_while_restored_is_not_placed(deal, tmp_path, monkeypatch):
    from bizwave_preloi.ops.intake import intake

    folder = tmp_path / "in"
    _pdf(folder / "Project CIM.pdf", "Confidential information memorandum, synthetic")
    intake(deal, folder, by="chan")
    inputs = settings().deals_dir / deal / "inputs"
    (inputs / "Project CIM.pdf").unlink()
    _file_changes_while_copied(monkeypatch)
    result = intake(deal, folder, by="chan")
    assert result.files[0].action == "already_recorded"
    assert "could not be restored" in result.files[0].problem and "changed while" in result.files[0].problem
    assert list(inputs.iterdir()) == []                                     # nothing placed, nothing left


def test_a_file_changing_while_copied_is_not_stored(deal, tmp_path, monkeypatch):
    from bizwave_preloi.ops.intake import intake

    folder = tmp_path / "in"
    _pdf(folder / "Project CIM.pdf", "Confidential information memorandum, synthetic")
    _file_changes_while_copied(monkeypatch)
    result = intake(deal, folder, by="chan")
    assert result.files[0].action == "failed" and "changed while" in result.files[0].problem
    assert list((settings().deals_dir / deal / "inputs").iterdir()) == []


def test_a_failed_restore_leaves_no_temporary_file(deal, tmp_path, monkeypatch):
    """round 3, nit 3: the restore removes its temporary copy on every failure."""
    from bizwave_preloi.ops import files as filestore
    from bizwave_preloi.ops.intake import intake

    folder = tmp_path / "in"
    _pdf(folder / "Project CIM.pdf", "Confidential information memorandum, synthetic")
    intake(deal, folder, by="chan")
    inputs = settings().deals_dir / deal / "inputs"
    (inputs / "Project CIM.pdf").unlink()

    def busy(temp, final):
        raise PermissionError(32, "The process cannot access the file because it is being used")
    monkeypatch.setattr(filestore, "place", busy)
    result = intake(deal, folder, by="chan")
    assert "could not be restored" in result.files[0].problem
    assert list(inputs.iterdir()) == []


def test_an_unreadable_recorded_copy_is_reported_as_recorded(deal, tmp_path, monkeypatch):
    """round 3, nit 5: a stored copy that cannot be read is the stored copy's problem; the file stays
    recorded and the message does not blame the buyer's file."""
    from bizwave_preloi.ops import files as filestore
    from bizwave_preloi.ops.intake import intake

    folder = tmp_path / "in"
    _pdf(folder / "Project CIM.pdf", "Confidential information memorandum, synthetic")
    intake(deal, folder, by="chan")
    real = filestore.sha256
    deals = settings().deals_dir

    def locked(path):
        if deals in path.parents:
            raise PermissionError(13, "locked by another program", str(path))
        return real(path)
    monkeypatch.setattr(filestore, "sha256", locked)
    result = intake(deal, folder, by="chan")
    f = result.files[0]
    assert (f.action, f.stored_path) == ("already_recorded", "inputs/Project CIM.pdf")
    assert "recorded copy inputs/Project CIM.pdf could not be read" in f.problem


def test_name_key_follows_the_disk(monkeypatch):
    """round 3, nit 4: the key itself, on Windows (normcase) and macOS (case and Unicode form)."""
    import ntpath
    import unicodedata

    from bizwave_preloi.ops import intake as intake_module

    real_normcase = intake_module.os.path.normcase
    if intake_module.os.name != "nt":
        assert intake_module._name_key("inputs/CIM.pdf") != intake_module._name_key("inputs/cim.pdf")
    monkeypatch.setattr(intake_module.os.path, "normcase", ntpath.normcase)               # as on Windows
    assert intake_module._name_key("inputs/CIM.pdf") == intake_module._name_key("inputs/cim.pdf")
    monkeypatch.setattr(intake_module.os.path, "normcase", real_normcase)   # not undo(): it undoes conftest
    monkeypatch.setattr(intake_module.sys, "platform", "darwin")
    nfd = unicodedata.normalize("NFD", "inputs/Résumé.pdf")
    assert intake_module._name_key(nfd) == intake_module._name_key("inputs/RÉSUMÉ.pdf")
