"""Loan arithmetic. Expected values match Excel's -PMT(rate/12, years*12, principal)*12
(also checked live by test_excel_parity.py)."""
import pytest

from bizwave_preloi.finance import annual_debt_service, monthly_payment, principal_supported


def test_matches_the_sop_summary_example():
    # Summary example: a $2.3M loan at 9.50% over 10 years is "about $357,000" a year.
    assert annual_debt_service(2_300_000, 0.095, 10) == pytest.approx(357_137.26, abs=0.01)


def test_each_100k_costs_about_15_5k_a_year():
    # Summary: "each $100,000 ... cuts annual debt service by roughly $15,500".
    assert annual_debt_service(100_000, 0.095, 10) == pytest.approx(15_527.71, abs=0.01)


def test_monthly_payment():
    assert monthly_payment(1_000_000, 0.10, 10) == pytest.approx(13_215.07, abs=0.01)


def test_zero_principal_and_zero_rate():
    assert annual_debt_service(0, 0.095, 10) == 0
    assert annual_debt_service(-5, 0.095, 10) == 0
    assert annual_debt_service(120_000, 0.0, 10) == pytest.approx(12_000)


def test_principal_supported_inverts_the_payment():
    payment = annual_debt_service(1_234_567, 0.0875, 10)
    assert principal_supported(payment, 0.0875, 10) == pytest.approx(1_234_567, abs=0.01)
    assert principal_supported(12_000, 0.0, 10) == pytest.approx(120_000)
    assert principal_supported(0, 0.09, 10) == 0


def test_years_must_be_positive():
    with pytest.raises(ValueError):
        monthly_payment(100_000, 0.09, 0)
