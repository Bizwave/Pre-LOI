"""ops/intake.py (P3), without the command line. Synthetic files only."""
import pytest

from bizwave_preloi.config import settings


@pytest.fixture
def deal():
    from bizwave_preloi.db import repo
    from bizwave_preloi.db.migrate import upgrade
    from bizwave_preloi.db.session import session_scope

    upgrade()
    with session_scope() as s:
        customer = repo.get_or_create_customer(s, name="Pat Buyer", email="pat@example.com")
        s.flush()
        repo.create_deal(s, deal_id="acme-hvac", customer_id=customer.id, tier="flash", by="chan")
        repo.transition(s, "acme-hvac", "awaiting_documents", by="chan")
    return "acme-hvac"


def _pdf(path, text):
    pytest.importorskip("reportlab")
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=letter)
    c.drawString(72, 720, text)
    c.showPage()
    c.save()


def test_an_interrupted_run_is_finished_without_copying_again(deal, tmp_path):
    from bizwave_preloi.ops.intake import intake

    folder = tmp_path / "in"
    _pdf(folder / "Project CIM.pdf", "Confidential information memorandum, synthetic company overview")
    copied = settings().deals_dir / deal / "inputs" / "Project CIM.pdf"
    copied.parent.mkdir(parents=True)
    copied.write_bytes((folder / "Project CIM.pdf").read_bytes())       # copied, never recorded
    result = intake(deal, folder, by="chan")
    assert [(f.action, f.stored_path, f.kind) for f in result.files] == [("recorded", "inputs/Project CIM.pdf", "cim")]
    assert result.status_after == "ready"


def test_kind_names_must_exist_and_be_unique(deal, tmp_path):
    from bizwave_preloi.ops.intake import intake

    folder = tmp_path / "in"
    _pdf(folder / "a" / "deck.pdf", "synthetic deck one")
    _pdf(folder / "b" / "deck.pdf", "synthetic deck two")
    with pytest.raises(ValueError, match="more than one file"):
        intake(deal, folder, by="chan", kinds={"deck.pdf": "cim"})
    with pytest.raises(ValueError, match="no such file"):
        intake(deal, folder, by="chan", kinds={"missing.pdf": "cim"})
    result = intake(deal, folder, by="chan", kinds={"a/deck.pdf": "cim"})
    assert {f.stored_path: f.kind for f in result.files} == {"inputs/a/deck.pdf": "cim", "inputs/b/deck.pdf": "other"}
    assert not list((settings().deals_dir / deal / "inputs").glob("*-v2*"))


def test_hidden_folders_and_links_are_skipped(deal, tmp_path):
    import os

    from bizwave_preloi.ops.intake import intake

    folder = tmp_path / "in"
    _pdf(folder / "Project CIM.pdf", "Confidential information memorandum, synthetic")
    _pdf(folder / ".sync" / "cache.pdf", "a sync client's hidden copy")
    outside = tmp_path / "outside.pdf"
    _pdf(outside, "a file outside the folder")
    try:
        os.symlink(outside, folder / "link.pdf")
    except (OSError, NotImplementedError):
        pass                                          # Windows without Developer Mode: no link to test
    result = intake(deal, folder, by="chan")
    assert [f.stored_path for f in result.files] == ["inputs/Project CIM.pdf"]
