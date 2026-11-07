---
description: Sprint check — where we stand against the master plan, drift, repeats, open decisions, next packet
disable-model-invocation: true
---

Report sprint status against the master plan. Read-only.

1. Read `tasks/sprint.md`, `docs/tech-plan.md` section 9, `docs/decisions.md`, `tasks/lessons.md` and the
   reviews in `tasks/reviews/`.
2. Verify against living sources, which win over the docs when they disagree:
   `git log --oneline -20`, current branch, open packet branches (`git branch -a`), plans and reviews in
   `tasks/plans/` and `tasks/reviews/`, and `python -m pytest -q`.
3. Report concisely, in this order:
   - **Today:** sprint day and date; packets done, in progress (and at which loop step), not started.
   - **Against plan:** ahead, on track or behind, in hours, using the tech plan's budget; if behind,
     which item the cut order removes next (console → Claude narrative → third live review).
   - **Drift:** work not traceable to a signed-off plan; packets started without sign-off; builds started
     without a stop after the latest plan revision; gate files edited without a spec amendment; changes
     touching CLAUDE.md section 3 invariants.
   - **Repeats:** review findings of the same kind in two or more packets, and any repeat of a
     `[promoted → ...]` lesson. Each repeat is a candidate for `/improve`.
   - **Lessons waiting:** count of `[note]` lessons not yet sorted by `/improve`.
   - **Decisions blocking work:** open rows in `docs/decisions.md` needed by the next two packets.
   - **Next:** the next packet per the tech plan and what Chan needs to do before it starts.
4. Do not start any work from this command.
