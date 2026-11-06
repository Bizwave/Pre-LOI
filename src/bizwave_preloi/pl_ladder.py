"""Profit and loss definitions and formulas — the ONE place they live.

Copied from Bizwave_mvp_master `backend/utils/pl_calculations.py` (commit b935d5c, 4 Nov 2026)
without logic changes, so a Flash Review and a later BizWave QoE climb the same ladder.
Keep the two in step: a change here is a change there. The packet and decision references
below (D14, D17, D23 ...) point at the MVP repository's plan documents.

Original header (Packet 4):

Every profit figure in the product is a rung on the same ladder:

    section totals → Gross Profit → Net Ordinary Income → Net Other Income → Net Income
    → EBITDA (Net Income + interest, taxes, depreciation, amortization; Packet 6, D36)
    and the margins on revenue

The ladder takes plain numbers only. Each caller turns its own data — saved ledger lines,
an uploaded table, adjusted totals — into (section, amount) pairs, groups them with
`section_totals`, and climbs with `compute_pl`. The caller chooses the period; the rules
for missing sections and signs live here, so no caller can apply them differently.

Pure on purpose: no database, no Flask, no `period_helpers`, so anything can import it.
A guard in the Packet 4 gate fails on any new copy of these formulas outside this file.

Plans: .claude/plan/2026-10-21_packet4_pl_formulas_plan.md (data contract: §5)
       .claude/plan/2026-08-23_pl_ingestion_calculated_fields_plan.md (D14, D16, D17, D31, D34)
"""
import logging
from typing import Dict, Iterable, Mapping, Optional, Tuple

logger = logging.getLogger(__name__)

__all__ = [
    "SECTIONS", "CANONICAL_CATEGORIES", "normalize_category",
    "CALC_KINDS", "CALC_NAME_KINDS", "CALC_KIND_DERIVATIONS", "normalise_calc_label",
    "section_totals", "compute_pl",
    "ITDA_CATEGORIES", "itda_totals", "compute_itda", "ebitda", "margins",
]

# ======================================================================= definitions
# Config, not logic (CLAUDE.md §8) — extend here for other accounting packages' spellings.

# The five sections every real account belongs to (moved from gl_population_service, D4.2).
SECTIONS = (
    'Income', 'Cost of Goods Sold', 'Expense', 'Other Income', 'Other Expense',
)
CANONICAL_CATEGORIES = SECTIONS          # the long-standing name, kept for existing callers

_CATEGORY_SYNONYMS = {
    # → Income
    'revenue': 'Income', 'revenues': 'Income', 'sales': 'Income',
    'total income': 'Income', 'ordinary income': 'Income', 'income': 'Income',
    # → Cost of Goods Sold
    'cogs': 'Cost of Goods Sold', 'cost of sales': 'Cost of Goods Sold',
    'cost of goods sold': 'Cost of Goods Sold', 'cost of revenue': 'Cost of Goods Sold',
    'direct costs': 'Cost of Goods Sold', 'direct cost': 'Cost of Goods Sold',
    # → Expense
    'expense': 'Expense', 'expenses': 'Expense', 'operating expense': 'Expense',
    'operating expenses': 'Expense', 'opex': 'Expense', 'sg&a': 'Expense',
    'sga': 'Expense', 'general and administrative': 'Expense', 'overhead': 'Expense',
    # → Other Income
    'other income': 'Other Income', 'other revenues': 'Other Income',
    'non-operating income': 'Other Income', 'nonoperating income': 'Other Income',
    # → Other Expense
    'other expense': 'Other Expense', 'other expenses': 'Other Expense',
    'non-operating expense': 'Other Expense', 'nonoperating expense': 'Other Expense',
}

# The eight kinds of calculated line (moved from pl_ingest/_rules, D4.2).
CALC_KINDS = ("group_total", "gross_profit", "net_ordinary_income", "net_other_income",
              "net_income", "ebitda", "income_before_taxes", "unlabelled")

# Which tidy names mean which kind. Keys are already tidy (see normalise_calc_label).
CALC_NAME_KINDS: Dict[str, str] = {
    "gross profit": "gross_profit",
    "gross margin": "gross_profit",
    "net ordinary income": "net_ordinary_income",       # QuickBooks' wording
    "net operating income": "net_ordinary_income",      # the app's own wording
    "operating income": "net_ordinary_income",
    "operating profit": "net_ordinary_income",
    "net other income": "net_other_income",
    "net income": "net_income",
    "net profit": "net_income",
    "net loss": "net_income",
    "ebitda": "ebitda",
    "income before taxes": "income_before_taxes",
}

# The formula in words, for display (kind -> text). `net_ordinary_income` is the ladder's
# `operating_income` output (D4.4).
CALC_KIND_DERIVATIONS: Dict[str, Optional[str]] = {
    "group_total": "Sum of the accounts in its group",
    "gross_profit": "Income − Cost of Goods Sold",
    "net_ordinary_income": "Gross Profit − Expense",
    "net_other_income": "Other Income − Other Expense",
    "net_income": "Net Ordinary Income + Net Other Income",
    "ebitda": "Net Income + Interest + Taxes + Depreciation + Amortization",
    "income_before_taxes": "Net Income + Income Taxes",
    "unlabelled": None,
}


