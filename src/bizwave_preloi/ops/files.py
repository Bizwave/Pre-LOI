"""Writing new files without ever replacing one (P3): intake copies, backup copies, database snapshots.

    temp, digest = copy_to_temporary(source, folder)   # a complete copy under a hidden name, and its sha256
    if place(temp, folder / "cim.pdf"): ...            # False when that name is taken; temp is then kept
    discard(temp)                                      # when giving up
    sha256(path); is_temporary(path)

A file appears under its final name only when complete. It is written first under a hidden temporary name
in the same folder (".<name>.<8 hex>.partial", created exclusively), then hard-linked to the final name.
Linking fails when the name is taken, so an existing file is never replaced, even by a second program
writing at the same moment. On a disk without hard links (FAT-formatted drives, some network shares) the
final name is reserved first (created exclusively) and the temporary file is then moved onto it.

A run that is killed can leave a temporary file behind; it is hidden, never mistaken for a deal file, and
backups skip it.
"""
from __future__ import annotations

import hashlib
import os
import re
import secrets
from pathlib import Path
from typing import Tuple

_TEMPORARY = re.compile(r"^\..+\.[0-9a-f]{8}\.partial$")
_CHUNK = 1 << 20


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def is_temporary(path: Path) -> bool:
    """True for a temporary file of this module (a killed run can leave one behind)."""
    return bool(_TEMPORARY.match(Path(path).name))


def new_temporary(folder: Path, name: str) -> Path:
    """A new, empty, hidden file in `folder` (created exclusively) to be written and then placed as `name`."""
    folder.mkdir(parents=True, exist_ok=True)
    while True:
        temp = folder / f".{name}.{secrets.token_hex(4)}.partial"
        try:
            with open(temp, "xb"):
                return temp
        except FileExistsError:
            continue


def copy_to_temporary(source: Path, folder: Path) -> Tuple[Path, str]:
    """Copy `source` into a new temporary file in `folder`; returns it and the sha256 of the bytes copied.
    On any failure the temporary file is removed and the error raised."""
    temp = new_temporary(folder, Path(source).name)
    h = hashlib.sha256()
    try:
        with open(source, "rb") as src, open(temp, "wb") as dst:
            for chunk in iter(lambda: src.read(_CHUNK), b""):
                h.update(chunk)
                dst.write(chunk)
            dst.flush()
            os.fsync(dst.fileno())
    except BaseException:
        discard(temp)
        raise
    return temp, h.hexdigest()


def place(temp: Path, final: Path) -> bool:
    """Give the complete file `temp` the name `final` (same folder) unless that name is taken. True when
    placed (`temp` is gone); False when `final` exists (`temp` is left as it was). Never replaces a file."""
    try:
        os.link(temp, final)
    except FileExistsError:
        return False
    except (OSError, NotImplementedError):          # no hard links on this disk
        return _place_without_link(temp, final)
    try:
        os.unlink(temp)                              # the file now lives under `final`
    except OSError:
        pass                                         # a hidden leftover at worst; never fail a placed file
    return True


def _place_without_link(temp: Path, final: Path) -> bool:
    try:
        with open(final, "xb"):                      # reserve the name; fails if it is taken
            pass
    except FileExistsError:
        return False
    try:
        os.replace(temp, final)                      # onto our own empty reservation only
    except BaseException:
        discard(final)
        raise
    return True


def discard(path: Path) -> None:
    """Remove a temporary file (or our own empty reservation); a missing file is fine."""
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
