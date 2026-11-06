"""Validation: footing checks run before any extracted figure is used."""
from .footing import CheckResult, FootingReport, check_bridge, check_statement

__all__ = ["check_statement", "check_bridge", "CheckResult", "FootingReport"]
