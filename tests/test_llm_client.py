"""The Claude door: register enforced, no-LLM mode, logging with prompt versions, failures -> None."""
import pytest
from pydantic import BaseModel

from bizwave_preloi.llm import USES, ask, enabled
from bizwave_preloi.llm.client import PROMPTS_DIR, load_prompt


class Shape(BaseModel):
    answer: str


class Other(BaseModel):
    x: int


USE = "narrative.draft"


def test_exactly_four_registered_uses():
    assert set(USES) == {"ingest.page_extraction", "addbacks.classify_unmatched",
                         "flags.cim_qualitative", "narrative.draft"}
    for use in USES.values():
        assert use.no_llm_path and use.sends and use.purpose


def test_every_use_has_its_prompt_file_and_no_stray_prompts():
    expected = {u.prompt_file for u in USES.values()}
    on_disk = {p.name for p in PROMPTS_DIR.glob("*.md")}
    assert expected <= on_disk, f"missing prompt files: {expected - on_disk}"
    stray = {name for name in on_disk - expected
             if not any(name.startswith(u + ".v") for u in USES)}   # older versions of a use are fine
    assert not stray


def test_unregistered_use_is_refused(fake_transport):
    with pytest.raises(ValueError, match="Unregistered"):
        ask("valuation.estimate", content="x", answer_shape=Shape, transport=fake_transport(Shape(answer="y")))


def test_no_api_key_means_no_llm(runlog):
    assert enabled(USE) == (False, "no ANTHROPIC_API_KEY")
    assert ask(USE, content="x", answer_shape=Shape, runlog=runlog) is None
    (record,) = list(runlog.records())
    assert record["event"] == "llm_skipped" and record["reason"] == "no ANTHROPIC_API_KEY"


def test_switches(monkeypatch, fake_transport):
    t = fake_transport(Shape(answer="y"))
    assert enabled(USE, t) == (True, None)
    monkeypatch.setenv("BIZWAVE_LLM_DISABLED_USES", "flags.cim_qualitative, narrative.draft")
    assert enabled(USE, t)[0] is False
    assert enabled("addbacks.classify_unmatched", t)[0] is True
    monkeypatch.setenv("BIZWAVE_NO_LLM", "1")
    assert enabled("addbacks.classify_unmatched", t) == (False, "no-LLM mode (BIZWAVE_NO_LLM)")


def test_a_call_is_logged_with_its_prompt_version(fake_transport, runlog):
    t = fake_transport(Shape(answer="drafted"))
    out = ask(USE, content="figures", answer_shape=Shape, deal_id="acme-hvac", transport=t, runlog=runlog)
    assert out == Shape(answer="drafted")
    call = t.calls[0]
    text, sha = load_prompt(USES[USE])
    assert call["system"] == text and call["answer_shape"] is Shape
    assert call["model"] == "claude-sonnet-5-5"
    (record,) = list(runlog.records())
    assert record["event"] == "llm_call"
    assert record["prompt_version"] == 1 and record["prompt_sha"] == sha
    assert record["deal_id"] == "acme-hvac" and record["output"] == {"answer": "drafted"}
    assert record["input_tokens"] == 100


def test_model_can_be_set_by_environment(monkeypatch, fake_transport, runlog):
    monkeypatch.setenv("BIZWAVE_LLM_MODEL", "claude-opus-5-5")
    t = fake_transport(Shape(answer="y"))
    ask(USE, content="x", answer_shape=Shape, transport=t, runlog=runlog)
    assert t.calls[0]["model"] == "claude-opus-5-5"


@pytest.mark.parametrize("kwargs, event", [
    ({"error": TimeoutError("slow")}, "llm_failed"),
    ({"answer": None}, "llm_unusable"),
    ({"answer": Shape(answer="cut off"), "stop_reason": "max_tokens"}, "llm_unusable"),
    ({"answer": Shape(answer="no"), "stop_reason": "refusal"}, "llm_unusable"),
    ({"answer": Other(x=1)}, "llm_unusable"),
])
def test_anything_unusable_returns_none(fake_transport, runlog, kwargs, event):
    assert ask(USE, content="x", answer_shape=Shape, transport=fake_transport(**kwargs), runlog=runlog) is None
    assert [r["event"] for r in runlog.records()] == [event]
