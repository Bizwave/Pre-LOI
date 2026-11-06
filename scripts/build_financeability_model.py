"""Write models/financeability_model.xlsx: the SOP 8.1 calculator as live Excel formulas, with the
sample scenarios the tests use. Re-run after changing rules/sba_sop_8_1.yaml or the calculator.

    python scripts/build_financeability_model.py

When LibreOffice is installed the workbook is recalculated once, so file previews show values;
Excel recalculates on open either way.
"""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from bizwave_preloi.finance.excel_model import build_model, sample_scenarios

OUT = Path(__file__).resolve().parents[1] / "models" / "financeability_model.xlsx"


def main() -> None:
    soffice = os.environ.get("SOFFICE") or shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        build_model(OUT, sample_scenarios())
        print(f"Wrote {OUT} (formulas only; LibreOffice not found)")
        return
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "in" / OUT.name
        build_model(raw, sample_scenarios())
        subprocess.run([soffice, "--headless", "--calc", "--convert-to", "xlsx", "--outdir", tmp, str(raw)],
                       check=True, capture_output=True, timeout=180)
        OUT.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(tmp) / OUT.name, OUT)
    print(f"Wrote {OUT} (recalculated with LibreOffice)")


if __name__ == "__main__":
    main()
