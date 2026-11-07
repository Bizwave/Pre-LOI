---
description: Self-improvement — sort every lesson into note, promote (with the exact edit) or retire
argument-hint: "[packet id, optional]"
disable-model-invocation: true
---

Turn lessons into enforced rules (CLAUDE.md section 6, "Self-improvement"). Run after `/lessons` at
packet close, or any time. $ARGUMENTS

1. Read `tasks/lessons.md` (every "For Claude Code (Me)" bullet), `tasks/reviews/` and the plans in
   `tasks/plans/`. Note any finding that repeats across packets.
2. For each lesson whose status is `[note]` or missing, propose ONE of:
   - **keep** `[note]`: useful context, nothing to enforce;
   - **promote** `[promoted → <where>]`: the rule belongs somewhere enforced. Choose the narrowest
     place that will actually catch it:
     a test (best: it fails), the `packet-reviewer` checklist, a step in a command, the plan template, or
     CLAUDE.md (only for rules every session must hold);
   - **retire** `[retired]`: no longer true, or superseded.
   Promote automatically when the same kind of finding appears in two packets.
3. Show Chan a table: lesson → proposed status → for promotions, the exact edit (file and text).
4. Apply after Chan's OK:
   - edits to `.claude/` commands and agents, the plan template and tests: on Chan's OK;
   - edits to CLAUDE.md: only with Chan's explicit consent to that text, in their own commit;
   - then set each lesson's status in `tasks/lessons.md`, e.g.
     `- [promoted → packet-reviewer checklist] ...`.
5. If a promotion adds a test, run the whole suite and hand over to `/verify-packet`.
6. Report what was promoted, kept and retired. Do not change product code from this command.
