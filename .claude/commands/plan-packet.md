---
description: Packet loop step 2 — write the packet plan from the template, then stop for sign-off
argument-hint: P<n>
disable-model-invocation: true
---

Write the plan for packet $ARGUMENTS (CLAUDE.md section 6, step 2).

1. Read `CLAUDE.md`, the packet's row in `docs/tech-plan.md` section 9, the research file in
   `tasks/research/` if there is one, and `tasks/plans/_TEMPLATE.md`.
2. Create `tasks/plans/YYYY-MM-DD_<packet>.md` (today's date) from the template. Fill every section:
   - goal and done-when, in plain words;
   - in scope and out of scope;
   - the **data contract**: exact field names, types and example values for every interface the
     packet creates or changes (function signatures, table columns, JSON shapes, CLI arguments);
   - sub-packets `P<n>.1, P<n>.2 ...` as checkboxes, each small enough to commit on its own;
   - the gate file name and every test in it, one line each, with the real values it asserts;
   - decisions it depends on (`docs/decisions.md`), risks, and how to roll back.
3. Keep it within the packet's hour budget in the tech plan; if it cannot fit, say so in the plan and
   propose a cut.
4. Report the plan's path and the questions for Chan. **STOP.** Do not write tests or code until Chan
   replies with an explicit go-ahead. Plan-mode approval alone is not sign-off.

When Chan adds `## Reviewer Note` to the plan, revise the plan to address every point, note what changed
under the reviewer note, and stop again.
