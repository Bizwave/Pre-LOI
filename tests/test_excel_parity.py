"""The Python calculator and the Excel model agree on every row of every sample scenario.

Builds the workbook, recalculates it with LibreOffice (headless), and compares the cached results
with `evaluate()`. Skipped when LibreOffice is not installed. On Windows, set SOFFICE to the full
path of soffice.exe if it is not on PATH.
"""
import os
import shutil
import subprocess

import openpyxl
import pytest

from bizwave_preloi.finance import evaluate
from bizwave_preloi.finance.excel_model import build_model, sample_scenarios
from bizwave_preloi.rules import sba_params

SOFFICE = os.environ.get("SOFFICE") or shutil.which("soffice") or shutil.which("libreoffice")
pytestmark = [pytest.mark.excel,
              pytest.mark.skipif(not SOFFICE, reason="LibreOffice (soffice) not installed")]


def _python_rows(sc) -> dict:
    s, e = sc["structure"], sc["earnings"]
    p = sba_params()
    ev = evaluate(sc["price"], e, s)
    return {
        "closing": ev.closing_costs, "project_cost": ev.project_cost,
        "base": ev.price if ev.injection_base == "purchase_price" else ev.project_cost,
        "required": ev.required_injection, "standby": ev.seller_note_standby,
        "amortizing": ev.seller_note_amortizing, "limited_offered": ev.limited_sources_offered,
        "limited_cap": ev.limited_sources_cap, "limited_counted": ev.limited_sources_counted,
        "countable": ev.countable_equity, "shortfall": ev.equity_shortfall, "sba_loan": ev.sba_loan,
        "sba_years": min(s.sba_term_years, p.loan.business_max_amortization_years),
        "note_years": min(s.seller_note_term_years, p.coverage.non_standby_seller_debt_max_amortization_years),
        "ds_sba": ev.debt_service.sba, "ds_note": ev.debt_service.seller_note, "ds_total": ev.debt_service.total,
        "deductions": s.replacement_salary + s.capex_reserve + s.income_taxes,
        "cash_last": ev.cash_available["last_fiscal_year"], "cash_avg": ev.cash_available["two_year_average"],
        "dscr_last": ev.dscr["last_fiscal_year"], "dscr_avg": ev.dscr["two_year_average"],
        "dscr_used": ev.dscr_used, "min_dscr": ev.minimum_dscr,
        "pass_equity": ev.passes["equity"], "pass_coverage": ev.passes["coverage"],
        "pass_loan_cap": ev.passes["loan_cap"], "financeable": ev.financeable,
    }


def test_excel_model_matches_python(tmp_path):
    scenarios = sample_scenarios()
    src = tmp_path / "in" / "model.xlsx"
    rows = build_model(src, scenarios)
    out = tmp_path / "out"
    subprocess.run([SOFFICE, "--headless", "--calc", "--convert-to", "xlsx", "--outdir", str(out), str(src)],
                   check=True, capture_output=True, timeout=180)
    ws = openpyxl.load_workbook(out / "model.xlsx", data_only=True)["Model"]

    mismatches = []
    for j, sc in enumerate(scenarios):
        expected = _python_rows(sc)
        for key, want in expected.items():
            got = ws.cell(row=rows[key], column=2 + j).value
            got = None if got == "" else got
            if isinstance(want, bool) or want is None:
                ok = got == want
            else:
                ok = got is not None and abs(float(got) - float(want)) <= max(0.01, abs(want) * 1e-9)
            if not ok:
                mismatches.append((sc["name"], key, want, got))
    assert not mismatches, mismatches

    # The scenarios cover both outcomes.
    outcomes = {ws.cell(row=rows["financeable"], column=2 + j).value for j in range(len(scenarios))}
    assert outcomes == {True, False}


def test_every_calculated_row_is_compared():
    from bizwave_preloi.finance.excel_model import ROW_KEYS, _ROWS
    calculated = {k for k, _, kind in _ROWS if kind not in ("input", "section")}
    assert calculated == set(_python_rows(sample_scenarios()[0]))
    assert set(ROW_KEYS) >= calculated
