"""Footing checks on a synthetic CIM income statement (no client data)."""
from datetime import date
from decimal import Decimal as D

import pytest

from bizwave_preloi.schemas import AddBack, LineItem, Period, ReadMethod, SourceRef, Statement
from bizwave_preloi.validate import check_bridge, check_statement

P = [Period(label="FY2023", kind="fiscal_year", end=date(2023, 12, 31), months=12),
     Period(label="FY2024", kind="fiscal_year", end=date(2024, 12, 31), months=12)]


def line(id, label, values, kind="account", section=None, parent=None, calc_kind=None, page=7):
    return LineItem(id=id, label=label, kind=kind, section=section, parent=parent, calc_kind=calc_kind,
                    values={k: (None if v is None else D(str(v))) for k, v in values.items()},
                    sources={k: SourceRef(document="cim.pdf", page=page, method=ReadMethod.TEXT_LAYER)
                             for k in values})


def statement(**overrides):
    lines = {
        "rev": line("rev", "Revenue", {"FY2023": 1_000_000, "FY2024": 1_200_000}, section="Income"),
        "mat": line("mat", "Materials", {"FY2023": 300_000, "FY2024": 360_000}, section="Cost of Goods Sold",
                    parent="cogs"),
        "lab": line("lab", "Direct labor", {"FY2023": 100_000, "FY2024": 120_000}, section="Cost of Goods Sold",
                    parent="cogs"),
        "cogs": line("cogs", "Total cost of sales", {"FY2023": 400_000, "FY2024": 480_000}, kind="subtotal"),
        "gp": line("gp", "Gross profit", {"FY2023": 600_000, "FY2024": 720_000}, kind="calculated",
                   calc_kind="gross_profit"),
        "rent": line("rent", "Rent", {"FY2023": 60_000, "FY2024": 60_000}, section="Expense", parent="opex"),
        "wages": line("wages", "Office wages", {"FY2023": 200_000, "FY2024": 230_000}, section="Expense",
                      parent="opex"),
        "util": line("util", "Utilities", {"FY2023": 15_000, "FY2024": 18_000}, section="Expense", parent="opex"),
        "opex": line("opex", "Total operating expenses", {"FY2023": 275_000, "FY2024": 308_000}, kind="subtotal"),
        "oi": line("oi", "Operating income", {"FY2023": 325_000, "FY2024": 412_000}, kind="calculated",
                   calc_kind="net_ordinary_income"),
        "int": line("int", "Interest expense", {"FY2023": 25_000, "FY2024": 20_000}, section="Other Expense"),
        "ni": line("ni", "Net income", {"FY2023": 300_000, "FY2024": 392_000}, kind="calculated",
                   calc_kind="net_income", page=8),
    }
    lines.update(overrides)
    return Statement(kind="income_statement", periods=P, lines=list(lines.values()))


def test_a_clean_statement_foots():
    report = check_statement(statement())
    assert report.ok
    assert not report.failures and not report.watches
    subtotal = [r for r in report.results if r.check == "subtotal"]
    ladder = [r for r in report.results if r.check == "ladder"]
    assert len(subtotal) == 4 and all(r.passed for r in subtotal)      # 2 subtotals x 2 years
    assert len(ladder) == 6 and all(r.passed for r in ladder)          # 3 ladder lines x 2 years


def test_subtotal_off_by_more_than_rounding_fails_with_its_source_page():
    st = statement(opex=line("opex", "Total operating expenses", {"FY2023": 275_000, "FY2024": 318_000},
                             kind="subtotal", page=9))
    failures = check_statement(st).failures
    sub = [r for r in failures if r.check == "subtotal"]
    assert len(sub) == 1
    assert sub[0].period == "FY2024" and sub[0].difference == pytest.approx(10_000)
    assert sub[0].sources[0].page == 9


def test_rounding_within_tolerance_passes():
    # Three parts summed: tolerance 1 + 0.5 x 3 = 2.5 dollars.
    st = statement(opex=line("opex", "Total operating expenses", {"FY2023": 275_002, "FY2024": 308_000},
                             kind="subtotal"))
    assert check_statement(st).ok


def test_misprinted_net_income_fails_the_ladder():
    st = statement(ni=line("ni", "Net income", {"FY2023": 300_000, "FY2024": 402_000}, kind="calculated",
                           calc_kind="net_income"))
    failures = [r for r in check_statement(st).failures if r.check == "ladder"]
    assert [(r.line_id, r.period) for r in failures] == [("ni", "FY2024")]
    assert failures[0].expected == pytest.approx(392_000)


def test_line_without_a_section_stops_the_ladder_check():
    st = statement(util=line("util", "Utilities", {"FY2023": 15_000, "FY2024": 18_000}, parent="opex"))
    report = check_statement(st)
    ladder = [r for r in report.results if r.check == "ladder"]
    assert len(ladder) == 1 and ladder[0].passed is None and ladder[0].severity == "watch"
    assert "'Utilities'" in ladder[0].message


def test_opposite_sign_inside_a_section_is_a_watch():
    st = statement(util=line("util", "Utilities", {"FY2023": -15_000, "FY2024": 18_000}, section="Expense",
                             parent="opex"))
    signs = [r for r in check_statement(st).results if r.check == "sign"]
    assert [(r.line_id, r.period) for r in signs] == [("util", "FY2023")]


def test_missing_value_is_reported():
    st = statement(int=line("int", "Interest expense", {"FY2023": 25_000, "FY2024": None},
                            section="Other Expense"))
    gaps = [r for r in check_statement(st).results if r.check == "gap"]
    assert gaps and gaps[0].line_id == "int"


def test_fiscal_years_not_a_year_apart_is_a_watch():
    periods = [Period(label="FY2023", kind="fiscal_year", end=date(2023, 6, 30), months=12),
               Period(label="FY2024", kind="fiscal_year", end=date(2024, 12, 31), months=12)]
    st = Statement(kind="income_statement", periods=periods, lines=statement().lines)
    assert any(r.check == "periods" for r in check_statement(st).watches)


def test_schema_refuses_values_for_unknown_periods():
    with pytest.raises(ValueError, match="unknown period"):
        Statement(kind="income_statement", periods=P[:1],
                  lines=[line("rev", "Revenue", {"FY2023": 1, "FY2024": 2}, section="Income")])


def test_sellers_bridge_ties_or_fails():
    addbacks = [AddBack(id="a1", description="Owner salary", amounts={"FY2024": D("150000")}),
                AddBack(id="a2", description="PPP forgiveness", amounts={"FY2024": D("-40000")})]
    ok = check_bridge({"FY2024": D("392000")}, addbacks, {"FY2024": D("502000")})
    assert ok[0].passed is True
    bad = check_bridge({"FY2024": D("392000")}, addbacks, {"FY2024": D("542000")})
    assert bad[0].passed is False and bad[0].difference == pytest.approx(40_000)
    missing = check_bridge({}, addbacks, {"FY2024": D("502000")})
    assert missing[0].passed is None
