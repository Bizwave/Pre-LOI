---
description: Sprint check — where we stand against the master plan, drift, open decisions, next packet
disable-model-invocation: true
---

Report sprint status against the master plan. Read-only.

1. Read `tasks/sprint.md`, `docs/tech-plan.md` section 9 and `docs/decisions.md`.
2. Verify against living sources, which win over the docs when they disagree:
   `git log --oneline -20`, current branch, open packet branches (`git branch -a`), plans and reviews in
   `tasks/plans/` and `tasks/reviews/`, and `python -m pytest -q`.
3. Report concisely, in this order:
   - **Today:** sprint day and date; packets done, in progress (and at which loop step), not started.
   - **Against plan:** ahead, on track or behind, in hours, using the tech plan's budget; if behind,
     which item the cut order removes next (console → Claude narrative → third live review).
   - **Drift:** work not traceable to a signed-off plan; packets started without sign-off; gate files
     edited without a spec amendment; changes touching CLAUDE.md section 3 invariants.
   - **Decisions blocking work:** open rows in `docs/decisions.md` needed by the next two packets.
   - **Next:** the next packet per the tech plan and what Chan needs to do before it starts.
4. Do not start any work from this command.
