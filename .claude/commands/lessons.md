---
description: Write lessons to tasks/lessons.md in two categories — at close, and the moment a mistake is found
disable-model-invocation: true
---

Write lessons to `tasks/lessons.md`. Run this at packet close AND immediately whenever gate-runner reports
RED, the reviewer returns a finding at should-fix or above, or Chan corrects Claude (CLAUDE.md section 6,
"Self-improvement").

1. Review what happened: research findings, plan revisions, gate first run, build friction,
   gate-runner results, review findings and corrections, Chan's corrections.
2. Add to the packet's entry at the TOP of the file (create it if missing; newest first):

```
## <Packet id and one-line description> (YYYY-MM-DD, branch `<branch>`)

### For You (Chan)
- <what Chan should know, check or do differently: product, process, decisions, things to verify>

### For Claude Code (Me)
- [note] <a specific rule for future sessions: when it applies and what to do> (source: <review round,
  gate run or Chan's correction>)
```

Rules
- Every "For Claude Code (Me)" line starts with a status: `[note]` when written; `/improve` later changes
  it to `[promoted → <where>]` or `[retired]`.
- Two to six lessons per category at close; one lesson is enough for an immediate capture.
- Specific beats general: name the file, rule or test. Cite the source.
- Include every review blocker and should-fix and what it taught.
- Append only; never rewrite earlier entries (except their status tag, via `/improve`).
