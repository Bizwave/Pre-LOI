# Lessons

Newest first. One entry per packet or session, written by `/lessons` at close and the moment a mistake
is found (CLAUDE.md section 6, "Self-improvement"). Every "For Claude Code (Me)" line carries a status set
by `/improve`: `[note]`, `[promoted → where it is now enforced]` or `[retired]`.

## P3 command line (2026-11-06, branch `p3-cli`)

### For You (Chan)
- The review showed how a wrong `--from` folder would mix clients: a folder that *contains* BizWaveData
  was accepted, and intake copied the live database and another deal's CIM into this deal, then started
  its clock. Fixed in round 1. Nothing undoes a mistaken intake yet; I will ask you about a `--dry-run`.
- `BIZWAVE_BACKUP_DIR` will hold a copy of every client file. It needs the same protection as
  BizWaveData: encrypted storage, and a Claude Code deny rule (your OK needed; asked at close).

### For Claude Code (Me)
- [note] Location refusals work in both directions and through links: refuse a folder that *contains* a
  protected folder (data, deals, backups, the repository) as well as one inside it, and compare paths with
  `config._real()` (links followed, case folded), never with `==`. Same kind as P1's run-log location gap:
  a promotion candidate for `/improve`. (source: P3 review round 1, should-fixes 1 and 8)
- [note] "Never overwrite" holds against every record of a name and through interruptions: pick names
  against recorded paths as well as the disk; write to an exclusive temporary file and link it into place;
  a backup never replaces a copy that differs (a difference means damage), it keeps both; a snapshot is
  written as `.partial` and renamed. Same kind as P2's destructive-defaults note: a promotion candidate.
  (source: P3 review round 1, should-fixes 3, 4, 5 and 6)
