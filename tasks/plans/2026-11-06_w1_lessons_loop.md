# 2026-11-06 — W1 Self-improvement loop (workflow packet)

Status: **closed 2026-11-06** · go-ahead 17:29 PT · review round 3 PASS WITH FIXES · **merge only after
Chan consents to the exact CLAUDE.md text on this branch, including b** (see Reviewer Note and Results).
Chan's "2. Go ahead" (chat, 16:26) approved the proposal below, not this plan, which was written afterwards.
Branch: `w1-lessons-loop` · Gate: `tests/plans/test_2026_11_06_w1_lessons_loop.py` · Budget: 1 hour
Research step skipped: light packet. Not one of P1–P15: a workflow packet ("W") before P2 so P2 uses it.

## Goal
Lessons stop being a diary and start changing behaviour: captured the moment a mistake is found, read
before every plan, and promoted into enforced places (reviewer checklist, command steps, the plan
template, tests, CLAUDE.md) with each lesson's status tracked.

**Done when:** CLAUDE.md §6 carries the self-improvement rules; `/improve` exists; `/plan-packet`,
`/execute`, `/verify-packet`, `/review-packet`, `/lessons`, `/sprint-status` and the reviewer apply them;
the plan template has "Lessons applied" and "Revision log"; four P1 lessons are promoted and every lesson
has a status; the whole suite passes.

## The approved proposal (chat, 6 Nov 16:23–16:26)
1. Capture right away: add a lesson the moment a correction happens (gate-runner RED, a review finding at
   should-fix or above, or Chan correcting Claude).
2. Read before planning: at session start and in `/plan-packet`, read the lessons; each plan lists the
   ones it applies under "Lessons applied".
3. New `/improve`: after `/lessons`, decide for each lesson: keep as a note, promote to an enforced place
   (showing the exact edit), or retire; mark its status ("promoted → reviewer checklist").
4. Reviewer checks that applicable lessons were applied; repeating a promoted lesson is at least a
   should-fix.
5. `/sprint-status` flags repeats; the same kind of finding in two packets means promote it.
6. First run, P1's lessons: (a) stop again after revising a plan → template revision log and
   `/plan-packet` step; (b) each gate test must fail on its own before the code → `/execute` records
   each test's first failure; (c) refusal tests must not be able to write into the real repo → reviewer
   checklist and CLAUDE.md §8; (d) no approval claimed in a commit message that is not on record →
   reviewer checklist. The fifth P1 lesson stays a note.

## Scope
In: CLAUDE.md §4 (command list), §6 (steps 2, 3 and 9, and a new "Self-improvement" rules block), §8 (one
line); `.claude/commands/`
(`improve.md` new; `plan-packet`, `execute`, `verify-packet`, `review-packet`, `close-packet`, `lessons`,
`sprint-status` updated); `.claude/agents/packet-reviewer.md`; `tasks/plans/_TEMPLATE.md`;
`tasks/lessons.md` (statuses); records: P1 confirmation, decisions D12 and D16 (also added after review:
D1–D3 dates, decisions M7 and M8, W1 in `tasks/sprint.md`). Corrections approved after review round 1
(Reviewer Note b–e): CLAUDE.md §6 step 4 (one line); the gate (spec amendment); `/execute` and the
template (Go-ahead line); new `tests/test_workflow.py`; the P1 plan (frozen exception).
Out: product code; the two P1 master-plan proposals (Chan asked for an explanation first).

## Data contract
- Lesson line format in `tasks/lessons.md`, "For Claude Code (Me)" sections:
  `- [status] lesson text (source: <review/packet ref>)` where status is one of
  `note`, `promoted → <where>`, `retired`.
- Plan template gains `## Lessons applied` (lesson, how this plan applies it) and `## Revision log`
  (date, what changed, "stopped for Chan: yes/no").
- `/improve` output: a table of lessons with proposed status and, for promotions, the exact edit; edits to
  `.claude/` and the template applied after Chan's OK; CLAUDE.md edits only with explicit consent.

