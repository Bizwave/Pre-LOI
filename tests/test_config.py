"""Settings and data folder: cases added after the P1 review (tasks/reviews/2026-11-06_p1_settings.md).
The P1 gate (tests/plans/test_2026_11_06_p1_settings.py) is unchanged; these extend its coverage."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from dotenv import dotenv_values

from bizwave_preloi import config
from bizwave_preloi.config import (DataFolderError, REPO_ROOT, ensure_data_dirs, load_settings,
                                   settings)


@pytest.fixture(autouse=True)
def _repo_root_known():
    assert REPO_ROOT is not None, "these tests run from the source tree"


@pytest.fixture
def fake_repo(tmp_path, monkeypatch):
    """A stand-in repository under the test's temp folder. Tests that would WRITE if the refusal ever
    broke use this, so a regression can never leave files in the real repository."""
    repo = tmp_path / "fake-repo"
    (repo / "src" / "bizwave_preloi").mkdir(parents=True)
    (repo / "pyproject.toml").write_text("[project]\nname = 'fake'\n")
    (repo / "deals").mkdir()
    monkeypatch.setattr(config, "REPO_ROOT", repo)
    return repo


# --------------------------------------------------------------- run log inside the repository

def test_runlog_inside_repo_is_refused_before_anything_is_created(tmp_path):
    target = REPO_ROOT / "deals" / "runlog.jsonl"
    s = load_settings(env={"BIZWAVE_DATA_DIR": str(tmp_path / "data"), "BIZWAVE_RUNLOG": str(target)},
                      home=tmp_path)
    with pytest.raises(DataFolderError) as err:
        ensure_data_dirs(s)
    assert "run log" in str(err.value) and str(target) in str(err.value)
    assert not (tmp_path / "data").exists()


def test_relative_runlog_from_the_repo_folder_is_refused(tmp_path, monkeypatch):
    monkeypatch.chdir(REPO_ROOT)
    s = load_settings(env={"BIZWAVE_DATA_DIR": str(tmp_path / "data"), "BIZWAVE_RUNLOG": "runlog.jsonl"},
                      home=tmp_path)
    assert s.runlog_path == REPO_ROOT / "runlog.jsonl"
    with pytest.raises(DataFolderError):
        ensure_data_dirs(s)
    assert not (REPO_ROOT / "runlog.jsonl").exists()


def test_runlog_default_refuses_a_data_folder_inside_the_repo(monkeypatch, fake_repo):
    from bizwave_preloi.ops import RunLog
    monkeypatch.setenv("BIZWAVE_DATA_DIR", str(fake_repo / "deals"))
    with pytest.raises(DataFolderError):
        RunLog()
    assert sorted(p.name for p in (fake_repo / "deals").iterdir()) == []


def test_runlog_env_variable_inside_repo_refused_through_runlog(monkeypatch, fake_repo):
    from bizwave_preloi.ops import RunLog
    monkeypatch.setenv("BIZWAVE_RUNLOG", str(fake_repo / "deals" / "runlog.jsonl"))
    with pytest.raises(DataFolderError):
        RunLog()


def test_claude_door_cannot_log_into_the_repo(monkeypatch, fake_repo):
    from pydantic import BaseModel

    from bizwave_preloi.llm import ask

    class Shape(BaseModel):
        answer: str

    monkeypatch.setenv("BIZWAVE_RUNLOG", str(fake_repo / "deals" / "runlog.jsonl"))
    with pytest.raises(DataFolderError):
        ask("narrative.draft", content="x", answer_shape=Shape)
    assert not (fake_repo / "deals" / "runlog.jsonl").exists()


# --------------------------------------------------------------- links to the repository

def _link(target, link):
    try:
        os.symlink(target, link, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not allowed here")


def test_repo_reached_through_a_link_is_refused(tmp_path, fake_repo):
    link = tmp_path / "linked-repo"
    _link(fake_repo, link)
    s = load_settings(env={"BIZWAVE_DATA_DIR": str(link / "deals")}, home=tmp_path)
    with pytest.raises(DataFolderError):
        ensure_data_dirs(s)
    assert list((fake_repo / "deals").iterdir()) == []


def test_real_repo_reached_through_a_link_is_refused_without_writing(tmp_path):
    """One check against the real repository; it cannot write because the refusal comes first,
    and even if it broke it would only touch the run-log check (no folders requested inside)."""
    link = tmp_path / "linked-real-repo"
    _link(REPO_ROOT, link)
    s = load_settings(env={"BIZWAVE_DATA_DIR": str(tmp_path / "data"),
                           "BIZWAVE_RUNLOG": str(link / "deals" / "runlog.jsonl")}, home=tmp_path)
    with pytest.raises(DataFolderError):
        ensure_data_dirs(s)


def test_mac_case_mismatch_is_refused(tmp_path, fake_repo, monkeypatch):
    monkeypatch.setattr(config.sys, "platform", "darwin")
    other_case = Path(str(fake_repo).replace("fake-repo", "FAKE-REPO"))
    s = load_settings(env={"BIZWAVE_DATA_DIR": str(other_case / "deals")}, home=tmp_path)
    with pytest.raises(DataFolderError):
        ensure_data_dirs(s)


# --------------------------------------------------------------- synced folders

@pytest.mark.parametrize("parts", [
    ("Library", "CloudStorage", "GoogleDrive-a@b.com", "My Drive", "BizWaveData"),
    ("G", "My Drive", "BizWaveData"),
    ("Library", "Mobile Documents", "com~apple~CloudDocs", "BizWaveData"),
    ("Dropbox (BizWave)", "BizWaveData"),
])
def test_other_sync_clients_warn(tmp_path, parts):
    s = load_settings(env={"BIZWAVE_DATA_DIR": str(tmp_path.joinpath(*parts))}, home=tmp_path)
    with pytest.warns(UserWarning, match="(?i)sync"):
        ensure_data_dirs(s)


def test_link_into_a_synced_folder_warns(tmp_path):
    synced = tmp_path / "OneDrive - BizWave" / "BizWaveData"
    synced.mkdir(parents=True)
    link = tmp_path / "BizWaveData"
    _link(synced, link)
    with pytest.warns(UserWarning, match="(?i)sync"):
        ensure_data_dirs(load_settings(env={"BIZWAVE_DATA_DIR": str(link)}, home=tmp_path))


def test_plain_folder_does_not_warn(tmp_path, recwarn):
    ensure_data_dirs(load_settings(env={"BIZWAVE_DATA_DIR": str(tmp_path / "BizWaveData")}, home=tmp_path))
    assert not [w for w in recwarn if issubclass(w.category, UserWarning)]


# --------------------------------------------------------------- .env behaviour

def test_load_flag_inside_the_file_cannot_switch_the_file_off(tmp_path, monkeypatch):
    """The review's scenario: the flag is absent from the environment and set to 0 inside the file.
    The file is read anyway, so a key in it switches Claude on (why .env.example no longer offers it)."""
    env_file = tmp_path / ".env"
    env_file.write_text("BIZWAVE_LOAD_DOTENV=0\nANTHROPIC_API_KEY=sk-from-file\nBIZWAVE_LLM_MODEL=from-file\n")
    monkeypatch.delenv("BIZWAVE_LOAD_DOTENV", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("BIZWAVE_LLM_MODEL", raising=False)
    s = settings(dotenv_path=env_file)
    assert s.has_api_key is True
    assert s.llm_model == "from-file"


def test_env_example_does_not_offer_the_load_flag():
    values = dotenv_values(REPO_ROOT / ".env.example")
    assert "BIZWAVE_LOAD_DOTENV" not in values
    assert "BIZWAVE_RUNLOG" in values and not values["BIZWAVE_RUNLOG"]   # empty: default inside the data folder
