"""Process rules of the packet loop that are checked mechanically (CLAUDE.md section 6).

Go-ahead check (W1 correction, approved by Chan 2026-11-06 16:52 PT, "d yes", and as built 17:29 PT,
"d - Yes - checks every plan, agreed"): every plan whose work has started records Chan's go-ahead as a `Go-ahead: YYYY-MM-DD HH:MM` line in its `## Reviewer Note`, and that
time is not earlier than the latest `## Revision log` row. Promoted from the first W1 lesson in
`tasks/lessons.md`: a checklist promotion alone did not stop a build before sign-off.
"""
from __future__ import annotations

import re
from datetime import datetime

import pytest

from bizwave_preloi.config import REPO_ROOT

PLANS = REPO_ROOT / "tasks" / "plans"
COMMANDS = REPO_ROOT / ".claude" / "commands"
# Plans written before the go-ahead rule (W1, 2026-11-06), kept as they are. Do not add to this list:
# every later plan is copied from the template and must pass the check.
LEGACY = {"2026-11-06_scaffold.md", "2026-11-06_p1_settings.md"}
# The headings the check reads. A plan without one of them fails rather than being skipped.
REQUIRED = ("Sub-packets", "Revision log", "Reviewer Note", "Gate — first run")
FENCE = re.compile(r"^```.*?^```[ \t]*$", re.M | re.S)
TICK = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\[[xX]\]", re.M)
PLACEHOLDER = re.compile(r"<[^<>]*>")
STAMP = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\b")
GO_AHEAD = re.compile(r"^Go-ahead: (\d{4}-\d{2}-\d{2} \d{2}:\d{2})\b", re.M)


def _section(text: str, heading: str) -> str | None:
    """Body of the '## heading' section, or None when the plan has no such section."""
    m = re.search(rf"^## {re.escape(heading)}[ \t]*$", text, re.M)
    if not m:
        return None
    nxt = re.search(r"^## ", text[m.end():], re.M)
    return text[m.end(): m.end() + nxt.start() if nxt else len(text)]


def _when(stamp: str) -> datetime | None:
    try:
        return datetime.strptime(stamp, "%Y-%m-%d %H:%M")
    except ValueError:
        return None


def _started(text: str) -> bool:
    """Work has started: a ticked box anywhere in the plan, or anything but placeholders in the first run."""
    first_run = PLACEHOLDER.sub("", _section(text, "Gate — first run") or "").strip()
    return bool(TICK.search(text)) or first_run != ""


def go_ahead_problems(text: str) -> list[str]:
    """Why a plan's record does not show a go-ahead after its latest revision.

    Empty when the record is in order, or when no work has started yet (nothing ticked, no first run).
    Fails closed: a missing heading is a problem, never a reason to skip. Fenced code blocks are ignored.
    """
    text = FENCE.sub("", text)
    if re.search(r"^```", text, re.M):
        return ["unclosed code fence"]
    missing = [f"missing ## {h}" for h in REQUIRED if _section(text, h) is None]
    twice = [f"duplicate ## {h}" for h in REQUIRED
             if len(re.findall(rf"^## {re.escape(h)}[ \t]*$", text, re.M)) > 1]
    if missing or twice:
        return missing + twice
    if not _started(text):
        return []
    log = _section(text, "Revision log")
    problems, revisions = [], []
    for line in log.splitlines():
        line = line.strip()
        if not line.startswith("|") or set(line) <= set("|-: "):
            continue
        cell = line.strip("|").split("|")[0].strip()
        if cell.lower() == "date":
            continue
        m = STAMP.match(cell)
        when = _when(m.group(1)) if m else None
        if when is None:
            problems.append(f"Revision log row without a YYYY-MM-DD HH:MM date: {cell!r}")
        else:
            revisions.append(when)
    if not revisions and not problems:
        problems.append("Revision log has no rows")
    stamps = [w for w in map(_when, GO_AHEAD.findall(_section(text, "Reviewer Note") or "")) if w]
    if not stamps:
        problems.append("no 'Go-ahead: YYYY-MM-DD HH:MM' line in ## Reviewer Note")
    elif revisions and max(stamps) < max(revisions):
        problems.append(f"go-ahead {max(stamps):%Y-%m-%d %H:%M} is earlier than the latest revision "
                        f"{max(revisions):%Y-%m-%d %H:%M}")
    return problems


def _plans():
    return sorted(p for p in PLANS.glob("*.md") if p.name != "_TEMPLATE.md" and p.name not in LEGACY)


@pytest.mark.parametrize("plan", _plans(), ids=lambda p: p.name)
def test_started_plan_has_a_go_ahead_after_its_latest_revision(plan):
    assert go_ahead_problems(plan.read_text(encoding="utf-8")) == []


def test_legacy_exemptions_name_real_plans():
    assert all((PLANS / name).exists() for name in LEGACY)


