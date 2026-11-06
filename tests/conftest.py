"""Shared test setup. Tests never call the real Claude API and never touch deals/."""
from __future__ import annotations

from typing import List, Optional

import pytest

from bizwave_preloi.llm import Reply
from bizwave_preloi.ops import RunLog
from bizwave_preloi.rules import reload


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    """No API key, Claude not forced off, run log in a temp folder, rules re-read from disk."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("BIZWAVE_NO_LLM", raising=False)
    monkeypatch.delenv("BIZWAVE_LLM_DISABLED_USES", raising=False)
    monkeypatch.delenv("BIZWAVE_LLM_MODEL", raising=False)
    monkeypatch.setenv("BIZWAVE_RUNLOG", str(tmp_path / "runlog.jsonl"))
    reload()
    yield
    reload()


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
