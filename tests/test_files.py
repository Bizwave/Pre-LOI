"""ops/files.py (P3 review round 1): files appear under their name only when complete, and an existing
file is never replaced, with or without hard links."""
import os

import pytest

from bizwave_preloi.ops import files as filestore


def test_place_never_replaces_and_leaves_no_temporary_file(tmp_path):
    source = tmp_path / "cim.pdf"
    source.write_bytes(b"new content")
    folder = tmp_path / "inputs"
    folder.mkdir()
    (folder / "cim.pdf").write_bytes(b"recorded content")
    temp, digest = filestore.copy_to_temporary(source, folder)
    assert filestore.is_temporary(temp) and digest == filestore.sha256(source)
    assert filestore.place(temp, folder / "cim.pdf") is False and temp.exists()
    assert (folder / "cim.pdf").read_bytes() == b"recorded content"
    assert filestore.place(temp, folder / "cim-v2.pdf") is True and not temp.exists()
    assert (folder / "cim-v2.pdf").read_bytes() == b"new content"
    assert sorted(p.name for p in folder.iterdir()) == ["cim-v2.pdf", "cim.pdf"]


def test_place_without_hard_links_never_replaces(tmp_path, monkeypatch):
    """FAT-formatted drives and some network shares have no hard links: the name is reserved, then filled."""
    def no_links(src, dst):
        raise PermissionError(1, "Operation not permitted")
    monkeypatch.setattr(filestore.os, "link", no_links)
    folder = tmp_path / "usb"
    folder.mkdir()
    (folder / "taken.db").write_bytes(b"old snapshot")
    temp = filestore.new_temporary(folder, "x.db")
    temp.write_bytes(b"new snapshot")
    assert filestore.place(temp, folder / "taken.db") is False
    assert (folder / "taken.db").read_bytes() == b"old snapshot"
    assert filestore.place(temp, folder / "free.db") is True
    assert (folder / "free.db").read_bytes() == b"new snapshot" and not temp.exists()


def test_a_failed_copy_removes_its_temporary_file(tmp_path, monkeypatch):
    source = tmp_path / "cim.pdf"
    source.write_bytes(b"x" * 10)
    folder = tmp_path / "inputs"

    def disk_full(fd):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(filestore.os, "fsync", disk_full)
    with pytest.raises(OSError, match="No space"):
        filestore.copy_to_temporary(source, folder)
    assert list(folder.iterdir()) == []


@pytest.mark.parametrize("name, temporary", [
    (".cim.pdf.0123abcd.partial", True), (".bizwave.db.89abcdef.partial", True),
    ("cim.pdf.partial", False), (".cim.pdf", False), ("cim.pdf", False), (".cim.pdf.0123ABCD.partial", False),
])
def test_is_temporary(name, temporary):
    assert filestore.is_temporary(name) is temporary
