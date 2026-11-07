---
description: Packet loop steps 4–5 — gate first, then build the signed-off plan sub-packet by sub-packet
argument-hint: P<n>
disable-model-invocation: true
---

Execute the signed-off plan for packet $ARGUMENTS (CLAUDE.md section 6, steps 4 and 5).

Before anything: confirm Chan gave an explicit go-ahead AFTER the latest row of the plan's
`## Revision log`. If not, stop and ask.

1. **Branch:** from an up-to-date `main`, create `p<n>-<topic>` (or resume it if it exists).
2. **Gate first** (skip if the gate is already committed):
   - write `tests/plans/test_YYYY_MM_DD_<packet>.py` exactly as listed in the plan;
   - run it with `-v` and record the first-run result of **each gate test**, not just the file:
     every test should fail for its own reason (the missing behaviour it checks). A test that
     **passes before** the code exists is flagged: either it is a deliberate preservation check (say so
     and why) or it is not testing the new behaviour and must be rewritten before committing;
   - paste the per-test summary under `## Gate — first run` in the plan;
   - commit the gate alone: `[Day N] P<n> gate`.
3. **Build** each unchecked sub-packet in order:
   - implement only what the plan says;
   - run the gate and the suite (`pytest -q`) as you go;
   - tick the sub-packet `- [ ]` → `- [x]` in the plan the moment it is done;
   - commit: `[Day N] P<n>.<k> short description`.
4. If a step fails in a way the plan did not foresee, or the plan does not fit the code, **STOP and
   report**. Do not improvise a different approach. If the gate itself is wrong, propose a
   `## Spec amendment` and wait for Chan.
5. When every sub-packet is ticked, say so and hand over to `/verify-packet $ARGUMENTS`. Do not certify
   the work yourself.

Never edit the gate file to make it pass. Never claim in a commit message an approval that is not
recorded in the plan.
