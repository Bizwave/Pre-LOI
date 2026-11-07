---
description: Packet loop step 6 — independent verification by the gate-runner subagent
argument-hint: P<n>
disable-model-invocation: true
---

Verify packet $ARGUMENTS independently (CLAUDE.md section 6, step 6).

1. Make sure all work is committed (`git status --short` is empty). If not, commit or stop and ask.
2. Find the gate file for $ARGUMENTS in `tests/plans/` and the plan in `tasks/plans/`.
3. Delegate to the **gate-runner** subagent with: the packet id, the gate file path and the plan path.
   Do not run the tests yourself for this step and do not summarize on its behalf.
4. Show gate-runner's report to Chan exactly as returned.
5. If the verdict is RED: capture the lesson **now** with `/lessons` (what failed, why it was missed, the
   rule that would have caught it) in `tasks/lessons.md`, then fix the CODE (never the gate), commit, and
   run this command again. If GREEN, hand over to `/review-packet $ARGUMENTS`.
