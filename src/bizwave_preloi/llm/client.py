"""The only door to Claude. `ask()` runs one registered use and returns a validated answer or None.

    from bizwave_preloi.llm import ask
    answer = ask("addbacks.classify_unmatched", content=text, answer_shape=MyShape, deal_id="acme-hvac")
    if answer is None:   # Claude off, failed, refused or gave an answer that does not fit
        ...              # take the use's no_llm_path

Rules (CLAUDE.md, invariants 2 and 3):
* A use not in `register.USES` is refused with ValueError.
* No-LLM mode: BIZWAVE_NO_LLM=1, the use listed in BIZWAVE_LLM_DISABLED_USES, or no API key.
  `ask()` then returns None at once and logs the skip; callers never need to check first.
* Every call (and every skip) is written to the run log with the prompt version, a hash of the
  prompt text, a hash of the input, the model, timing and token counts.
* One call per batch. Never call `ask()` in a per-row loop.

The transport is swappable (tests pass a fake). The default uses the Anthropic SDK's structured
outputs: `client.messages.parse(..., output_format=PydanticModel)` -> `response.parsed_output`.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Protocol, Tuple, Type, Union

from pydantic import BaseModel

from ..ops.runlog import RunLog
from .register import USES, Use

PROMPTS_DIR = Path(__file__).parent / "prompts"
DEFAULT_MODEL = "claude-sonnet-5-5"
Content = Union[str, list]


@dataclass
class Reply:
    parsed: Optional[BaseModel]
    stop_reason: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None


class Transport(Protocol):
    def parse(self, *, model: str, system: str, content: Content, answer_shape: Type[BaseModel],
              max_tokens: int, timeout_seconds: float) -> Reply: ...


class AnthropicTransport:
    """Structured outputs through the Anthropic Python SDK (installed with the `llm` extra)."""

    def __init__(self, api_key: Optional[str] = None):
        import anthropic                          # loaded only when Claude is actually called
        self._client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))

    def parse(self, *, model, system, content, answer_shape, max_tokens, timeout_seconds) -> Reply:
        response = self._client.with_options(timeout=float(timeout_seconds), max_retries=1).messages.parse(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": content}],
            output_format=answer_shape,
        )
        usage = getattr(response, "usage", None)
        return Reply(parsed=getattr(response, "parsed_output", None),
                     stop_reason=getattr(response, "stop_reason", None),
                     input_tokens=getattr(usage, "input_tokens", None),
                     output_tokens=getattr(usage, "output_tokens", None))


# ------------------------------------------------------------------------------ settings

def enabled(use: str, transport: Optional[Transport] = None) -> Tuple[bool, Optional[str]]:
    """(True, None) when `use` may call Claude now, else (False, why not)."""
    if use not in USES:
        raise ValueError(f"Unregistered Claude use '{use}' — add it to llm/register.py first.")
    if os.environ.get("BIZWAVE_NO_LLM", "0").strip() in ("1", "true", "yes"):
        return False, "no-LLM mode (BIZWAVE_NO_LLM)"
    disabled = {u.strip() for u in os.environ.get("BIZWAVE_LLM_DISABLED_USES", "").split(",") if u.strip()}
    if use in disabled:
        return False, "use disabled (BIZWAVE_LLM_DISABLED_USES)"
    if transport is None and not os.environ.get("ANTHROPIC_API_KEY"):
        return False, "no ANTHROPIC_API_KEY"
    return True, None


def load_prompt(use: Use) -> Tuple[str, str]:
    """(prompt text, first 12 hex characters of its SHA-256)."""
    text = (PROMPTS_DIR / use.prompt_file).read_text(encoding="utf-8")
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _hash(content: Any) -> str:
    raw = content if isinstance(content, str) else json.dumps(content, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


# ------------------------------------------------------------------------------ the call

def ask(use: str, *, content: Content, answer_shape: Type[BaseModel], deal_id: Optional[str] = None,
        transport: Optional[Transport] = None, model: Optional[str] = None,
        runlog: Optional[RunLog] = None, timeout_seconds: float = 120.0) -> Optional[BaseModel]:
    """Run one registered use. Returns an instance of `answer_shape`, or None (see module doc)."""
    ok, why_not = enabled(use, transport)          # raises on an unregistered use
    spec = USES[use]
    log = runlog or RunLog()
    prompt, prompt_sha = load_prompt(spec)
    model = model or os.environ.get("BIZWAVE_LLM_MODEL") or DEFAULT_MODEL
    base = dict(use=use, deal_id=deal_id, prompt_version=spec.prompt_version, prompt_sha=prompt_sha,
                model=model, input_sha=_hash(content))
    if not ok:
        log.append("llm_skipped", **base, reason=why_not)
        return None

    started = time.monotonic()
    try:
        reply = (transport or AnthropicTransport()).parse(
            model=model, system=prompt, content=content, answer_shape=answer_shape,
            max_tokens=spec.max_tokens, timeout_seconds=timeout_seconds)
    except Exception as err:                       # network, timeout, SDK missing, bad request
        log.append("llm_failed", **base, error=f"{type(err).__name__}: {err}",
                   latency_ms=int((time.monotonic() - started) * 1000))
        return None

    latency_ms = int((time.monotonic() - started) * 1000)
    usable = (reply.parsed is not None and isinstance(reply.parsed, answer_shape)
              and reply.stop_reason not in ("refusal", "max_tokens"))
    log.append("llm_call" if usable else "llm_unusable", **base, stop_reason=reply.stop_reason,
               latency_ms=latency_ms, input_tokens=reply.input_tokens, output_tokens=reply.output_tokens,
               output=reply.parsed.model_dump(mode="json") if reply.parsed is not None else None)
    return reply.parsed if usable else None
