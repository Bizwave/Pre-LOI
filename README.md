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

If you move the data folder, the run log or the database (`BIZWAVE_DATABASE_URL`), or set
`BIZWAVE_BACKUP_DIR` (it holds a copy of every client file and database snapshots), also add a matching
`Read(...)` deny rule to `.claude/settings.json`: the rule there only covers the default `~/BizWaveData`,
which includes the default backup folder.

## Running deals (`bw`)

```bash
bw new-deal --customer pat@example.com --name "Pat Buyer" --tier flash   # prints the code name, e.g. amber-falcon
bw paid amber-falcon                                  # payment received (by hand until Stripe); add --pilot to new-deal to skip
bw intake amber-falcon --from "C:\Users\<you>\OneDrive\Requests\amber"   # copy, hash, classify, record the files
bw intake amber-falcon --from <same folder> --kind "deck.pdf=cim"             # correct a file's kind
bw status                                             # open deals and hours since the package was complete
bw backup                                             # database snapshot + deal files into BIZWAVE_BACKUP_DIR
```

Intake never overwrites a file: a different file under a name already taken is saved as `-v2`, `-v3`.
Give `--from` the folder holding only this buyer's files: a folder that contains the data folder, the
backup folder, the database or the repository is refused. A file that cannot be read (say, a OneDrive file
not downloaded yet) is reported and the rest are taken in; run intake again once it is available.
The 24-hour clock starts when a paid (or pilot) deal has a CIM whose pages could be read. Set
`BIZWAVE_BACKUP_DIR` to your encrypted backup folder (a synced folder is fine for backups); upgrading or
undoing the live database also writes a snapshot there first. A backup never replaces or deletes
anything: a deal file that changed since its last copy is kept as a second, dated copy and reported
(deal files are not meant to change, so check it). After pulling P3, run `pip install -e .` again so the
`bw` command exists.

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
