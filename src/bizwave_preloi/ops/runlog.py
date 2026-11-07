"""Append-only run log (JSON lines): every Claude call, and later SLA timestamps and credits.

The file holds model outputs for client deals, so it lives in the data folder outside the
repository: `settings().runlog_path` (BIZWAVE_RUNLOG, default <data folder>/runlog.jsonl).
P15 moves these records into the `llm_calls` table.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from ..config import ensure_data_dirs


class RunLog:
    def __init__(self, path: Optional[os.PathLike] = None):
        # The default path goes through ensure_data_dirs(), so a data folder inside the repository
        # is refused here too (config.DataFolderError).
        self.path = Path(path) if path else ensure_data_dirs().runlog_path

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
