"""Add-back classification: the rules table first, Claude only for leftovers, CPA for the rest."""
from datetime import datetime, timezone
from decimal import Decimal as D

import pytest

from bizwave_preloi.classify import classify_addbacks, match_rule, normalize
from bizwave_preloi.classify.addbacks import ClaudePick, ClaudePicks
from bizwave_preloi.ops import RunLog
from bizwave_preloi.schemas import AddBack, Override


@pytest.mark.parametrize("description, rule_id", [
    ("Depreciation", "depreciation"),
    ("Depreciation - owner vehicle", "depreciation"),
    ("Amortization of loan costs", "amortization"),
    ("Interest expense", "interest_expense"),
    ("Interest income", "gains_other_income"),
    ("Income tax expense", "income_taxes"),
    ("Payroll taxes", None),
    ("PPP loan forgiveness", "government_support"),
    ("ERC refund", "government_support"),
    ("Gain on sale of equipment", "gains_other_income"),
    ("One-time revenue from storm cleanup contract", "one_time_revenue"),
    ("Pro forma rent savings", "pro_forma"),
    ("Expected price increase", "pro_forma"),
    ("Cash sales not recorded", "cash_unreported"),
    ("COVID cleaning costs", "covid_costs"),
    ("Owner's payroll taxes", "owner_payroll_taxes"),
    ("Health insurance - owner & spouse", "owner_health_insurance"),
    ("Owner 401(k) contribution", "owner_retirement"),
    ("Life insurance", "owner_life_insurance"),
    ("Owner's auto lease", "owner_vehicle"),
    ("Personal auto expense", "owner_vehicle"),
    ("Owner cell phone", "owner_phone"),
    ("Meals & entertainment - personal", "owner_travel_meals"),
    ("Country club dues", "owner_travel_meals"),
    ("Wife's salary (does not work in business)", "family_payroll"),
    ("Officer compensation", "owner_salary"),
    ("Wages - owner", "owner_salary"),
    ("Owner's salary in excess of market", "owner_salary"),
    ("Personal expenses", "owner_personal_unspecified"),
    ("Charitable contributions", "charitable"),
    ("Legal fees - sale of business", "transaction_costs"),
    ("Business broker retainer", "transaction_costs"),
    ("One-time legal settlement", "legal_litigation"),
    ("Rent paid to owner's LLC above market", "related_party"),
    ("Management fees to parent", "related_party"),
    ("Non-recurring repairs", "major_repairs"),
    ("Roof replacement", "major_repairs"),
    ("Bad debt write-off", "write_offs"),
    ("Website redesign (one-time)", "one_time_project"),
    ("Startup costs - second location", "one_time_project"),
    ("Severance", "one_time_project"),
    ("Miscellaneous", None),
])
def test_rule_table(description, rule_id):
    m = match_rule(description)
    assert (m.rule_id if m else None) == rule_id


def test_normalize():
    assert normalize("Owner’s Auto & Fuel (personal)") == "owners auto and fuel personal"
    assert normalize("401(k)") == "401 k"


def _ab(id, description, amount="10000"):
    return AddBack(id=id, description=description, amounts={"FY2024": D(amount)})


def test_rules_set_the_lender_view_and_support():
    report = classify_addbacks([_ab("a1", "Officer compensation")])
    a = report.addbacks[0]
    assert (a.rule_id, a.classified_by, a.confidence, a.lender_view) == ("owner_salary", "rule", 1.0,
                                                                          "needs_support")
    assert "Owner W-2 or K-1 for each year" in a.support_required
    assert report.by_rule == ["a1"] and not report.for_cpa


def test_no_llm_mode_leaves_unmatched_for_the_cpa(monkeypatch, tmp_path):
    monkeypatch.setenv("BIZWAVE_NO_LLM", "1")
    log = RunLog(tmp_path / "log.jsonl")
    report = classify_addbacks([_ab("a1", "Officer compensation"), _ab("a2", "Misc adjustments")],
                               runlog=log, deal_id="test-deal")
    assert report.by_rule == ["a1"] and report.for_cpa == ["a2"]
    assert report.addbacks[1].lender_view is None
    assert [r["event"] for r in log.records()] == ["llm_skipped"]


def test_claude_picks_a_row_and_the_table_rates_it(fake_transport, runlog):
    transport = fake_transport(ClaudePicks(picks=[
        ClaudePick(addback_id="a2", rule_id="owner_travel_meals", confidence=0.9, reason="Spouse trip"),
        ClaudePick(addback_id="a3", rule_id="owner_salary", confidence=0.5, reason="Unclear"),
        ClaudePick(addback_id="a4", rule_id="made_up_rule", confidence=0.99, reason="?"),
    ]))
    addbacks = [_ab("a1", "Officer compensation"), _ab("a2", "Hawaii trip w/ spouse"),
                _ab("a3", "Jim's stuff"), _ab("a4", "Adjustment 7"), _ab("a5", "Other")]
    report = classify_addbacks(addbacks, transport=transport, runlog=runlog)

    assert len(transport.calls) == 1                            # one batched call
    sent = transport.calls[0]["content"]
    assert "Hawaii trip" in sent and "10000" not in sent        # descriptions only, no amounts
    assert "Officer compensation" not in sent                   # rule matches never go to Claude

    a2 = report.addbacks[1]
    assert (a2.rule_id, a2.classified_by, a2.confidence) == ("owner_travel_meals", "claude", 0.9)
    assert a2.lender_view == "needs_support"                    # from the table, not from Claude
    assert report.by_claude == ["a2"]
    assert report.for_cpa == ["a3", "a4", "a5"]
    assert {r["addback_id"] for r in report.claude_rejected} == {"a3", "a4"}
    assert report.addbacks[2].lender_view is None


def test_cpa_classification_is_never_overwritten(fake_transport, runlog):
    cpa = _ab("a1", "Officer compensation").model_copy(update={
        "rule_id": "family_payroll", "classified_by": "cpa", "lender_view": "likely_rejected"})
    report = classify_addbacks([cpa], transport=fake_transport(ClaudePicks(picks=[])), runlog=runlog)
    assert report.addbacks[0].rule_id == "family_payroll"
    assert report.addbacks[0].lender_view == "likely_rejected"


def test_override_wins_and_needs_a_reason():
    a = _ab("a1", "Officer compensation").model_copy(update={"lender_view": "needs_support"})
    a.override = Override(lender_view="likely_accepted", reason="W-2s provided for 2023-24", by="Chan",
                          at=datetime(2026, 11, 18, tzinfo=timezone.utc))
    assert a.effective_view == "likely_accepted"
    with pytest.raises(ValueError):
        Override(lender_view="likely_accepted", reason="ok", by="Chan", at=datetime.now(timezone.utc))
