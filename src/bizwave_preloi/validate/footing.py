"""Footing checks: does the statement agree with itself before any figure is used?

    check_statement(statement)                       -> FootingReport
    check_bridge(start, addbacks, stated_total, ...) -> list of CheckResult

Checks on a statement, per period:
* periods     labels unique (schema), period ends in one direction, fiscal years ~12 months apart
* subtotals   every subtotal equals the sum of the lines that roll into it
* ladder      printed Gross Profit / Net Ordinary Income / Net Other Income / Net Income equal the
              ladder (pl_ladder.compute_pl) recomputed from the leaf lines' sections
* signs       a leaf whose sign differs from the rest of its section (watch: sign error or contra)
* gaps        a line with a value in some periods and none in others (info)

A failed check is "serious": the figure goes to the CPA and the Flash Review cannot be delivered
while it is unresolved (rules/flags.yaml, footing_failure). Nothing here changes a figure.
Tolerance per check, in the statement's units: base + per_line x lines summed (rules/validation.yaml).

Idea carried over from the MVP's pl_ingest/_check.py (recompute the file's own lines with the
shared ladder and compare); rewritten for the PDF statement schema.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Mapping, Optional

from ..pl_ladder import compute_pl, section_totals
from ..rules import ValidationSettings, validation
from ..schemas import AddBack, LineItem, LineKind, SourceRef, Statement


@dataclass
class CheckResult:
    check: str                          # periods | subtotal | ladder | sign | gap | bridge
    passed: Optional[bool]              # None = could not be checked
    severity: str                       # serious | watch | info
    message: str
    period: Optional[str] = None
    line_id: Optional[str] = None
    expected: Optional[float] = None    # what the parts add up to
    found: Optional[float] = None       # what the document printed
    difference: Optional[float] = None
    tolerance: Optional[float] = None
    sources: List[SourceRef] = field(default_factory=list)


@dataclass
class FootingReport:
    results: List[CheckResult]

    @property
    def failures(self) -> List[CheckResult]:
        return [r for r in self.results if r.passed is False and r.severity == "serious"]

    @property
    def watches(self) -> List[CheckResult]:
        return [r for r in self.results if r.severity == "watch"]

    @property
    def not_checked(self) -> List[CheckResult]:
        return [r for r in self.results if r.passed is None]

    @property
    def ok(self) -> bool:
        """No serious failure. Watches and unchecked items still go to the CPA."""
        return not self.failures


def _f(v: Optional[Decimal]) -> Optional[float]:
    return None if v is None else float(v)


def _tol(settings: ValidationSettings, n: int) -> float:
    return settings.tolerance.base + settings.tolerance.per_line * n


def _src(line: LineItem, period: str) -> List[SourceRef]:
    return [line.sources[period]] if period in line.sources else []


def _leaves(st: Statement) -> List[LineItem]:
    """Lines that are not calculated and have nothing rolling into them."""
    parents = {line.parent for line in st.lines if line.parent}
    return [line for line in st.lines if line.kind != LineKind.CALCULATED and line.id not in parents]


# ------------------------------------------------------------------------------ checks

def _check_periods(st: Statement) -> List[CheckResult]:
    out = []
    ends = [p.end for p in st.periods]
    increasing = all(a < b for a, b in zip(ends, ends[1:]))
    decreasing = all(a > b for a, b in zip(ends, ends[1:]))
    if len(ends) > 1 and not (increasing or decreasing):
        out.append(CheckResult("periods", False, "watch",
                               "Period end dates are not in one direction; check the column headings."))
    years = sorted((p for p in st.periods if p.kind == "fiscal_year"), key=lambda p: p.end)
    for a, b in zip(years, years[1:]):
        gap = (b.end - a.end).days
        if not 360 <= gap <= 370:
            out.append(CheckResult("periods", False, "watch",
                                   f"Fiscal years {a.label} and {b.label} end {gap} days apart; "
                                   "a changed year-end or a mislabeled column?", period=b.label))
    return out


def _check_subtotals(st: Statement, settings: ValidationSettings) -> List[CheckResult]:
    out = []
    for line in st.lines:
        if line.kind != LineKind.SUBTOTAL:
            continue
        kids = st.children(line.id)
        if not kids:
            out.append(CheckResult("subtotal", None, "info",
                                   f"'{line.label}': no lines roll into this subtotal, so it is not checked.",
                                   line_id=line.id))
            continue
        for period in (p.label for p in st.periods):
            printed = _f(line.values.get(period))
            if printed is None:
                continue
            parts = [_f(k.values.get(period)) for k in kids]
            total = sum(v for v in parts if v is not None)
            tol = _tol(settings, len(kids))
            diff = printed - total
            passed = abs(diff) <= tol
            out.append(CheckResult(
                "subtotal", passed, "info" if passed else "serious",
                f"'{line.label}' {period}: printed {printed:,.2f}, parts add to {total:,.2f}"
                + ("" if passed else f" (off by {diff:,.2f})"),
                period=period, line_id=line.id, expected=total, found=printed, difference=diff,
                tolerance=tol, sources=_src(line, period)))
    return out


def _check_ladder(st: Statement, settings: ValidationSettings) -> List[CheckResult]:
    if st.kind != "income_statement":
        return []
    checked = [line for line in st.lines
               if line.kind == LineKind.CALCULATED and line.calc_kind in settings.ladder_checks]
    if not checked:
        return []
    leaves = _leaves(st)
    unmapped = [line for line in leaves if line.section is None]
    if unmapped:
        names = ", ".join(f"'{line.label}'" for line in unmapped[:5])
        return [CheckResult("ladder", None, "watch",
                            f"{len(unmapped)} line(s) have no section ({names}); the printed profit "
                            "lines cannot be recomputed until they do.")]
    out = []
    for period in (p.label for p in st.periods):
        sections = section_totals((line.section, _f(line.values.get(period)) or 0.0) for line in leaves)
        ladder = compute_pl(sections)
        for line in checked:
            printed = _f(line.values.get(period))
            if printed is None:
                continue
            expected = ladder[settings.ladder_checks[line.calc_kind]]
            tol = _tol(settings, len(leaves))
            diff = printed - expected
            passed = abs(diff) <= tol
            out.append(CheckResult(
                "ladder", passed, "info" if passed else "serious",
                f"'{line.label}' {period}: printed {printed:,.2f}, recomputed {expected:,.2f}"
                + ("" if passed else f" (off by {diff:,.2f})"),
                period=period, line_id=line.id, expected=expected, found=printed, difference=diff,
                tolerance=tol, sources=_src(line, period)))
    return out


def _check_signs(st: Statement) -> List[CheckResult]:
    out = []
    leaves = [line for line in _leaves(st) if line.section is not None]
    for period in (p.label for p in st.periods):
        by_section: Dict[str, List[LineItem]] = {}
        for line in leaves:
            if line.values.get(period) not in (None, Decimal(0)):
                by_section.setdefault(line.section, []).append(line)
        for section, lines in by_section.items():
            positive = [line for line in lines if line.values[period] > 0]
            negative = [line for line in lines if line.values[period] < 0]
            minority = negative if len(positive) >= len(negative) else positive
            if len(lines) < 3 or not minority or len(minority) == len(lines) / 2:
                continue
            for line in minority:
                out.append(CheckResult(
                    "sign", None, "watch",
                    f"'{line.label}' {period} has the opposite sign to the rest of {section}: "
                    "a contra item, or a sign read wrongly?",
                    period=period, line_id=line.id, found=_f(line.values[period]),
                    sources=_src(line, period)))
    return out


def _check_gaps(st: Statement) -> List[CheckResult]:
    out = []
    labels = [p.label for p in st.periods]
    for line in st.lines:
        have = [p for p in labels if line.values.get(p) is not None]
        if have and len(have) < len(labels):
            missing = [p for p in labels if p not in have]
            out.append(CheckResult("gap", None, "info",
                                   f"'{line.label}' has no value for {', '.join(missing)}.",
                                   line_id=line.id))
    return out


# ------------------------------------------------------------------------------ public

def check_statement(st: Statement, settings: Optional[ValidationSettings] = None) -> FootingReport:
    s = settings or validation()
    return FootingReport(_check_periods(st) + _check_subtotals(st, s) + _check_ladder(st, s)
                         + _check_signs(st) + _check_gaps(st))


def check_bridge(start: Mapping[str, Decimal], addbacks: List[AddBack], stated_total: Mapping[str, Decimal],
                 start_label: str = "reported earnings", total_label: str = "adjusted earnings",
                 settings: Optional[ValidationSettings] = None) -> List[CheckResult]:
    """Seller's bridge: starting earnings + add-backs as presented = the adjusted total they state.
    Amounts are summed as presented (a deduction is printed negative)."""
    s = settings or validation()
    out = []
    for period, printed in stated_total.items():
        if printed is None or start.get(period) is None:
            out.append(CheckResult("bridge", None, "watch",
                                   f"{period}: {start_label} or {total_label} missing; bridge not checked.",
                                   period=period))
            continue
        amounts = [a.amounts[period] for a in addbacks if period in a.amounts]
        expected = float(start[period]) + float(sum(amounts, Decimal(0)))
        tol = _tol(s, len(amounts) + 1)
        diff = float(printed) - expected
        passed = abs(diff) <= tol
        out.append(CheckResult(
            "bridge", passed, "info" if passed else "serious",
            f"{period}: {start_label} plus {len(amounts)} add-back(s) = {expected:,.2f}; "
            f"stated {total_label} {float(printed):,.2f}" + ("" if passed else f" (off by {diff:,.2f})"),
            period=period, expected=expected, found=float(printed), difference=diff, tolerance=tol))
    return out
