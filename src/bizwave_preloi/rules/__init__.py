"""Rules as data: every threshold, keyword list, lender view and SBA parameter lives in the YAML
files next to this module. This module loads them and refuses a file that is malformed, so a
typo in a rule fails loudly at load time instead of silently changing a Flash Review.

    from bizwave_preloi.rules import addback_rules, sba_params, flag_rules, taxonomy, validation, intake_rules

Each loader is cached; call `reload()` in tests after editing a file.
"""
from __future__ import annotations

import re
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Literal, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

RULES_DIR = Path(__file__).parent


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _read(name: str) -> dict:
    with open(RULES_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ------------------------------------------------------------------------------ taxonomy

class Category(_Strict):
    name: str
    description: str


class Taxonomy(_Strict):
    version: int
    categories: Dict[str, Category]


@lru_cache(maxsize=None)
def taxonomy() -> Taxonomy:
    return Taxonomy(**_read("taxonomy.yaml"))


# ------------------------------------------------------------------------------ add-backs

class AddBackRule(_Strict):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    name: str
    category: str
    mvp_subtype: Optional[str]
    effect: Literal["add_back", "deduct"]
    lender_view: Literal["likely_accepted", "needs_support", "likely_rejected"]
    patterns: List[str] = Field(min_length=1)
    exclude: List[str] = Field(default_factory=list)
    support_required: List[str]
    seller_question: Optional[str]
    lender_note: str

    @field_validator("patterns", "exclude")
    @classmethod
    def _compiles(cls, patterns):
        for p in patterns:
            try:
                re.compile(p)
            except re.error as err:
                raise ValueError(f"pattern {p!r} does not compile: {err}") from err
        return patterns

    def compiled(self):
        return [re.compile(p) for p in self.patterns], [re.compile(p) for p in self.exclude]


class AddBackRules(_Strict):
    version: int
    status: Literal["draft", "confirmed"]
    updated: date
    claude_min_confidence: float = Field(gt=0, le=1)
    rules: List[AddBackRule]

    @model_validator(mode="after")
    def _ids_unique_and_categories_known(self):
        ids = [r.id for r in self.rules]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"add-back rule ids repeat: {sorted(dupes)}")
        known = set(taxonomy().categories)
        bad = {r.id: r.category for r in self.rules if r.category not in known}
        if bad:
            raise ValueError(f"add-back rules use unknown categories: {bad}")
        return self

    def by_id(self, rule_id: str) -> AddBackRule:
        for rule in self.rules:
            if rule.id == rule_id:
                return rule
        raise KeyError(rule_id)


@lru_cache(maxsize=None)
def addback_rules() -> AddBackRules:
    return AddBackRules(**_read("addbacks.yaml"))


# ------------------------------------------------------------------------------ SBA SOP 8.1

class Coverage(_Strict):
    minimum_dscr: Dict[str, float]
    earnings_bases: List[Literal["last_fiscal_year", "two_year_average"]]
    projections_allowed: bool
    non_standby_seller_debt_max_amortization_years: int = Field(gt=0)


class Equity(_Strict):
    injection_share_of_project_cost: float = Field(gt=0, lt=1)
    injection_base: Dict[str, Literal["project_cost", "purchase_price"]]
    reducible_by_lender: List[str]
    limited_sources_max_share_of_required_injection: float = Field(ge=0, le=1)
    seller_note_counts_only_on_full_standby: bool
    minority_investor_max_ownership: float = Field(gt=0, lt=1)


class Loan(_Strict):
    business_max_amortization_years: int = Field(gt=0)
    max_7a_loan: float = Field(gt=0)
    total_debt_capped_at_appraised_value: bool


class LenderQoe(_Strict):
    required_at_purchase_price: float = Field(gt=0)
    applies_to: List[str]


class RateAssumption(_Strict):
    prime: float = Field(gt=0, lt=1)
    prime_as_of: date
    spread: float = Field(ge=0, lt=1)
    stale_after_days: int = Field(gt=0)


