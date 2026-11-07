# 2026-11-06 — P4 research: financeability persisted, intake answers, and P3's carry-overs

Read-only. Sources:
- `docs/tech-plan.md` §4.1, §4.2, §6.1, §6.3, §7 (consent) and §9 (P4 row after M13: 3 hours);
- `docs/decisions.md` M11–M14;
- the P3 plan (Q3, Results, the nits carried over), the P3 reviews, `tasks/lessons.md`;
- the code on `main` at 5e764a3: `finance/financeability.py`, `rules/sba_sop_8_1.yaml`, `db/models.py`,
  `db/migrations/versions/0001_core.py`, `db/repo.py`, `ops/intake.py`, `cli.py`;
- the P3 gate `tests/plans/test_2026_11_06_p3_cli.py`.

## What the master plan asks of P4 (tech plan §9, M12, M13)
1. **`financeability_runs` table:** deal_id, created_at, earnings (JSON), structure (JSON), result (JSON),
   params_version, params_verified, is_final.
2. **Structure from the intake form, and `bw finance DEAL`,** which "prints the financeability result for
   the saved structure (useful on calls)".
3. **The intake form answers and AI consent (moved from P3, M12):**
   - fields: asking price, proposed price, buyer cash, seller-note ideas, lender and quoted rate,
     working capital, offer deadline, industry, consent to AI-assisted processing (tech plan §6.3);
   - P4 stores the consent; P7 makes a deal without consent run in no-LLM mode (§7).
4. **`bw intake --dry-run`** (M13).
5. **A draft `rules/intake.yaml` row** sending forecast, projected/projection and budget file names to
   `other`; "pro forma" unchanged (M13).
6. **The two nits carried from P3's focused review (M13):**
   - the `_record` fallback must refuse when the plan found a problem, and `repo.add_document` should take
     the expected sha256;
   - the macOS guard in `test_name_key_follows_the_disk`.

## What exists and fits
- **`finance/financeability.py` (scaffold, tested, Excel parity):**
  - `Earnings(last_fy, prior_fy)`, `Structure(...)`, `evaluate(price, ...)`, `max_financeable_price(...)`
    and `sensitivity(...)`;
  - every SBA number comes from `rules/sba_sop_8_1.yaml`: `version: 1`, `verified_against_sop_text: false`;
  - the notes already disclose the unverified parameters and a missing replacement salary.
  - Inputs are floats; the result is pydantic, so it serializes to JSON as it is.
- **`deals` (P2)** already has `asking_price`, `proposed_price` (DecimalText), `industry` and
  `offer_deadline`. `deal_events` has kind `note` for an audit line.
- **`ops/files.py` (P3)** copies a buyer's file into a deal folder without ever replacing one. **`ops/intake.py`**
  has the source-folder refusals and the per-file planning that a dry run can reuse.
- **Migrations:** 0001 is frozen. A new revision is round-trip tested, and the live database gets a
  snapshot before a real upgrade (M11/M13).

## Gaps and conflicts found
1. **The P3 gate pins the old clock rule.** P3's Q3 (accepted) said "P4 adds 'intake answers received'"
   to when the 24-hour clock starts. Four P3 gate tests take a deal to `ready` by intake alone:
   - `test_intake_starts_the_clock_for_a_paid_deal_with_a_cim`;
   - `test_intake_kind_override_and_correction`;
   - `test_intake_unreadable_pdf_is_recorded_and_reported`;
   - `test_status_lists_open_deals`.

   Adding the rule changes their expected status. A committed gate changes only through a
   `## Spec amendment` with Chan's OK. This is Chan's decision.
2. **The intake form's tool is not chosen yet** (D11, Day 8), so its export format is unknown. Reading
   our own answers file avoids guessing. When the form tool is chosen, a small converter maps its export
   to that file.
3. **Percent ambiguity:**
   - Buyers write "10" or "0.10" for 10%. A wrong guess changes seller notes, and therefore the maximum
     financeable price, tenfold.
   - The answers file must use one convention, and refuse the other.
4. **Earnings have no source yet.** Supportable earnings come from statements and accepted add-backs
   (P5–P9). Until then the CPA keys them in. Invariant 1 needs each keyed figure to carry where it came
   from (document and page, or "CPA judgment").
5. **Silent defaults would overstate the result.**
   - `Structure` defaults replacement salary, capex reserve and taxes to 0. A run that forgets them
     shows a higher maximum financeable price than a lender would.
   - The SBA rate default (Prime + spread from the rules file) goes stale; CLAUDE.md says a Flash Review
     uses the lender's quoted rate.
6. **Which price is tested:** the buyer's proposed price, or the asking price when there is none. The
   maximum financeable price is always shown.
7. **Price provenance** (P2 review round 1 note): asking and proposed prices sit next to the result in the
   memo and need a recorded source. The answers row, with its file hash, gives one.
8. **Size:** items 1–6 are two different kinds of work:
   - files, the clock and intake;
   - SBA computation and its storage.

   P3 showed that a large packet draws many review findings. The tech plan's 3 hours covers neither half
   comfortably: answers, clock, dry run and nits come to about 3 hours; financeability runs and
   `bw finance` to about 2.5.

## Risks
- **A buyer's answers file is client data.** It is copied into the deal folder through `ops/files.py`,
  never into the repository, and refused from inside the repository or the data folder (as intake does).
- **YAML pitfalls:**
  - unquoted `no` reads as false, and `1.25e6` reads as a float;
  - the loader must be strict (unknown keys refused) and money parsed exactly.
- **Consent must fail closed:** no answers recorded means no consent.
- **No valuation wording** in anything `bw finance` prints (invariant 5). The output says "maximum
  financeable price at your structure", carries the unverified-SOP note, and is labelled unreviewed until
  the CPA marks a run final.
- **One final run per deal:** enforced in the database (a partial unique index works on SQLite and
  Postgres), not only in code.
- **Changing the clock rule** affects `bw paid`, `bw intake` and the new `bw answers`. Each must call the
  same check (`start_clock_if_complete`).

## Recommendation in one paragraph
Split P4 in two:
- **P4a, intake answers and P3 carry-overs (about 3 hours):**
  - our own answers file (`bw answers DEAL --template`, then `--from FILE`), strict and with exact money;
    percents written as 10 for 10%, and a value between 0 and 1 refused;
  - an `intake_answers` table with the file's hash (provenance for the prices) and the consent, read fail
    closed;
  - the clock waits for answers, with a spec amendment to the four P3 gate tests;
  - `bw intake --dry-run`, the projections row, and the two carried nits.
- **P4b, financeability persisted (about 2.5 hours):**
  - `financeability_runs`, and `bw finance` with the CPA's earnings (each with a source) and explicit
    replacement salary and capex reserve;
  - the lender's quoted rate or `--sba-rate`, never the file default silently;
  - one final run per deal.
