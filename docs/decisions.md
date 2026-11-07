# Decisions

Open items are Chan's to decide. Record the decision, date and reason; never delete a row.

## Open

| # | Decision | Default in the code until decided | Needed by |
|---|---|---|---|
| D1 | Verify every value in `rules/sba_sop_8_1.yaml` against the SOP 50 10 8.1 text; then set `verified_against_sop_text: true` | Values from practitioner summaries; every result carries an "unverified" note | Before the first live review (18 Nov) (Chan: Tue 10 Nov) |
| D2 | Which earnings basis the headline maximum price uses: lower of last FY and two-year average, last FY, two-year average, or higher of | `lower_of` (conservative; the SOP lets the lender use either) | Day 2 (Chan: Tue 10 Nov) |
| D3 | Confirm or change the lender view on each of the 27 add-back rows, then set `status: confirmed` | Draft views in `rules/addbacks.yaml` | Day 4 (Chan: Tue 10 Nov) |
| D4 | Confirm the flag thresholds in `rules/flags.yaml` | Draft thresholds | Day 5 |
| D5 | Confidence at which Claude's add-back pick is applied without the CPA | 0.75 (`claude_min_confidence`) | Day 4, after the accuracy report |
| D6 | Model for the four Claude uses | `claude-sonnet-5-5` for all (`BIZWAVE_LLM_MODEL`) | Day 3 |
| D7 | List price $750 vs $495; pilot price $295 | — (not in code) | Before outreach |
| D8 | No value range in any output (VS 100 line); confirm with the AICPA ethics hotline or counsel | Enforced: "maximum financeable price at your structure" only | Before the first live review |
| D9 | Lender firewall: no lender-commissioned QoE on a deal where BizWave did buyer-side work | — (policy, not code) | Before outreach to lenders |
| D10 | What "24 business hours" means for the SLA clock | Proposed: 24 clock hours skipping weekends and US federal holidays, in `rules/sla.yaml` | Day 8 |
| D11 | Upload tool for buyers | Proposed: OneDrive "Request files" or a Dropbox file request | Day 8 |
| D12 | Real sample CIMs inside Claude Code | **Decided 6 Nov → M5** | — |
| D13 | Engagement letter signature | Proposed: terms consent at Stripe checkout plus an e-signed letter for pilots | Before outreach |
| D14 | Delivery channel | Proposed: email the PDF and workbook, or an expiring share link | Day 8 |
| D15 | Credit terms | Proposed: 100% of the fee, 120 days, any deal, not transferable, in `rules/commercial.yaml` | Day 8 |
| D16 | Database and stack (`docs/tech-plan.md`) | **Decided 6 Nov → M6** | — |

## Made

| # | Decision | Date | Reason |
|---|---|---|---|
| M1 | New repository, separate from the MVP; copy, never import | 6 Nov 2026 | Keep the sprint code clean; MVP is database- and Flask-bound |
| M2 | Code owns numbers; Claude in four registered uses only; no-LLM mode must always work | 6 Nov 2026 | Chan: do not rely on the Claude API 100% |
| M3 | Do not reuse the MVP's SBA services | 6 Nov 2026 | Pre-SOP-8.1 rules and sign errors (see `docs/mvp-reuse-audit.md`) |
| M4 | Keep the MVP's eight Level-1 adjustment codes | 6 Nov 2026 | Add-backs keep their category when a deal moves into a QoE |
| M5 (D12) | Claude Code builds only with redacted or public sample CIMs; live client deals run outside it | 6 Nov 2026 | Anything Claude Code reads or prints goes to the model (Chan: "5. Yes") |
| M6 (D16) | Stack as in `docs/tech-plan.md`: SQLite + SQLAlchemy + Alembic, Typer CLI, Streamlit console, docxtpl + LibreOffice, all local; prioritize within it if time is short (cut order in the tech plan) | 6 Nov 2026 | Chan: "4. Sure - prioritize if needed" |
| M7 | P1 data folder outside the repository (`~/BizWaveData`), refusal also covers the run log; CLAUDE.md invariant 8 reworded | 6 Nov 2026 | Chan: Q1 yes, Q2 fine; review fixes confirmed ("1. yes", PR #3 merged) |
| M8 | Self-improvement loop (W1): lessons captured immediately, read before planning, promoted by `/improve` | 6 Nov 2026 | Chan: "2. Go ahead" |
| M9 | Tech plan §8: a moved data folder or run log needs a matching `.claude/settings.json` deny rule (P1 proposal) | 6 Nov 2026 | Chan: "3b yes" (P2 sign-off, 16:52) |
| M10 | P2 database core: a database file inside the repository is refused (Q1); a deal may go `created` → `awaiting_documents` without payment (Q2); the status flow lives in code (Q4); `on_hold` returns only to the status before the hold, or `cancelled` (tech plan §4.3); one file, one document row (a changed file is saved under a new name) | 6 Nov 2026 | Chan: Q1 yes, Q2 yes, Q4 ok (16:52); "1. Ok / 2. Agree with your recommendation" (17:59) |
| M11 | P2 after review round 3: a second, conflicting move of the same deal is refused; undo (`downgrade`) needs the database named; automatic backup before every upgrade or downgrade of the live database goes into P3 | 6 Nov 2026 | Chan: "P2: 1a, 2a, backups in P3" (19:00) |
| M12 | P3 command line as planned (Q1–Q9): intake answers and AI consent move to P4; a deal without AI consent runs in no-LLM mode (P4 stores, P7 enforces); `bw paid` by hand until P15; the clock starts for a paid deal with a readable CIM; document kinds from `rules/intake.yaml` (draft); backups into `BIZWAVE_BACKUP_DIR`; Windows reserved names refused; generated code names; three CLAUDE.md §4 lines | 6 Nov 2026 | Chan: "P3 all recommended - let's go" (20:36) |
