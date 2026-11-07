"""bw: the operator's command line (P3).

    bw new-deal --customer EMAIL --name NAME --tier flash [--code ID] [--pilot]
    bw paid DEAL
    bw intake DEAL --from FOLDER [--kind "NAME=KIND" ...]
    bw status [--all]
    bw backup [--to FOLDER]

Installed as the `bw` command by `pip install -e .`; also `python -m bizwave_preloi.cli`. Exit codes:
0 done, 1 refused (the message says why) or a file had a problem, 2 a usage error. In a Claude Code session,
run it only with BIZWAVE_DATA_DIR pointing at a scratch folder (live deals stay out of it, M5).
"""
from __future__ import annotations

import getpass
import warnings
from pathlib import Path
from typing import Dict, List, NoReturn, Optional

import sqlalchemy as sa
import typer

app = typer.Typer(help="BizWave Flash Review: the operator's commands.", no_args_is_help=True,
                  add_completion=False, pretty_exceptions_show_locals=False)   # locals can hold client data


def _fail(message: str) -> NoReturn:
    typer.echo(message, err=True)
    raise typer.Exit(1)


def _who(by: Optional[str]) -> str:
    try:
        return by or getpass.getuser() or "operator"
    except Exception:                                   # no user name available (rare on Windows services)
        return by or "operator"


def _require_database() -> None:
    """The data folder's database must exist and be at the newest revision. Call it inside the command's
    `try`, so a refused location (ValueError) is one line, not a traceback."""
    from .db import migrate
    try:
        current = migrate.current_revision()
    except FileNotFoundError:
        current = None
    if current != migrate.head_revision():
        _fail("The database is not ready (missing or not up to date). Run: python -m bizwave_preloi.db upgrade")


@app.command("new-deal")
def new_deal(
    customer: str = typer.Option(..., "--customer", help="the buyer's e-mail address"),
    name: str = typer.Option(..., "--name", help="the buyer's name"),
    firm: Optional[str] = typer.Option(None, "--firm", help="the buyer's firm, if any"),
    tier: str = typer.Option("flash", "--tier", help="instant, flash or flash_qoe"),
    code: Optional[str] = typer.Option(None, "--code", help="choose the deal's code name (default: generated)"),
    pilot: bool = typer.Option(False, "--pilot", help="no payment needed (pilot or invoiced): wait for documents"),
    by: Optional[str] = typer.Option(None, "--by", help="who is doing this (default: your user name)"),
) -> None:
    """Open a deal for a buyer (the customer is created if new) and print its code name."""
    from .db import repo
    from .db.session import session_scope

    who = _who(by)
    try:
        _require_database()
        with session_scope() as s:
            buyer = repo.get_or_create_customer(s, name=name, email=customer, firm=firm)
            s.flush()
            deal_id = code if code is not None else repo.suggest_deal_id(s)
            repo.create_deal(s, deal_id=deal_id, customer_id=buyer.id, tier=tier, by=who)
            next_status = "awaiting_documents" if pilot else "awaiting_payment"
            repo.transition(s, deal_id, next_status, by=who, detail="pilot: no payment" if pilot else None)
            email = buyer.email
    except (ValueError, OSError) as exc:
        _fail(str(exc))
    typer.echo(f"Deal opened for {email}: {next_status.replace('_', ' ')}.")
    typer.echo(deal_id)


@app.command()
def paid(
    deal: str = typer.Argument(..., help="the deal's code name"),
    by: Optional[str] = typer.Option(None, "--by", help="who is doing this (default: your user name)"),
) -> None:
    """Record a payment by hand (until Stripe, P15): the deal then waits for documents, or starts its clock."""
    from .db import repo
    from .db.session import session_scope
    from .ops.intake import start_clock_if_complete

    who = _who(by)
    try:
        _require_database()
        with session_scope() as s:
            repo.transition(s, deal, "awaiting_documents", by=who, detail="payment recorded by hand (bw paid)")
            _, message = start_clock_if_complete(s, deal, by=who)
    except (ValueError, OSError) as exc:
        _fail(str(exc))
    typer.echo(f"Payment recorded for {deal}. {message}")


