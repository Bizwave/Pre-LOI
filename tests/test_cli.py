"""cli.py (P3): the refusals and messages around the commands. Synthetic data only."""
from typer.testing import CliRunner


def _bw(*args):
    from bizwave_preloi.cli import app
    return CliRunner().invoke(app, [str(a) for a in args])


def test_commands_refuse_a_database_that_is_not_set_up():
    for args in (["status"], ["paid", "acme-hvac"],
                 ["new-deal", "--customer", "pat@example.com", "--name", "Pat Buyer"]):
        r = _bw(*args)
        assert r.exit_code == 1 and "python -m bizwave_preloi.db upgrade" in r.output, args
    r = _bw("backup")
    assert r.exit_code == 1 and "no database to back up" in r.output


def test_status_with_no_deals_and_a_bad_kind_argument(tmp_path):
    from bizwave_preloi.db.migrate import upgrade

    upgrade()
    assert "No open deals." in _bw("status").output
    folder = tmp_path / "in"
    folder.mkdir()
    r = _bw("intake", "acme-hvac", "--from", folder, "--kind", "deck.pdf")
    assert r.exit_code == 2 and "NAME=KIND" in r.output          # a usage error (P3 review round 1, nit 19)


def test_no_arguments_shows_help():
    r = _bw()
    assert "intake" in r.output and "backup" in r.output


# --------------------------------------------------------------------------- P3 review round 1

def _pdf(path, text):
    import pytest
    pytest.importorskip("reportlab")
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=letter)
    c.drawString(72, 720, text)
    c.showPage()
    c.save()


def _status(code):
    from bizwave_preloi.db.models import Deal
    from bizwave_preloi.db.session import session_scope
    with session_scope() as s:
        deal = s.get(Deal, code)
        return deal.status, deal.package_complete_at


def test_paid_after_intake_starts_the_clock(tmp_path):
    """Files in before payment: `bw paid` then starts the clock (Q3; should-fix 10)."""
    from bizwave_preloi.db.migrate import upgrade

    upgrade()
    assert _bw("new-deal", "--customer", "pat@example.com", "--name", "Pat Buyer", "--code", "acme-hvac").exit_code == 0
    folder = tmp_path / "in"
    _pdf(folder / "Project CIM.pdf", "Confidential information memorandum, synthetic")
    r = _bw("intake", "acme-hvac", "--from", folder)
    assert r.exit_code == 0 and "bw paid acme-hvac" in r.output
    assert _status("acme-hvac") == ("awaiting_payment", None)
    r = _bw("paid", "acme-hvac")
    assert r.exit_code == 0 and "clock started" in r.output
    status, started = _status("acme-hvac")
    assert status == "ready" and started is not None


def test_paid_with_no_files_says_what_comes_next(tmp_path):
    from bizwave_preloi.db.migrate import upgrade

    upgrade()
    _bw("new-deal", "--customer", "pat@example.com", "--name", "Pat Buyer", "--code", "acme-hvac")
    r = _bw("paid", "acme-hvac")
    assert r.exit_code == 0 and "No files are recorded" in r.output and "bw intake acme-hvac" in r.output
    assert "--kind" not in r.output                                  # nit 24: no files to correct yet


def test_refusals_name_the_rule():
    """A refused code or name says which rule it broke (nits 21 and 23)."""
    from bizwave_preloi.db.migrate import upgrade

    upgrade()
    base = ["new-deal", "--customer", "pat@example.com"]
    cases = [(["--name", "Pat Buyer", "--code", "con"], "reserved name on Windows"),
             (["--name", "Pat Buyer", "--code", "Acme"], "lower-case letters"),
             (["--name", ""], "needs a name"), (["--name", "   "], "needs a name")]
    for extra, rule in cases:
        r = _bw(*base, *extra)
        assert r.exit_code == 1 and rule in r.output and "Traceback" not in r.output, extra
    assert "No open deals." in _bw("status", "--all").output.replace("No deals.", "No open deals.")


