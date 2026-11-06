# Flash Review build plan (summary)

> Technical stack, database schema and packets: `docs/tech-plan.md`.

The full plan, with market research and pricing, is the "BizWave Pre-LOI Offering — Market Research and
Product Plan" doc (section B6). This page is the part Claude Code needs while building.

## Goal and dates

Two weeks: Mon 9 Nov – Fri 20 Nov 2026 (demo day). About 50 hours of Chan's time with Claude Code.
The Flash Review is sellable end to end, and at least three paid reviews are delivered before demo day.

## Definition of done (20 Nov)

- A buyer can pay, sign, upload a CIM or recast, and receive a CPA-reviewed Flash Review within
  24 business hours.
- At least 3 paid Flash Reviews delivered, with CPA minutes, turnaround and buyer decisions logged.
- Every figure in the report is computed by code and traced to a source page; every Claude output is
  logged with its prompt version.
- No unresolved serious error in any delivered review.

## What a Flash Review contains

1. Verdict: pursue / pursue with conditions / pass, with the three reasons behind it.
2. Lender-lens earnings bridge: each add-back rated likely accepted / needs support / likely rejected,
   with the support a lender would ask for; the supportable earnings that result.
3. SOP 50 10 8.1 financeability: 1.25x historical coverage on supportable earnings (no projections),
   10% equity and the standby-note/minority cap, maximum financeable price at the buyer's structure,
   sensitivity to a 10–20% earnings miss.
4. Red flags and what could not be tested.
5. LOI terms that protect the buyer without lowering the headline.
6. Post-LOI request list, sequenced to spare the seller.
7. Buyer Readiness Letter (optional, one page, for the broker).
8. Seller and broker questions, ordered by how much price rides on each answer.

Excluded: audit, review or QoE; any value conclusion or range; testing of bank deposits or tax returns.

## Day by day

| Day | Date | Work | Output |
|---|---|---|---|
| 1 | Mon 9 Nov | Repo, CLAUDE.md, schemas, tests; MVP audit; 8–10 sample PDFs, hand-key 3 as ground truth; outreach; engagement letter | Scaffold; reuse list; ground truth; outreach sent |
| 2 | Tue 10 Nov | SOP 8.1 calculator with tests matching Excel; rules tables (add-backs, flag thresholds) | Calculator and rules v1 |
| 3 | Wed 11 Nov | PDF ingestion: text and tables, no-text-page detection, Claude fallback with schema and page references | Ingestion v1 |
| 4 | Thu 12 Nov | Footing checks; add-back classifier; accuracy against the ground truth | Accuracy report |
| 5 | Fri 13 Nov | End-to-end on 5 PDFs; flag engine and question library; 3 paid partners confirmed | Week-1 gate |
| 6 | Mon 16 Nov | Review console | Console v1 |
| 7 | Tue 17 Nov | Memo, workbook, readiness letter; Claude narrative sections | Outputs v1 |
| 8 | Wed 18 Nov | Intake folder and payment link; run log, SLA timer, credit ledger; first live review | 1 delivered |
| 9 | Thu 19 Nov | Live reviews 2–3; fixes; redacted sample and pilot numbers for the deck | 3 delivered |
| 10 | Fri 20 Nov | Demo day | Live demo plus traction |

The 6 Nov scaffold already covers most of Days 1–2 in code (see `tasks/sprint.md`), which frees
Day 1–2 hours for sample PDFs, ground truth, outreach and verifying the SBA parameters.

**Week-1 gate (13 Nov):** figures correct after review flags on all 5 sample PDFs; the pipeline runs
in no-LLM mode; 3 paid design partners confirmed.

**Cut order if behind:** review console (review in the workbook instead) → Claude narrative drafting
(write by hand) → third live review moves to the week after demo day. Never cut: footing checks,
calculator tests, the CPA check.

**Deferred (December on):** Flash QoE tier (tax returns, bank statements, deposit tie-out); handoff
into the QoE workspace and seller portal; benchmark data; Search Pass; partner integrations.
