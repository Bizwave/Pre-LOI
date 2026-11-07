---
description: Packet loop steps 7–8 — independent review by the packet-reviewer subagent, then corrections
argument-hint: P<n>
disable-model-invocation: true
---

Review packet $ARGUMENTS independently and correct (CLAUDE.md section 6, steps 7 and 8).

1. Gate-runner must have reported GREEN on the current commit. If not, run `/verify-packet` first.
2. Delegate to the **packet-reviewer** subagent with the packet id. Give it nothing else: it reads the
   plan, CLAUDE.md, `tasks/lessons.md` and the diff itself, so its judgment is independent of yours.
3. Save its report VERBATIM to `tasks/reviews/YYYY-MM-DD_<packet>.md` (append a `## Round N` heading on
   later rounds) and show Chan the verdict and the blockers.
4. **Capture lessons now:** for every blocker and should-fix, add a lesson to `tasks/lessons.md` with
   `/lessons` (status `[note]` until `/improve` sorts it), citing the review round. Do this before fixing.
5. **Correct:** fix every blocker and should-fix in the code, one commit per finding
   (`[Day N] P<n> fix: <finding>`); nits at your discretion. Never edit the gate.
   If a finding is wrong, do not fix it: write why under the finding in the review file for Chan.
6. Run `/verify-packet $ARGUMENTS` again, then this command again (round 2). The reviewer re-checks the
   earlier findings.
7. After two correction rounds with blockers remaining: **STOP** and report to Chan as a plan problem.
8. On PASS or PASS WITH FIXES (nits only left): hand over to `/close-packet $ARGUMENTS`.
