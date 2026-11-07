---
description: Self-improvement — sort every lesson into note, promote (with the exact edit) or retire
argument-hint: "[packet id, optional]"
disable-model-invocation: true
---

Turn lessons into enforced rules (CLAUDE.md section 6, "Self-improvement"). Run after the packet's lessons
are written at close, or any time. $ARGUMENTS

1. Read `tasks/lessons.md` (every "For Claude Code (Me)" bullet), `tasks/reviews/` and the plans in
   `tasks/plans/`. Note any finding that repeats across packets.
2. For each lesson whose status is `[note]` or missing, propose ONE of:
   - **keep** `[note]`: useful context, nothing to enforce;
   - **promote** `[promoted → <where>]`: the rule belongs somewhere enforced. Choose the narrowest
     place that will actually catch it:
     - a test: always a module test file (`tests/test_<module>.py`, or a new `tests/test_workflow.py`
       for process rules), **never an existing gate in `tests/plans/`** (changing a committed gate
       needs a `## Spec amendment` and Chan's OK, through the packet loop, not this command);
     - the `packet-reviewer` checklist; a step in a command; the plan template;
     - CLAUDE.md, only for rules every session must hold;
   - **retire** `[retired]`: no longer true, or superseded.
   When the same kind of finding appears in two packets, propose promotion; keeping it as a note is not
   an option.
3. Show Chan a table: lesson → proposed status → for promotions, the exact edit (file and text).
4. Apply only what Chan approves, line by line:
   - edits to `.claude/` commands and agents, the plan template and module tests: on Chan's OK;
   - edits to CLAUDE.md: only with Chan's explicit consent to that exact text;
   - then set each lesson's status in `tasks/lessons.md`, e.g.
     `- [promoted → packet-reviewer checklist] ...`.
5. Commit these edits on their own: `[Day N] P<n> improve`. Chan's line-by-line OK is their review. If a
   promotion added or changed a test, have the **gate-runner** subagent run the whole suite once; do not
   go back into `/review-packet` (that would be a third review round).
6. Report what was promoted, kept and retired. Do not change product code from this command.
