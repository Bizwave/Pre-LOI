"""The register of Claude uses. Claude is called in these four places and nowhere else.

Pattern carried over from the MVP's `llm_service.LLM_USES`: `client.ask()` refuses a use that is
not listed here, so a new Claude call cannot be added without a line saying what it is for,
what leaves the system, and which prompt version it runs.

Changing a prompt: never edit a released prompt file. Copy it to the next version
(`<use>.v2.md`), edit the copy, and bump `prompt_version` here. The run log records the version
and a hash of the prompt text for every call, so any Flash Review can be traced to its prompt.

Every use must have a non-Claude path (`no_llm_path`): the pipeline still runs, and a Flash
Review can still be delivered, with Claude switched off.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class Use:
    name: str
    purpose: str
    called_from: str
    sends: str
    prompt_version: int
    no_llm_path: str
    max_tokens: int = 8000

    @property
    def prompt_file(self) -> str:
        return f"{self.name}.v{self.prompt_version}.md"


USES: Dict[str, Use] = {u.name: u for u in [
    Use(
        name="ingest.page_extraction",
        purpose="Read one PDF page that has no usable text layer, or whose table the parser could "
                "not read, into the statement schema with page references.",
        called_from="bizwave_preloi.ingest (Day 3)",
        sends="The single page as a one-page PDF, the period labels already found, and the schema. "
              "No buyer name, no file name, no other pages.",
        prompt_version=1,
        no_llm_path="The page is listed as unread; the reviewer keys its figures in on the review screen "
                    "(read method 'manual').",
        max_tokens=16000,
    ),
    Use(
        name="addbacks.classify_unmatched",
        purpose="Pick the add-back rule row for descriptions no keyword pattern matched, with a "
                "confidence score. The lender view still comes from the rules table.",
        called_from="bizwave_preloi.classify.addbacks.classify_addbacks",
        sends="The unmatched add-back descriptions (text only, no amounts) and the rule table "
              "(ids, names, categories, notes).",
        prompt_version=1,
        no_llm_path="Unmatched add-backs stay unclassified and are rated by the CPA on review.",
    ),
    Use(
        name="flags.cim_qualitative",
        purpose="Suggest qualitative red flags from CIM narrative text (owner dependence, customer "
                "language, licensing, key staff), each with the page it came from.",
        called_from="bizwave_preloi.flags (Day 5)",
        sends="Narrative pages of the CIM as text. No financial tables, no buyer name.",
        prompt_version=1,
        no_llm_path="No qualitative suggestions; the CPA reads the CIM narrative directly.",
    ),
    Use(
        name="narrative.draft",
        purpose="Draft the prose sections of the Flash Review memo from figures and flags the "
                "pipeline already computed and the CPA already approved.",
        called_from="bizwave_preloi.outputs (Day 7)",
        sends="Approved figures, ratings, flags and LOI-term choices for one deal, under its code name.",
        prompt_version=1,
        no_llm_path="The CPA writes the sections from the memo template.",
    ),
]}
