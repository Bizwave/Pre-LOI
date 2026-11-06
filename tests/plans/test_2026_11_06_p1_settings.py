"""P1 gate — settings and data folder (tasks/plans/2026-11-06_p1_settings.md).

Written before the code. Never edited to make it pass (CLAUDE.md section 6).
"""
from __future__ import annotations

import importlib.util
import os
from dataclasses import fields
from pathlib import Path

import pytest
from pydantic import BaseModel

from bizwave_preloi import config
from bizwave_preloi.config import (DataFolderError, REPO_ROOT, ensure_data_dirs, load_settings,
                                   settings)

VARS = ("BIZWAVE_DATA_DIR", "BIZWAVE_RUNLOG", "BIZWAVE_DATABASE_URL", "BIZWAVE_NO_LLM",
        "BIZWAVE_LLM_DISABLED_USES", "BIZWAVE_LLM_MODEL", "BIZWAVE_LOAD_DOTENV", "ANTHROPIC_API_KEY")


@pytest.fixture(autouse=True)
def _restore_environ():
    """load_dotenv writes into os.environ; put it back exactly after every test."""
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)


# ------------------------------------------------------------------------- load_settings (pure)

def test_defaults_with_nothing_set(tmp_path):
    s = load_settings(env={}, home=tmp_path)
    data = tmp_path / "BizWaveData"
    assert s.data_dir == data
    assert s.deals_dir == data / "deals"
    assert s.samples_dir == data / "samples"
    assert s.runlog_path == data / "runlog.jsonl"
    assert s.database_url == "sqlite:///" + (data / "bizwave.db").as_posix()
    assert s.no_llm is False
    assert s.disabled_uses == frozenset()
    assert s.llm_model == "claude-sonnet-5-5"
    assert s.has_api_key is False


def test_every_variable_overrides(tmp_path):
    env = {
        "BIZWAVE_DATA_DIR": str(tmp_path / "d"),
        "BIZWAVE_RUNLOG": str(tmp_path / "logs" / "run.jsonl"),
        "BIZWAVE_DATABASE_URL": "postgresql://localhost/bizwave",
        "BIZWAVE_NO_LLM": "1",
        "BIZWAVE_LLM_DISABLED_USES": "narrative.draft",
        "BIZWAVE_LLM_MODEL": "claude-opus-5-5",
        "ANTHROPIC_API_KEY": "sk-x",
    }
    s = load_settings(env=env, home=tmp_path)
    assert s.data_dir == tmp_path / "d"
    assert s.deals_dir == tmp_path / "d" / "deals"
    assert s.samples_dir == tmp_path / "d" / "samples"
    assert s.runlog_path == tmp_path / "logs" / "run.jsonl"
    assert s.database_url == "postgresql://localhost/bizwave"
    assert s.no_llm is True
    assert s.disabled_uses == frozenset({"narrative.draft"})
    assert s.llm_model == "claude-opus-5-5"
    assert s.has_api_key is True


def test_home_shortcut_and_relative_paths(tmp_path, monkeypatch):
    assert load_settings(env={"BIZWAVE_DATA_DIR": "~/x"}, home=tmp_path).data_dir == tmp_path / "x"
    assert load_settings(env={"BIZWAVE_DATA_DIR": "~"}, home=tmp_path).data_dir == tmp_path
    monkeypatch.chdir(tmp_path)
    s = load_settings(env={"BIZWAVE_DATA_DIR": os.path.join("rel", "data")}, home=tmp_path)
    assert s.data_dir.is_absolute()
    assert s.data_dir == Path(os.getcwd()) / "rel" / "data"


@pytest.mark.parametrize("value, expected", [
    ("1", True), ("true", True), ("TRUE", True), ("yes", True), ("on", True), (" Yes ", True),
    ("0", False), ("false", False), ("", False), ("no", False), ("off", False), ("maybe", False)])
def test_no_llm_values(tmp_path, value, expected):
    assert load_settings(env={"BIZWAVE_NO_LLM": value}, home=tmp_path).no_llm is expected


def test_disabled_uses_parsing(tmp_path):
    s = load_settings(env={"BIZWAVE_LLM_DISABLED_USES": " a , b,,c "}, home=tmp_path)
    assert s.disabled_uses == frozenset({"a", "b", "c"})


def test_api_key_presence_only(tmp_path):
    s = load_settings(env={"ANTHROPIC_API_KEY": "sk-test-123"}, home=tmp_path)
    assert s.has_api_key is True
    assert "sk-test-123" not in repr(s)
    assert all("sk-test-123" not in str(getattr(s, f.name)) for f in fields(s))
    assert load_settings(env={"ANTHROPIC_API_KEY": "   "}, home=tmp_path).has_api_key is False


# ------------------------------------------------------------------------- data folder

