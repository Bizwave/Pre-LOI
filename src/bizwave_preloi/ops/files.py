"""Writing new files without ever replacing one (P3): intake copies, backup copies, database snapshots.

    temp, digest = copy_to_temporary(source, folder)   # a complete copy under a temporary name, and its sha256
    if place(temp, folder / "cim.pdf"): ...            # False when that name is taken; temp is then kept
    final = place_first(temp, names)                   # the first free name of `names`; temp discarded on failure
    discard(temp)                                      # when giving up
    sha256(path); is_temporary(path)

A file appears under its final name only when complete. It is written first under a short temporary name
in the same folder (".bw-<8 hex>.partial", created exclusively; hidden on a Mac and Linux, not on Windows),
then hard-linked to the final name. Linking fails when the name is taken, so an existing file is never
replaced, even by a second program writing at the same moment. On a disk without hard links (FAT or exFAT
drives, some network shares): on Windows the file is renamed, which refuses an existing name; elsewhere the
final name is reserved first (created exclusively) and the file then moved onto it, so a run killed in that
instant can leave an empty file under the name, never a replaced one.

A run that is killed can leave a temporary file behind; it is never mistaken for a deal file, and backups
skip it.
"""
from __future__ import annotations

import hashlib
import os
import re
import secrets
from pathlib import Path
from typing import Iterable, Tuple

_TEMPORARY = re.compile(r"\.bw-[0-9a-f]{8}\.partial")
_CHUNK = 1 << 20
_WINDOWS = os.name == "nt"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def is_temporary(path: Path) -> bool:
    """True for a temporary file of this module (a killed run can leave one behind)."""
    return bool(_TEMPORARY.fullmatch(Path(path).name))


def new_temporary(folder: Path) -> Path:
    """A new, empty temporary file in `folder` (created exclusively), to be written and then placed. The name
    is short, so a long final name never fails on the temporary one (Windows' 260-character paths)."""
    folder.mkdir(parents=True, exist_ok=True)
    while True:
        temp = folder / f".bw-{secrets.token_hex(4)}.partial"
        try:
            with open(temp, "xb"):
                return temp
        except FileExistsError:
            continue


def copy_to_temporary(source: Path, folder: Path) -> Tuple[Path, str]:
    """Copy `source` into a new temporary file in `folder`; returns it and the sha256 of the bytes copied.
    On any failure the temporary file is removed and the error raised."""
    temp = new_temporary(folder)
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
        pass                                         # a temporary leftover at worst; never fail a placed file
    return True


def place_first(temp: Path, names: Iterable[Path]) -> Path:
    """Place `temp` under the first name of `names` that is free and return it. On any failure (or if
    `names` runs out) `temp` is removed and the error raised."""
    try:
        for name in names:
            if place(temp, name):
                return name
        raise FileExistsError(f"every name offered for {temp.name} is taken")
    except BaseException:
        discard(temp)
        raise


def _place_without_link(temp: Path, final: Path) -> bool:
    if _WINDOWS:
        try:
            os.rename(temp, final)                   # Windows: refuses an existing name; nothing to reserve
        except FileExistsError:
            return False
        return True
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
