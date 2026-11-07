# CLAUDE.md — BizWave Pre-LOI (Flash Review)

> Do not change this file without Chan's explicit consent.
> Master plan: `docs/build-plan.md` (what and why) and `docs/tech-plan.md` (stack, database, packets
> P1–P15). Checklist: `tasks/sprint.md`. Decisions: `docs/decisions.md`. MVP reuse: `docs/mvp-reuse-audit.md`.
> Every change follows the packet loop in section 6. It is binding in every session, whether or not a
> slash command was used.

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
8. **Client data never enters git.** Live deals live in `BIZWAVE_DATA_DIR/deals/<deal-id>/`, outside
   the repository, as do the run log and the database (`config.ensure_data_dirs` refuses a data
   folder inside the repository). Tests and fixtures use synthetic data only; refer to deals by code name.
9. **YAML gotcha:** quote category codes. Unquoted `NO` is read as `false`. The loader refuses it.

## 4. Commands

```bash
pip install -e ".[dev]"            # add ,llm for the Anthropic SDK: pip install -e ".[dev,llm]"
pytest                             # whole suite, ~3 seconds; run it before every commit
pytest tests/plans/test_YYYY_MM_DD_<packet>.py -v   # one packet's gate
pytest -m "not excel"              # skip the LibreOffice parity test
python scripts/build_financeability_model.py   # rewrite models/financeability_model.xlsx
python scripts/pdf_inventory.py   # which sample pages have a text layer (<data folder>/samples)
python -m bizwave_preloi.db upgrade    # create or update the database (in the data folder)
```

Slash commands for the packet loop (section 6), in `.claude/commands/`:
`/sprint-status`, `/research P<n>`, `/plan-packet P<n>`, `/execute P<n>`, `/verify-packet P<n>`,
`/review-packet P<n>`, `/close-packet P<n>`, `/lessons`. Subagents in `.claude/agents/`:
`gate-runner` (runs tests, reports raw results, never edits) and `packet-reviewer` (independent
review against the plan and section 3, never edits).

Windows: if LibreOffice is installed but not on PATH, set `SOFFICE` to the full path of
`soffice.exe` for the Excel parity test and the model script.

## 5. Layout

```
src/bizwave_preloi/
  schemas.py          data contracts (Statement, LineItem, SourceRef, AddBack, Flag, Deal)
  pl_ladder.py        P&L ladder, copied from the MVP (keep the two in step)
  db/                 models, types, sessions, migrations (Alembic), repository functions
  rules/              *.yaml rules + loader that refuses malformed files
  finance/            amortization, SOP 8.1 financeability, Excel model builder
  validate/           footing checks
  classify/           add-back classification (rules first, Claude fallback)
  llm/                register of uses, ask(), prompts/<use>.v<N>.md
  ingest/             PDF inventory (Day 1); statement reading (Day 3)
  outputs/            xlsx_style from the MVP; memo, workbook, letter (Day 7)
  ops/                run log; SLA clock and credit ledger (Day 8)
tests/                one file per module; synthetic data only
tests/plans/          one gate file per packet: test_YYYY_MM_DD_<packet>.py (written first)
models/               financeability_model.xlsx (live formulas, generated)
docs/                 master plan (build-plan, tech-plan), decisions, MVP reuse audit
tasks/                sprint.md, plans/ (packet plans + _TEMPLATE.md), research/, reviews/, lessons.md
.claude/              settings.json (deny rules), commands/ (the loop), agents/ (gate-runner, packet-reviewer)
deals/                git-ignored safety net only; live client work is in BIZWAVE_DATA_DIR (config.py)
```

## 6. The packet loop (binding)

Three levels. **Master plan** (`docs/build-plan.md`, `docs/tech-plan.md`) → **packets** (P1–P15,
one at a time, named by Chan) → **sub-packets** (the numbered tasks inside one packet plan, e.g.
P2.1 models, P2.2 migration, P2.3 repository layer).

```
 1 RESEARCH  ->  2 PLAN  ->  3 SIGN-OFF  ->  4 GATE FIRST  ->  5 BUILD
                    ^            (Chan)                          |
                    |                                            v
 9 CLOSE  <-  8 CORRECT  <->  7 REVIEW (independent)  <-  6 VERIFY (independent)
 (STOP)        max 2 rounds, then STOP and re-plan with Chan
```

