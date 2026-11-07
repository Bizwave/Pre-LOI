"""W1 gate — self-improvement loop (tasks/plans/2026-11-06_w1_lessons_loop.md).

Workflow files are product here: if a command or the reviewer loses a rule, the loop silently stops
improving. Written before the changes; never edited to make it pass (CLAUDE.md section 6).
"""
from __future__ import annotations

import re

import pytest
import yaml

from bizwave_preloi.config import REPO_ROOT

CLAUDE = REPO_ROOT / ".claude"
COMMANDS = CLAUDE / "commands"
AGENTS = CLAUDE / "agents"
EXPECTED_COMMANDS = {"sprint-status", "research", "plan-packet", "execute", "verify-packet",
                     "review-packet", "close-packet", "lessons", "improve"}
STATUS = re.compile(r"^- \[(note|retired|promoted → [^\]]+)\] ")


def _frontmatter(path):
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), path.name
    return yaml.safe_load(text.split("---\n")[1]), text


def _section(text: str, heading: str) -> str:
    """Text from a '## heading' line to the next '## ' heading."""
    start = text.index(heading)
    nxt = text.find("\n## ", start + len(heading))
    return text[start: nxt if nxt != -1 else len(text)]


def _claude_md() -> str:
    return (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")


def test_every_command_has_frontmatter_and_improve_exists():
    found = {p.stem for p in COMMANDS.glob("*.md")}
    # Spec amendment (Chan 2026-11-06 16:52 PT, "c ok"): later packets may add commands.
    assert EXPECTED_COMMANDS <= found, EXPECTED_COMMANDS - found
    for p in COMMANDS.glob("*.md"):
        meta, _ = _frontmatter(p)
        assert meta.get("description"), p.name
        assert meta.get("disable-model-invocation") is True, p.name


def test_review_agents_cannot_edit():
    for name in ("gate-runner", "packet-reviewer"):
        meta, _ = _frontmatter(AGENTS / f"{name}.md")
        tools = {t.strip() for t in str(meta["tools"]).split(",")}
        assert not tools & {"Edit", "Write", "NotebookEdit"}, name


def test_claude_md_self_improvement_rules():
    text = _claude_md()
    loop = _section(text, "## 6. The packet loop")
    rules = loop[loop.index("Self-improvement"):]
    assert "tasks/lessons.md" in rules
    assert "/improve" in rules
    assert re.search(r"(?i)the moment", rules)                       # capture right away
    assert re.search(r"(?i)session start", rules)                    # read before planning
    assert "Lessons applied" in rules
    assert re.search(r"(?i)promot", rules)
    assert "/improve" in _section(text, "## 4. Commands")
    assert re.search(r"(?i)refusal", _section(text, "## 8. Things that will bite"))


def test_template_has_lessons_and_revision_log():
    text = (REPO_ROOT / "tasks" / "plans" / "_TEMPLATE.md").read_text(encoding="utf-8")
    assert "## Lessons applied" in text
    assert "## Revision log" in text
    assert re.search(r"(?i)stopped for chan", _section(text, "## Revision log"))


def _claude_lessons():
    text = (REPO_ROOT / "tasks" / "lessons.md").read_text(encoding="utf-8")
    lines = []
    for block in text.split("### For Claude Code (Me)")[1:]:
        block = block.split("\n## ")[0].split("\n### ")[0]
        lines += [ln for ln in block.splitlines() if ln.startswith("- ")]
    return text, lines


def test_every_claude_lesson_has_a_status():
    _, lines = _claude_lessons()
    assert len(lines) >= 10
    missing = [ln for ln in lines if not STATUS.match(ln)]
    assert not missing, missing


def test_p1_lessons_promoted_where_promised():
    text, _ = _claude_lessons()
    p1 = text[text.index("## P1 settings and data folder"):]
    p1 = p1[: p1.index("\n## ", 5)]
    claude_part = p1[p1.index("### For Claude Code (Me)"):]
    # Spec amendment (Chan 2026-11-06 16:52 PT, "c ok"): no exact counts, because /improve exists to
    # change statuses; each of the four named P1 lessons must still carry a status.
    bullets = re.split(r"\n(?=- )", claude_part.split("\n", 1)[1].strip())
    for phrase in ("STOP again", "commit message", "passes before the code", "Tests of a refusal"):
        hits = [b for b in bullets if phrase.lower() in " ".join(b.split()).lower()]
        assert len(hits) == 1, phrase
        assert STATUS.match(hits[0]), hits[0][:80]
    plan_packet = (COMMANDS / "plan-packet.md").read_text(encoding="utf-8")
    execute = (COMMANDS / "execute.md").read_text(encoding="utf-8")
    reviewer = (AGENTS / "packet-reviewer.md").read_text(encoding="utf-8")
    assert re.search(r"(?i)stop again", plan_packet)                         # lesson (a)
    assert re.search(r"(?i)each (gate )?test", execute) and "first run" in execute.lower()   # lesson (b)
    assert re.search(r"(?i)real repositor", reviewer)                        # lesson (c)
    assert re.search(r"(?i)refusal", _section(_claude_md(), "## 8. Things that will bite"))
    assert re.search(r"(?i)commit message", reviewer) and re.search(r"(?i)approv", reviewer)   # lesson (d)


def test_reviewer_checks_lessons_and_commit_claims():
    reviewer = (AGENTS / "packet-reviewer.md").read_text(encoding="utf-8")
    assert "tasks/lessons.md" in reviewer
    assert re.search(r"(?i)repeat", reviewer) and "should-fix" in reviewer
    assert "Lessons applied" in reviewer


def test_plan_packet_reads_lessons_and_stops_again():
    text = (COMMANDS / "plan-packet.md").read_text(encoding="utf-8")
    assert "tasks/lessons.md" in text
    assert "Lessons applied" in text
    assert "Revision log" in text
    assert re.search(r"(?i)stop again", text)


def test_execute_records_each_gate_test_failing_first():
    text = (COMMANDS / "execute.md").read_text(encoding="utf-8")
    assert re.search(r"(?i)each gate test", text)
    assert re.search(r"(?i)passes? before", text)          # a test that passes before the code is flagged


@pytest.mark.parametrize("command", ["verify-packet", "review-packet"])
def test_corrections_capture_lessons_immediately(command):
    text = (COMMANDS / f"{command}.md").read_text(encoding="utf-8")
    assert "tasks/lessons.md" in text or "/lessons" in text


def test_improve_and_sprint_status_handle_promotion_and_repeats():
    improve = (COMMANDS / "improve.md").read_text(encoding="utf-8")
    for word in ("note", "promote", "retire", "CLAUDE.md", "consent"):
        assert word.lower() in improve.lower(), word
    status = (COMMANDS / "sprint-status.md").read_text(encoding="utf-8")
    assert re.search(r"(?i)repeat", status) and "tasks/lessons.md" in status
    close = (COMMANDS / "close-packet.md").read_text(encoding="utf-8")
    assert "/improve" in close