def test_ensure_data_dirs_creates_and_is_idempotent(tmp_path):
    s = load_settings(env={"BIZWAVE_DATA_DIR": str(tmp_path / "data")}, home=tmp_path)
    assert ensure_data_dirs(s) == s
    for d in (s.data_dir, s.deals_dir, s.samples_dir):
        assert d.is_dir()
    keep = s.deals_dir / "acme-hvac" / "note.txt"
    keep.parent.mkdir()
    keep.write_text("keep me")
    ensure_data_dirs(s)
    assert keep.read_text() == "keep me"


def test_data_folder_inside_repo_refused(tmp_path):
    assert REPO_ROOT is not None and (REPO_ROOT / "pyproject.toml").exists()
    for inside in (REPO_ROOT, REPO_ROOT / "deals", REPO_ROOT / "deals" / "new-folder"):
        s = load_settings(env={"BIZWAVE_DATA_DIR": str(inside)}, home=tmp_path)
        with pytest.raises(DataFolderError) as err:
            ensure_data_dirs(s)
        assert str(inside) in str(err.value)
    assert not (REPO_ROOT / "deals" / "new-folder").exists()
    outside = load_settings(env={"BIZWAVE_DATA_DIR": str(tmp_path / "elsewhere")}, home=tmp_path)
    ensure_data_dirs(outside)
    assert (tmp_path / "elsewhere" / "deals").is_dir()


def test_sync_folder_warns(tmp_path):
    s = load_settings(env={"BIZWAVE_DATA_DIR": str(tmp_path / "OneDrive - BizWave" / "BizWaveData")},
                      home=tmp_path)
    with pytest.warns(UserWarning, match="(?i)sync") as caught:
        ensure_data_dirs(s)
    assert any("database" in str(w.message).lower() for w in caught)
    assert s.deals_dir.is_dir()


# ------------------------------------------------------------------------- .env

def test_dotenv_loaded_but_env_wins(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("BIZWAVE_LLM_MODEL=from-file\nBIZWAVE_NO_LLM=1\n")
    monkeypatch.setenv("BIZWAVE_LOAD_DOTENV", "1")
    monkeypatch.setenv("BIZWAVE_LLM_MODEL", "from-env")
    monkeypatch.delenv("BIZWAVE_NO_LLM", raising=False)
    s = settings(dotenv_path=env_file)
    assert s.llm_model == "from-env"
    assert s.no_llm is True


def test_dotenv_off_ignores_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("ANTHROPIC_API_KEY=sk-file\nBIZWAVE_NO_LLM=1\n")
    monkeypatch.setenv("BIZWAVE_LOAD_DOTENV", "0")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("BIZWAVE_NO_LLM", raising=False)
    s = settings(dotenv_path=env_file)
    assert s.has_api_key is False
    assert s.no_llm is False
    assert "ANTHROPIC_API_KEY" not in os.environ


# ------------------------------------------------------------------------- consumers

def test_runlog_defaults_to_data_folder():
    from bizwave_preloi.ops import RunLog
    log = RunLog()
    expected = settings().runlog_path
    assert log.path == expected
    log.append("test_event", detail="p1")
    assert expected.exists()
    assert REPO_ROOT not in expected.parents
    assert [r["event"] for r in log.records()] == ["test_event"]


class _Shape(BaseModel):
    answer: str


def test_llm_switches_come_from_settings(monkeypatch, fake_transport):
    from bizwave_preloi.llm import ask
    from bizwave_preloi.ops import RunLog
    monkeypatch.setenv("BIZWAVE_NO_LLM", "1")
    assert ask("narrative.draft", content="x", answer_shape=_Shape) is None
    events = [(r["event"], r.get("reason")) for r in RunLog(settings().runlog_path).records()]
    assert ("llm_skipped", "no-LLM mode (BIZWAVE_NO_LLM)") in events

    monkeypatch.setenv("BIZWAVE_NO_LLM", "0")
    monkeypatch.setenv("BIZWAVE_LLM_MODEL", "claude-opus-5-5")
    t = fake_transport(_Shape(answer="ok"))
    assert ask("narrative.draft", content="x", answer_shape=_Shape, transport=t) == _Shape(answer="ok")
    assert t.calls[0]["model"] == "claude-opus-5-5"


def test_tests_are_isolated(tmp_path):
    s = settings()
    assert tmp_path in s.data_dir.parents or s.data_dir == tmp_path
    assert REPO_ROOT not in s.data_dir.parents
    assert os.environ.get("BIZWAVE_LOAD_DOTENV") == "0"
    assert "ANTHROPIC_API_KEY" not in os.environ
    assert s.has_api_key is False


def test_pdf_inventory_default_folder(capsys):
    script = REPO_ROOT / "scripts" / "pdf_inventory.py"
    spec = importlib.util.spec_from_file_location("pdf_inventory_script", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main()
    assert f"No PDFs under {settings().samples_dir}" in capsys.readouterr().out


def test_module_exposes_the_contract():
    assert config.APP_DIR_NAME == "BizWaveData"
    assert {"onedrive", "dropbox"} <= set(config.SYNC_FOLDER_MARKERS)
    assert issubclass(DataFolderError, ValueError)
