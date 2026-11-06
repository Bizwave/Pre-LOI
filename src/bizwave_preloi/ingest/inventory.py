"""Which pages of a PDF can be read from the text layer, and which need Claude or keying in.

Run on the Day-1 sample set to see how much of the real input is scanned:

    python scripts/pdf_inventory.py path/to/folder
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

import pdfplumber

# A page with fewer characters than this in its text layer is treated as having none
# (scanned pages often carry a few stray characters from headers or OCR stamps).
MIN_TEXT_CHARS = 40


@dataclass(frozen=True)
class PageInfo:
    page: int               # 1-based
    chars: int              # characters in the text layer
    has_text_layer: bool
    tables_found: int       # tables pdfplumber detects with its default settings
    images: int


def inventory(pdf_path: Path) -> List[PageInfo]:
    pages = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            chars = len(text.strip())
            try:
                tables = len(page.find_tables())
            except Exception:                    # malformed page: count it as no table
                tables = 0
            pages.append(PageInfo(page=number, chars=chars, has_text_layer=chars >= MIN_TEXT_CHARS,
                                  tables_found=tables, images=len(page.images)))
    return pages
