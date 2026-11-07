"""Column types that keep figures exact and times unambiguous on SQLite and Postgres alike.

    Cents        whole cents as an integer (prices, payments, credits); floats and booleans refused.
    DecimalText  exact decimals stored as text: a figure read from a page is stored exactly as the
                 Decimal it was read into, and comes back as that Decimal. Floats are refused, so a
                 computed float can never be saved as if it had been read (CLAUDE.md invariant 1).
                 Text cannot be summed or compared numerically in SQL: do arithmetic in Python.
    UTCDateTime  timezone-aware datetimes only, stored as UTC. SQLite drops the time zone, so the
                 result is always given back as an aware UTC datetime.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.types import TypeDecorator


class Cents(TypeDecorator):
    impl = sa.Integer
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return check_cents(value)


def check_cents(value):
    """None, or an int number of cents. A float (750.5) or a bool would be stored as REAL or 1."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"Cents take an int, not {type(value).__name__} ({value!r})")
    return value


DECIMAL_TEXT_LENGTH = 40


class DecimalText(TypeDecorator):
    impl = sa.String(DECIMAL_TEXT_LENGTH)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return check_decimal(value)

    def process_result_value(self, value, dialect):
        return None if value is None else Decimal(value)


def check_decimal(value):
    """None, or the text a Decimal or int is stored as. Floats are refused (invariant 1); so is anything
    longer than the column (Postgres would refuse it, SQLite would quietly keep it)."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (Decimal, int)):
        raise TypeError(f"DecimalText takes a Decimal or an int, not {type(value).__name__} ({value!r})")
    text = str(Decimal(value))
    if len(text) > DECIMAL_TEXT_LENGTH:
        raise ValueError(f"{text[:20]}... is longer than {DECIMAL_TEXT_LENGTH} characters")
    return text


class UTCDateTime(TypeDecorator):
    impl = sa.DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else check_aware(value).astimezone(timezone.utc)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


def check_aware(value):
    """A timezone-aware datetime (naive ones are ambiguous: ValueError)."""
    if not isinstance(value, datetime):
        raise TypeError(f"UTCDateTime takes a datetime, not {type(value).__name__}")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"UTCDateTime needs a timezone-aware datetime, got naive {value!r}")
    return value


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
