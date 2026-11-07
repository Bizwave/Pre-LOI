"""The deal status flow (tech plan §4.3). Structure of the workflow, kept in code (Chan, P2 Q4).

    created -> awaiting_payment -> awaiting_documents -> ready (SLA clock starts) -> processing
            -> in_review -> approved -> delivered
    side states: on_hold (waiting on the buyer), cancelled
    on_hold returns only to the status the deal had before the hold, or to cancelled (Chan, 2026-11-06),
    so a hold can never skip ready (the SLA clock) or the pipeline run
    created -> awaiting_documents directly for invoiced or free pilots (Chan, P2 Q2)

`repo.transition()` is the only place that changes a deal's status, and it checks ALLOWED.
"""
from __future__ import annotations

from typing import Dict, FrozenSet, Optional

STATUSES = ("created", "awaiting_payment", "awaiting_documents", "ready", "processing", "in_review",
            "approved", "delivered", "on_hold", "cancelled")

ALLOWED: Dict[str, FrozenSet[str]] = {
    "created": frozenset({"awaiting_payment", "awaiting_documents", "cancelled"}),
    "awaiting_payment": frozenset({"awaiting_documents", "cancelled"}),
    "awaiting_documents": frozenset({"ready", "on_hold", "cancelled"}),
    "ready": frozenset({"processing", "on_hold", "cancelled"}),
    "processing": frozenset({"in_review", "ready", "on_hold", "cancelled"}),     # ready: failed run, retry
    "in_review": frozenset({"approved", "processing", "on_hold", "cancelled"}),  # processing: forced re-run
    "approved": frozenset({"delivered", "in_review", "cancelled"}),              # in_review: reopened
    # every status a hold can return to; check() narrows it to the one the deal came from
    "on_hold": frozenset({"awaiting_documents", "ready", "processing", "in_review", "cancelled"}),
    "delivered": frozenset(),
    "cancelled": frozenset(),
}
if set(ALLOWED) != set(STATUSES):        # an explicit check: `assert` is skipped under python -O
    raise RuntimeError("status.ALLOWED must list every status in STATUSES")


class InvalidTransition(ValueError):
    """A status change the flow does not allow (nothing is written)."""


def check(current: str, target: str, *, held_from: Optional[str] = None) -> None:
    """Raise InvalidTransition unless current -> target is allowed. For a deal on hold, held_from is the
    status it had before the hold (repo.transition reads it from the deal's events)."""
    if target not in STATUSES:
        raise InvalidTransition(f"'{target}' is not a deal status; known: {', '.join(STATUSES)}")
    if current == "on_hold" and target != "cancelled":
        if held_from not in ALLOWED["on_hold"]:
            raise InvalidTransition(f"Cannot tell which status this deal was on hold from ({held_from!r}); "
                                    f"it can only be cancelled.")
        if target != held_from:
            raise InvalidTransition(f"A deal on hold goes back to '{held_from}', where it was before the "
                                    f"hold, or to 'cancelled'; not to '{target}'.")
        return
    if target not in ALLOWED[current]:
        allowed = ", ".join(sorted(ALLOWED[current])) or "none (final)"
        raise InvalidTransition(f"A deal cannot go from '{current}' to '{target}'. From '{current}': {allowed}.")
