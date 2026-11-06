"""The financeability model as a live Excel workbook, for the CPA to open and audit.

`build_model(path, scenarios)` writes one column per scenario. Every calculated cell is an
Excel formula (PMT, MIN, VLOOKUP ...) built from the same SBA parameters file as the Python
calculator, so the two can be checked against each other: tests/test_excel_parity.py
recalculates the workbook with LibreOffice and compares every row with `evaluate()`.

Rows are keyed (`ROW_KEYS`) so tests and later output code can find a figure by name.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from ..outputs.xlsx_style import HEADER_FILL, HEADER_FONT, SECTION_FONT, TITLE_FONT
from ..rules import SbaParams, sba_params
from .financeability import Earnings, Structure

INPUT_FONT = Font(color="1F4E78")             # blue = typed-in input (banking convention)

# (key, label, kind) — kind: "input" or a formula template using {c} for the column letter and
# {r[key]} for another row of the same column. SBA parameters live on the 'SBA' sheet.
_ROWS: List[tuple] = [
    ("h_inputs", "Inputs", "section"),
    ("price", "Purchase price", "input"),
    ("transaction_type", "Transaction type", "input"),
    ("last_fy", "Supportable earnings, last fiscal year", "input"),
    ("prior_fy", "Supportable earnings, prior fiscal year (blank if none)", "input"),
    ("basis_policy", "Coverage basis policy", "input"),
    ("working_capital", "Working capital funded", "input"),
    ("closing_costs", "Closing costs (fixed)", "input"),
    ("closing_costs_pct", "Closing costs (% of price)", "input"),
    ("buyer_cash", "Buyer cash", "input"),
    ("minority_equity", "Minority investor equity", "input"),
    ("sn_standby_pct", "Seller note on full standby (% of price)", "input"),
    ("sn_amort_pct", "Seller note amortizing (% of price)", "input"),
    ("sn_rate", "Seller note rate", "input"),
    ("sn_term", "Seller note term (years)", "input"),
    ("sba_rate", "SBA loan rate", "input"),
    ("sba_term", "SBA loan term (years)", "input"),
    ("replacement_salary", "Replacement salary deducted", "input"),
    ("capex_reserve", "Capex reserve deducted", "input"),
    ("income_taxes", "Cash income taxes deducted", "input"),
    ("other_ds", "Other annual debt service", "input"),

    ("h_equity", "Uses and equity", "section"),
    ("closing", "Closing costs", "={c}{closing_costs}+{c}{closing_costs_pct}*{c}{price}"),
    ("project_cost", "Total project cost", "={c}{price}+{c}{working_capital}+{c}{closing}"),
    ("base", "Injection base",
     "=IF(VLOOKUP({c}{transaction_type},SBA!$A$12:$C$15,3,FALSE)=\"purchase_price\",{c}{price},{c}{project_cost})"),
    ("required", "Required injection", "=SBA!$B$3*{c}{base}"),
    ("standby", "Seller note on standby", "={c}{sn_standby_pct}*{c}{price}"),
    ("amortizing", "Seller note amortizing", "={c}{sn_amort_pct}*{c}{price}"),
    ("limited_offered", "Limited sources offered", "={c}{standby}+{c}{minority_equity}"),
    ("limited_cap", "Limited sources cap", "=SBA!$B$4*{c}{required}"),
    ("limited_counted", "Limited sources counted", "=MIN({c}{limited_offered},{c}{limited_cap})"),
    ("countable", "Countable equity", "={c}{buyer_cash}+{c}{limited_counted}"),
    ("shortfall", "Equity shortfall", "=MAX(0,{c}{required}-{c}{countable})"),

    ("h_debt", "Debt and coverage", "section"),
    ("sba_loan", "SBA loan",
     "=MAX(0,{c}{project_cost}-{c}{buyer_cash}-{c}{minority_equity}-{c}{standby}-{c}{amortizing})"),
    ("sba_years", "SBA amortization used (years)", "=MIN({c}{sba_term},SBA!$B$5)"),
    ("note_years", "Seller note amortization used (years)", "=MIN({c}{sn_term},SBA!$B$6)"),
    ("ds_sba", "Debt service, SBA loan",
     "=IF({c}{sba_loan}<=0,0,-PMT({c}{sba_rate}/12,{c}{sba_years}*12,{c}{sba_loan})*12)"),
    ("ds_note", "Debt service, seller note",
     "=IF({c}{amortizing}<=0,0,IF({c}{sn_rate}=0,{c}{amortizing}/{c}{note_years},"
     "-PMT({c}{sn_rate}/12,{c}{note_years}*12,{c}{amortizing})*12))"),
    ("ds_total", "Total debt service", "={c}{ds_sba}+{c}{ds_note}+{c}{other_ds}"),
    ("deductions", "Lender deductions from earnings",
     "={c}{replacement_salary}+{c}{capex_reserve}+{c}{income_taxes}"),
    ("cash_last", "Cash available, last fiscal year", "={c}{last_fy}-{c}{deductions}"),
    ("cash_avg", "Cash available, two-year average",
     "=IF({c}{prior_fy}=\"\",\"\",({c}{last_fy}+{c}{prior_fy})/2-{c}{deductions})"),
    ("dscr_last", "DSCR, last fiscal year", "=IF({c}{ds_total}<=0,\"\",{c}{cash_last}/{c}{ds_total})"),
    ("dscr_avg", "DSCR, two-year average",
     "=IF(OR({c}{ds_total}<=0,{c}{prior_fy}=\"\"),\"\",{c}{cash_avg}/{c}{ds_total})"),
    ("dscr_used", "DSCR used",
     "=IF({c}{ds_total}<=0,\"\",IF({c}{prior_fy}=\"\",{c}{dscr_last},"
     "IF({c}{basis_policy}=\"last_fiscal_year\",{c}{dscr_last},"
     "IF({c}{basis_policy}=\"two_year_average\",{c}{dscr_avg},"
     "IF({c}{basis_policy}=\"lower_of\",MIN({c}{dscr_last},{c}{dscr_avg}),MAX({c}{dscr_last},{c}{dscr_avg}))))))"),
    ("min_dscr", "Minimum DSCR", "=VLOOKUP({c}{transaction_type},SBA!$A$12:$C$15,2,FALSE)"),

    ("h_tests", "Tests", "section"),
    ("pass_equity", "Equity test passed", "={c}{shortfall}<=0.005"),
    ("pass_coverage", "Coverage test passed", "=OR({c}{ds_total}<=0,{c}{dscr_used}>={c}{min_dscr})"),
    ("pass_loan_cap", "Loan cap test passed", "={c}{sba_loan}<=SBA!$B$7"),
    ("financeable", "Financeable", "=AND({c}{pass_equity},{c}{pass_coverage},{c}{pass_loan_cap})"),
]
ROW_KEYS = [key for key, _, kind in _ROWS if kind != "section"]
FIRST_ROW = 4                                   # rows 1-3: title, note, scenario header

_DOLLARS = '#,##0;(#,##0);"-"'
_FORMATS = {
    **{k: '0.0%' for k in ("closing_costs_pct", "sn_standby_pct", "sn_amort_pct")},
    **{k: '0.00%' for k in ("sn_rate", "sba_rate")},
    **{k: '0' for k in ("sn_term", "sba_term", "sba_years", "note_years")},
    **{k: '0.00"x"' for k in ("dscr_last", "dscr_avg", "dscr_used", "min_dscr")},
}
_TEXT = {"transaction_type", "basis_policy", "pass_equity", "pass_coverage", "pass_loan_cap", "financeable"}


def _inputs(price: float, earnings: Earnings, s: Structure) -> Dict[str, object]:
    return {
        "price": price, "transaction_type": s.transaction_type,
        "last_fy": earnings.last_fy, "prior_fy": earnings.prior_fy,
        "basis_policy": s.basis_policy, "working_capital": s.working_capital,
        "closing_costs": s.closing_costs, "closing_costs_pct": s.closing_costs_pct_of_price,
        "buyer_cash": s.buyer_cash, "minority_equity": s.minority_equity,
        "sn_standby_pct": s.seller_note_standby_pct, "sn_amort_pct": s.seller_note_amortizing_pct,
        "sn_rate": s.seller_note_rate, "sn_term": s.seller_note_term_years,
        "sba_rate": s.sba_rate, "sba_term": s.sba_term_years,
        "replacement_salary": s.replacement_salary, "capex_reserve": s.capex_reserve,
        "income_taxes": s.income_taxes, "other_ds": s.other_annual_debt_service,
    }


def _sba_sheet(wb: Workbook, p: SbaParams) -> None:
    ws = wb.create_sheet("SBA")
    ws["A1"], ws["A1"].font = f"{p.sop} parameters (from rules/sba_sop_8_1.yaml)", TITLE_FONT
    ws["A2"] = f"verified against SOP text: {p.verified_against_sop_text}"
    rows = [("Injection share of base", p.equity.injection_share_of_project_cost),
            ("Limited sources max share of required injection",
             p.equity.limited_sources_max_share_of_required_injection),
            ("Business portion max amortization (years)", p.loan.business_max_amortization_years),
            ("Non-standby seller debt max amortization (years)",
             p.coverage.non_standby_seller_debt_max_amortization_years),
            ("Maximum 7(a) loan", p.loan.max_7a_loan),
            ("Lender QoE required at purchase price", p.lender_qoe.required_at_purchase_price)]
    for i, (label, value) in enumerate(rows, start=3):          # B3..B8
        ws.cell(row=i, column=1, value=label)
        ws.cell(row=i, column=2, value=value)
    ws["A11"], ws["B11"], ws["C11"] = "Transaction type", "Minimum DSCR", "Injection base"
    types = ["initial_acquisition", "owner_buyout", "business_expansion", "esop_cooperative"]
    for i, t in enumerate(types, start=12):                      # A12:C15
        ws.cell(row=i, column=1, value=t)
        ws.cell(row=i, column=2, value=p.coverage.minimum_dscr[t])
        ws.cell(row=i, column=3, value=p.equity.injection_base[t])
    ws.column_dimensions["A"].width = 48
    ws.column_dimensions["B"].width = 16
    ws.column_dimensions["C"].width = 16


def build_model(path: Path, scenarios: List[dict], params: Optional[SbaParams] = None) -> Dict[str, int]:
    """Write the workbook. Each scenario: {"name", "price", "earnings": Earnings, "structure": Structure}.
    Returns {row key: row number} so callers can read figures back."""
    p = params or sba_params()
    wb = Workbook()
    ws = wb.active
    ws.title = "Model"
    ws["A1"], ws["A1"].font = "BizWave Flash Review — SOP 50 10 8.1 financeability model", TITLE_FONT
    ws["A2"] = ("A computation from supportable historical earnings and SBA terms. Not a valuation. "
                "Blue cells are inputs; everything else is a formula.")

    rownum: Dict[str, int] = {}
    r = FIRST_ROW
    for key, _, _ in _ROWS:
        rownum[key] = r
        r += 1

    ws.cell(row=3, column=1, value="")
    for j, sc in enumerate(scenarios):
        col = get_column_letter(2 + j)
        head = ws.cell(row=3, column=2 + j, value=sc["name"])
        head.font, head.fill = HEADER_FONT, HEADER_FILL
        values = _inputs(sc["price"], sc["earnings"], sc["structure"])
        for key, label, kind in _ROWS:
            row = rownum[key]
            if j == 0:
                cell = ws.cell(row=row, column=1, value=label)
                if kind == "section":
                    cell.font = SECTION_FONT
            if kind == "section":
                continue
            if kind == "input":
                cell = ws.cell(row=row, column=2 + j, value=values[key])
                cell.font = INPUT_FONT
            else:
                cell = ws.cell(row=row, column=2 + j, value=kind.format(c=col, **rownum))
            if key not in _TEXT:
                cell.number_format = _FORMATS.get(key, _DOLLARS)
    ws.column_dimensions["A"].width = 52
    for j in range(len(scenarios)):
        ws.column_dimensions[get_column_letter(2 + j)].width = 18
    ws.freeze_panes = "B4"
    _sba_sheet(wb, p)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return {k: rownum[k] for k in ROW_KEYS}


def sample_scenarios() -> List[dict]:
    """Four synthetic deals that exercise every branch. Used by the parity test and the committed model."""
    return [
        {"name": "A: standby note", "price": 2_000_000.0,
         "earnings": Earnings(last_fy=500_000, prior_fy=450_000),
         "structure": Structure(buyer_cash=150_000, working_capital=100_000, closing_costs=50_000,
                                seller_note_standby_pct=0.05, sba_rate=0.095)},
        {"name": "B: amortizing note", "price": 1_500_000.0,
         "earnings": Earnings(last_fy=600_000, prior_fy=520_000),
         "structure": Structure(buyer_cash=160_000, working_capital=50_000, closing_costs_pct_of_price=0.03,
                                seller_note_amortizing_pct=0.10, seller_note_rate=0.06,
                                seller_note_term_years=5, sba_rate=0.0975, replacement_salary=120_000,
                                capex_reserve=25_000)},
        {"name": "C: cap binds, one year", "price": 1_200_000.0,
         "earnings": Earnings(last_fy=300_000),
         "structure": Structure(buyer_cash=100_000, minority_equity=50_000, seller_note_standby_pct=0.15,
                                sba_rate=0.095, basis_policy="two_year_average")},
        {"name": "D: owner buyout", "price": 800_000.0,
         "earnings": Earnings(last_fy=220_000, prior_fy=200_000),
         "structure": Structure(transaction_type="owner_buyout", buyer_cash=80_000, sba_rate=0.1025,
                                sba_term_years=15, seller_note_amortizing_pct=0.2, seller_note_rate=0.0,
                                seller_note_term_years=12, basis_policy="last_fiscal_year")},
        {"name": "E: fails twice", "price": 1_000_000.0,
         "earnings": Earnings(last_fy=150_000, prior_fy=170_000),
         "structure": Structure(buyer_cash=50_000, sba_rate=0.095, basis_policy="higher_of",
                                income_taxes=5_000)},
    ]