class SbaParams(_Strict):
    version: int
    sop: str
    effective: date
    verified_against_sop_text: bool
    sources: List[str]
    coverage: Coverage
    equity: Equity
    loan: Loan
    lender_qoe: LenderQoe
    seller_consulting_max_months: int
    default_rate_assumption: RateAssumption


@lru_cache(maxsize=None)
def sba_params() -> SbaParams:
    return SbaParams(**_read("sba_sop_8_1.yaml"))


# ------------------------------------------------------------------------------ flags

class FlagRule(_Strict):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    metric: str
    direction: Literal["above", "below"]
    watch: Optional[float]
    serious: Optional[float]
    blocks_delivery: bool = False
    title: str
    why: str

    @model_validator(mode="after")
    def _has_a_level_in_order(self):
        if self.watch is None and self.serious is None:
            raise ValueError(f"flag {self.id}: needs a watch or a serious threshold")
        if self.watch is not None and self.serious is not None:
            ordered = self.watch <= self.serious if self.direction == "above" else self.watch >= self.serious
            if not ordered:
                raise ValueError(f"flag {self.id}: watch must be reached before serious")
        return self


class FlagRules(_Strict):
    version: int
    status: Literal["draft", "confirmed"]
    updated: date
    rules: List[FlagRule]
    metrics: Dict[str, str]

    @model_validator(mode="after")
    def _metrics_defined(self):
        missing = {r.metric for r in self.rules} - set(self.metrics)
        if missing:
            raise ValueError(f"flags use metrics with no definition: {sorted(missing)}")
        ids = [r.id for r in self.rules]
        if len(set(ids)) != len(ids):
            raise ValueError("flag ids repeat")
        return self


@lru_cache(maxsize=None)
def flag_rules() -> FlagRules:
    return FlagRules(**_read("flags.yaml"))


# ------------------------------------------------------------------------------ validation

class Tolerance(_Strict):
    base: float = Field(ge=0)
    per_line: float = Field(ge=0)


class ValidationSettings(_Strict):
    version: int
    tolerance: Tolerance
    ladder_checks: Dict[str, str]


@lru_cache(maxsize=None)
def validation() -> ValidationSettings:
    return ValidationSettings(**_read("validation.yaml"))


# ------------------------------------------------------------------------------ intake

# The values of documents.kind (db/models.py); a test keeps the two lists equal.
DocumentKind = Literal["cim", "recast", "p_and_l", "balance_sheet", "other"]


class DocumentKindRule(_Strict):
    kind: DocumentKind
    patterns: List[str] = Field(min_length=1)

    @field_validator("patterns")
    @classmethod
    def _compile(cls, patterns: List[str]) -> List[str]:
        for pattern in patterns:
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(f"pattern {pattern!r} does not compile: {exc}") from None
        return patterns


class IntakeRules(_Strict):
    status: Literal["draft", "confirmed"]
    source: str
    document_kinds: List[DocumentKindRule] = Field(min_length=1)
    unmatched_kind: DocumentKind
    skip_names: List[str]
    skip_prefixes: List[str] = Field(default_factory=list)

    def kind_for(self, file_name: str) -> str:
        """The kind of a file, from its name (first matching row wins)."""
        text = normalize_file_name(file_name)
        for row in self.document_kinds:
            if any(re.search(p, text) for p in row.patterns):
                return row.kind
        return self.unmatched_kind

    def skips(self, file_name: str) -> bool:
        name = file_name.lower()
        return (name.startswith(".") or name in {n.lower() for n in self.skip_names}
                or any(name.startswith(prefix.lower()) for prefix in self.skip_prefixes if prefix))


def normalize_file_name(file_name: str) -> str:
    text = file_name.lower().replace("&", " and ")
    text = re.sub(r"[_\-.]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@lru_cache(maxsize=None)
def intake_rules() -> IntakeRules:
    return IntakeRules(**_read("intake.yaml"))


def reload() -> None:
    """Forget cached rules (tests, or after editing a YAML file in a running session)."""
    for loader in (taxonomy, addback_rules, sba_params, flag_rules, validation, intake_rules):
        loader.cache_clear()
