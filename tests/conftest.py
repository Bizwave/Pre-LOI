"""Shared test setup. Tests never call the real Claude API, never read a .env file and never touch
the real data folder or the repository's deals/ folder."""
from __future__ import annotations

import os
from typing import List, Optional

import pytest

from bizwave_preloi.db.session import dispose_engines
from bizwave_preloi.llm import Reply
from bizwave_preloi.ops import RunLog
from bizwave_preloi.rules import reload

_CLEARED = ("ANTHROPIC_API_KEY", "BIZWAVE_NO_LLM", "BIZWAVE_LLM_DISABLED_USES", "BIZWAVE_LLM_MODEL",
            "BIZWAVE_RUNLOG", "BIZWAVE_DATABASE_URL", "BIZWAVE_BACKUP_DIR")


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    """Every test: a temporary data folder, .env loading off, Claude settings cleared, rules re-read
    from disk, database engines closed afterwards (so Windows can delete temporary database files), and
    os.environ restored exactly afterwards (python-dotenv writes into it)."""
    saved = dict(os.environ)
    for name in _CLEARED:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("BIZWAVE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("BIZWAVE_LOAD_DOTENV", "0")
    reload()
    yield
    dispose_engines()
    reload()
    os.environ.clear()
    os.environ.update(saved)


@pytest.fixture
def db_url(tmp_path) -> str:
    """A temporary SQLite database, migrated to the newest revision, for any test that needs one."""
    from bizwave_preloi.db.migrate import upgrade
    url = "sqlite:///" + (tmp_path / "test.db").as_posix()
    upgrade(url)
    return url


@pytest.fixture
def runlog(tmp_path) -> RunLog:
    return RunLog(tmp_path / "runlog.jsonl")


class FakeTransport:
    """Stands in for the Anthropic SDK. Returns `answer` (or raises `error`) and records each call."""

    def __init__(self, answer=None, error: Optional[Exception] = None, stop_reason: str = "end_turn"):
        self.answer, self.error, self.stop_reason = answer, error, stop_reason
        self.calls: List[dict] = []

    def parse(self, **kwargs) -> Reply:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        answer = self.answer(kwargs) if callable(self.answer) else self.answer
        return Reply(parsed=answer, stop_reason=self.stop_reason, input_tokens=100, output_tokens=20)


@pytest.fixture
def fake_transport():
    return FakeTransport
