# 2026-11-06 — P4a Intake answers, the clock, dry run and P3 carry-overs

Status: draft
Branch: `p4a-intake-answers` · Gate: `tests/plans/test_2026_11_06_p4a_intake_answers.py` · Budget: about
3 hours if Q1 splits P4 (tech plan §9 has 3 hours for the whole of P4; see Q1 and Q9)
Research: `tasks/research/2026-11-06_p4_financeability.md`
Base: `main` at 5e764a3 (P3 merged, PR #7). Not based on `p3-improve` (PR #8, lesson promotions, open), so
the two pull requests stay independent.

## Goal
The buyer's intake answers arrive as a small file. Chan records them with one command, and they get
the same care as any buyer file:
- copied into the deal folder without ever replacing a file;
- hashed, checked strictly, and kept with every earlier version.

What they provide:
- **Prices:** the asking and proposed prices now have a recorded source, the answers file and its hash.
- **Consent:** the buyer's AI consent is stored and read fail closed, ready for P7 to enforce.
- **The clock:** the 24-hour clock waits for the answers as well as a readable CIM (P3 Q3).

Also in this packet:
- `bw intake --dry-run` shows what an intake would do before anything is copied;
- projection and budget files no longer pass as financial statements;
- the two small items carried from P3 are fixed.

**Done when:**
- `bw answers acme-hvac --from answers.yaml` on a synthetic file:
  - copies it to `deals/acme-hvac/intake/`;
  - records one `intake_answers` row (asking 1,250,000; proposed 1,100,000; AI consent yes);
  - sets the deal's prices, industry and offer deadline;
  - starts the clock for a paid deal that has a readable CIM.
- `repo.ai_consent` is False until answers say yes.
- `bw intake --dry-run` writes nothing.
- "Forecast P&L 2025.xlsx" is classified `other`.
- The whole suite passes on Python 3.12 and 3.13.

## Scope
In:
- **`schemas.IntakeAnswers`:** a strict answers model with exact money and percents.
- **`ops/answers.py`:** `take_answers` and the answers-file template.
- **`db`:**
  - table `intake_answers` in migration `0002_intake_answers`;
  - `repo.record_intake_answers`, `latest_intake_answers` and `ai_consent`;
  - `repo.add_document(..., expected_sha256=)`.
- **`ops/intake.py`:**
  - the clock waits for answers;
  - `dry_run`;
  - the fallback refuses when the plan found a problem;
  - every new copy is recorded only if its bytes still match.
- **`rules/intake.yaml`:** a draft row sending projections and budgets to `other` (M13).
- **`cli.py`:** `bw answers` and `bw intake --dry-run`.
- **Tests:**
  - the gate;
  - module tests, including the macOS guard carried from P3;
  - the P3 gate's spec amendment if Q2 is accepted.
- **Docs:**
  - README;
  - CLAUDE.md §4: one line, only with consent to the exact text in Q8;
  - tech plan §6.1, §9;
  - a decisions row.

Out:
- **P4b:** `financeability_runs` and `bw finance` (plan written after P4a closes; its questions are below).
- **Day 8:** a converter from the chosen form tool's export (D11).
- **P7:** enforcing consent on Claude calls.
- Reading answers out of the CIM.
- Any change to how `ops/files.py` writes files.

## Data contract
```python
# schemas.py
class IntakeAnswers(Model):           # strict: unknown keys refused
    form_version: Literal[1]
    asking_price: Decimal | None      # money: int, exact float, or text such as "$1,250,000"; > 0
    proposed_price: Decimal | None    # same
    buyer_cash: Decimal | None        # same; >= 0
    seller_note_standby_pct: Decimal | None     # PERCENT, written 10 for 10%: 0 or 1..100; a value strictly
    seller_note_amortizing_pct: Decimal | None  #   between 0 and 1 is refused ("write 10 for 10%"), never
    seller_note_rate_pct: Decimal | None        #   guessed; standby + amortizing <= 100
    seller_note_term_years: Decimal | None      # > 0
    seller_note_notes: str | None               # the buyer's words, <= 2000 characters
    lender_name: str | None                     # <= 200
    lender_quoted_rate_pct: Decimal | None      # percent as above, 1..30
    working_capital: Decimal | None             # money, >= 0
    offer_deadline: date | None
    industry: str | None                        # <= 120 (deals.industry)
    ai_consent: bool                  # REQUIRED; yes/no/true/false; text such as "maybe" refused
    notes: str | None                 # <= 2000
def parse_intake_answers(text: str) -> IntakeAnswers
    # YAML (safe_load) -> IntakeAnswers; ValueError naming the field and the rule on any problem

# db/models.py, migration 0002_intake_answers (revises 0001_core; 0001 untouched)
class IntakeAnswerSet(Base):          # table "intake_answers"
    id: int (PK)
    deal_id: str (FK deals.id, not null, indexed)
    stored_path: str (500, not null)  # relative to the deal folder, "intake/answers-20261106-225800.yaml"
    sha256: str (64, not null)
    received_at: datetime (UTC, not null)
    recorded_by: str (100, not null)
    ai_consent: bool (not null)
    answers: dict (JSON, not null)    # IntakeAnswers.model_dump(mode="json"): money and percents as text
    # unique (deal_id, sha256) -> uq_intake_answers_deal_id; unique (deal_id, stored_path) ->
    # uq_intake_answers_deal_id_stored_path (both names pinned by the gate)

# db/repo.py (additions)
def record_intake_answers(s, deal_id: str, path: Path, *, by: str,
                          received_at: datetime | None = None) -> IntakeAnswerSet
    # path inside the deal folder; parses the STORED bytes (the record matches the file); refuses an unknown
    # or closed deal (ValueError) before writing; same content -> the existing row, nothing changed.
    # A new set is the deal's current answers: deals.asking_price, proposed_price, industry and offer_deadline
    # are set from it (a field left empty clears the deal's value); offer_deadline is stored as 00:00 UTC of
    # that date (never later than the buyer's date). One deal_events note: "intake answers #<id>
    # (<stored_path>): asking <x>, proposed <y>, AI consent yes|no".
def latest_intake_answers(s, deal_id: str) -> IntakeAnswerSet | None   # newest received_at, then id
def ai_consent(s, deal_id: str) -> bool     # the latest set's ai_consent; no set -> False (fails closed)
def add_document(s, deal_id, path, *, kind, received_at=None, expected_sha256: str | None = None)
    # P2 contract unchanged when expected_sha256 is None; otherwise a different digest -> ValueError before
    # anything is added ("<path> changed after it was copied ...") (P3 focused review, nit 1)

# ops/answers.py
TEMPLATE: str                         # YAML with a comment per field; every IntakeAnswers field present
@dataclass(frozen=True)
class AnswersResult:
    deal_id: str
    stored_path: str
    action: str                       # "recorded" | "already_recorded"
    answers_id: int
    ai_consent: bool
    status_before: str
    status_after: str
    message: str                      # the clock line, as for intake
def take_answers(deal_id: str, source: Path, *, by: str, url: str | None = None) -> AnswersResult
    # Refuses (ValueError, nothing copied or recorded): unknown or closed deal; source not a file; source
    #   inside the repository, the data folder or the backup folder; a file that does not parse or validate.
    # Validates BEFORE copying. Same content already recorded -> "already_recorded", no copy. Otherwise copies
    #   through ops/files into deals/<deal>/intake/answers-<UTC YYYYMMDD-HHMMSS>[-n]<suffix>, never replacing a
    #   file, then record_intake_answers, then start_clock_if_complete. OSError -> one line at the CLI.

# ops/intake.py
# The SLA clock (P3 Q3 completed, if Q2 is accepted): a deal in awaiting_documents moves to ready when it has
#   a CIM with readable pages AND a recorded answers set. start_clock_if_complete is called by bw paid,
#   bw intake and bw answers. Waiting messages name what is missing: files, a readable CIM, or the answers
#   ("run `bw answers DEAL --from FILE`").
def intake(deal_id, source, *, by, kinds=None, url=None, dry_run: bool = False) -> IntakeResult
    # dry_run: the same checks and refusals; nothing copied, restored or recorded; no clock change.
    #   IntakeFile.action is "would_copy" | "would_copy_as_new_version" | "would_record" | "already_recorded"
    #   | "would_restore" | "failed"; stored_path is the planned path; pages come from reading the SOURCE
    #   PDF (read-only); a changed stored copy is reported as in a real run.
IntakeResult.dry_run: bool = False
# Recording: every new copy, and the fallback for a second identical file, is recorded with
#   expected_sha256 = the planned sha; the fallback first returns the plan's problem if there was one.

# rules/intake.yaml (draft, M13): a first row, so it wins over the statement kinds:
  - kind: "other"                     # projections and budgets are not historical statements
    patterns: ['\bforecast', '\bprojected\b', '\bprojections?\b', '\bbudget']
# Trade-off: a CIM whose file name contains "projections" becomes `other` and needs --kind; the dry run
# shows it first. "pro forma" is unchanged.

# cli.py
bw answers DEAL --from FILE [--by WHO]   # one line (recorded / already recorded, stored path, AI consent
                                         # yes|no), then the clock line; exit 1 on a refusal
bw answers --template                    # prints TEMPLATE; DEAL and --from not needed
bw intake DEAL --from FOLDER --dry-run   # lines as for intake with the would_* actions, then
                                         # "DRY RUN: nothing was copied or recorded; the clock is unchanged";
                                         # exit 1 if a file would have a problem
```

Correction-round additions (filled during review corrections; Scope is not edited, which would reset the
go-ahead): none yet.

## Sub-packets
- [ ] P4a.1 `schemas.IntakeAnswers` and `parse_intake_answers`; `ops/answers.TEMPLATE`
- [ ] P4a.2 Model `IntakeAnswerSet`, migration `0002_intake_answers`; repo `record_intake_answers`,
      `latest_intake_answers`, `ai_consent`; `add_document(expected_sha256=)`
- [ ] P4a.3 `ops/answers.take_answers`; the clock waits for answers (with the P3 gate's spec amendment if Q2
      is accepted)
- [ ] P4a.4 `intake(dry_run=True)`; the recording fixes carried from P3; the projections row
- [ ] P4a.5 `cli.py`: `bw answers`, `--template`, `bw intake --dry-run`
- [ ] P4a.6 Docs: README, CLAUDE.md §4 (Q8, own commit), tech plan §6.1 and §9 (own commit), decisions row

## Gate tests (written first)
Synthetic data only. Expected values come from running the fixtures when the gate is written.

| Test | Asserts (real values) |
|---|---|
| `test_answers_template_parses_and_lists_every_field` | `bw answers --template` exit 0; with `ai_consent: yes` filled it parses; every `IntakeAnswers` field name is in it |
| `test_answers_recorded_with_their_source` | the fixture file through `bw answers`: exit 0; stored under `intake/answers-*.yaml`, sha256 equal to the source; row values asking 1250000, proposed 1100000, buyer cash 125000, standby 10, amortizing 5, note rate 6, quoted rate 10.25, working capital 50000, consent True; deal asking/proposed set, industry "HVAC services", offer_deadline 2026-11-20 00:00 UTC; one note event naming the row id and stored path |
| `test_answers_money_and_percent_parsing` | "$1,250,000" → 1250000; 1250000.5 → 1250000.5; percent 10 → 10; 0.1 refused with "write 10 for 10%"; "abc", -5, standby 60 + amortizing 50 refused |
| `test_answers_refusals` | no ai_consent; ai_consent "maybe"; an unknown key; form_version 2; source not a file; source inside the (fake) repository; inside the data folder; unknown deal; cancelled deal → exit 1, message names the field or rule, no `intake/` folder, no row |
| `test_answers_twice_and_a_revision` | the same file again → `already_recorded`, 1 row, 1 file; a revision (proposed 1050000, consent no) → 2 rows, 2 files, deal proposed 1050000, consent False, the first file's bytes unchanged |
| `test_ai_consent_fails_closed` | no answers → False; yes → True; a later no → False; another deal unaffected |
| `test_clock_waits_for_the_answers` | paid deal with a readable CIM and no answers → `awaiting_documents`, message names `bw answers`; `bw answers` → `ready`, clock message; pilot deal with answers first → `ready` at intake; deal awaiting payment with CIM and answers → still `awaiting_payment`; `bw paid` → `ready` |
| `test_dry_run_writes_nothing` | buyer folder (CIM 3 pages, P&L 2 pages, notes.xlsx, damaged broken.pdf) → lines `would copy` with kinds cim, p_and_l, other and pages 3, 2, -, and a problem for broken.pdf; "DRY RUN" line; exit 1; no deal folder, no document rows, status unchanged. After a real intake: dry run shows `already recorded`; a deleted stored copy shows `would restore`; a changed source CIM shows `would copy as new version` `inputs/cim-v2.pdf` |
| `test_projections_are_not_statements` | `Forecast P&L 2025.xlsx`, `Projected Income Statement 2026-2028.pdf`, `Budget - Profit and Loss 2026.xlsx`, `Adjusted EBITDA Projections.xlsx` → other; near misses `Project Falcon CIM.pdf` → cim, `Profit and Loss 2024.pdf` → p_and_l, `Pro Forma Balance Sheet.pdf` → balance_sheet (unchanged) |
| `test_add_document_refuses_unexpected_bytes` | `expected_sha256` mismatch → ValueError, no row after flush; without it the P2 behaviour holds (same file → the same row) |
| `test_a_copy_changed_after_placing_is_not_recorded` | the focused-review probe: bytes appended to a copy right after it is placed, two identical files, the first record failing once → no row holds the changed bytes; both CIM lines report a problem; the P&L is recorded |
| `test_migration_0002_round_trip_with_rows` | a database with a deal and an answers set: upgrade → downgrade to `0001_core` (table gone, deal kept) → upgrade; constraint names `uq_intake_answers_deal_id`, `uq_intake_answers_deal_id_stored_path` |
| `test_cli_lists_answers` | `bw --help` lists `answers` (a subset check, so later commands do not break it) |

## Depends on
Decisions: M11, M12, M13, M14 (P3 lesson promotions, PR #8). Packets: P2, P3 (merged).

## Questions for Chan
Each comes with my recommendation and what it changes now and later. If you agree with every one, reply
**"P4a: all recommended, go ahead"**.

1. **Split P4 into P4a (this plan) and P4b (financeability persisted).** This is a master-plan change: the
   tech plan's P4 row becomes two rows.
   - **Recommended.**
   - **Now:** smaller reviews. P3's size drew 12 should-fixes in its first review. P4a is files and the
     clock; P4b is SBA arithmetic and its storage, two kinds of risk kept apart.
   - **Later:** about 30 minutes more overhead (two gates, two reviews). P4 grows from 3 to about
     5.5 hours (P4a 3, P4b 2.5); the tech plan total becomes about 59.5 hours.
   - **If no:** one packet of about 5.5 hours, reviewed as one.
2. **The clock waits for the intake answers** (as P3's Q3 said P4 would add), with a spec amendment to
   P3's gate.
   - **The amendment:** four P3 gate tests take a deal to `ready` by intake alone. In each, one line
     records synthetic answers first; every other assertion stays as it is. It is recorded in the P3
     plan's `## Spec amendment` with your OK.
     - `test_intake_starts_the_clock_for_a_paid_deal_with_a_cim`;
     - `test_intake_kind_override_and_correction`;
     - `test_intake_unreadable_pdf_is_recorded_and_reported`;
     - `test_status_lists_open_deals`.
   - **Recommended.**
   - **Now:** the 24 hours never run while you are still missing the buyer's cash, notes and rate. You
     can't finish a review without them.
   - **Later:** P7 can rely on answers being present for every deal in `ready`.
   - **If no:** the clock starts on the CIM alone, and P7 refuses to run without answers. Then the SLA
     can run out while you wait for the buyer.
3. **Answers format:** our own YAML answers file, with `bw answers --template` to produce a blank one.
   - **Recommended.**
   - **Now:** no guessing at a form tool's export before D11 is decided (Day 8). Strict checks on every
     field.
   - **Later:** on Day 8 a small converter maps the chosen form's export to this file. The checks and
     storage stay the same.
   - **Alternatives:**
     - command options for each field: long commands, easy to mistype;
     - wait for D11: blocks P4 until Day 8.
4. **Percents are written as 10 for 10%, and a value between 0 and 1 is refused, never guessed.**
   - **Recommended.**
   - "0.10" versus "10" is a tenfold difference in seller notes and rates. Guessing could quietly
     overstate or understate the maximum financeable price in P4b.
   - **Cost:** a buyer or form that writes 0.10 gets a clear message to fix it.
5. **AI consent fails closed:** no answers recorded means no consent.
   - **Recommended.**
   - **Now:** nothing changes; no Claude call exists yet.
   - **Later:** in P7, a deal without answers runs in no-LLM mode until the answers arrive. With Q2 that
     can't happen in `ready` anyway.
6. **A revised answers file replaces the deal's current answers; earlier files and rows are kept.**
   - **Recommended.**
   - A field left empty in the newer file clears the deal's value, so the record always matches the
     latest file exactly.
   - The offer deadline is stored as the start of that day in UTC: never later than the buyer's date.
7. **The projections row goes first in `rules/intake.yaml`** (M13 placed no order).
   - **Recommended.**
   - Projections never pass as a statement.
   - **Cost:** a CIM whose file name contains "projections" becomes `other` and needs
     `--kind "NAME=cim"`; the dry run shows it before anything is copied.
8. **CLAUDE.md §4: consent to this exact line,** added after the `bw intake` line:
   ```
   bw answers DEAL --from FILE        # records the buyer's intake answers (prices, structure ideas, AI consent)
   ```
   - **Recommended,** so every session knows the command. Nothing else in CLAUDE.md changes.
9. **Budget:** about 3 hours for P4a, about 2.5 for P4b (Q1). Tech plan §9 updated in its own commit.

### For P4b, to answer now or when its plan comes (they are your judgment as the CPA)
- **B1. Earnings until P7 computes them.** You key in last-FY and prior-FY supportable earnings, each
  with a required source note (document and page, or "CPA judgment"). The source is stored with the run
  (invariant 1).
  - **Recommended.**
- **B2. Replacement salary and capex reserve are required on every run** (0 allowed, but typed). Taxes
  and other debt service default to 0 and are shown in the output.
  - **Recommended:** a forgotten deduction would overstate the maximum financeable price.
- **B3. SBA rate.** The lender's quoted rate from the answers, otherwise `--sba-rate`. The rules file's
  default (Prime + spread) is never used silently.
  - **Recommended.**
- **B4. Price tested.** The proposed price, or the asking price if there is none. The maximum financeable
  price and the 10% and 20% earnings-miss sensitivity are always shown.
  - **Recommended.**

## Risks and rollback
- **Client data:** the answers file is copied through `ops/files.py` into the deal folder and refused from
  inside the repository, the data folder or the backup folder. Tests use synthetic files and a fake
  repository. Manual runs here use a scratch `BIZWAVE_DATA_DIR`.
- **YAML:** `safe_load` only; strict model; money parsed exactly. Floats are taken by their written form,
  not binary.
- **The clock change (Q2):** one function, called by all three commands; tested on each path.
- **Migration:** additive (a new table), round-trip tested with rows. The live database gets a snapshot
  before upgrading (M11).
- **Dry run:** shares the planning code with the real run. A test checks it writes nothing, not even a
  folder.
- **Rollback:** revert the branch; `python -m bizwave_preloi.db downgrade --url ... 0001_core` drops only
  `intake_answers`.

## Lessons applied
- [W1, promoted] Go-ahead recorded with its time after the latest Revision log row → this plan stops now.
- [P1, promoted] Each gate test fails first for its own reason; refusal tests use a fake repository → the
  first run is recorded per test; the source refusals use `fake_repo`.
- [P1, P2, P3 → reviewer checklist 1, /execute (PR #8)] Contract reach → clarifications made while
  writing the gate go into the Data contract in the gate commit; the contract above names every refusal
  and status effect.
- [P3 → checklist 8 (PR #8)] Location rules in both directions with `config.is_inside`; client files only
  through `ops/files.py` → the answers file and dry run use them.
- [P3 → checklist 10 (PR #8)] One item never stops the batch → no change to intake's per-file handling,
  except the carried fix; answers are one file, refused as a whole.
- [P2/W1 → checklist 9 (PR #8)] Pin what never changes → the help test checks a subset; constraint names
  are pinned, the migration head is not.
- [P3, note] Near-miss tests for every pattern → the projections row has near misses in the gate.
- [P3, note] A new setting arrives with its isolation → no new setting in P4a.
- [P3, note] Every promised case gets a test, checked by breaking the line → after the build, each fix
  is broken in a scratch copy.
- [P2, note] Work out expected values by running; test the way it runs → fixture values come from runs;
  the suite runs on 3.12 and 3.13.
- [P2, note] Check inputs where they enter → `parse_intake_answers` and `record_intake_answers` refuse
  before writing.
- [P2, note] Destructive defaults → nothing in P4a deletes or replaces; a revision keeps the earlier set.

## Revision log
Dates as `YYYY-MM-DD HH:MM`, Pacific time (`tests/test_workflow.py` reads them).

| Date | What changed | Stopped for Chan |
|---|---|---|
| 2026-11-06 22:50 | Plan written (research: `tasks/research/2026-11-06_p4_financeability.md`) | yes |

## Reviewer Note
<Chan writes here. Claude answers each point below it, adds a Revision log row, and stops again.>

## Gate — first run
<before any code>

## Spec amendment
<only if the gate proves this plan wrong>

## Results
<filled at close>

## Master-plan change proposal
<at close>