## Sub-packets
- [x] W1.1 CLAUDE.md §4, §6, §8
- [x] W1.2 Commands: new `/improve`; updated `plan-packet`, `execute`, `verify-packet`, `review-packet`,
      `close-packet`, `lessons`, `sprint-status`
- [x] W1.3 Reviewer agent checklist
- [x] W1.4 Plan template sections
- [x] W1.5 `tasks/lessons.md`: status on every lesson; four P1 lessons promoted
- [x] W1.6 Records: P1 confirmation (P1 plan), D12 and D16 made (`docs/decisions.md`)

Corrections after review round 1 (Reviewer Note, b–e; what is still open for Chan is listed there):
- [x] W1.7 Gate spec amendment (c)
- [x] W1.8 CLAUDE.md §6 step 4 line (b)
- [x] W1.9 Go-ahead check (d): `/execute`, plan template, new `tests/test_workflow.py`
- [x] W1.10 P1 plan: frozen exception (e); W1 lesson statuses (bookkeeping, not part of b–e: the tags
      record where round-1 fixes now live)

## Gate tests (written first)
| Test | Asserts |
|---|---|
| `test_every_command_has_frontmatter_and_improve_exists` | the 9 command files incl. `improve.md` exist (more are allowed, after the spec amendment), each with a description and `disable-model-invocation: true` |
| `test_review_agents_cannot_edit` | `gate-runner` and `packet-reviewer` tools contain no Edit or Write |
| `test_claude_md_self_improvement_rules` | §6 has the capture, read and promote rules naming `tasks/lessons.md` and `/improve`; §4 lists `/improve`; §8 has the refusal-test line |
| `test_template_has_lessons_and_revision_log` | `## Lessons applied` and `## Revision log` in `_TEMPLATE.md` |
| `test_every_claude_lesson_has_a_status` | every bullet under "For Claude Code (Me)" starts with `[note]`, `[promoted → …]` or `[retired]` |
| `test_p1_lessons_promoted_where_promised` | each of the four named P1 lessons carries a status (exact counts until the spec amendment); destinations hold the rule: "stop again" in `/plan-packet` (already true on main), per-test first run in `/execute`, real-repository and commit-message checks in the reviewer, refusal line in CLAUDE.md §8 |
| `test_reviewer_checks_lessons_and_commit_claims` | reviewer prompt names `tasks/lessons.md`, "Lessons applied", repeat = should-fix |
| `test_plan_packet_reads_lessons_and_stops_again` | `/plan-packet` reads lessons, fills "Lessons applied" and "Revision log", stops again after any revision |
| `test_execute_records_each_gate_test_failing_first` | `/execute` requires each gate test's first-run result and flags a test that passes before the code |
| `test_corrections_capture_lessons_immediately` (2 cases) | `/verify-packet` and `/review-packet` write lessons when a correction happens |
| `test_improve_and_sprint_status_handle_promotion_and_repeats` | `/improve` covers note, promote, retire and CLAUDE.md consent; `/sprint-status` reports repeats from `tasks/lessons.md`; `/close-packet` calls for `/improve` |
Not covered: the text of `.claude/commands/lessons.md` itself (only the lessons data file is checked).

## Depends on
Decisions: none. Packets: P1 (merged).

## Risks and rollback
Process overhead: `/improve` adds a few minutes per packet; promotions keep the loop from repeating
mistakes. Rollback: revert the branch.

## Lessons applied
- [P1, promoted] Stop again after revising a plan: intended to apply by recording the approved proposal
  verbatim. **Not applied in practice**: the plan was not shown to Chan before building (review round 1,
  should-fix 1).
- [P1, promoted] Never claim approval beyond what is on record: **not applied** to commit 055b55f's subject
  (review round 1, should-fix 1).
- [P1, promoted] Each gate test fails first for its own reason: applied; the one early pass is declared a
  preservation check.
- [Day 0] Do not shadow built-in command names: applied (`/improve` is not a built-in).
- [W1, promoted] Record the go-ahead with date and time, after the latest revision: **not applied** in
  9bbd463, which added sub-packets from Chan's answers without a Revision log row and built at once
  (review round 2, should-fix 1); applied from correction round 2 (rows added; Chan's literal "go ahead"
  recorded at 17:29, after the latest row).