- [note] Every keyword pattern gets a near-miss test, a name that must not match ("NDA - Confidential
  Information", "Forecast" containing "recast"). (source: P3 review round 1, should-fix 2)
- [note] One bad item never stops a batch: catch per-item errors, including `OSError`, into that item's
  problem; the command line catches `OSError` at its edge and prints one line. (source: P3 review round 1,
  should-fix 7)
- [note] A new setting arrives with its test isolation (`_CLEARED` in conftest) and, if it names a folder
  that holds client data, the same deny-rule guidance as the data folder, in the same commit. (source: P3
  review round 1, should-fixes 9 and 11)
- [note] Every case the plan promises a test for gets one; check it by deleting the line that implements
  it and watching a test fail. (source: P3 review round 1, should-fix 10)
- [note] The contract lagged the code a third time (P1, P2, P3): clarifications made while writing the
  gate (`recorded`, the no-op upgrade, `hours_since_package_complete`) went into a note, not the contract.
  Same kind in three packets: must be promoted at close (reviewer checklist and `/execute`; Chan's OK).
  (source: P3 review round 1, should-fix 12)
- [note] A gate test whose first failure is a setup error (the missing CLI) has not shown that it fails
  for its own reason; break the behaviour in a scratch copy and record that run. Repeat of a promoted P1
  lesson. (source: P3 review round 1, nit 20)

## P2 database core (2026-11-06, branch `p2-database`)

### For You (Chan)
- The independent reviews earned their time three rounds running. Each found a real problem the tests
  missed: database updates that would fail once deals exist; my fix for that, which stopped two writers
  from waiting for each other; and an undo command that could empty the live database.
- Run `pytest` on your Windows machine (Python 3.12) before merging P2: it is the first run of the
  database file paths on Windows.
- Until P3's backup command exists, copy `BizWaveData` before any manual database command, with nothing
  running.
- I read your "1a" as allowing the one focused review beyond the two-round limit that option described.
  It found one more gap (the contract did not say how far the new guard reaches). If you would rather
  never allow exceptions, say so and I will carry such items to the next packet instead.

### For Claude Code (Me)
- [note] Work out every expected value in a gate by running it (`len(...)`), never by hand: the gate's
  340 should have been 330. (source: P2 gate-runner RED during the build)
- [note] Test the way it will run: on the Python version the tech plan names (3.12) as well as the
  container's 3.13; migrations over a database holding rows, through a table rebuild; any change to
  transactions or the connection pool with two sessions at once; and assert the thing claimed (a column
  only the migration changes). The round-1 fix disabled busy_timeout, undoing it reopened a lost-update
  race, and a CLI fix checked only on 3.13 still failed on 3.12. (source: P2 review round 1 should-fix
  1; round 2 should-fixes 1, 2 and 5; round 3 should-fix 1)
- [note] Check inputs in the function that receives them and raise the contract's error type before
  anything is written; match whole strings with `re.fullmatch` (`$` accepts a trailing newline).
  (source: P2 review round 1, should-fixes 4 and 5)
- [note] Pin what must never change (0001's constraint names, the naming convention), never what grows
  (the newest migration revision). Same kind as W1's "do not pin state the loop changes", now in a
  second packet: a promotion candidate for `/improve`. (source: P2 review round 1 should-fix 8; round 2
  should-fixes 3 and 4)
- [note] When a fix changes behaviour, write its whole reach into the contract in the same commit: who
  else it affects and what state a refusal leaves behind (the deal guard covers every deal update and
  rolls back the whole session). Repeat of P1's [note] on contract changes from review fixes, now in a
  second packet: a promotion candidate for `/improve`. (source: P2 focused review, should-fix 1)
- [note] Look for destructive defaults and shortcut paths in anything touching the live database or the
  deal flow: a bare `downgrade` emptied the live database, and `on_hold` skipped `ready`. (source: P2
  review round 1 should-fix 2; round 3 should-fix 2)

## W1 self-improvement loop (2026-11-06, branch `w1-lessons-loop`)

### For You (Chan)
- A "go ahead" on a proposal in chat covers that proposal's words, not a plan written afterwards or
  CLAUDE.md text you have not seen. Expect to be shown the plan and any CLAUDE.md diff before building.
- Promoting a lesson to a checklist did not stop me repeating it in the very next packet; the reviewer
  caught it after the fact. The mechanical go-ahead check (`/execute` and `tests/test_workflow.py`) is the
  stronger fix.
- A numbered "Yes" confirms the items asked, not the plan as I revise it afterwards. The cleanest sign-off
  is a literal "go ahead" after I show you the final plan; the check now needs one recorded with its time.

### For Claude Code (Me)
- [promoted → tests/test_workflow.py go-ahead check, /execute, plan template] A go-ahead given before a
  plan exists covers only the proposal text. Write the plan, show Chan the plan and the exact CLAUDE.md
  diff, and wait; record the go-ahead with date and time in the Reviewer Note before writing the gate.
  Repeat of promoted lessons (a) and (d). (source: W1 review round 1, should-fix 1)
- [note] Tests of the loop itself: never pin state the loop is meant to change (exact lesson counts, the
  exact command list); assert presence and destinations. And fail closed: when a check cannot find what
  it reads (a heading, a date), it reports a problem instead of skipping the file. (source: W1 review
  round 1, should-fix 2; round 2, should-fix 3)
- [promoted → /improve steps 2 and 5] `/improve` promotions to tests go in module test files
  (`tests/test_<module>.py`), never into an existing gate without a spec amendment, and are committed
  separately. (source: W1 review round 1, should-fix 3)
- [note] Every edit to a plan's Scope or Sub-packets gets a Revision log row, including edits that only
  transcribe Chan's answers; the go-ahead check then forces the stop. Leaving the row out let W1 pass its
  own check. Repeat of promoted lesson (a). (source: W1 review round 2, should-fix 1)
- [note] Questions to Chan: show the exact text he is consenting to (for CLAUDE.md, the diff lines
  themselves, never a summary), with my recommendation, what each option changes now and later, and what
  could break; ask only what his rules reserve for him or what is genuinely his call. Record each
  question and answer verbatim with times. (source: W1 review round 2, should-fix 2; round 3,
  should-fix 1; Chan's correction 2026-11-06 17:29)
- [note] When a record is corrected, re-check every commit message and status line (`tasks/sprint.md`)
  that cited the old record, and note each overclaim in Results (no history rewrite). Repeat of promoted
  lesson (d). (source: W1 review round 3, should-fix 2)

## P1 settings and data folder (2026-11-06, branch `p1-settings`)

### For You (Chan)
- Answering a plan's questions is not the same as signing off the plan. When I revise a plan after your
  answers, I should stop and you should reply "go ahead" (or tell me answers count as sign-off). P1 skipped
  that stop; the reviewer caught it.
- The independent reviewer earned its place on the first packet: it found a real gap the 142 passing tests
  missed (the run log could still be written inside the repo through `BIZWAVE_RUNLOG`, which the old
  `.env.example` pointed at), and proved it by deleting the guard and watching every test still pass.
- If you move the data folder (an encrypted drive, say), add a matching `Read(...)` deny rule in
  `.claude/settings.json`; the default rule covers only `~/BizWaveData`.

### For Claude Code (Me)
- [promoted → plan template Revision log, /plan-packet, CLAUDE.md §6 step 3] After revising a plan in
  response to Chan's answers, STOP again before writing the gate, even for small revisions. Record the
  stop. (source: P1 review round 1, should-fix 4)
- [promoted → packet-reviewer checklist 12, /execute] Never write "approved by Chan" in a commit message
  beyond the exact text Chan approved. (source: P1 review round 2, should-fix 2)
- [promoted → /execute gate first run, packet-reviewer checklist 12] A test that passes before the code
  exists is a warning sign: `test_runlog_defaults_to_data_folder` passed early because the old code read
  the same variable. Check that each gate test fails first for its own reason, not just that the file
  fails to import. (source: P1 build, implementer's observation)
- [promoted → packet-reviewer checklist 13, CLAUDE.md §8] Tests of a refusal must not be able to write
  into the real repository if the refusal breaks: point `config.REPO_ROOT` at a fake repository under the
  test's temp folder. (source: P1 review round 2, nit)
- [note] When a review fix changes the contract, update the plan's contract and spec amendment in the
  same commit as the fix, so the record never lags the code. (source: P1 review round 2, should-fix 1)

## Day 0 — packet loop added to CLAUDE.md (2026-11-06, branch `day-0/packet-loop`)

### For You (Chan)
- The loop is binding through CLAUDE.md itself, which every session loads; the slash commands only make
  it convenient. (Same lesson as the MVP's 2026-08-11 entry: a command file is read only when invoked.)
- Independent checks are two subagents with fresh context that cannot edit files: `gate-runner` (tests)
  and `packet-reviewer` (diff against plan and invariants). Their reports are evidence for your merge.

### For Claude Code (Me)
- [note] Name custom commands so they do not shadow built-ins: `/plan-packet`, `/review-packet`,
  `/verify-packet`, `/sprint-status` rather than `/plan`, `/review`, `/status`. (source: Day 0 setup)

## Day 0 — scaffold (2026-11-06, branch `scaffold/day-0`)

### For You (Chan)
- The MVP's SBA services are not SOP 8.1 and have sign errors in the SDE formula; the MVP's own
  reports may be showing those numbers (`report_generation_routes.py`). Worth a packet in the MVP.
- Every lender view, flag threshold and SBA parameter is a draft until you confirm it; the files say
  so in their `status` / `verified_against_sop_text` fields, and results carry the caveat until then.

### For Claude Code (Me)
- [promoted → CLAUDE.md invariant 9, tests/test_rules.py] YAML 1.1 reads an unquoted `NO` as `false`.
  The category code for non-operating items broke the rules loader on first run. Quote every category
  code; the loader and a test now catch it. (source: scaffold first test run)
- [promoted → tests/test_addback_classifier.py] Apostrophes are dropped in normalization, so "wife's"
  becomes "wifes". Patterns must allow the trailing `s` (`wifes?`, `owners?`, `spouses?`).
  (source: scaffold classifier tests)
- [promoted → CLAUDE.md §6 step 4] The scaffold's tests were written alongside the code, not before
  it. From P1 on, the gate comes first. (source: scaffold self-review)
- [note] A mutation check (changing one Excel formula) confirmed the parity test catches formula
  errors; repeat that check whenever a new parity test is added. (source: scaffold)
