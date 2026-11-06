"""SOP 50 10 8.1 financeability: will this price survive SBA underwriting at the buyer's structure?

This is a COMPUTATION from supportable historical earnings and SBA terms. It is not a valuation
and must never be presented as one (AICPA VS 100 guardrail, CLAUDE.md invariant 5). The output
is "maximum financeable price at your structure", plus the tests behind it.

    evaluate(price, earnings, structure)          -> Evaluation  (one price)
    max_financeable_price(earnings, structure)    -> MaxPrice    (largest price that passes)
    sensitivity(earnings, structure, price)       -> list of SensitivityRow (earnings misses)

Every SBA number comes from rules/sba_sop_8_1.yaml through `sba_params()`. Inputs:

* `Earnings` are SUPPORTABLE historical earnings: reported earnings plus only the add-backs the
  CPA accepts, before owner pay is replaced. Never projections (SOP 8.1 excludes them).
* `Structure` is the buyer's proposed deal: cash, seller notes, rate, and the deductions a lender
  makes from earnings before coverage (replacement salary, capex reserve, cash taxes).

Excel parity: tests/test_excel_parity.py recalculates models/financeability_model.xlsx with
LibreOffice and checks `evaluate` against it cell by cell.
"""
from __future__ import annotations

from datetime import date
from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..rules import SbaParams, sba_params
from .amortization import annual_debt_service

