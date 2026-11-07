# Decisions

Open items are Chan's to decide. Record the decision, date and reason; never delete a row.

## Open

| # | Decision | Default in the code until decided | Needed by |
|---|---|---|---|
| D1 | Verify every value in `rules/sba_sop_8_1.yaml` against the SOP 50 10 8.1 text; then set `verified_against_sop_text: true` | Values from practitioner summaries; every result carries an "unverified" note | Before the first live review (18 Nov) |
| D2 | Which earnings basis the headline maximum price uses: lower of last FY and two-year average, last FY, two-year average, or higher of | `lower_of` (conservative; the SOP lets the lender use either) | Day 2 |
| D3 | Confirm or change the lender view on each of the 27 add-back rows, then set `status: confirmed` | Draft views in `rules/addbacks.yaml` | Day 4 (Chan doing D1–D3 on Tue 10 Nov) |
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
