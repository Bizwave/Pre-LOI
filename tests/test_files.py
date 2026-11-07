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
    temp = filestore.new_temporary(folder)
    temp.write_bytes(b"new snapshot")
    assert filestore.place(temp, folder / "taken.db") is False
    assert (folder / "taken.db").read_bytes() == b"old snapshot"
    assert filestore.place(temp, folder / "free.db") is True
    assert (folder / "free.db").read_bytes() == b"new snapshot" and not temp.exists()


def test_place_without_hard_links_on_windows_renames_without_reserving(tmp_path, monkeypatch):
    """On Windows the fallback is a rename, which refuses an existing name: no empty reservation can be left
    under the real name if the run dies (P3 review round 2, nit 4). Windows' rename is simulated here."""
    def no_links(src, dst):
        raise OSError(1, "Incorrect function")       # what FAT/exFAT gives on Windows
    renames = []

    def windows_rename(src, dst):
        renames.append(dst)
        if os.path.exists(dst):
            raise FileExistsError(17, "Cannot create a file when that file already exists", str(dst))
        os.replace(src, dst)
    monkeypatch.setattr(filestore.os, "link", no_links)
    monkeypatch.setattr(filestore.os, "rename", windows_rename)
    monkeypatch.setattr(filestore, "_WINDOWS", True)
    folder = tmp_path / "usb"
    folder.mkdir()
    (folder / "taken.db").write_bytes(b"old snapshot")
    temp = filestore.new_temporary(folder)
    temp.write_bytes(b"new snapshot")
    assert filestore.place(temp, folder / "taken.db") is False
    assert (folder / "taken.db").read_bytes() == b"old snapshot" and temp.exists()
    assert filestore.place(temp, folder / "free.db") is True
    assert (folder / "free.db").read_bytes() == b"new snapshot" and not temp.exists()
    assert renames == [folder / "taken.db", folder / "free.db"]


def test_place_first_takes_the_first_free_name_and_cleans_up(tmp_path):
    folder = tmp_path / "f"
    folder.mkdir()
    (folder / "a.db").write_bytes(b"old")
    temp = filestore.new_temporary(folder)
    temp.write_bytes(b"new")
    assert filestore.place_first(temp, [folder / "a.db", folder / "b.db"]) == folder / "b.db"
    temp = filestore.new_temporary(folder)
    with pytest.raises(FileExistsError):
        filestore.place_first(temp, [folder / "a.db", folder / "b.db"])
    assert sorted(p.name for p in folder.iterdir()) == ["a.db", "b.db"]       # the temporary file is gone


def test_a_long_file_name_fits(tmp_path):
    """The temporary name is short: a long final name that the disk accepts never fails on it (nit 5)."""
    name = "c" * 236 + ".pdf"                         # 240 characters; the old temporary name was 258
    source = tmp_path / "in" / name
    source.parent.mkdir()
    source.write_bytes(b"x")
    folder = tmp_path / "out"
    temp, _ = filestore.copy_to_temporary(source, folder)
    assert len(temp.name) == len(".bw-0123abcd.partial")
    assert filestore.place(temp, folder / name) and (folder / name).read_bytes() == b"x"


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
    (".bw-0123abcd.partial", True), (".bw-89abcdef.partial", True),
    ("bw-0123abcd.partial", False), (".bw-0123ABCD.partial", False), (".bw-0123abcd.partial.pdf", False),
    (".cim.pdf.0123abcd.partial", False), ("cim.pdf", False),
])
def test_is_temporary(name, temporary):
    assert filestore.is_temporary(name) is temporary
