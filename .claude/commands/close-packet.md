---
description: Packet loop step 9 — results, sprint tick, lessons, improve, pull request; then stop
argument-hint: P<n>
disable-model-invocation: true
---

Close packet $ARGUMENTS (CLAUDE.md section 6, step 9).

1. Confirm the latest gate-runner verdict is GREEN and the latest review verdict is PASS or PASS WITH
   FIXES. If not, stop.
2. Fill `## Results` in `tasks/plans/*_$ARGUMENTS.md`: what changed (files, tables, commands), gate and
   suite counts, deviations from the plan and why, review verdict and rounds, hours spent if Chan gave
   them, and any `## Master-plan change proposal`.
3. Tick the packet's items in `tasks/sprint.md`.
4. Write this packet's lessons in `tasks/lessons.md` in the `/lessons` format
   (`.claude/commands/lessons.md`), then follow `/improve` (`.claude/commands/improve.md`) to propose a
   status for every new lesson. Apply promotions only after Chan's OK, in a separate `[Day N] P<n> improve`
   commit; CLAUDE.md only with his explicit consent. (The model cannot invoke those commands itself; Chan
   may also run `/lessons` and `/improve` directly.)
5. Commit (`[Day N] P<n> close`), push the branch, and give Chan the pull-request link
   (`https://github.com/Bizwave/pre-loi/compare/main...<branch>`) with a five-line summary for the
   PR description: what, gate count, review verdict, decisions needed, next packet per the tech plan.
6. **STOP.** Do not start the next packet until Chan names it.
