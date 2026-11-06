"""Shared openpyxl styling for the Flash Review workbook.

Copied unchanged from Bizwave_mvp_master `backend/services/report/excel/xlsx_style.py`
(commit b935d5c, 4 Nov 2026) so the Flash Review workbook looks like the BizWave databook.
For the live-formula pattern (totals written as =SUM(...) rather than values), see the MVP's
`databook_workbook.py`; copy pieces from it on Day 7 rather than importing it.

Original header (Sprint 8):

Conventions from the reviewer's reference databook: `Currency: $ 000` header line,
section title rows, `Source:` / `Ref:` footers, `nq` (not quantified) and `[Open]`
markers, frozen panes, bold+fill column headers, bordered totals.

All amounts are written in $000s — `k(value)` is the ONE scaling point; the
assembly payload stays whole-dollar.
"""

from typing import List, Optional

from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from openpyxl.utils import get_column_letter

NUM_K = '#,##0'            # $000s, no decimals (sample convention)
NUM_PCT = '0.0%'
HEADER_FILL = PatternFill('solid', fgColor='1F4E78')
SUBTLE_FILL = PatternFill('solid', fgColor='DCE6F1')
TITLE_FONT = Font(bold=True, size=12)
SECTION_FONT = Font(bold=True, size=10, color='1F4E78')
HEADER_FONT = Font(bold=True, color='FFFFFF')
TOTAL_FONT = Font(bold=True)
FOOT_FONT = Font(italic=True, size=8, color='808080')
TOTAL_BORDER = Border(top=Side(style='thin'), bottom=Side(style='double'))
SUBTOTAL_BORDER = Border(top=Side(style='thin'))

NQ = 'nq'                  # not quantified (sample convention)
OPEN = '[Open]'            # pending / placeholder cell (sample convention)


def k(value) -> Optional[float]:
    """Whole dollars → $000s. None stays None (renders blank/nq by caller choice)."""
    return None if value is None else round(float(value) / 1000.0, 1)


class SheetWriter:
    """Tiny row-cursor helper so builders never hand-count row numbers.

    Tracks the current row; `row()` writes a list of values starting at col A and
    returns the written row index (for later formula references).
    """

    def __init__(self, ws, freeze: str = 'D6'):
        self.ws = ws
        self.r = 1
        if freeze:
            ws.freeze_panes = freeze

    def row(self, values: List, styles: Optional[dict] = None,
            number_format: Optional[str] = None, start_col: int = 1) -> int:
        idx = self.r
        for j, v in enumerate(values, start=start_col):
            cell = self.ws.cell(row=idx, column=j, value=v)
            if number_format and isinstance(v, (int, float)):
                cell.number_format = number_format
            if styles:
                for attr, val in styles.items():
                    setattr(cell, attr, val)
        self.r += 1
        return idx

    def blank(self, n: int = 1) -> None:
        self.r += n

    def title(self, section: str, heading: str) -> None:
        self.row([section], styles={'font': SECTION_FONT})
        self.row([heading], styles={'font': TITLE_FONT})
        self.blank()

    def header(self, values: List, start_col: int = 1) -> int:
        idx = self.row(values, styles={'font': HEADER_FONT, 'fill': HEADER_FILL,
                                       'alignment': Alignment(horizontal='right')},
                       start_col=start_col)
        for j in range(1, start_col):
            self.ws.cell(row=idx, column=j).alignment = Alignment(horizontal='left')
        return idx

    def footer_source_ref(self, source: str, ref: str) -> None:
        self.blank()
        self.row([f'Source: {source}'], styles={'font': FOOT_FONT})
        self.row([f'Ref: {ref}'], styles={'font': FOOT_FONT})


def autosize(ws, first_width: int = 38, data_width: int = 10, max_col: int = None):
    ws.column_dimensions['A'].width = first_width
    for j in range(2, (max_col or ws.max_column) + 1):
        ws.column_dimensions[get_column_letter(j)].width = data_width


def col(idx: int) -> str:
    return get_column_letter(idx)
