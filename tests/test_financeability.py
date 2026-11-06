"""SOP 50 10 8.1 financeability. Expected values are worked by hand in the comments; the same
scenarios are recalculated in Excel by test_excel_parity.py."""
from datetime import date

import pytest

from bizwave_preloi.finance import (Earnings, Structure, default_sba_rate, evaluate,
                                    max_financeable_price, sensitivity)

ANNUAL_PER_DOLLAR_9_5_10Y = 15_527.71 / 100_000        # -PMT(0.095/12,120,1)*12


@pytest.fixture
def base():
    """$2.0M price, $100K working capital, $50K closing, $150K buyer cash, 5% seller note on full standby."""
    return (Earnings(last_fy=500_000, prior_fy=450_000),
            Structure(buyer_cash=150_000, working_capital=100_000, closing_costs=50_000,
                      seller_note_standby_pct=0.05, sba_rate=0.095))


def test_base_case_every_figure(base):
    e, s = base
    ev = evaluate(2_000_000, e, s)
    assert ev.project_cost == 2_150_000                    # 2.0M + 100K + 50K
    assert ev.required_injection == pytest.approx(215_000)  # 10% of project cost
    assert ev.seller_note_standby == pytest.approx(100_000) # 5% of price
    assert ev.limited_sources_cap == pytest.approx(107_500) # half of the required injection
    assert ev.limited_sources_counted == pytest.approx(100_000)
    assert ev.countable_equity == pytest.approx(250_000)
    assert ev.equity_shortfall == 0
    assert ev.sba_loan == pytest.approx(1_900_000)          # 2.15M - 150K - 100K
    assert ev.debt_service.sba == pytest.approx(295_026.43, abs=0.01)
    assert ev.dscr["last_fiscal_year"] == pytest.approx(500_000 / 295_026.43, abs=1e-6)
    assert ev.dscr["two_year_average"] == pytest.approx(475_000 / 295_026.43, abs=1e-6)
    assert ev.basis_used == "two_year_average"              # lower_of picks the weaker basis
    assert ev.minimum_dscr == 1.25
    assert ev.passes == {"equity": True, "coverage": True, "loan_cap": True}
    assert ev.financeable and not ev.lender_qoe_required


def test_limited_sources_count_for_at_most_half_the_injection():
    # Required 120K; standby 15% = 180K + minority 50K offered = 230K, only 60K counts.
    s = Structure(buyer_cash=100_000, minority_equity=50_000, seller_note_standby_pct=0.15, sba_rate=0.095)
    ev = evaluate(1_200_000, Earnings(last_fy=300_000), s)
    assert ev.required_injection == pytest.approx(120_000)
    assert ev.limited_sources_offered == pytest.approx(230_000)
    assert ev.limited_sources_counted == pytest.approx(60_000)
    assert ev.countable_equity == pytest.approx(160_000)
    assert any("only the capped amount counts" in n for n in ev.notes)


def test_equity_shortfall_fails_the_deal():
    # 10% of 1.5M = 150K required; 100K cash and nothing else.
    ev = evaluate(1_500_000, Earnings(last_fy=900_000), Structure(buyer_cash=100_000, sba_rate=0.095))
    assert ev.equity_shortfall == pytest.approx(50_000)
    assert ev.passes["equity"] is False and ev.passes["coverage"] is True
    assert not ev.financeable


def test_amortizing_seller_note_is_debt_not_equity():
    # 20% note at 0% over 12 years: counted in coverage at 10 years -> 160K / 10 = 16K a year.
    s = Structure(transaction_type="owner_buyout", buyer_cash=80_000, sba_rate=0.1025,
                  seller_note_amortizing_pct=0.2, seller_note_rate=0.0, seller_note_term_years=12)
    ev = evaluate(800_000, Earnings(last_fy=220_000, prior_fy=200_000), s)
    assert ev.seller_note_amortizing == pytest.approx(160_000)
    assert ev.debt_service.seller_note == pytest.approx(16_000)
    assert ev.limited_sources_counted == 0
    assert ev.sba_loan == pytest.approx(560_000)            # 800K - 80K - 160K
    assert any("10-year amortization" in n for n in ev.notes)


def test_owner_buyout_injection_is_on_purchase_price():
    s = Structure(transaction_type="owner_buyout", buyer_cash=80_000, working_capital=200_000, sba_rate=0.1)
    ev = evaluate(800_000, Earnings(last_fy=300_000), s)
    assert ev.injection_base == "purchase_price"
    assert ev.required_injection == pytest.approx(80_000)    # not 10% of 1.0M project cost
    assert any("may reduce the injection" in n for n in ev.notes)


def test_sba_term_is_capped_at_ten_years():
    s15 = Structure(buyer_cash=100_000, sba_rate=0.095, sba_term_years=15)
    s10 = Structure(buyer_cash=100_000, sba_rate=0.095, sba_term_years=10)
    e = Earnings(last_fy=400_000)
    assert evaluate(1_000_000, e, s15).debt_service.sba == pytest.approx(
        evaluate(1_000_000, e, s10).debt_service.sba)
    assert any("capped at 10 years" in n for n in evaluate(1_000_000, e, s15).notes)


def test_lender_deductions_come_off_earnings():
    s = Structure(buyer_cash=150_000, sba_rate=0.095, replacement_salary=120_000, capex_reserve=25_000,
                  income_taxes=5_000)
    ev = evaluate(1_000_000, Earnings(last_fy=500_000, prior_fy=400_000), s)
    assert ev.cash_available == {"last_fiscal_year": 350_000, "two_year_average": 300_000}


@pytest.mark.parametrize("policy, expected", [
    ("lower_of", "two_year_average"), ("higher_of", "last_fiscal_year"),
    ("last_fiscal_year", "last_fiscal_year"), ("two_year_average", "two_year_average")])