def normalize_category(raw_value) -> Tuple[Optional[str], Optional[str], bool]:
    """Normalize an uploaded category label to the canonical vocabulary.

    Returns (canonical, raw, mapped): canonical is what consumers should store;
    raw is the original wording (for dim_account.category_raw); mapped is False
    for values the map doesn't know — those PASS THROUGH unchanged with a Rule-12
    warning (never silently dropped or miscategorized)."""
    if raw_value is None:
        return None, None, True
    raw = str(raw_value).strip()
    if not raw or raw.lower() == 'nan':
        return None, None, True
    if raw in CANONICAL_CATEGORIES:
        return raw, raw, True
    mapped = _CATEGORY_SYNONYMS.get(raw.lower())
    if mapped:
        return mapped, raw, True
    logger.warning(f"D4: unmapped category '{raw}' — stored as-is; consumers expect "
                   f"one of {CANONICAL_CATEGORIES} (Rule 12)")
    return raw, raw, False


def normalise_calc_label(label) -> str:
    """Tidy a name for matching against CALC_NAME_KINDS: trim, ignore case, squeeze
    spaces, drop a trailing colon. Account numbers are NOT stripped."""
    if not isinstance(label, str):
        return ""
    return " ".join(label.casefold().split()).rstrip(":").strip()


# ======================================================================== grouping

def section_totals(pairs: Iterable[Tuple[Optional[str], object]]) -> Dict:
    """Add up (section, amount) pairs into the five section totals.

    Amounts may be float, int or Decimal; results are plain float. All five sections are
    always present (0.0 when absent). Anything that is not one of the five — including
    None — is NOT added to any section; it is returned under "unmapped" and logged, so a
    caller can ask about it instead of losing it silently (D4.7).
    """
    totals: Dict = {s: 0.0 for s in SECTIONS}
    unmapped: Dict = {}
    for section, amount in pairs:
        value = float(amount or 0)
        if section in totals:
            totals[section] += value
        else:
            unmapped[section] = unmapped.get(section, 0.0) + value
    if unmapped:
        logger.warning("[pl_calculations] left out of every section (not one of %s): %s",
                       SECTIONS, unmapped)
    totals["unmapped"] = unmapped
    return totals


# ====================================================================== the ladder

def compute_pl(sections: Mapping) -> Dict[str, float]:
    """The ladder down to Net Income, from the five section totals.

    Sign rule (roadmap D17, as the official engine has always applied it): Cost of Goods
    Sold, Expense and Other Expense totals are made positive; Income and Other Income are
    kept as stored. A missing section counts as zero. No rounding.
    """
    def total(name):
        return float(sections.get(name) or 0)

    revenue = total('Income')
    cogs = abs(total('Cost of Goods Sold'))
    expense = abs(total('Expense'))
    other_income = total('Other Income')
    other_expense = abs(total('Other Expense'))

    gross_profit = revenue - cogs
    operating_income = gross_profit - expense
    net_other = other_income - other_expense
    net_income = operating_income + net_other
    return {
        'revenue': revenue,
        'cogs': cogs,
        'gross_profit': gross_profit,
        'expense': expense,
        'operating_income': operating_income,
        'other_income': other_income,
        'other_expense': other_expense,
        'net_other': net_other,
        'net_income': net_income,
    }


# ================================================================ the EBITDA rung (Packet 6)

# The add-back tags, in the words every stored tag uses (ebitda_account_tag.ebitda_category).
ITDA_CATEGORIES = ("Depreciation", "Amortization", "Interest Expense", "Interest Income",
                   "Income Taxes")


def itda_totals(pairs: Iterable[Tuple[Optional[str], object]]) -> Dict[str, float]:
    """Add up (add-back tag, amount) pairs into the five tag totals (0.0 when absent).
    A pair whose tag is not one of ITDA_CATEGORIES is left out and logged."""
    totals: Dict[str, float] = {c: 0.0 for c in ITDA_CATEGORIES}
    left_out: Dict = {}
    for tag, amount in pairs:
        if tag in totals:
            totals[tag] += float(amount or 0)
        else:
            left_out[tag] = left_out.get(tag, 0.0) + float(amount or 0)
    if left_out:
        logger.warning("[pl_calculations] add-back amounts with no known tag left out: %s", left_out)
    return totals


def compute_itda(totals: Mapping) -> Dict[str, float]:
    """Interest, taxes, depreciation and amortization from the five tag totals.

    Sign rule (the official engine's, D17): depreciation, interest expense, taxes and
    amortization are made positive; interest income is kept as stored and nets against
    interest expense."""
    def total(name):
        return float(totals.get(name) or 0)

    depreciation = abs(total('Depreciation'))
    interest_expense = abs(total('Interest Expense'))
    interest_income = total('Interest Income')
    taxes = abs(total('Income Taxes'))
    amortization = abs(total('Amortization'))
    interest_net = interest_expense - interest_income
    return {
        'depreciation': depreciation,
        'interest_expense': interest_expense,
        'interest_income': interest_income,
        'interest_net': interest_net,
        'taxes': taxes,
        'amortization': amortization,
        'total': interest_net + taxes + depreciation + amortization,
    }


def ebitda(net_income: float, itda: Mapping) -> float:
    """EBITDA = Net Income + interest, taxes, depreciation and amortization (D23)."""
    return float(net_income or 0) + float(itda.get('total') or 0)


def margins(revenue: float, gross_profit: float, operating_income: float,
            ebitda_value: float, net_income: float) -> Dict[str, Optional[float]]:
    """Margins as fractions of revenue. None (not 0) when revenue is 0 — no silent zero."""
    if not revenue:
        logger.warning("[pl_calculations] revenue is 0 — margins not available")
        return {"gross": None, "operating": None, "ebitda": None, "net": None}
    return {
        "gross": gross_profit / revenue,
        "operating": operating_income / revenue,
        "ebitda": ebitda_value / revenue,
        "net": net_income / revenue,
    }
