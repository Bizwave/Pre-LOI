"""PDF inventory on a synthetic two-page PDF: one page with a text layer, one image-only page."""
import pytest

pytest.importorskip("reportlab")
from reportlab.lib.pagesizes import letter  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402

from bizwave_preloi.ingest import inventory  # noqa: E402


def _pdf(path):
    c = canvas.Canvas(str(path), pagesize=letter)
    c.drawString(72, 720, "Synthetic Co. Income Statement for the years ended December 31")
    for i, (label, a, b) in enumerate([("Revenue", "1,000,000", "1,200,000"),
                                       ("Cost of sales", "400,000", "480,000"),
                                       ("Gross profit", "600,000", "720,000")]):
        y = 680 - 20 * i
        c.drawString(72, y, label)
        c.drawRightString(400, y, a)
        c.drawRightString(500, y, b)
    c.showPage()
    c.rect(72, 300, 400, 300, fill=1)       # a "scanned" page: shapes only, no text
    c.showPage()
    c.save()


def test_inventory_tells_text_pages_from_scanned_pages(tmp_path):
    path = tmp_path / "synthetic.pdf"
    _pdf(path)
    pages = inventory(path)
    assert [p.page for p in pages] == [1, 2]
    assert pages[0].has_text_layer and pages[0].chars > 40
    assert not pages[1].has_text_layer and pages[1].chars == 0
