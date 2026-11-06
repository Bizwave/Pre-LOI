# Lessons

Newest first. One entry per packet or session, written by `/lessons` (CLAUDE.md section 6, step 9).

## Day 0 — packet loop added to CLAUDE.md (2026-11-06, branch `day-0/packet-loop`)

### For You (Chan)
- The loop is binding through CLAUDE.md itself, which every session loads; the slash commands only make
  it convenient. (Same lesson as the MVP's 2026-08-11 entry: a command file is read only when invoked.)
- Independent checks are two subagents with fresh context that cannot edit files: `gate-runner` (tests)
  and `packet-reviewer` (diff against plan and invariants). Their reports are evidence for your merge.

### For Claude Code (Me)
- Name custom commands so they do not shadow built-ins: `/plan-packet`, `/review-packet`,
  `/verify-packet`, `/sprint-status` rather than `/plan`, `/review`, `/status`.

## Day 0 — scaffold (2026-11-06, branch `scaffold/day-0`)

### For You (Chan)
- The MVP's SBA services are not SOP 8.1 and have sign errors in the SDE formula; the MVP's own
  reports may be showing those numbers (`report_generation_routes.py`). Worth a packet in the MVP.
- Every lender view, flag threshold and SBA parameter is a draft until you confirm it; the files say
  so in their `status` / `verified_against_sop_text` fields, and results carry the caveat until then.

### For Claude Code (Me)
- YAML 1.1 reads an unquoted `NO` as `false`. The category code for non-operating items broke the
  rules loader on first run. Quote every category code; the loader and a test now catch it.
- Apostrophes are dropped in normalization, so "wife's" becomes "wifes". Patterns must allow the
  trailing `s` (`wifes?`, `owners?`, `spouses?`).
- The scaffold's tests were written alongside the code, not before it. From P1 on, the gate comes
  first (CLAUDE.md section 6, step 4).
- A mutation check (changing one Excel formula) confirmed the parity test catches formula errors;
  repeat that check whenever a new parity test is added.
