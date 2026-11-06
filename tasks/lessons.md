# Lessons

Two sections, newest first. Add after every packet and after any correction.

## For Chan

### 2026-11-06 — scaffold
- The MVP's SBA services are not SOP 8.1 and have sign errors in the SDE formula; the MVP's own
  reports may be showing those numbers (`report_generation_routes.py`). Worth a packet in the MVP.
- Every lender view, flag threshold and SBA parameter is a draft until you confirm it; the files say
  so in their `status` / `verified_against_sop_text` fields, and results carry the caveat until then.

## For Claude Code

### 2026-11-06 — scaffold
- YAML 1.1 reads an unquoted `NO` as `false`. The category code for non-operating items broke the
  rules loader on first run. Quote every category code; the loader and a test now catch it.
- Apostrophes are dropped in normalization, so "wife's" becomes "wifes". Patterns must allow the
  trailing `s` (`wifes?`, `owners?`, `spouses?`).
- The scaffold's tests were written alongside the code, not before it. From Day 1 on, tests come
  first (CLAUDE.md section 6).
- A mutation check (changing one Excel formula) confirmed the parity test catches formula errors;
  repeat that check whenever a new parity test is added.
