"""Report, for every PDF in a folder, how many pages have a text layer and how many tables.

    python scripts/pdf_inventory.py                 # the samples folder: <data folder>/samples
    python scripts/pdf_inventory.py path/to/folder

Use on the Day-1 sample set: pages without a text layer go to Claude (ingest.page_extraction)
or to keying in, so this tells you how much of the input depends on the fallback.
"""
import sys
from pathlib import Path
from typing import Optional

from bizwave_preloi.config import settings
from bizwave_preloi.ingest import inventory


def main(folder: Optional[str] = None) -> None:
    root = Path(folder) if folder else settings().samples_dir
    pdfs = sorted(root.rglob("*.pdf")) if root.is_dir() else []
    if not pdfs:
        print(f"No PDFs under {root}")
        return
    total_pages = total_text = 0
    for pdf in pdfs:
        pages = inventory(pdf)
        text = sum(p.has_text_layer for p in pages)
        tables = sum(p.tables_found for p in pages)
        no_text = [p.page for p in pages if not p.has_text_layer]
        total_pages += len(pages)
        total_text += text
        print(f"{pdf.name}: {len(pages)} pages, {text} with text, {tables} tables"
              + (f"; no text layer on pages {no_text}" if no_text else ""))
    print(f"\nAll: {total_text}/{total_pages} pages have a text layer")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
