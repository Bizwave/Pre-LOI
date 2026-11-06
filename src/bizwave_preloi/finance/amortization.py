"""Loan payment arithmetic. Matches Excel: annual_debt_service(p, r, n) == -PMT(r/12, n*12, p) * 12."""
from __future__ import annotations


def monthly_payment(principal: float, annual_rate: float, years: float) -> float:
    """Level monthly payment that repays `principal` over `years` at `annual_rate` (0.095 = 9.5%)."""
    if principal <= 0:
        return 0.0
    if years <= 0:
        raise ValueError("years must be positive")
    n = round(years * 12)
    r = annual_rate / 12.0
    if r == 0:
        return principal / n
    return principal * r / (1.0 - (1.0 + r) ** -n)


def annual_debt_service(principal: float, annual_rate: float, years: float) -> float:
    """Twelve level monthly payments."""
    return 12.0 * monthly_payment(principal, annual_rate, years)


def principal_supported(annual_payment: float, annual_rate: float, years: float) -> float:
    """The largest principal that `annual_payment` repays over `years` (Excel: PV(r/12, n*12, -pmt/12))."""
    if annual_payment <= 0:
        return 0.0
    n = round(years * 12)
    r = annual_rate / 12.0
    pmt = annual_payment / 12.0
    if r == 0:
        return pmt * n
    return pmt * (1.0 - (1.0 + r) ** -n) / r
