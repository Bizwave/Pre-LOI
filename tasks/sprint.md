# Sprint checklist — Flash Review, 9–20 Nov 2026

Tick items as they finish. Packets (P1–P15) are defined in `docs/tech-plan.md` section 9; each gets a
plan in `tasks/plans/` before it is built. Items marked "(scaffold)" were done on 6 Nov before the sprint.

## Done before the sprint (scaffold, 6 Nov)
- [x] Repository structure, `pyproject.toml`, `.gitignore`, `.claude/settings.json` deny rules
- [x] `CLAUDE.md`, README, build plan, technical plan, decisions, MVP reuse audit
- [x] Data schemas (`schemas.py`); P&L ladder and Excel styling copied from the MVP
- [x] Rules: taxonomy, 27 add-back rows, SBA SOP 8.1 parameters, 15 flags, footing tolerances
- [x] SOP 8.1 financeability (evaluate, maximum price, sensitivity) and the Excel model with parity test
- [x] Claude door: four registered uses, no-LLM mode, run log, v1 prompts
- [x] Footing checks and seller-bridge check; add-back classifier; PDF inventory tool

## Day 1 — Mon 9 Nov
- [ ] Merge the scaffold pull request; set up the environment; `pytest` green on your machine
- [x] P1 Settings and data folder (`config.py`, `BIZWAVE_DATA_DIR` outside the repo, run log moved) — merged 6 Nov (PR #3); confirmed 16:26
- [x] W1 Self-improvement loop (workflow packet) — closed 2026-11-06 (go-ahead 17:29; review round 3 PASS WITH FIXES); CLAUDE.md text consented 17:59; merged (PR #4)
- [x] P2 Database core (customers, deals, deal_events, documents, pages, pipeline_runs; Alembic; `DecimalText`) — closed 2026-11-06; four reviews; ready to merge
- [ ] P3 CLI skeleton (`bw new-deal`, `bw intake`, `bw status`, `bw backup`; backup before every database upgrade or downgrade, M11)
- [ ] 8–10 sample CIMs (redacted or public where possible); run `scripts/pdf_inventory.py`
- [ ] Design-partner outreach sent; engagement letter adapted (consulting, buyer-only reliance, AI disclosure)

## Day 2 — Tue 10 Nov
- [ ] D1 verify `rules/sba_sop_8_1.yaml` against the SOP text
- [ ] D2 headline earnings basis
- [ ] D3 lender view on each add-back row; set `status: confirmed`
- [ ] Hand-key 3 samples as ground truth (`truth.yaml`: periods, lines, add-backs, pages)
- [ ] P4 Financeability persisted (`financeability_runs`, `bw finance`; intake answers and AI consent, M12; `bw intake --dry-run`, projections rule, P3 carried nits, M13)
- [ ] Open `models/financeability_model.xlsx` in Excel and check it against one of your own deal models

## Day 3 — Wed 11 Nov
- [ ] P5 Statement reader (text layer and tables, period headings, line kinds, sections, add-back schedule)
- [ ] P6 Claude page fallback (one-page PDF, schema validation, no-LLM path)

## Day 4 — Thu 12 Nov
- [ ] P7 Pipeline orchestrator (`run_deal`, `footing_results`, `overrides`)
- [ ] P8 Accuracy report against the ground truth; tune; D5 Claude confidence threshold

## Day 5 — Fri 13 Nov (WEEK-1 GATE)
- [ ] P9 Flag engine (one tested function per metric)
- [ ] P10 Questions and LOI terms libraries
- [ ] P11 End to end on 5 samples, with and without Claude
- [ ] Gate: figures correct after review flags on all 5; no-LLM run works; 3 paid partners confirmed

## Day 6 — Mon 16 Nov
- [ ] P12 Review console (first to cut: review in the workbook instead)

## Day 7 — Tue 17 Nov
- [ ] P13 Outputs: memo, letter, workbook; PDF via LibreOffice; banned-language test
- [ ] P14 Narrative drafts (second to cut: write by hand)

## Day 8 — Wed 18 Nov
- [ ] P15 Operations: SLA clock, commercial rules, payments, credits ledger, `llm_calls` table, CPA timer
- [ ] Stripe Payment Link, upload link and intake form live (D10, D11, D13)
- [ ] First live Flash Review delivered; CPA minutes logged

## Day 9 — Thu 19 Nov
- [ ] Live reviews 2–3 (third to cut: move to the week after)
- [ ] Fixes; redacted sample and pilot numbers for the deck

## Day 10 — Fri 20 Nov: demo day
