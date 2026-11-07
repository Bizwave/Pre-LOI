# BizWave Pre-LOI — Flash Review

The pipeline behind the BizWave Flash Review: a CPA-reviewed pre-LOI financial review of a small-business
acquisition, delivered within 24 business hours from CIM-level PDFs.

**Code computes every figure. Claude reads messy pages and drafts language in four registered places.
The CPA makes the judgments and signs.** It runs end to end with Claude switched off.

## Start

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"                               # add ,llm to call Claude
pytest
python -m bizwave_preloi.db upgrade                   # create or update the database in the data folder
```

Copy `.env.example` to `.env` to set an API key; without one the pipeline runs in no-LLM mode.

Client files, the run log and the database live in a data folder **outside the repository**, by
default `C:\Users\<you>\BizWaveData` (`~/BizWaveData` on a Mac); set `BIZWAVE_DATA_DIR` to move it.
Keep it out of OneDrive, Dropbox, Google Drive or iCloud: sync can corrupt the open database. Put
sample PDFs in its `samples` folder and run `python scripts/pdf_inventory.py`.

If you move the data folder, the run log or the database (`BIZWAVE_DATABASE_URL`), also add a matching
`Read(...)` deny rule to `.claude/settings.json`: the rule there only covers the default `~/BizWaveData`.

## What is here

- **SOP 50 10 8.1 financeability** (`finance/`): coverage at 1.25x on historical earnings, 10% equity with
  the limited-sources cap, standby and amortizing seller notes, 10-year amortization, 7(a) loan cap,
  lender-QoE trigger, maximum financeable price at the buyer's structure, sensitivity to an earnings miss.
  `models/financeability_model.xlsx` is the same model in live Excel formulas; a test recalculates it
  with LibreOffice and checks every row against the Python.
- **Rules as data** (`rules/`): 27 add-back rows with lender views, support lists and seller questions;
  flag thresholds; SBA parameters with sources. Drafts until confirmed.
- **Database** (`db/`): customers, deals and every status change, documents, pages and pipeline runs, in
  SQLite in the data folder; schema only through Alembic migrations; writes only through `db/repo.py`.
- **Footing checks** (`validate/`), **add-back classifier** (`classify/`), **Claude door with no-LLM mode
  and run log** (`llm/`), **PDF inventory** (`ingest/`).

Read `CLAUDE.md` before changing anything. Plan: `docs/build-plan.md`. Stack, database and packets:
`docs/tech-plan.md`. Checklist: `tasks/sprint.md`.

Client data never goes into this repository: live deals live in the data folder outside it.
