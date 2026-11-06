# CLAUDE.md — BizWave Pre-LOI (Flash Review)

> Do not change this file without Chan's explicit consent.
> Build plan: `docs/build-plan.md`. Day-by-day checklist: `tasks/sprint.md`. What came from the MVP
> and why: `docs/mvp-reuse-audit.md`. Open decisions: `docs/decisions.md`.

## 1. What this is

The pipeline behind the **BizWave Flash Review**: a CPA-reviewed pre-LOI financial review,
delivered within 24 business hours from CIM-level PDFs, for $750 credited toward a BizWave QoE.
The buyer gets a verdict, a lender-lens earnings bridge, SOP 50 10 8.1 financeability ("maximum
financeable price at your structure"), red flags and data gaps, LOI terms, a post-LOI request
list, seller questions and an optional Buyer Readiness Letter.

This repository is separate from `Bizwave_mvp_master` on purpose. Code from the MVP is **copied,
never imported**, and each copied file says where it came from (section 7).

## 2. The design rule

**Code owns anything with a right answer. Claude reads messy documents and writes language.
The CPA owns judgment and signs.**

| Pipeline step | Code | Claude (registered use) | CPA |
|---|---|---|---|
| PDF ingestion | text layer and tables | `ingest.page_extraction` for unreadable pages | keys in what neither could read |
| Validation | footing checks | — | resolves every failure |
| Add-back classification | `rules/addbacks.yaml` patterns | `addbacks.classify_unmatched` for leftovers | approves |
| Lender view | rules table lookup | — (never) | overrides with a written reason |
| Financeability | SOP 8.1 calculator | — (never) | sets structure assumptions |
| Red flags | `rules/flags.yaml` thresholds | `flags.cim_qualitative` suggestions | keeps or dismisses |
| Narrative | memo template | `narrative.draft` from approved figures | edits and signs |

## 3. Invariants (breaking one breaks the product silently)

1. **Every figure traces.** A number in a deliverable is either read from a page (a `Decimal` with
   a `SourceRef`: document, page, method) or computed by code from such numbers (`float`, rounded
   only when presented). Claude never supplies a number that code does not re-derive or the footing
   checks do not tie out. A figure Claude read that fails footing goes to the CPA.
2. **Claude goes through `llm.ask()` only**, and only for a use listed in `llm/register.py`. A new
   use needs a register entry (purpose, what is sent, its no-LLM path) and a prompt file.
   **Never edit a released prompt file**: copy to `<use>.v<N+1>.md`, edit, bump `prompt_version`.
   One batched call per step, never a call per row.
3. **No-LLM mode always works.** With `BIZWAVE_NO_LLM=1` or no API key the pipeline still runs end
   to end and a Flash Review can still be delivered (figures keyed in, narrative written by hand).
   Every new Claude feature ships with its fallback and a test of the fallback.
4. **Rules are data.** Thresholds, keyword patterns, lender views and SBA parameters live in
   `src/bizwave_preloi/rules/*.yaml`, each with its source or status. Never write one of those
   numbers into logic. Never bind code to one deal (no account names, years or amounts from a
   sample in logic; the MVP learned this the hard way).
5. **No valuation.** No output may state or imply a value, a value range or what a business is
   "worth" (AICPA VS 100). Use "maximum financeable price at your structure". Instant Screen output
   is labeled unreviewed. Do not add market-multiple value ranges.
6. **The lender view comes from the rules table or a CPA override with a reason.** Never from Claude.
7. **Footing failures block delivery** until the CPA resolves them (`rules/flags.yaml`,
   `footing_failure`). Nothing in `validate/` changes a figure.
8. **Client data never enters git.** Live deals live in `deals/<deal-id>/` (git-ignored, as is the
   run log). Tests and fixtures use synthetic data only; refer to deals by code name.
9. **YAML gotcha:** quote category codes. Unquoted `NO` is read as `false`. The loader refuses it.

## 4. Commands

```bash
pip install -e ".[dev]"            # add ,llm for the Anthropic SDK: pip install -e ".[dev,llm]"
pytest                             # whole suite, ~3 seconds; run it before every commit
pytest -m "not excel"              # skip the LibreOffice parity test
python scripts/build_financeability_model.py   # rewrite models/financeability_model.xlsx
python scripts/pdf_inventory.py deals/samples  # which sample pages have a text layer
```

Windows: if LibreOffice is installed but not on PATH, set `SOFFICE` to the full path of
`soffice.exe` for the Excel parity test and the model script.

## 5. Layout

```
src/bizwave_preloi/
  schemas.py          data contracts (Statement, LineItem, SourceRef, AddBack, Flag, Deal)
  pl_ladder.py        P&L ladder, copied from the MVP (keep the two in step)
  rules/              *.yaml rules + loader that refuses malformed files
  finance/            amortization, SOP 8.1 financeability, Excel model builder
  validate/           footing checks
  classify/           add-back classification (rules first, Claude fallback)
  llm/                register of uses, ask(), prompts/<use>.v<N>.md
  ingest/             PDF inventory (Day 1); statement reading (Day 3)
  outputs/            xlsx_style from the MVP; memo, workbook, letter (Day 7)
  ops/                run log; SLA clock and credit ledger (Day 8)
tests/                one file per module; synthetic data only
models/               financeability_model.xlsx (live formulas, generated)
docs/  tasks/         plan, audit, decisions; sprint checklist, packet plans, lessons
deals/                live client work (git-ignored)
```

## 6. How we work

1. **Packet first.** For anything beyond a small fix, write `tasks/plans/YYYY-MM-DD_<topic>.md`:
   goal, data contract (exact fields both sides use), tasks as checkboxes, the tests that prove it.
   Wait for Chan's go-ahead before building.
2. **Tests first.** Write the tests for the packet before the code and watch them fail for the
   right reason. Assert real values (dollars, counts, page numbers), not just "no error".
3. **Never edit a test to make it pass.** Fix the code. If the plan was wrong, write the spec change
   in the plan doc first, then change the test.
4. **Run the whole suite** (`pytest`) before saying a packet is done. It is fast; unlike the MVP,
   there is no reason to run a subset.
5. **Stop after each packet**, tick it in `tasks/sprint.md`, and add anything learned to
   `tasks/lessons.md`. Do not start the next packet without Chan.
6. **Branches.** Never commit to `main` directly; one branch and pull request per packet.
   Commit messages: `[Day N] short description`.

## 7. Copying from the MVP

Copy a file or function, do not import across repositories. Put the source path and commit at the
top of the copied file, keep the logic unchanged where possible, and add a test in this repository
before relying on it. `docs/mvp-reuse-audit.md` lists what is worth copying and what is not
(notably: do not copy the MVP's `dscr_calculation_service.py`; see the audit).

## 8. Things that will bite

- `pl_ladder.compute_pl` makes Cost of Goods Sold, Expense and Other Expense positive; Income and
  Other Income keep their sign. Feed it section totals as printed.
- Fiscal years in CIMs run newest-first or oldest-first; never assume column order.
- Some CIMs print only subtotals (Revenue, COGS, Gross Profit ...). A subtotal with no children is
  a leaf for the ladder check and needs a `section`.
- `rules/sba_sop_8_1.yaml` has `verified_against_sop_text: false` until Chan checks it; every
  financeability result carries that note until then.
- The default Prime rate in the SBA file goes stale; a Flash Review uses the lender's quoted rate.