def test_a_refused_data_folder_is_one_line_not_a_traceback(tmp_path, monkeypatch):
    """The database check runs inside each command's error handling (nit 13)."""
    from bizwave_preloi import config

    repo_dir = tmp_path / "fake-repo"
    repo_dir.mkdir()
    (repo_dir / "pyproject.toml").write_text("[project]\nname = 'fake'\n")
    monkeypatch.setattr(config, "REPO_ROOT", repo_dir)
    monkeypatch.setenv("BIZWAVE_DATABASE_URL", "sqlite:///" + (tmp_path / "elsewhere.db").as_posix())
    from bizwave_preloi.db.migrate import upgrade
    from bizwave_preloi.db.session import dispose_engines
    upgrade()                                               # a ready database outside the repository...
    dispose_engines()
    monkeypatch.setenv("BIZWAVE_DATA_DIR", str(repo_dir / "data"))      # ...but the data folder inside it
    folder = tmp_path / "in"
    folder.mkdir()
    for args in (["status"], ["intake", "acme-hvac", "--from", folder], ["paid", "acme-hvac"],
                 ["new-deal", "--customer", "pat@example.com", "--name", "Pat Buyer"]):
        r = _bw(*args)
        assert r.exit_code == 1 and "inside the repository" in r.output, args
        assert r.exception is None or isinstance(r.exception, SystemExit), args
    assert not (repo_dir / "data").exists()


def test_a_file_system_error_is_one_line(tmp_path, monkeypatch):
    """An OSError outside any one file (a folder that cannot be listed) ends the command with one line
    (should-fix 7)."""
    from bizwave_preloi.db.migrate import upgrade
    from bizwave_preloi.ops import intake as intake_module

    upgrade()
    _bw("new-deal", "--customer", "pat@example.com", "--name", "Pat Buyer", "--code", "acme-hvac", "--pilot")
    folder = tmp_path / "in"
    folder.mkdir()

    def denied(source):
        raise PermissionError(13, "Permission denied", str(source))
    monkeypatch.setattr(intake_module, "_source_files", denied)
    r = _bw("intake", "acme-hvac", "--from", folder)
    assert r.exit_code == 1 and "Permission denied" in r.output
    assert isinstance(r.exception, SystemExit)


def test_an_unreadable_file_is_reported_and_the_rest_taken_in(tmp_path, monkeypatch):
    from bizwave_preloi.db.migrate import upgrade
    from bizwave_preloi.ops import files as filestore

    upgrade()
    _bw("new-deal", "--customer", "pat@example.com", "--name", "Pat Buyer", "--code", "acme-hvac", "--pilot")
    folder = tmp_path / "in"
    _pdf(folder / "Project CIM.pdf", "Confidential information memorandum, synthetic")
    _pdf(folder / "cloud only.pdf", "not downloaded")
    real = filestore.sha256

    def unreadable(path):
        if path.name == "cloud only.pdf":
            raise OSError(22, "The cloud operation was unsuccessful")
        return real(path)
    monkeypatch.setattr(filestore, "sha256", unreadable)
    r = _bw("intake", "acme-hvac", "--from", folder)
    assert r.exit_code == 1 and isinstance(r.exception, SystemExit)
    assert "(not stored)" in r.output and "cloud operation" in r.output and "clock started" in r.output


def test_backup_reports_changed_files(tmp_path):
    from bizwave_preloi.config import settings
    from bizwave_preloi.db.migrate import upgrade

    upgrade()
    outputs = settings().deals_dir / "acme-hvac" / "outputs"
    outputs.mkdir(parents=True)
    (outputs / "memo.pdf").write_bytes(b"version 1")
    assert _bw("backup", "--to", tmp_path / "b").exit_code == 0
    (outputs / "memo.pdf").write_bytes(b"version 2")
    r = _bw("backup", "--to", tmp_path / "b")
    assert r.exit_code == 0 and "differ from their last backup copy" in r.output
    assert "acme-hvac/outputs/memo.pdf" in r.output
    r = _bw("backup", "--to", tmp_path / "b" / "deals" / "acme-hvac" / "outputs" / "memo.pdf")
    assert r.exit_code == 1 and "is a file" in r.output and isinstance(r.exception, SystemExit)


def test_no_unclosed_database_warning_at_exit(tmp_path):
    """Pooled SQLite connections are closed before Python exits (P3 review round 3, nit 6): `bw backup`
    into the default folder printed "ResourceWarning: unclosed database" after finishing."""
    import os
    import subprocess
    import sys

    from bizwave_preloi.config import REPO_ROOT, settings
    from bizwave_preloi.db.migrate import upgrade

    upgrade()
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src"), "BIZWAVE_DATA_DIR": str(settings().data_dir),
           "BIZWAVE_LOAD_DOTENV": "0"}
    for args in (["backup"], ["status"]):
        run = subprocess.run([sys.executable, "-X", "dev", "-m", "bizwave_preloi.cli", *args], env=env,
                             capture_output=True, text=True, timeout=120)
        assert run.returncode == 0, run.stderr
        assert "ResourceWarning" not in run.stderr, (args, run.stderr)
