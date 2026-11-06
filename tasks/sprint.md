# Sprint checklist — Flash Review, 9–20 Nov 2026

Tick items as they finish. One packet plan per item group in `tasks/plans/`. Items marked
"(scaffold)" were done on 6 Nov before the sprint started; review them on Day 1 rather than rebuild.

## Day 1 — Mon 9 Nov: foundation
- [x] Repository structure, `pyproject.toml`, `.gitignore` (client data and run log ignored) (scaffold)
- [x] `CLAUDE.md` (scaffold) — Chan to review and approve
- [x] Data schemas: `schemas.py` (scaffold)
- [x] Test harness: `pytest`, fake Claude transport, synthetic fixtures (scaffold)
- [x] MVP reuse audit: `docs/mvp-reuse-audit.md` (scaffold) — Chan to review
- [x] PDF inventory tool: `scripts/pdf_inventory.py` (scaffold)
- [ ] Gather 8–10 sample PDFs (CIMs, broker recasts) into `deals/samples/`; run the inventory
- [ ] Hand-key 3 as ground truth (`deals/samples/<name>.truth.yaml`: periods, lines, add-backs, source pages)
- [ ] Design-partner outreach sent; adapt the engagement letter (consulting, CS 100, buyer-only reliance)

## Day 2 — Tue 10 Nov: calculator and rules
- [x] SOP 8.1 financeability: `evaluate`, `max_financeable_price`, `sensitivity` with tests (scaffold)
- [x] Excel model with live formulas, recalculated by LibreOffice in the parity test (scaffold)
- [x] Rules tables: 27 add-back rows, 15 flag thresholds, SBA parameters, taxonomy (scaffold)
- [ ] D1: verify `rules/sba_sop_8_1.yaml` against the SOP text; set `verified_against_sop_text: true`
- [ ] D2: choose the headline earnings basis
- [ ] D3: confirm the lender view on each add-back row; set `status: confirmed`
- [ ] Open `models/financeability_model.xlsx` in Excel and check it against one of your own deal models

## Day 3 — Wed 11 Nov: PDF ingestion
- [ ] Packet plan: `ingest.read_package(deal_dir)` per the contract in `ingest/__init__.py`
- [ ] Text-layer statement reader (pdfplumber words and tables; camelot for ruled tables)
- [ ] Period headings: FY, TTM, YTD, "12/31/2024", newest-first or oldest-first
- [ ] Line kinds: account / subtotal / calculated; sections from headings; parents for subtotals
- [ ] Seller add-back schedule reader (descriptions verbatim)
- [ ] Claude fallback (`ingest.page_extraction`): send ONE page as a one-page PDF; validate against the schema; method `claude` with confidence
- [ ] Unread pages listed for keying in (no-LLM path)

## Day 4 — Thu 12 Nov: validation and classification
- [x] Footing checks: subtotals, ladder, periods, signs, gaps, seller bridge (scaffold)
- [x] Add-back classifier: rules first, one batched Claude call, CPA for the rest (scaffold)
- [ ] Accuracy report against the 3 ground-truth PDFs: figures read correctly, footing results, add-backs classified correctly
- [ ] D5: set `claude_min_confidence` from the accuracy report

## Day 5 — Fri 13 Nov: end to end (WEEK-1 GATE)
- [ ] Flag engine: one function per metric in `rules/flags.yaml`, each unit-tested
- [ ] Qualitative flag suggestions (`flags.cim_qualitative`), status `open` until the CPA decides
- [ ] Question library keyed to flags and add-back rows (seed: MVP screening questions and playbooks)
- [ ] LOI-terms library keyed to flags
- [ ] End-to-end run on 5 PDFs to structured output, also with `BIZWAVE_NO_LLM=1`
- [ ] Gate: figures correct after review flags on all 5; no-LLM run works; 3 paid partners confirmed

## Day 6 — Mon 16 Nov: review console (first to cut)
- [ ] Simple internal screen: figures with source page, ratings, overrides with reasons, flag decisions, sign-off
- [ ] Fallback if cut: review in the workbook

## Day 7 — Tue 17 Nov: outputs
- [ ] Memo: docx template → PDF; every figure from the computed results
- [ ] Workbook: bridge, financeability (reuse `finance/excel_model.py`), flags, questions; live formulas
- [ ] Buyer Readiness Letter
- [ ] Narrative sections via `narrative.draft` (second to cut: write by hand)
- [ ] Output check: no value language anywhere (test that scans rendered text)

## Day 8 — Wed 18 Nov: operations and first live review
- [ ] Intake folder and Stripe Payment Link; SLA clock starts when the package is complete
- [ ] Run log events for SLA timestamps; credit ledger (100% credit, 120 days, any deal)
- [ ] First live Flash Review delivered; CPA minutes logged

## Day 9 — Thu 19 Nov
- [ ] Live reviews 2–3 (third to cut: move to the week after)
- [ ] Fixes from live reviews; redacted sample; pilot numbers for the deck

## Day 10 — Fri 20 Nov: demo day
