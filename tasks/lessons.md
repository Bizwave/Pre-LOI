# Lessons

Newest first. One entry per packet or session, written by `/lessons` at close and the moment a mistake
is found (CLAUDE.md section 6, "Self-improvement"). Every "For Claude Code (Me)" line carries a status set
by `/improve`: `[note]`, `[promoted → where it is now enforced]` or `[retired]`.

## W1 self-improvement loop (2026-11-06, branch `w1-lessons-loop`)

### For You (Chan)
- A "go ahead" on a proposal in chat covers that proposal's words, not a plan written afterwards or
  CLAUDE.md text you have not seen. Expect to be shown the plan and any CLAUDE.md diff before building.
- Promoting a lesson to a checklist did not stop me repeating it in the very next packet; the reviewer
  caught it after the fact. A mechanical check before building (proposed) is the stronger fix.

### For Claude Code (Me)
- [promoted → tests/test_workflow.py go-ahead check, /execute, plan template] A go-ahead given before a
  plan exists covers only the proposal text. Write the plan, show Chan the plan and the exact CLAUDE.md
  diff, and wait; record the go-ahead with date and time in the Reviewer Note before writing the gate.
  Repeat of promoted lessons (a) and (d). (source: W1 review round 1, should-fix 1)
- [note] A gate must not pin state the loop is designed to change (exact lesson counts, the exact list of
  commands). Assert presence and destinations, not totals. (source: W1 review round 1, should-fix 2)
- [promoted → /improve steps 2 and 5] `/improve` promotions to tests go in module test files
  (`tests/test_<module>.py`), never into an existing gate without a spec amendment, and are committed
  separately. (source: W1 review round 1, should-fix 3)

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
