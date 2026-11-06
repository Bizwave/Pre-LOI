"""Data contracts for a Flash Review. Every stage reads and writes these shapes.

Two kinds of number live in this repository, and they are kept apart on purpose:

* Figures READ from a document (statement lines, seller add-backs) are `Decimal`, exactly as
  printed, and each carries a `SourceRef` naming the file and page it came from.
* Figures COMPUTED by code (coverage, debt service, maximum financeable price) are `float`
  and are rounded only when presented. They are never stored back as if they had been read.

A figure in a deliverable must trace to one of the two. Claude never supplies a figure that
is not either re-derived by code or tied out by the footing checks (CLAUDE.md, invariant 1).
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .pl_ladder import CALC_KINDS, SECTIONS


class Model(BaseModel):
    """Base for every contract: unknown fields are an error, not silently dropped."""
    model_config = ConfigDict(extra="forbid")


# ------------------------------------------------------------------------- provenance

class ReadMethod(str, Enum):
    TEXT_LAYER = "text_layer"   # words from the PDF's own text layer
    TABLE = "table"             # a table parser (pdfplumber / camelot) on the text layer
    CLAUDE = "claude"           # registered use ingest.page_extraction (scanned or messy page)
    MANUAL = "manual"           # keyed in by the reviewer (no-LLM mode, or a correction)


class SourceRef(Model):
    """Where a figure was read. `page` is 1-based, as a PDF viewer numbers pages."""
    document: str = Field(min_length=1)          # file name inside the deal folder
    page: int = Field(ge=1)
    method: ReadMethod
    excerpt: Optional[str] = None                # the text as read, shown on the review screen
    confidence: Optional[float] = Field(default=None, ge=0, le=1)   # Claude reads only


# --------------------------------------------------------------------------- statements

Section = Literal["Income", "Cost of Goods Sold", "Expense", "Other Income", "Other Expense"]
assert set(Section.__args__) == set(SECTIONS)   # the ladder and the schema agree

CalcKind = Literal[CALC_KINDS]


class LineKind(str, Enum):
    ACCOUNT = "account"          # money actually posted (Rent, Fuel, Sales)
    SUBTOTAL = "subtotal"        # sums the lines whose `parent` is this line
    CALCULATED = "calculated"    # a ladder rung the document printed (Gross Profit, Net Income)


class Period(Model):
    label: str = Field(min_length=1)             # as printed: "FY2024", "TTM Jun-25"
    kind: Literal["fiscal_year", "ttm", "ytd", "interim"]
    end: date
    months: int = Field(ge=1, le=12)

    @model_validator(mode="after")
    def _twelve_months_for_annual(self):
        if self.kind in ("fiscal_year", "ttm") and self.months != 12:
            raise ValueError(f"{self.label}: a {self.kind} period covers 12 months, not {self.months}")
        return self


class LineItem(Model):
    id: str = Field(min_length=1)
    label: str                                   # as printed (may be "" for an unlabelled total)
    kind: LineKind = LineKind.ACCOUNT
    section: Optional[Section] = None            # required for accounts before the ladder runs
    calc_kind: Optional[CalcKind] = None         # for calculated lines only
    parent: Optional[str] = None                 # id of the subtotal this line rolls into
    values: Dict[str, Optional[Decimal]]         # period label -> amount as printed
    sources: Dict[str, SourceRef] = Field(default_factory=dict)   # period label -> where read

    @model_validator(mode="after")
    def _calc_kind_only_on_calculated(self):
        if self.calc_kind is not None and self.kind != LineKind.CALCULATED:
            raise ValueError(f"line {self.id}: calc_kind is only for calculated lines")
        if self.kind == LineKind.CALCULATED and self.calc_kind is None:
            raise ValueError(f"line {self.id}: a calculated line needs a calc_kind")
        return self


class Statement(Model):
    kind: Literal["income_statement", "balance_sheet", "sde_recast"]
    units: Literal["dollars", "thousands"] = "dollars"
    periods: List[Period]
    lines: List[LineItem]

    @model_validator(mode="after")
    def _consistent(self):
        labels = [p.label for p in self.periods]
        if len(set(labels)) != len(labels):
            raise ValueError(f"period labels repeat: {labels}")
        ids = [line.id for line in self.lines]
        if len(set(ids)) != len(ids):
            raise ValueError("line ids repeat")
        known = set(labels)
        for line in self.lines:
            unknown = set(line.values) - known
            if unknown:
                raise ValueError(f"line {line.id}: values for unknown period(s) {sorted(unknown)}")
            if line.parent is not None and line.parent not in ids:
                raise ValueError(f"line {line.id}: parent {line.parent} is not a line")
        return self

    def line(self, line_id: str) -> LineItem:
        return next(line for line in self.lines if line.id == line_id)

    def children(self, line_id: str) -> List[LineItem]:
        return [line for line in self.lines if line.parent == line_id]


# ----------------------------------------------------------------------------- add-backs

LenderView = Literal["likely_accepted", "needs_support", "likely_rejected"]
Effect = Literal["add_back", "deduct"]


class Override(Model):
    """A CPA decision that replaces the rules table's view. The reason is mandatory."""
    lender_view: LenderView
    amounts: Optional[Dict[str, Decimal]] = None     # revised amounts by period, if any
    reason: str = Field(min_length=5)
    by: str = Field(min_length=1)
    at: datetime


class AddBack(Model):
    id: str = Field(min_length=1)
    description: str = Field(min_length=1)           # the seller's or broker's words, verbatim
    amounts: Dict[str, Decimal]                      # period label -> amount as presented
    sources: Dict[str, SourceRef] = Field(default_factory=dict)
    rule_id: Optional[str] = None                    # row of rules/addbacks.yaml
    classified_by: Optional[Literal["rule", "claude", "cpa"]] = None
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    lender_view: Optional[LenderView] = None         # from the rules table, never from Claude
    support_required: List[str] = Field(default_factory=list)
    override: Optional[Override] = None

    @property
    def effective_view(self) -> Optional[str]:
        return self.override.lender_view if self.override else self.lender_view


# -------------------------------------------------------------------------------- flags

class Flag(Model):
    id: str
    rule_id: Optional[str] = None                    # row of rules/flags.yaml, when a rule raised it
    severity: Literal["info", "watch", "serious"]
    title: str
    detail: str
    evidence: List[SourceRef] = Field(default_factory=list)
    raised_by: Literal["rule", "claude", "cpa"]
    status: Literal["open", "kept", "dismissed"] = "open"   # the CPA decides what stays


# --------------------------------------------------------------------------------- deal

class Deal(Model):
    """One Flash Review engagement. Grows as the sprint adds stages."""
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,40}$")   # folder name under deals/
    name: str                                     # internal code name, not the seller's name
    received_at: Optional[datetime] = None        # SLA clock starts when the package is complete
    documents: List[str] = Field(default_factory=list)
    statements: List[Statement] = Field(default_factory=list)
    addbacks: List[AddBack] = Field(default_factory=list)
    flags: List[Flag] = Field(default_factory=list)
    asking_price: Optional[Decimal] = None
    proposed_price: Optional[Decimal] = None
