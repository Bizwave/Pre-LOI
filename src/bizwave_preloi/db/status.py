"""The deal status flow (tech plan §4.3). Structure of the workflow, kept in code (Chan, P2 Q4).

    created -> awaiting_payment -> awaiting_documents -> ready (SLA clock starts) -> processing
            -> in_review -> approved -> delivered
    side states: on_hold (waiting on the buyer), cancelled
    created -> awaiting_documents directly for invoiced or free pilots (Chan, P2 Q2)

`repo.transition()` is the only place that changes a deal's status, and it checks ALLOWED.
"""
from __future__ import annotations

from typing import Dict, FrozenSet

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
    "on_hold": frozenset({"awaiting_documents", "ready", "processing", "in_review", "cancelled"}),
    "delivered": frozenset(),
    "cancelled": frozenset(),
}
if set(ALLOWED) != set(STATUSES):        # an explicit check: `assert` is skipped under python -O
    raise RuntimeError("status.ALLOWED must list every status in STATUSES")


class InvalidTransition(ValueError):
    """A status change the flow does not allow (nothing is written)."""


def check(current: str, target: str) -> None:
    if target not in STATUSES:
        raise InvalidTransition(f"'{target}' is not a deal status; known: {', '.join(STATUSES)}")
    if target not in ALLOWED[current]:
        allowed = ", ".join(sorted(ALLOWED[current])) or "none (final)"
        raise InvalidTransition(f"A deal cannot go from '{current}' to '{target}'. From '{current}': {allowed}.")