def _parse_kinds(items: List[str]) -> Dict[str, str]:
    kinds = {}
    for item in items:
        name, sep, kind = item.rpartition("=")
        if not sep or not name or not kind:            # a usage error: exit 2, like any malformed option
            raise typer.BadParameter(f'{item!r}: write it as "NAME=KIND", e.g. "deck.pdf=cim"',
                                     param_hint="--kind")
        kinds[name] = kind
    return kinds


@app.command()
def intake(
    deal: str = typer.Argument(..., help="the deal's code name"),
    source: Path = typer.Option(..., "--from", help="the folder the buyer's files were delivered to"),
    kind: List[str] = typer.Option([], "--kind", help='set or correct a file\'s kind: "NAME=KIND" (repeatable)'),
    by: Optional[str] = typer.Option(None, "--by", help="who is doing this (default: your user name)"),
) -> None:
    """Copy the buyer's files into the deal folder (never overwriting), hash, classify, inventory and record
    them; start the SLA clock when the package is complete."""
    from .ops.intake import intake as run_intake

    kinds = _parse_kinds(kind)
    try:
        _require_database()
        result = run_intake(deal, source, by=_who(by), kinds=kinds)
    except (ValueError, OSError) as exc:
        _fail(str(exc))
    for f in result.files:
        pages = "-" if f.pages is None else str(f.pages)
        where = f.stored_path if f.stored_path is not None else f"(not stored) {f.source}"
        line = f"{f.action.replace('_', ' '):<24} {f.kind:<14} {pages:>5} pages  {where}"
        typer.echo(line + (f"\n    PROBLEM: {f.problem}" if f.problem else ""))
    if not result.files:
        typer.echo("No files found in the folder.")
    typer.echo(result.message)
    if any(f.problem for f in result.files):
        raise typer.Exit(1)


@app.command()
def status(all_deals: bool = typer.Option(False, "--all", help="include delivered and cancelled deals")) -> None:
    """Open deals: status, buyer and time since the package was complete (time left on the SLA: P15)."""
    from .db import repo
    from .db.models import Customer, Deal
    from .db.session import session_scope
    from .db.types import utcnow

    try:
        _require_database()
    except (ValueError, OSError) as exc:
        _fail(str(exc))
    now = utcnow()
    with session_scope() as s:
        deals = (list(s.scalars(sa.select(Deal).order_by(Deal.created_at.desc(), Deal.id)))
                 if all_deals else repo.open_deals(s))
        rows = []
        for d in deals:
            hours = repo.hours_since_package_complete(d, now)
            rows.append((d.id, d.tier, d.status, s.get(Customer, d.customer_id).email,
                         "-" if d.package_complete_at is None else f"{d.package_complete_at:%Y-%m-%d %H:%M}",
                         "-" if hours is None else f"{hours:.1f} h"))
    if not rows:
        typer.echo("No open deals." if not all_deals else "No deals.")
        return
    header = ("deal", "tier", "status", "buyer", "package complete (UTC)", "since")
    widths = [max(len(str(r[i])) for r in rows + [header]) for i in range(len(header))]
    for row in [header] + rows:
        typer.echo("  ".join(str(cell).ljust(w) for cell, w in zip(row, widths)).rstrip())


@app.command()
def backup(to: Optional[Path] = typer.Option(None, "--to", help="backup folder (default: BIZWAVE_BACKUP_DIR)")) -> None:
    """Snapshot the database and copy new or changed deal files into the backup folder (nothing is deleted)."""
    from .config import database_file, settings
    from .ops.backup import backup as run_backup

    live = database_file(settings().database_url)
    if live is not None and not live.exists():
        _fail("There is no database to back up yet. Run: python -m bizwave_preloi.db upgrade")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            result = run_backup(to)
        except (ValueError, OSError) as exc:
            _fail(str(exc))
    for w in caught:
        typer.echo(f"Warning: {w.message}", err=True)
    typer.echo(f"Database snapshot: {result.database}")
    typer.echo(f"Deal files: {result.deal_files_copied} copied, {result.deal_files_unchanged} unchanged, "
               f"in {result.folder / 'deals'}")
    if result.deal_files_changed:
        typer.echo(f"Warning: {len(result.deal_files_changed)} deal file(s) differ from their last backup copy. "
                   f"Deal files are not meant to change; both copies are kept. Check:", err=True)
        for path in result.deal_files_changed:
            typer.echo(f"    {path}", err=True)
    for problem in result.problems:
        typer.echo(f"PROBLEM: not backed up: {problem}", err=True)
    if result.problems:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
