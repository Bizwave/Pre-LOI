"""The rules files load, are internally consistent, and hold the values the plan relies on."""
import re

import pytest
import yaml

from bizwave_preloi.rules import (RULES_DIR, addback_rules, flag_rules, sba_params, taxonomy,
                                  validation)

# Subtypes in the MVP's backend/services/qoe/qa_adjustments_catalog.py (commit b935d5c).
MVP_SUBTYPES = {
    "out_of_period_trueup", "one_off_legal_fees", "gain_loss_on_disposal", "insurance_proceeds",
    "severance", "capitalized_labor", "bad_debt_normalization", "divested_operations",
    "shared_services_allocation", "standalone_costs", "lease_presentation", "stock_based_compensation",
    "restructuring_savings", "fx_translational", "deal_costs", "erp_implementation",
    "one_time_consulting", "litigation_settlement", "grant_income", "contract_exit_costs",
    "unrealized_fv_marks", "impairment", "amortization_classification", "straight_line_rent",
    "pension_opeb", "aro_accretion", "director_sbc", "fx_remeasurement", "inventory_cost_variance",
    "one_time_write_off", "bonus_accrual_normalization", "pto_accrual_trueup", "warranty_reserve_trueup",
    "self_insurance_reserve", "rebates_returns_trueup", "commission_timing", "major_maintenance",
    "year_end_cleanup", "rev_rec_policy_change", "cutoff_correction", "interest_income_misclass",
    "other_income_misclass", "depreciation_classification", "error_correction",
    "mgmt_statutory_reconciling", "acquisition_runrate", "customer_loss", "price_reset",
    "tsa_standalone", "owner_comp",
}


def test_every_rules_file_loads():
    assert taxonomy().categories
    assert addback_rules().rules
    assert sba_params().coverage.minimum_dscr
    assert flag_rules().rules
    assert validation().tolerance.base >= 0


def test_taxonomy_matches_the_mvp_codes():
    assert set(taxonomy().categories) == {"A", "NR", "EM", "NO", "AO", "PF", "PM", "OT"}


def test_category_codes_are_strings_not_yaml_booleans():
    # Unquoted NO in YAML 1.1 is False. Both files must keep the codes as text.
    raw = yaml.safe_load((RULES_DIR / "taxonomy.yaml").read_text())
    assert all(isinstance(k, str) for k in raw["categories"])
    raw = yaml.safe_load((RULES_DIR / "addbacks.yaml").read_text())
    assert all(isinstance(r["category"], str) for r in raw["rules"])


def test_addback_table_size_and_ids():
    rules = addback_rules().rules
    assert 20 <= len(rules) <= 30
    ids = [r.id for r in rules]
    assert len(ids) == len(set(ids))


def test_addback_rows_point_at_real_mvp_subtypes():
    bad = {r.id: r.mvp_subtype for r in addback_rules().rules
           if r.mvp_subtype is not None and r.mvp_subtype not in MVP_SUBTYPES}
    assert not bad


def test_every_addback_row_is_usable_on_review():
    for r in addback_rules().rules:
        assert r.lender_note.strip(), r.id
        if r.lender_view != "likely_rejected":
            assert r.seller_question, f"{r.id}: needs a question for the seller"
        for p in r.patterns + r.exclude:
            re.compile(p)


def test_pro_forma_items_are_rejected_under_sop_8_1():
    assert addback_rules().by_id("pro_forma").lender_view == "likely_rejected"
    assert sba_params().coverage.projections_allowed is False


def test_sba_values_the_calculator_relies_on():
    p = sba_params()
    assert p.coverage.minimum_dscr["initial_acquisition"] == 1.25
    assert p.coverage.minimum_dscr["business_expansion"] == 1.15
    assert set(p.coverage.earnings_bases) == {"last_fiscal_year", "two_year_average"}
    assert p.equity.injection_share_of_project_cost == 0.10
    assert p.equity.limited_sources_max_share_of_required_injection == 0.50
    assert p.equity.injection_base["owner_buyout"] == "purchase_price"
    assert p.loan.business_max_amortization_years == 10
    assert p.coverage.non_standby_seller_debt_max_amortization_years == 10
    assert p.loan.max_7a_loan == 5_000_000
    assert p.lender_qoe.required_at_purchase_price == 3_000_000
    assert set(p.equity.injection_base) == set(p.coverage.minimum_dscr)


def test_flag_metrics_are_all_defined():
    fr = flag_rules()
    assert {r.metric for r in fr.rules} <= set(fr.metrics)
    assert any(r.blocks_delivery for r in fr.rules if r.id == "footing_failure")


def test_flag_coverage_threshold_matches_sba_minimum():
    coverage = next(r for r in flag_rules().rules if r.id == "coverage_thin")
    assert coverage.serious == sba_params().coverage.minimum_dscr["initial_acquisition"]


def test_a_broken_rule_file_is_refused(tmp_path, monkeypatch):
    from bizwave_preloi import rules as rules_module
    bad = yaml.safe_load((RULES_DIR / "addbacks.yaml").read_text())
    bad["rules"][0]["patterns"] = ["(unclosed"]
    (tmp_path / "addbacks.yaml").write_text(yaml.safe_dump(bad))
    (tmp_path / "taxonomy.yaml").write_text((RULES_DIR / "taxonomy.yaml").read_text())
    monkeypatch.setattr(rules_module, "RULES_DIR", tmp_path)
    rules_module.reload()
    with pytest.raises(ValueError, match="does not compile"):
        rules_module.addback_rules()


def test_intake_document_kinds_match_the_database():
    """rules.DocumentKind lists the documents.kind values (db/models.py); the two must not drift."""
    import typing

    from bizwave_preloi.db.models import Document
    from bizwave_preloi.rules import DocumentKind
    assert set(typing.get_args(DocumentKind)) == set(Document.__table__.c.kind.type.enums)


@pytest.mark.parametrize("name, kind", [
    ("Project Falcon CIM.pdf", "cim"), ("2024 P&L.pdf", "p_and_l"), ("Profit_and_Loss.pdf", "p_and_l"),
    ("Balance-Sheet 2024.pdf", "balance_sheet"), ("Add-backs schedule.xlsx", "recast"),
    ("decimal notes.pdf", "other"), ("deck.pdf", "other"),
])
def test_intake_kinds_from_file_names(name, kind):
    from bizwave_preloi.rules import intake_rules
    assert intake_rules().kind_for(name) == kind