TransactionType = Literal["initial_acquisition", "owner_buyout", "business_expansion", "esop_cooperative"]
BasisPolicy = Literal["lower_of", "last_fiscal_year", "two_year_average", "higher_of"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Earnings(_Strict):
    """Supportable historical earnings for the last two fiscal years (prior is optional)."""
    last_fy: float
    prior_fy: Optional[float] = None
    label: str = "supportable earnings"

    @property
    def two_year_average(self) -> Optional[float]:
        return None if self.prior_fy is None else (self.last_fy + self.prior_fy) / 2.0

    def scaled(self, factor: float) -> "Earnings":
        return Earnings(last_fy=self.last_fy * factor,
                        prior_fy=None if self.prior_fy is None else self.prior_fy * factor,
                        label=self.label)


class Structure(_Strict):
    """The buyer's proposed structure. Percentages are fractions of the purchase price."""
    transaction_type: TransactionType = "initial_acquisition"
    # uses of funds beyond the price
    working_capital: float = Field(default=0.0, ge=0)
    closing_costs: float = Field(default=0.0, ge=0)
    closing_costs_pct_of_price: float = Field(default=0.0, ge=0, lt=1)
    # sources of funds other than the SBA loan
    buyer_cash: float = Field(ge=0)
    minority_equity: float = Field(default=0.0, ge=0)          # non-controlling, under 20% ownership
    seller_note_standby_pct: float = Field(default=0.0, ge=0, le=1)    # full standby, life of the loan
    seller_note_amortizing_pct: float = Field(default=0.0, ge=0, le=1)  # paid during the loan
    seller_note_rate: float = Field(default=0.0, ge=0, lt=1)
    seller_note_term_years: float = Field(default=10.0, gt=0)
    # the SBA loan
    sba_rate: float = Field(gt=0, lt=1)
    sba_term_years: float = Field(default=10.0, gt=0)
    # what a lender takes off earnings before measuring coverage
    replacement_salary: float = Field(default=0.0, ge=0)
    capex_reserve: float = Field(default=0.0, ge=0)
    income_taxes: float = Field(default=0.0, ge=0)
    other_annual_debt_service: float = Field(default=0.0, ge=0)
    # which earnings basis the coverage test uses (SOP 8.1 allows last FY or the two-year average)
    basis_policy: BasisPolicy = "lower_of"

    @model_validator(mode="after")
    def _notes_within_price(self):
        if self.seller_note_standby_pct + self.seller_note_amortizing_pct > 1:
            raise ValueError("seller notes cannot exceed the purchase price")
        return self


class DebtService(_Strict):
    sba: float
    seller_note: float
    other: float
    total: float


class Evaluation(_Strict):
    price: float
    transaction_type: TransactionType
    project_cost: float
    closing_costs: float
    # equity
    injection_base: Literal["project_cost", "purchase_price"]
    required_injection: float
    buyer_cash: float
    limited_sources_offered: float
    limited_sources_cap: float
    limited_sources_counted: float
    countable_equity: float
    equity_shortfall: float
    # sources
    seller_note_standby: float
    seller_note_amortizing: float
    minority_equity: float
    sba_loan: float
    # coverage
    debt_service: DebtService
    cash_available: Dict[str, Optional[float]]
    dscr: Dict[str, Optional[float]]           # None when there is no debt service
    basis_used: str
    dscr_used: Optional[float]
    minimum_dscr: float
    # results
    passes: Dict[str, bool]                    # equity, coverage, loan_cap
    financeable: bool
    lender_qoe_required: bool
    notes: List[str]


class MaxPrice(_Strict):
    max_price: Optional[float]                 # None when no price on the grid passes
    binding_constraint: Optional[str]          # the test that fails one step above max_price
    step: float
    ceiling: float
    at_max: Optional[Evaluation]


class SensitivityRow(_Strict):
    earnings_miss: float                       # 0.10 = supportable earnings 10% lower
    dscr_used: Optional[float]
    financeable_at_price: bool
    max_price: Optional[float]


# --------------------------------------------------------------------------- the core

def _core(price: float, earnings: Earnings, s: Structure, p: SbaParams) -> dict:
    """Every figure for one price, as plain numbers. Shared by evaluate() and the price scan."""
    closing = s.closing_costs + s.closing_costs_pct_of_price * price
    project_cost = price + s.working_capital + closing

    base_kind = p.equity.injection_base[s.transaction_type]
    base = price if base_kind == "purchase_price" else project_cost
    required = p.equity.injection_share_of_project_cost * base

    standby = s.seller_note_standby_pct * price
    amortizing = s.seller_note_amortizing_pct * price
    limited_offered = standby + s.minority_equity
    limited_cap = p.equity.limited_sources_max_share_of_required_injection * required
    limited_counted = min(limited_offered, limited_cap)
    countable = s.buyer_cash + limited_counted
    shortfall = max(0.0, required - countable)

    sba_loan = max(0.0, project_cost - s.buyer_cash - s.minority_equity - standby - amortizing)

    sba_years = min(s.sba_term_years, p.loan.business_max_amortization_years)
    note_years = min(s.seller_note_term_years, p.coverage.non_standby_seller_debt_max_amortization_years)
    ds_sba = annual_debt_service(sba_loan, s.sba_rate, sba_years)
    ds_note = annual_debt_service(amortizing, s.seller_note_rate, note_years)
    ds_total = ds_sba + ds_note + s.other_annual_debt_service

    deductions = s.replacement_salary + s.capex_reserve + s.income_taxes
    cash = {"last_fiscal_year": earnings.last_fy - deductions,
            "two_year_average": None if earnings.two_year_average is None
            else earnings.two_year_average - deductions}
    dscr = {k: (None if v is None or ds_total <= 0 else v / ds_total) for k, v in cash.items()}

    basis_used, dscr_used = _pick_basis(s.basis_policy, dscr, ds_total)
    minimum = p.coverage.minimum_dscr[s.transaction_type]
    coverage_ok = ds_total <= 0 or (dscr_used is not None and dscr_used >= minimum)

    passes = {"equity": shortfall <= 0.005,
              "coverage": coverage_ok,
              "loan_cap": sba_loan <= p.loan.max_7a_loan}
    return dict(closing=closing, project_cost=project_cost, base_kind=base_kind, required=required,
                standby=standby, amortizing=amortizing, limited_offered=limited_offered,
                limited_cap=limited_cap, limited_counted=limited_counted, countable=countable,
                shortfall=shortfall, sba_loan=sba_loan, sba_years=sba_years, note_years=note_years,
                ds_sba=ds_sba, ds_note=ds_note, ds_total=ds_total, cash=cash, dscr=dscr,
                basis_used=basis_used, dscr_used=dscr_used, minimum=minimum, passes=passes)


def _pick_basis(policy: str, dscr: Dict[str, Optional[float]], ds_total: float) -> Tuple[str, Optional[float]]:
    if ds_total <= 0:
        return "no_debt_service", None
    available = {k: v for k, v in dscr.items() if v is not None}
    if policy in available:
        return policy, available[policy]
    if policy == "two_year_average":              # no prior year: fall back, and say so
        return "last_fiscal_year", available["last_fiscal_year"]
    pick = min if policy == "lower_of" else max
    key = pick(available, key=available.get)
    return key, available[key]


# --------------------------------------------------------------------------- public API

def evaluate(price: float, earnings: Earnings, structure: Structure,
             params: Optional[SbaParams] = None) -> Evaluation:
    """All SOP 8.1 tests for one purchase price at the buyer's structure."""
    p = params or sba_params()
    c = _core(price, earnings, structure, p)
    notes = _notes(price, earnings, structure, p, c)
    return Evaluation(
        price=price, transaction_type=structure.transaction_type,
        project_cost=c["project_cost"], closing_costs=c["closing"],
        injection_base=c["base_kind"], required_injection=c["required"],
        buyer_cash=structure.buyer_cash, limited_sources_offered=c["limited_offered"],
        limited_sources_cap=c["limited_cap"], limited_sources_counted=c["limited_counted"],
        countable_equity=c["countable"], equity_shortfall=c["shortfall"],
        seller_note_standby=c["standby"], seller_note_amortizing=c["amortizing"],
        minority_equity=structure.minority_equity, sba_loan=c["sba_loan"],
        debt_service=DebtService(sba=c["ds_sba"], seller_note=c["ds_note"],
                                 other=structure.other_annual_debt_service, total=c["ds_total"]),
        cash_available=c["cash"], dscr=c["dscr"], basis_used=c["basis_used"],
        dscr_used=c["dscr_used"], minimum_dscr=c["minimum"], passes=c["passes"],
        financeable=all(c["passes"].values()),
        lender_qoe_required=(structure.transaction_type in p.lender_qoe.applies_to
                             and price >= p.lender_qoe.required_at_purchase_price),
        notes=notes,
    )


def max_financeable_price(earnings: Earnings, structure: Structure, params: Optional[SbaParams] = None,
                          step: float = 1000.0, ceiling: Optional[float] = None) -> MaxPrice:
    """The largest price, on a `step` grid, that passes every SOP 8.1 test at this structure.

    Coverage and the loan cap only get harder as the price rises (debt grows with price, earnings
    do not), so the largest price passing both is found by bisection. The equity test can switch
    regimes where the limited-sources cap starts to bind, so it is not assumed monotone: from that
    bound the grid is walked down until every test passes. Exact to `step`.
    """
    p = params or sba_params()
    if step <= 0:
        raise ValueError("step must be positive")
    top = ceiling if ceiling is not None else max(25_000_000.0, 20.0 * abs(earnings.last_fy))
    n = int(top // step)

    def monotone_ok(i: int) -> bool:
        passes = _core(i * step, earnings, structure, p)["passes"]
        return passes["coverage"] and passes["loan_cap"]

    best: Optional[int] = None
    if n >= 1 and monotone_ok(1):
        lo, hi = 1, n                             # invariant: monotone_ok(lo)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if monotone_ok(mid):
                lo = mid
            else:
                hi = mid - 1
        for i in range(lo, 0, -1):               # walk down for the equity test
            if all(_core(i * step, earnings, structure, p)["passes"].values()):
                best = i
                break
    if best is None:
        return MaxPrice(max_price=None, binding_constraint=_first_failure(step, earnings, structure, p),
                        step=step, ceiling=top, at_max=None)
    max_price = best * step
    binding = "ceiling" if best == n else _first_failure(max_price + step, earnings, structure, p)
    return MaxPrice(max_price=max_price, binding_constraint=binding, step=step, ceiling=top,
                    at_max=evaluate(max_price, earnings, structure, p))


def sensitivity(earnings: Earnings, structure: Structure, price: float,
                misses: Tuple[float, ...] = (0.10, 0.20), params: Optional[SbaParams] = None,
                step: float = 1000.0) -> List[SensitivityRow]:
    """What a lender QoE trimming earnings by each `miss` does to coverage and to the maximum price."""
    p = params or sba_params()
    rows = []
    for miss in (0.0,) + tuple(misses):
        e = earnings.scaled(1.0 - miss)
        c = _core(price, e, structure, p)
        rows.append(SensitivityRow(
            earnings_miss=miss, dscr_used=c["dscr_used"],
            financeable_at_price=all(c["passes"].values()),
            max_price=max_financeable_price(e, structure, p, step=step).max_price))
    return rows


def default_sba_rate(today: date, params: Optional[SbaParams] = None) -> Tuple[float, Optional[str]]:
    """Prime + spread from the rules file, with a warning when the Prime date is stale.
    For the Instant Screen only; a Flash Review uses the lender's quoted rate."""
    p = params or sba_params()
    a = p.default_rate_assumption
    warning = None
    age = (today - a.prime_as_of).days
    if age > a.stale_after_days:
        warning = (f"Default Prime rate is {age} days old (as of {a.prime_as_of}); "
                   f"update rules/sba_sop_8_1.yaml or use the lender's quoted rate.")
    return a.prime + a.spread, warning


# --------------------------------------------------------------------------- helpers

def _first_failure(price: float, earnings: Earnings, s: Structure, p: SbaParams) -> Optional[str]:
    passes = _core(price, earnings, s, p)["passes"]
    for test in ("coverage", "equity", "loan_cap"):
        if not passes[test]:
            return test
    return None


def _notes(price: float, earnings: Earnings, s: Structure, p: SbaParams, c: dict) -> List[str]:
    notes = []
    if not p.verified_against_sop_text:
        notes.append("SBA parameters are from practitioner summaries of SOP 50 10 8.1 and have not "
                      "yet been checked against the SOP text.")
    if earnings.prior_fy is None:
        notes.append("Only one fiscal year given: coverage is measured on the last fiscal year alone.")
    if s.basis_policy == "two_year_average" and earnings.prior_fy is None:
        notes.append("Two-year average requested but no prior year given; last fiscal year used.")
    if s.sba_term_years > p.loan.business_max_amortization_years:
        notes.append(f"SBA term capped at {p.loan.business_max_amortization_years} years for the business portion.")
    if s.seller_note_amortizing_pct > 0 and s.seller_note_term_years > p.coverage.non_standby_seller_debt_max_amortization_years:
        notes.append("Seller note not on full standby is counted in debt service at a "
                     f"{p.coverage.non_standby_seller_debt_max_amortization_years}-year amortization.")
    if s.seller_note_amortizing_pct > 0:
        notes.append("The amortizing seller note does not count toward the equity injection.")
    if c["limited_offered"] > c["limited_cap"] + 0.005:
        notes.append("Standby seller debt and minority equity exceed half of the required injection; "
                     "only the capped amount counts toward equity.")
    if s.minority_equity > 0:
        notes.append("Minority equity counts only if each investor holds under "
                     f"{p.equity.minority_investor_max_ownership:.0%} with no control.")
    if s.transaction_type in p.equity.reducible_by_lender:
        notes.append("For this transaction type the lender may reduce the injection with documented liquidity.")
    if s.replacement_salary == 0:
        notes.append("No replacement salary deducted. If owner pay was added back, a lender will deduct "
                     "a market salary for whoever runs the business after closing.")
    if c["ds_total"] <= 0:
        notes.append("No debt service at this structure; coverage test not applicable.")
    if price >= p.lender_qoe.required_at_purchase_price and s.transaction_type in p.lender_qoe.applies_to:
        notes.append("At this price the lender must order an independent QoE; a buyer-commissioned QoE "
                     "does not satisfy the requirement.")
    if p.loan.total_debt_capped_at_appraised_value:
        notes.append("Total debt is also capped at the appraised business value, which this review "
                     "does not estimate.")
    return notes
