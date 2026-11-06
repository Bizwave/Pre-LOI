---
description: Packet loop step 1 — read-only research for a packet; saves a dated research file
argument-hint: P<n> [topic]
disable-model-invocation: true
---

Research packet $ARGUMENTS (CLAUDE.md section 6, step 1). Read-only: no code changes, no plan.

1. Find the packet in `docs/tech-plan.md` section 9 and `tasks/sprint.md`. Read the related sections of
   `docs/tech-plan.md`, `docs/decisions.md`, and the code and rules the packet touches.
2. If the packet copies from the MVP, read the source files named in `docs/mvp-reuse-audit.md` (the MVP
   repository may be cloned next to this one; never import from it).
3. Use an Explore subagent for broad searches; read the key files yourself.
4. Save `tasks/research/YYYY-MM-DD_<packet>.md` (today's date) with:
   - **Plain-language summary:** what the packet must achieve, what exists, what is missing, in words a
     non-engineer can follow. No unexplained abbreviations.
   - **What exists:** files, functions, data shapes, with paths.
   - **Gaps and risks:** what could go wrong, open questions for Chan, decisions it depends on.
   - **Suggested sub-packets and tests** (input to the plan, not the plan).
5. Report a short summary and the open questions. **Stop.**