def _plan(sub="- [x] P9.1 step", log_rows=("| 2026-11-06 16:00 | Plan written | yes |",),
          note="Go-ahead: 2026-11-06 16:30 PT (chat: \"go ahead\")", first_run="<placeholder>",
          results=""):
    rows = "\n".join(log_rows)
    return (f"# plan\n\n## Sub-packets\n{sub}\n\n## Revision log\n| Date | What changed | Stopped for Chan |\n"
            f"|---|---|---|\n{rows}\n\n## Reviewer Note\n{note}\n\n## Gate — first run\n{first_run}\n\n"
            f"## Results\n{results}\n")


@pytest.mark.parametrize("text, expected", [
    (_plan(), None),
    (_plan(note="Go-ahead: 2026-11-06 16:00 PT"), None),                       # same minute as the revision
    (_plan(sub="- [ ] P9.1 step", note=""), None),                              # not started: nothing to check
    (_plan(note=""), "no 'Go-ahead"),
    (_plan(note="", results="Go-ahead: 2026-11-06 16:30"), "no 'Go-ahead"),      # only counts in Reviewer Note
    (_plan(note="Chan said `Go-ahead: 2026-11-06 16:30` here"), "no 'Go-ahead"),  # must start the line
    (_plan(log_rows=("| 2026-11-06 16:00 | Plan written | yes |", "| 2026-11-06 16:45 | Revised | yes |")),
     "earlier than the latest revision 2026-11-06 16:45"),
    (_plan(log_rows=("| 6 Nov 16:26 | Plan written | yes |",)), "without a YYYY-MM-DD HH:MM date"),
    (_plan(log_rows=("| 2026-13-06 16:00 | Plan written | yes |",)), "without a YYYY-MM-DD HH:MM date"),
    (_plan(log_rows=()), "Revision log has no rows"),
    (_plan(sub="- [ ] P9.1 step", note="", first_run="2 failed for their own reasons"), "no 'Go-ahead"),
    (_plan(sub="- [ ] P9.1 step", note="", results="- [x] P9.1 done"), "no 'Go-ahead"),  # a tick anywhere
    (_plan(note="Go-ahead: 2026-13-06 16:30"), "no 'Go-ahead"),                  # impossible date
    (_plan(note="Go-ahead: 6 Nov 16:30"), "no 'Go-ahead"),                        # old free-text format
    (_plan(note="```\nGo-ahead: 2026-11-06 16:30\n```"), "no 'Go-ahead"),       # inside a code fence
    (_plan(note="```\n## not a heading\n```\nGo-ahead: 2026-11-06 16:30"), None),  # fence does not end it
    (_plan(sub="* [x] P9.1 step", note=""), "no 'Go-ahead"),                    # other list markers count
    (_plan(sub="1. [x] P9.1 step", note=""), "no 'Go-ahead"),
    (_plan(sub="-  [X] P9.1 step", note=""), "no 'Go-ahead"),
    (_plan(sub="- [ ] P9.1 step", note="", first_run="<placeholder>\n3 failed"), "no 'Go-ahead"),
    (_plan(sub="- [ ] P9.1 step", note="", first_run="<two-line\nplaceholder>"), None),
    (_plan(note="```\nGo-ahead: 2026-11-06 16:30"), "unclosed code fence"),
    (_plan() + "\n## Revision log\n| 2026-11-06 18:00 | Later | yes |\n", "duplicate ## Revision log"),
    (_plan().replace("## Sub-packets", "## Tasks"), "missing ## Sub-packets"),
    (_plan(sub="- [ ] P9.1 step", note="").replace("## Gate — first run", "## Gate - first run"),
     "missing ## Gate — first run"),
])
def test_go_ahead_check_on_synthetic_plans(text, expected):
    problems = go_ahead_problems(text)
    if expected is None:
        assert problems == []
    else:
        assert any(expected in p for p in problems), problems


def test_go_ahead_check_needs_every_heading_it_reads():
    for heading in REQUIRED:
        text = _plan(sub="- [ ] P9.1 step", note="").replace(f"## {heading}", "## Something else")
        assert go_ahead_problems(text) == [f"missing ## {heading}"]


def test_template_carries_the_formats_and_is_not_started():
    text = (PLANS / "_TEMPLATE.md").read_text(encoding="utf-8")
    assert "YYYY-MM-DD HH:MM" in _section(text, "Revision log")
    assert re.search(r"^Go-ahead: YYYY-MM-DD HH:MM", _section(text, "Reviewer Note"), re.M)
    assert go_ahead_problems(text) == []


def test_execute_requires_the_go_ahead_line():
    text = (COMMANDS / "execute.md").read_text(encoding="utf-8")
    assert "Go-ahead: YYYY-MM-DD HH:MM" in text
    assert "Revision log" in text
    assert "tests/test_workflow.py" in text
