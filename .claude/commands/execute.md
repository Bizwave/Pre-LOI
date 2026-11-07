---
description: Packet loop steps 4–5 — gate first, then build the signed-off plan sub-packet by sub-packet
argument-hint: P<n>
disable-model-invocation: true
---

Execute the signed-off plan for packet $ARGUMENTS (CLAUDE.md section 6, steps 4 and 5).

Before anything: the plan's `## Reviewer Note` must hold a line
`Go-ahead: YYYY-MM-DD HH:MM PT (<where, Chan's exact words>)` recording Chan's explicit go-ahead, and that
time must not be earlier than the latest row of `## Revision log` (rows dated `YYYY-MM-DD HH:MM`). If the
line is missing, or the plan was revised after it, stop and ask. Write the line only after Chan has given
the go-ahead, quoting him; never in advance. `tests/test_workflow.py` checks this for every plan whose
work has started.

1. **Branch:** from an up-to-date `main`, create `p<n>-<topic>` (or resume it if it exists).
2. **Gate first** (skip if the gate is already committed):
   - write `tests/plans/test_YYYY_MM_DD_<packet>.py` exactly as listed in the plan;
   - run it with `-v` and record the first-run result of **each gate test**, not just the file:
     every test should fail for its own reason (the missing behaviour it checks). A test that
     **passes before** the code exists is flagged: either it is a deliberate preservation check (say so
     and why) or it is not testing the new behaviour and must be rewritten before committing;
   - paste the per-test summary under `## Gate — first run` in the plan;
   - write every clarification made while writing the gate into the plan's Data contract in the gate
     commit, never only into a note;
   - a gate test whose first failure is a setup error (a module or command this packet adds) has not
     shown it fails for its own reason: after the build, break that behaviour in a scratch copy, run it,
     and record the result under `## Gate — first run`;
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
