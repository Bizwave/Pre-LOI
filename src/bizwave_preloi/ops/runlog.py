"""Append-only run log (JSON lines): every Claude call, and later SLA timestamps and credits.

The file holds prompts' outputs for client deals, so it lives under deals/ and is git-ignored.
Path: $BIZWAVE_RUNLOG, default deals/runlog.jsonl.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

DEFAULT_PATH = Path("deals") / "runlog.jsonl"


class RunLog:
    def __init__(self, path: Optional[os.PathLike] = None):
        self.path = Path(path or os.environ.get("BIZWAVE_RUNLOG") or DEFAULT_PATH)

    def append(self, event: str, **fields: Any) -> Dict[str, Any]:
        record = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "event": event, **fields}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
        return record

    def records(self) -> Iterator[Dict[str, Any]]:
        if not self.path.exists():
            return
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)
