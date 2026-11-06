"""Add-back classification: rules first, Claude only for what the rules cannot match.

    classify_addbacks(addbacks, deal_id=...) -> ClassificationReport

1. Each description is normalized and tried against rules/addbacks.yaml in file order; the first
   matching row wins (method "rule", confidence 1.0).
2. Descriptions no row matched go to Claude in ONE batched call (use addbacks.classify_unmatched),
   text only, no amounts. Claude may only name a row id from the table. A pick at or above
   `claude_min_confidence` is applied (method "claude"); anything else stays unclassified.
3. The lender view and the support list always come from the table row, never from Claude.
4. Whatever is still unclassified goes to the CPA on the review screen.

With Claude off (no-LLM mode) step 2 is skipped and step 4 catches the rest.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import List, Optional

from pydantic import BaseModel, Field

from ..llm import Transport, ask
from ..rules import AddBackRule, AddBackRules, addback_rules
from ..schemas import AddBack

USE = "addbacks.classify_unmatched"

_APOSTROPHES = re.compile(r"[’'`]")
_NON_WORD = re.compile(r"[^a-z0-9]+")


def normalize(text: str) -> str:
    """Lower case, "&" -> " and ", apostrophes dropped, other punctuation -> space, spaces squeezed."""
    t = str(text or "").lower().replace("&", " and ")
    t = _APOSTROPHES.sub("", t)
    return " ".join(_NON_WORD.sub(" ", t).split())


@dataclass(frozen=True)
class RuleMatch:
    rule_id: str
    pattern: str


def match_rule(description: str, rules: Optional[AddBackRules] = None) -> Optional[RuleMatch]:
    """The first rule row whose pattern is found and no exclude pattern is found, or None."""
    text = normalize(description)
    for rule in (rules or addback_rules()).rules:
        patterns, excludes = rule.compiled()
        if any(x.search(text) for x in excludes):
            continue
        for pattern in patterns:
            if pattern.search(text):
                return RuleMatch(rule.id, pattern.pattern)
    return None


# --------------------------------------------------------------------- Claude answer shape

class ClaudePick(BaseModel):
    addback_id: str
    rule_id: Optional[str] = None
    confidence: float = Field(ge=0, le=1)
    reason: str


class ClaudePicks(BaseModel):
    picks: List[ClaudePick]


def _claude_content(unmatched: List[AddBack], rules: AddBackRules) -> str:
    table = [{"id": r.id, "name": r.name, "category": r.category, "effect": r.effect, "note": r.lender_note}
             for r in rules.rules]
    items = [{"addback_id": a.id, "description": a.description} for a in unmatched]
    return ("Rule table:\n" + json.dumps(table, indent=1) +
            "\n\nAdd-backs to classify:\n" + json.dumps(items, indent=1))


# --------------------------------------------------------------------------- the report

@dataclass
class ClassificationReport:
    addbacks: List[AddBack]                        # same order as given, classifications applied
    by_rule: List[str] = field(default_factory=list)
    by_claude: List[str] = field(default_factory=list)
    for_cpa: List[str] = field(default_factory=list)             # still unclassified
    claude_rejected: List[dict] = field(default_factory=list)    # picks not applied, with why


def _apply(addback: AddBack, rule: AddBackRule, method: str, confidence: float) -> AddBack:
    return addback.model_copy(update={
        "rule_id": rule.id, "classified_by": method, "confidence": confidence,
        "lender_view": rule.lender_view, "support_required": list(rule.support_required)})


def classify_addbacks(addbacks: List[AddBack], *, deal_id: Optional[str] = None,
                      rules: Optional[AddBackRules] = None,
                      transport: Optional[Transport] = None, runlog=None) -> ClassificationReport:
    """Classify every add-back. Add-backs already classified by the CPA are left as they are."""
    table = rules or addback_rules()
    out: List[AddBack] = list(addbacks)
    report = ClassificationReport(addbacks=out)
    unmatched_idx: List[int] = []

    for i, a in enumerate(out):
        if a.classified_by == "cpa":
            continue
        m = match_rule(a.description, table)
        if m:
            out[i] = _apply(a, table.by_id(m.rule_id), "rule", 1.0)
            report.by_rule.append(a.id)
        else:
            unmatched_idx.append(i)

    if unmatched_idx:
        unmatched = [out[i] for i in unmatched_idx]
        answer = ask(USE, content=_claude_content(unmatched, table), answer_shape=ClaudePicks,
                     deal_id=deal_id, transport=transport, runlog=runlog)
        picks = {p.addback_id: p for p in (answer.picks if answer else [])}
        known = {r.id for r in table.rules}
        for i in unmatched_idx:
            a = out[i]
            pick = picks.get(a.id)
            if pick is None or pick.rule_id is None:
                report.for_cpa.append(a.id)
                continue
            if pick.rule_id not in known:
                report.claude_rejected.append({"addback_id": a.id, "rule_id": pick.rule_id,
                                               "why": "not a rule id in the table"})
                report.for_cpa.append(a.id)
            elif pick.confidence < table.claude_min_confidence:
                report.claude_rejected.append({"addback_id": a.id, "rule_id": pick.rule_id,
                                               "why": f"confidence {pick.confidence:.2f} below "
                                                      f"{table.claude_min_confidence:.2f}"})
                report.for_cpa.append(a.id)
            else:
                out[i] = _apply(a, table.by_id(pick.rule_id), "claude", pick.confidence)
                report.by_claude.append(a.id)
    return report