1. **Research** (`/research P<n>`). Read-only. Explore the code, rules, docs and, when copying, the
   MVP. Save `tasks/research/YYYY-MM-DD_<packet>.md` with a plain-language summary and risks.
   Light packets (planned at 1 hour or less) may skip this step.
2. **Plan** (`/plan-packet P<n>`). Write `tasks/plans/YYYY-MM-DD_<packet>.md` from
   `tasks/plans/_TEMPLATE.md`: goal, in and out of scope, the **data contract** (exact field names and
   types both sides use), sub-packets as checkboxes, the gate tests by name, risks, rollback.
   **STOP.**
3. **Sign-off.** Chan adds `## Reviewer Note` in the plan; Claude revises and stops again. Build only
   after an explicit message ("go ahead", "please execute", "implement it"). Approving plan mode
   alone is not sign-off.
4. **Gate first.** Write `tests/plans/test_YYYY_MM_DD_<packet>.py` before any code. It carries the
   packet's regression duty: schema shape, happy path, error and edge paths, **real values** (dollars,
   counts, page numbers), behavior of direct consumers of anything changed, and a migration
   upgrade → downgrade → upgrade when a migration ships. Run it; it must fail for the right reason
   (missing behavior, not a typo). Paste the failure summary into the plan under `## Gate — first run`.
   Commit the gate on its own (`[Day N] P<n> gate`).
5. **Build** (`/execute P<n>`). Branch `p<n>-<topic>` from `main`. Implement sub-packets in order,
   tick each box the moment it is done, commit per sub-packet (`[Day N] P<n>.<k> short description`).
   Only what the plan says. If a step fails or the plan does not fit reality, **STOP and report**;
   do not improvise.
6. **Verify, independently** (`/verify-packet P<n>`). The `gate-runner` subagent (fresh context, cannot
   edit) runs the gate file and then the whole suite and reports raw results. The implementer never
   certifies its own work. The gate is green only when gate-runner says so.
7. **Review, independently** (`/review-packet P<n>`). The `packet-reviewer` subagent (fresh context,
   cannot edit) reviews `git diff main...HEAD` against the plan and section 3, and returns findings
   rated **blocker / should-fix / nit** with file and line, plus a verdict: PASS, PASS WITH FIXES or
   FAIL. Save them verbatim to `tasks/reviews/YYYY-MM-DD_<packet>.md`.
8. **Correct.** Fix every blocker and should-fix **in the code** (nits at Claude's discretion), then
   run steps 6 and 7 again; the reviewer re-checks the earlier findings and the new diff. At most two
   correction rounds; if blockers remain, **STOP** and take it back to Chan as a plan problem.
9. **Close** (`/close-packet P<n>`). Fill `## Results` in the plan (what changed, test counts,
   deviations, review verdict), tick `tasks/sprint.md`, add lessons (`/lessons`), push the branch and
   give Chan the pull-request link with a short summary. **STOP. Do not start the next packet** until
   Chan names it.

Rules that hold across the loop:
- **Never edit a gate test to make it pass.** Fix the code. If the gate shows the *plan* was wrong,
  add `## Spec amendment` to the plan (what, why, date), get Chan's OK, then change the test. That is
  the only legitimate edit to a gate after it is committed, and the reviewer checks for it.
- **No autonomous building.** Never start a packet Chan has not named, and never build from
  `tasks/sprint.md` or the tech plan alone; a signed-off packet plan is required.
- **Master-plan changes are proposals.** If a packet shows the master plan is wrong (scope, schedule,
  design, a rules value), write a `## Master-plan change proposal` in the plan's results. Chan
  decides; the decision goes in `docs/decisions.md` and the master plan is updated in its own commit.
- **Small fixes** (a typo, a failing import, one-line config) skip steps 1–3 but still get a test,
  gate-runner verification and a commit message that says what and why.
- **Run the whole suite** at step 6 every time; it takes seconds.
- **Branches:** never commit to `main`; one branch and pull request per packet; Chan merges.

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
- SQLite: foreign keys and WAL are switched on per connection in db/session.py; never open a raw
  sqlite3 connection. Times are stored as UTC and must be timezone-aware. Decimals are stored as
  text, so sum and compare them in Python, not in SQL.
- Schema changes only through a new Alembic migration in db/migrations/versions/ (upgrade ->
  downgrade -> upgrade tested); never create_all() outside tests.