- [W1, note] Do not pin state the loop is meant to change, and fail closed: applied by the gate spec
  amendment (c) and the fail-closed go-ahead check.
- [W1, note] Every edit to Scope or Sub-packets gets a Revision log row: applied from correction round 2.
- [W1, note] Questions to Chan show exact text, impact and a recommendation: applied to b at 17:30 and to
  the CLAUDE.md consent requested at close; **not applied** to the 16:53 list, which summarised the
  CLAUDE.md changes instead of showing the text (review round 3, should-fix 1).
- [W1, note] Re-check commit messages after a record is corrected: applied at close (Results notes).

## Revision log
| Date | Change | Stopped for Chan |
|---|---|---|
| 2026-11-06 16:28 | Plan written from the approved proposal (committed with the gate, 055b55f) | no (approval given before the plan existed) |
| 2026-11-06 16:39 | Records corrected after review round 1 (scope, gate table, lessons applied); `/improve` test route and wording fixed; spec amendment proposed (64c53d8) | yes |
| 2026-11-06 17:09 | Chan's answers recorded; Scope and correction sub-packets W1.7–W1.10 added from them (9bbd463) | no: W1.7 was built 24 seconds later (review round 2, should-fix 1) |
| 2026-11-06 17:24 | Correction round 2: chat questions recorded verbatim; the 17:04 line relabelled as a confirmation, not a go-ahead; b wording and d details put to Chan; `tests/test_workflow.py` fails closed (review round 2, should-fix 3); Lessons applied; W1.10 label | yes |

Times are Pacific time, to the minute the row was written (from the commits; the 17:24 row's commit
landed at 17:25).

## Reviewer Note
**Was open for Chan (review round 1, should-fix 1 and 2), as written in this plan:**
1. Confirm this plan and the exact CLAUDE.md diff on this branch (§4 command list; §6 steps 2, 3 and 9;
   the new "Self-improvement" block; §8 refusal-test line), or name the lines to revert. Only the §8 line
   was named in the approved proposal.
2. Also consent (or not) to one more CLAUDE.md line the review found stale: §6 step 4 "Paste the failure
   summary" → "Paste each gate test's first-run result (flag any test that passed before the code)".
3. Approve the proposed spec amendment below (the W1 gate stops pinning exact counts).

**The questions as Chan saw them in chat (verbatim).** About 16:43 PT:
> - **a.** Confirm the W1 plan and these `CLAUDE.md` changes, or name the lines to revert. Only the first was in the proposal.
>   - a section 8 line saying tests of a refusal must use a fake repo
>   - `/improve` added to the command list
>   - plan step reads the lessons first
>   - sign-off step: stop again after every revision, and answers don't count as sign-off
>   - close step adds `/improve`
>   - the new "Self-improvement" rules block
> - **b.** One more `CLAUDE.md` line the review found out of date. "Paste the failure summary" in the tests-first step becomes "paste each new test's first result, and flag any test that passed before the code".
> - **c.** Let W1's tests stop pinning exact lesson counts and the exact command list. As written, the first time `/improve` re-sorts a lesson, or a later packet adds a command, the suite fails.
> - **d.** A mechanical check, which is the real fix for my repeat. `/execute` refuses to start unless the plan's Reviewer Note has a "Go-ahead" line with a date and time later than its last revision, and a test checks this too. I recommend yes.
> - **e.** One older P1 test still uses the real repo folder, which breaks the new rule. Either freeze it as a recorded exception (I recommend this) or amend it.

