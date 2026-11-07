# 2026-11-06 — W1 Self-improvement loop (workflow packet)

Status: **signed off 6 Nov 2026 16:26** (Chan, chat: "2. Go ahead" to the proposal below) · building
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
In: CLAUDE.md §4 (command list), §6 (rules and steps 2, 8, 9), §8 (one line); `.claude/commands/`
(`improve.md` new; `plan-packet`, `execute`, `verify-packet`, `review-packet`, `close-packet`, `lessons`,
`sprint-status` updated); `.claude/agents/packet-reviewer.md`; `tasks/plans/_TEMPLATE.md`;
`tasks/lessons.md` (statuses); records: P1 confirmation, decisions D12 and D16.
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
- [ ] W1.6 Records: P1 confirmation (P1 plan), D12 and D16 made (`docs/decisions.md`)

## Gate tests (written first)
| Test | Asserts |
|---|---|
| `test_every_command_has_frontmatter_and_improve_exists` | 9 command files incl. `improve.md`, each with a description and `disable-model-invocation: true` |
| `test_review_agents_cannot_edit` | `gate-runner` and `packet-reviewer` tools contain no Edit or Write |
| `test_claude_md_self_improvement_rules` | §6 has the capture, read and promote rules naming `tasks/lessons.md` and `/improve`; §4 lists `/improve`; §8 has the refusal-test line |
| `test_template_has_lessons_and_revision_log` | `## Lessons applied` and `## Revision log` in `_TEMPLATE.md` |
| `test_every_claude_lesson_has_a_status` | every bullet under "For Claude Code (Me)" starts with `[note]`, `[promoted → …]` or `[retired]` |
| `test_p1_lessons_promoted_where_promised` | the four P1 lessons are promoted, and each destination file contains the rule |
| `test_reviewer_checks_lessons_and_commit_claims` | reviewer prompt names `tasks/lessons.md`, repeat = should-fix, commit-message approval check, refusal-test check |
| `test_plan_packet_reads_lessons_and_stops_again` | `/plan-packet` reads lessons, fills "Lessons applied", stops again after any revision |
| `test_execute_records_each_gate_test_failing_first` | `/execute` requires each gate test's first-run result |

## Depends on
Decisions: none. Packets: P1 (merged).

## Risks and rollback
Process overhead: `/improve` adds a few minutes per packet; promotions keep the loop from repeating
mistakes. Rollback: revert the branch.

## Lessons applied
- [P1] Stop again after revising a plan: this plan records the approved proposal verbatim; anything
  beyond it will stop for Chan.
- [P1] Never claim approval beyond what is on record: commit messages cite "Chan, chat 16:26".

## Revision log
| Date | Change | Stopped for Chan |
|---|---|---|
| 6 Nov 16:26 | Plan written from the approved proposal | — (approval given before the plan) |

## Reviewer Note
<Chan>

## Gate — first run
6 Nov, before any change: 11 failed, 1 passed. Each failure is the missing rule or file it tests
(`improve.md` missing; no self-improvement rules in CLAUDE.md; no template sections; lessons without
status; reviewer, `/plan-packet`, `/execute`, `/verify-packet`, `/review-packet`, `/sprint-status`,
`/close-packet` lacking the new steps).
Passed before the change, on purpose: `test_review_agents_cannot_edit` is a preservation check (the two
independent agents must stay read-only through this packet), not new behaviour.

## Spec amendment
<none>

## Results
<filled at step 9>