def test_basis_policy(policy, expected):
    s = Structure(buyer_cash=150_000, sba_rate=0.095, basis_policy=policy)
    ev = evaluate(1_000_000, Earnings(last_fy=500_000, prior_fy=400_000), s)
    assert ev.basis_used == expected
    assert ev.dscr_used == ev.dscr[expected]


def test_two_year_average_without_prior_year_falls_back_and_says_so():
    s = Structure(buyer_cash=150_000, sba_rate=0.095, basis_policy="two_year_average")
    ev = evaluate(1_000_000, Earnings(last_fy=500_000), s)
    assert ev.basis_used == "last_fiscal_year"
    assert ev.dscr["two_year_average"] is None
    assert any("no prior year" in n for n in ev.notes)


def test_business_expansion_uses_1_15():
    s = Structure(transaction_type="business_expansion", buyer_cash=100_000, sba_rate=0.095)
    ev = evaluate(1_000_000, Earnings(last_fy=400_000), s)
    assert ev.minimum_dscr == 1.15


def test_coverage_between_1_15_and_1_25_fails_an_acquisition():
    # Loan 900K -> DS 139,749.39; earnings 167,000 -> DSCR 1.195.
    s = Structure(buyer_cash=100_000, sba_rate=0.095)
    ev = evaluate(1_000_000, Earnings(last_fy=167_000), s)
    assert ev.debt_service.total == pytest.approx(900_000 * ANNUAL_PER_DOLLAR_9_5_10Y, abs=0.5)
    assert 1.15 < ev.dscr_used < 1.25
    assert ev.passes["coverage"] is False


def test_loan_over_the_7a_maximum_fails():
    s = Structure(buyer_cash=700_000, sba_rate=0.095)
    ev = evaluate(7_000_000, Earnings(last_fy=3_000_000), s)
    assert ev.sba_loan == pytest.approx(6_300_000)
    assert ev.passes["loan_cap"] is False and not ev.financeable


def test_lender_qoe_threshold():
    e, s = Earnings(last_fy=2_000_000), Structure(buyer_cash=400_000, sba_rate=0.095)
    assert evaluate(3_000_000, e, s).lender_qoe_required is True
    assert evaluate(2_999_999, e, s).lender_qoe_required is False
    buyout = Structure(transaction_type="owner_buyout", buyer_cash=400_000, sba_rate=0.095)
    assert evaluate(3_500_000, e, buyout).lender_qoe_required is False


def test_no_debt_service_passes_coverage():
    s = Structure(buyer_cash=1_000_000, sba_rate=0.095)
    ev = evaluate(900_000, Earnings(last_fy=100_000), s)
    assert ev.sba_loan == 0 and ev.dscr_used is None and ev.passes["coverage"]


def test_structure_rejects_notes_above_price():
    with pytest.raises(ValueError):
        Structure(buyer_cash=1, sba_rate=0.09, seller_note_standby_pct=0.6, seller_note_amortizing_pct=0.5)


def test_unverified_parameters_are_disclosed(base):
    e, s = base
    assert any("not yet been checked against the SOP text" in n for n in evaluate(2_000_000, e, s).notes)


# --------------------------------------------------------------------------- maximum price

def test_max_price_when_coverage_binds(base):
    # Cash 475,000 (two-year average) / 1.25 = 380,000 debt service -> loan 2,447,241;
    # loan = 0.95 x price -> price 2,576,043 -> 2,576,000 on the $1,000 grid.
    e, s = base
    m = max_financeable_price(e, s)
    assert m.max_price == 2_576_000
    assert m.binding_constraint == "coverage"
    assert m.at_max.financeable
    assert not evaluate(m.max_price + 1_000, e, s).financeable


def test_max_price_when_equity_binds():
    # Plenty of earnings; 100K cash covers 10% of at most 1.0M project cost.
    m = max_financeable_price(Earnings(last_fy=2_000_000), Structure(buyer_cash=100_000, sba_rate=0.095))
    assert m.max_price == 1_000_000
    assert m.binding_constraint == "equity"


def test_max_price_when_the_loan_cap_binds():
    # Huge earnings and cash: the 7(a) loan tops out at 5M -> price = 5M + cash.
    m = max_financeable_price(Earnings(last_fy=10_000_000), Structure(buyer_cash=1_000_000, sba_rate=0.095))
    assert m.max_price == 6_000_000
    assert m.binding_constraint == "loan_cap"


def test_no_financeable_price():
    m = max_financeable_price(Earnings(last_fy=-50_000), Structure(buyer_cash=10_000, working_capital=200_000,
                                                                   sba_rate=0.095))
    assert m.max_price is None and m.at_max is None
    assert m.binding_constraint == "coverage"


def test_sensitivity_to_an_earnings_miss(base):
    # 10% miss: 427,500 / 1.25 = 342,000 -> price 2,318,433; 20%: 380,000 / 1.25 -> 2,060,829.
    e, s = base
    rows = sensitivity(e, s, price=2_000_000)
    assert [r.earnings_miss for r in rows] == [0.0, 0.10, 0.20]
    assert [r.max_price for r in rows] == [2_576_000, 2_318_000, 2_060_000]
    assert all(r.financeable_at_price for r in rows)
    assert rows[1].dscr_used == pytest.approx(0.9 * rows[0].dscr_used)


def test_default_rate_warns_when_prime_is_stale():
    rate, warning = default_sba_rate(date(2026, 11, 6))
    assert rate == pytest.approx(0.095)                     # 6.75% + 2.75%
    assert warning and "days old" in warning
    assert default_sba_rate(date(2026, 8, 15))[1] is None