About 16:53 PT, after Chan's question on a:
> Please also confirm the rest of (a), the `CLAUDE.md` changes in W1. Only the first was in your approved proposal.
> 1. The fake-repo line in "things that will bite" (above). […the explanation of the fake-repo rule, sent just before, is omitted here]
> 2. `/improve` in the command list.
> 3. The plan step reads lessons first and lists the ones it applies.
> 4. The sign-off step: stop again after every revision, and answering questions isn't sign-off.
> 5. The close step adds `/improve`.
> 6. A new "Self-improvement" rules block: capture lessons immediately, read them before planning, promote them through `/improve`, and treat repeats as at least should-fix.
>
> […] **W1 (e): the one P1 test.** P1's own early tests include one that points at the real repo folder, the pattern (a) now says to avoid. Our rules say a committed test of that kind can only change through an approved spec amendment. The options:
> - **Freeze (my recommendation):** leave it and record it as a known exception. The risk is tiny. It could only leave empty folders in `deals/`, and only if the refusal broke. The newer pretend-repo tests cover the same refusal and would fail loudly first.
> - **Amend:** approve rewriting that test to use the pretend repo. It's about 10 minutes and cleaner, but it reopens a closed packet's tests.
>
> Either is fine; tell me which.

Note: the 16:53 list summarised the CLAUDE.md changes; the exact text was not shown in chat (review round 3,
should-fix 1). Consent to the exact text is requested at close.

**Chan's answers (chat), as given:**
- 2026-11-06 16:52 PT: "W1: a - why fake repo? is this severe?, b ok, c ok, d yes, e please elaborate on this."
- 2026-11-06 17:04 PT: "1. Yes 2. Yes 3. Yes 4. Yes 5. Yes 6. Yes / w1(e) - freeze"

