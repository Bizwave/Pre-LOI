"""Column types that keep figures exact and times unambiguous on SQLite and Postgres alike.

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


class DecimalText(TypeDecorator):
    impl = sa.String(40)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (Decimal, int)):
            raise TypeError(f"DecimalText takes a Decimal or an int, not {type(value).__name__} ({value!r})")
        return str(Decimal(value))

    def process_result_value(self, value, dialect):
        return None if value is None else Decimal(value)


class UTCDateTime(TypeDecorator):
    impl = sa.DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, datetime):
            raise TypeError(f"UTCDateTime takes a datetime, not {type(value).__name__}")
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"UTCDateTime needs a timezone-aware datetime, got naive {value!r}")
        return value.astimezone(timezone.utc)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
