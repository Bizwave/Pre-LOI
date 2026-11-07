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
    assert r.exit_code == 1 and "NAME=KIND" in r.output


def test_no_arguments_shows_help():
    r = _bw()
    assert "intake" in r.output and "backup" in r.output
