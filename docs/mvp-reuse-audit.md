# MVP reuse audit

Audit of `Bizwave/Bizwave_mvp_master` at commit `b935d5c` (merge of `sung_working_session`, 4 Nov 2026),
done 6 Nov 2026 for the Flash Review build. Rule: copy what fits, never import across repositories,
record the source at the top of every copied file.

## Headline findings

1. **The MVP has no PDF ingestion.** Its reader (`backend/services/data_ingest/pl_ingest/`) reads
   QuickBooks-style Excel P&L sheets only, and no PDF or OCR library is imported anywhere in the
   backend. Module 4's "Tier 2 PDF/OCR" was not built. PDF ingestion (Day 3) is new work; the
   MVP contributes patterns, not code.
2. **The MVP's SBA code predates SOP 50 10 8.1 and should not be copied.** See "Do not copy" below.
3. **The add-back knowledge is the most valuable reusable asset**: the reviewer-approved taxonomy,
   the 50-item adjustment catalog, the keyword lists, the account-type playbooks and the
   screening questions. They are written for mid-market QoE on ledger data; the Flash Review needs
   an SMB, lender-lens version, so they were mined into `rules/addbacks.yaml` rather than copied
   whole.

## Copied now

| MVP source | Here | Why |
|---|---|---|
| `backend/utils/pl_calculations.py` (pure, 249 lines) | `src/bizwave_preloi/pl_ladder.py` | The one P&L ladder (sections, synonyms, Gross Profit → Net Income → EBITDA, sign rules). Copied unchanged so a Flash Review and a later QoE compute the same figures. |
| `backend/services/report/excel/xlsx_style.py` | `src/bizwave_preloi/outputs/xlsx_style.py` | Databook look and feel (`SheetWriter`, `$000` scaling, header and total styles). Used by the Excel model now and the Flash Review workbook on Day 7. |
| `backend/services/qoe/qa_taxonomy.py` (`QA_CATEGORIES`) | `rules/taxonomy.yaml` | Same eight Level-1 codes (A, NR, EM, NO, AO, PF, PM, OT), so add-backs keep their category when a deal moves to a QoE. |
| `backend/services/llm/llm_service.py` (`LLM_USES`, `ask_structured`) | `llm/register.py`, `llm/client.py` | The register pattern: an unlisted Claude use is refused. Extended with prompt versions and hashes, per-use switches, a swappable transport and a run log. |

## Mined into the rules tables (adapted, not copied)

| MVP source | Used for |
|---|---|
| `qoe/qa_adjustments_catalog.py` (50 adjustments) | `mvp_subtype` on each row of `rules/addbacks.yaml`; a test checks every name still exists in the catalog list. |
| `qoe/qoe_config.py` keyword lists (owner related, non-recurring, non-operating, clarification) | Patterns in `rules/addbacks.yaml`, with an SMB lender view, support list and seller question added to every row. |
| `utils/ebitda_tags.py` (ITDA keywords, income-tax exclusions) | The four definitional rows (depreciation, amortization, interest, income taxes) and the payroll/property/sales-tax exclusions. |

## Copy later, when the packet needs it

| MVP source | Day | Notes |
|---|---|---|
| `backend/data/qoe_screening_questions.json` (9 seller questions) | 5 | Seed for the seller and broker question library; already in plain words. |
| `qoe/qa_playbooks.py` (probes and document requests by account type) | 5 | Seed for the post-LOI request list and for questions keyed to flags. Its `JARGON_BLOCKLIST` is a good rule for seller-facing text. |
| `utils/period_header_normalizer.py` | 3 | Only if sample PDFs have monthly columns. Depends on `period_helpers.MONTH_ORDER`; copy that constant with it. |
| `report/excel/databook_workbook.py` | 7 | Reference for live-formula totals (`=SUM(...)` written into cells, reported → adjusted EBITDA as formulas). Copy pieces, not the whole builder: it reads the MVP's assembled databook payload. |
| `data_ingest/pl_ingest/_claude.py` | 3 | Reference for prompt wording and pydantic answer shapes. The page-extraction use here sends a single PDF page instead of flattened rows. |

## Reference only

| MVP source | Why not copied |
|---|---|
| `data_ingest/pl_ingest/_check.py` | The idea (recompute the file's own subtotals with the shared ladder; turn failures into hints) is in `validate/footing.py`, rewritten for the PDF statement schema. |
| `qoe/qa_interview_service.py` | Seller Q&A interview bound to the MVP database and its candidate model. The Flash Review produces questions, it does not run an interview. Revisit for the QoE handoff (December). |
| `anomaly/anomaly_engine.py` (z-score detection, 1,883 lines) | Needs monthly ledger data; pre-LOI input is annual summary figures. Revisit for the Flash QoE tier. |
| `qoe/qoe_detection_engine.py`, `qoe_candidate_service.py` | Ledger-flux driven and database bound. |

## Do not copy

| MVP source | Problem |
|---|---|
| `sba/dscr_calculation_service.py` | Uses a 1.15x minimum for 7(a) (SOP 8.1 requires 1.25x for acquisitions). Its SDE formula **subtracts** non-recurring and personal expenses instead of adding them back. It **raises** SDE by a seasonality factor. No equity-injection, seller-standby or 10-year amortization logic, and no reference to SOP 50 10 8 or 8.1. |
| `sba/sba_compliance_service.py` | Heuristic maximum loan (annual debt service × 3.5, 75% loan-to-value) rather than SOP rules. |
| `report/pdf_report_engine.py`, `pdf_generation_service.py` | A valuation-report template. The Flash Review must not present a value conclusion (AICPA VS 100); the memo is built from a docx template instead. |

**Note for the MVP itself:** `report_generation_routes.py` imports both SBA services above, so MVP
reports may show their coverage figures. Worth replacing with the calculator in this repository
(`finance/financeability.py`) once SOP 8.1 parameters are verified.