**What they settle, and what they do not (Claude's reading, for Chan to correct):**
- **a**, 1–6 "Yes": the six CLAUDE.md changes as listed. Nothing reverted. The 16:43 question also asked
  to confirm "the W1 plan"; the 16:53 list covered only the CLAUDE.md changes, so the plan itself has no
  explicit confirmation on record.
- **b** "ok": answered the chat wording above. The line applied in 4c9c1b3 uses this plan's wording
  (item 2 above), which the chat did not show. The two differ in scope, not only in words: "each new
  test" also reads as every module test added in a build, and would disagree with `/execute` and the
  template, which say "gate test": **open.**
- **c** "ok": the spec amendment below; applied in 3de3632.
- **d** "yes": the check as worded in chat. Its details were written afterwards and not shown: **open**
  (listed below).
- **e** "freeze": recorded in the P1 plan's `## Frozen exception` (9d8c482).

Recorded, 2026-11-06 17:04 PT: "1. Yes … 6. Yes", a confirmation of the six CLAUDE.md items, not a
go-ahead for this plan.

**d as built (51ae7f3, and correction round 2), for Chan's OK:**
- `/execute` stops unless the Reviewer Note has a line `Go-ahead: YYYY-MM-DD HH:MM PT (<where, Chan's
  words>)` whose time is not earlier than the latest Revision log row. (The chat said "later than"; the
  same minute is accepted.) The line is written only after Chan gives the go-ahead, quoting him.
- The plan template states the `YYYY-MM-DD HH:MM` date format for Revision log rows and carries the
  Go-ahead placeholder.
- `tests/test_workflow.py` checks every plan in `tasks/plans/`. A plan missing any of the four headings it
  reads (Sub-packets, Revision log, Reviewer Note, Gate — first run) fails. Once work has started (a
  ticked box anywhere in the plan, or a first run recorded), every Revision log row needs a
  `YYYY-MM-DD HH:MM` date, and the Go-ahead line must be present and not earlier than the latest row.
  Code fences are ignored.
- Exempt: the scaffold and P1 plans, written before the rule.

**Open for Chan now:**
1. b: keep the applied wording ("Paste each gate test's first-run result (flag any test that passed
   before the code)"), or use the chat wording ("paste each new test's first result, and flag any test
   that passed before the code")?
2. d: OK the details as built (above), or name what to change.
3. A go-ahead on this plan as it now stands. Until it is recorded here, `tests/test_workflow.py` reports
   this plan RED by design.

**The questions as Chan saw them in chat, about 17:26 PT (verbatim excerpt):**
> **What I need from you**
> 1. **(b) wording.** Which exact text should the CLAUDE.md line use?
>    - Keep what's applied: "Paste each gate test's first-run result (flag any test that passed before the code)".
>    - Or use the chat version: "paste each new test's first result, and flag any test that passed before the code".
> 2. **(d) as built.** Are you OK with these details?
>    - `/execute` won't start unless the plan has a line `Go-ahead: YYYY-MM-DD HH:MM PT (your words)`, timed no earlier than the plan's last revision. A go-ahead in the same minute counts.
>    - A test checks every plan. A plan missing one of the four headings the check reads fails. Once any box is ticked or the first test run is recorded, the revision dates and the go-ahead line must be valid.
>    - The scaffold and P1 plans are exempt because they were written before the rule.
> 3. **A go-ahead on the W1 plan as it now stands.** Please reply with the words "go ahead". The review pointed out that a numbered "Yes" confirms the items I asked about, not a plan I revise afterwards. Your 17:04 answer is recorded as confirming the six CLAUDE.md items, not as a go-ahead.
> 4. **P2 (still open).** Do you approve changing the P2 gate's expected file size from 340 to 330? It's my arithmetic error, and nothing else changes.

**Chan's answers, 2026-11-06 17:29 PT (chat), as given:** "1. b - what's the difference? / 2. d - Yes -
checks every plan, agreed / 3. go ahead / 4. yes approved" (4 is the P2 spec amendment).
- 1 (b): a question, not a choice. The difference and its impact were explained in chat at about 17:30
  ("gate test" vs "new test", "first-run result" vs "first result"; no product impact; "new test" is
  broader and would disagree with `/execute` and the template; recommendation: keep the applied wording).
  **Still open**; CLAUDE.md:135 stays as applied until Chan picks, and W1 does not merge before then.
- 2 (d): the details as built are approved.
- 3: go-ahead on this plan as it stands (Revision log row 2026-11-06 17:24).
- Also: "can you make sure you also share impact on my decisions? … Make sure all responses should not
  result in breakage of the product." Captured as a lesson.

Go-ahead: 2026-11-06 17:29 PT (chat: "3. go ahead")

## Gate — first run
6 Nov, before any change: 11 failed, 1 passed. Each failure is the missing rule or file it tests
(`improve.md` missing; no self-improvement rules in CLAUDE.md; no template sections; lessons without
status; reviewer, `/plan-packet`, `/execute`, `/verify-packet`, `/review-packet`, `/sprint-status`,
`/close-packet` lacking the new steps).
Passed before the change, on purpose: `test_review_agents_cannot_edit` is a preservation check (the two
independent agents must stay read-only through this packet), not new behaviour.

## Spec amendment
**Proposed after review round 1 (2026-11-06 16:39); approved by Chan 2026-11-06 16:52 PT (chat, "c ok").**
Applied to the gate in its own commit; no other line of the gate changes.
- `test_p1_lessons_promoted_where_promised`: replace the exact counts (4 promoted, 1 note) with: each of
  the four named P1 lessons carries a status, and each destination contains its rule. Why: `/improve`
  exists to change statuses; exact counts would turn the suite RED on every legitimate re-sort.
- `test_every_command_has_frontmatter_and_improve_exists`: `EXPECTED_COMMANDS <= found` instead of
  equality. Why: a later packet adding a command must not break W1's gate.

## Results
**What changed**
- CLAUDE.md: §4 adds `/improve`; §6 steps 2, 3, 4 and 9 and a new "Self-improvement" block; §8 the
  refusal-test line. Exact text awaiting Chan's consent before merge (see below).
- `.claude/commands/`: new `improve.md`; `plan-packet`, `execute` (Go-ahead check), `verify-packet`,
  `review-packet`, `close-packet`, `lessons`, `sprint-status` updated. `.claude/agents/packet-reviewer.md`
  checklist items 11–13.
- `tasks/plans/_TEMPLATE.md`: Lessons applied, Revision log (dated `YYYY-MM-DD HH:MM`), Go-ahead
  placeholder, per-test first run.
- New `tests/test_workflow.py`: the go-ahead check, run on every plan, failing closed.
- `tasks/lessons.md`: a status on every lesson; four P1 lessons promoted; W1 entry (six lessons).
- Records: P1 confirmation and frozen exception; decisions D12, D16, M7, M8; D1–D3 dates; W1 in the sprint.

**Tests:** gate 12/12 (two tests changed once, by the approved spec amendment); `tests/test_workflow.py`
30 cases; whole suite 200 passed (170 at round 1). Independent gate-runner runs: GREEN at 9d8c482 (186),
GREEN at 54929ca (193); the round-3 nit fixes (1d64f55) were run by the implementer only (200 passed).

**Review:** round 1 PASS WITH FIXES (3 should-fix, 10 nits); round 2 PASS WITH FIXES (3 should-fix, 6
nits); round 3 PASS WITH FIXES (2 should-fix, 7 nits). Both correction rounds used. Round-3 should-fix 2
and the code and record nits are fixed below; should-fix 1 (exact-text consent to CLAUDE.md) needs Chan
and blocks the merge. Reports: `tasks/reviews/2026-11-06_w1_lessons_loop.md`.

**Before merge (Chan):** consent to the exact `git diff main...w1-lessons-loop -- CLAUDE.md` (5 hunks),
including the wording of the §6 step 4 line (b). If any line is not consented, it is reverted to main's
text in its own commit before merge. Merge W1 before P2; P2 is then rebased, and the two §8 additions
(W1's refusal-test line, P2's two SQLite lines) are kept word for word and shown to Chan.

**Deviations**
- Built before the plan was shown (round 1) and corrections built before a logged stop (9bbd463);
  recorded in the Revision log as "no". The go-ahead (17:29) came after the whole build.
- Commits not split as the loop asks: 055b55f (plan with gate), e359adb (W1.3 with W1.4), 7376acf
  (review save, lessons and fixes together; the fix commit came before the lessons commit).

**Commit messages that claim more than the record** (no history rewrite; this is the correction):
- 055b55f: "approved by Chan in chat 16:26: 'Go ahead'": Chan approved the chat proposal, not this plan.
- 213c3f8 (W1.1, CLAUDE.md): "Approved by Chan … 16:26 'Go ahead' to the proposal": the proposal named only
  the §8 line; §4 and §6 were confirmed at 17:04 as summarised items, and the exact text is still awaiting
  consent.
- 9bbd463: "and go-ahead in the plan" and "corrections W1.7-W1.10 listed as approved": the 17:04 answer was
  a confirmation of six CLAUDE.md items, not a go-ahead; d's details were approved only at 17:29; W1.10's
  lesson tags were not part of b–e.
- 4c9c1b3: "("b ok" to this text)" and "the consented wording": "b ok" answered the chat wording, which
  differs; b is still open.

**Hours:** not tracked; commits span 16:28–17:45 on 6 Nov against a 1-hour budget, including three review
rounds.

**Proposals for later (from the reviews; none built; for a small workflow packet after P2):**
- The go-ahead must predate the build: compare its time with the gate file's first commit (rounds 2–3).
- Chan types the `Go-ahead:` line himself, so it cannot be written for him (round 2).
- Reviewer checklist item 12: the LEGACY exemption list does not grow and the check is not loosened.
- `/plan-packet` names the `YYYY-MM-DD HH:MM` format (only the template does now).
- `/execute` or `/verify-packet`: a RED from a plan waiting for its go-ahead is the stop signal, not a
  defect (round 3).
- `/improve` candidates: "every edit to Scope or Sub-packets gets a Revision log row" into `/plan-packet`;
  "re-check commit messages after a record is corrected" into `/close-packet`.

Notes for the record:
- Commit 055b55f's subject ("approved by Chan in chat 16:26: 'Go ahead'") overstates the approval: Chan
  approved the chat proposal, not this plan. History is not rewritten.
- The gate was committed together with the plan (055b55f), and W1.3 and W1.4 share a commit (e359adb);
  the loop asks for separate commits.
- W1.5 back-filled "(source: …)" on every older lesson as a one-off migration; afterwards only status
  tags change.
