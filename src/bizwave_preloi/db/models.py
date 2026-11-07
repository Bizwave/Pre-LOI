"""The six core tables (tech plan §4.2, P2). Later packets add tables in their own migrations.

A naming convention is set from the first migration so constraint and index names are stable across
SQLite and Postgres (the MVP's autogenerate "index rename noise" came from not having one).
Enums are stored as strings with CHECK constraints (native_enum=False), which works on both databases.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .status import STATUSES
from .types import DecimalText, UTCDateTime, utcnow

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

TIERS = ("instant", "flash", "flash_qoe")
VERDICTS = ("pursue", "pursue_with_conditions", "pass")
EVENT_KINDS = ("status_change", "sla_pause", "sla_resume", "note")
DOCUMENT_KINDS = ("cim", "recast", "p_and_l", "balance_sheet", "other")
READ_STATUSES = ("pending", "text", "table", "claude", "manual", "unread", "skipped")
RUN_STATUSES = ("running", "succeeded", "failed")
LLM_MODES = ("on", "off")


def _enum(name: str, values) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True, length=30)


class Base(DeclarativeBase):
    metadata = sa.MetaData(naming_convention=NAMING_CONVENTION)


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(200))
    email: Mapped[str] = mapped_column(sa.String(254), unique=True)
    firm: Mapped[Optional[str]] = mapped_column(sa.String(200))
    referred_by: Mapped[Optional[str]] = mapped_column(sa.String(200))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class Deal(Base):
    __tablename__ = "deals"
    id: Mapped[str] = mapped_column(sa.String(41), primary_key=True)
    customer_id: Mapped[int] = mapped_column(sa.ForeignKey("customers.id"))
    tier: Mapped[str] = mapped_column(_enum("tier", TIERS))
    status: Mapped[str] = mapped_column(_enum("deal_status", STATUSES), default="created")
    list_price_cents: Mapped[Optional[int]] = mapped_column(sa.Integer)
    asking_price: Mapped[Optional[Decimal]] = mapped_column(DecimalText())
    proposed_price: Mapped[Optional[Decimal]] = mapped_column(DecimalText())
    industry: Mapped[Optional[str]] = mapped_column(sa.String(120))
    offer_deadline: Mapped[Optional[datetime]] = mapped_column(UTCDateTime())
    package_complete_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime())
    due_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime())
    delivered_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime())
    verdict: Mapped[Optional[str]] = mapped_column(_enum("verdict", VERDICTS))
    buyer_decision: Mapped[Optional[str]] = mapped_column(sa.String(200))
    buyer_decision_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class DealEvent(Base):
    __tablename__ = "deal_events"
    __table_args__ = (sa.Index("ix_deal_events_deal_id_at", "deal_id", "at"),)
    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True)
    deal_id: Mapped[str] = mapped_column(sa.ForeignKey("deals.id"))
    at: Mapped[datetime] = mapped_column(UTCDateTime())
    kind: Mapped[str] = mapped_column(_enum("event_kind", EVENT_KINDS))
    from_status: Mapped[Optional[str]] = mapped_column(sa.String(30))
    to_status: Mapped[Optional[str]] = mapped_column(sa.String(30))
    by: Mapped[str] = mapped_column(sa.String(80))
    detail: Mapped[Optional[str]] = mapped_column(sa.Text)


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (sa.UniqueConstraint("deal_id", "sha256"),)
    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True)
    deal_id: Mapped[str] = mapped_column(sa.ForeignKey("deals.id"))
    filename: Mapped[str] = mapped_column(sa.String(255))
    kind: Mapped[str] = mapped_column(_enum("document_kind", DOCUMENT_KINDS))
    sha256: Mapped[str] = mapped_column(sa.String(64))
    size_bytes: Mapped[int] = mapped_column(sa.Integer)
    page_count: Mapped[Optional[int]] = mapped_column(sa.Integer)
    stored_path: Mapped[str] = mapped_column(sa.String(1024))   # relative to the deal folder, "/" separators
    received_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True)
    deal_id: Mapped[str] = mapped_column(sa.ForeignKey("deals.id"))
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime())
    status: Mapped[str] = mapped_column(_enum("run_status", RUN_STATUSES), default="running")
    git_sha: Mapped[Optional[str]] = mapped_column(sa.String(40))
    rules_hash: Mapped[str] = mapped_column(sa.String(64))
    llm_mode: Mapped[str] = mapped_column(_enum("llm_mode", LLM_MODES))
    stages: Mapped[dict] = mapped_column(sa.JSON, default=dict)
    error: Mapped[Optional[str]] = mapped_column(sa.Text)


class Page(Base):
    __tablename__ = "pages"
    __table_args__ = (sa.UniqueConstraint("document_id", "page_no"),
                      sa.CheckConstraint("page_no >= 1", name="page_no_positive"))
    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(sa.ForeignKey("documents.id"))
    page_no: Mapped[int] = mapped_column(sa.Integer)
    chars: Mapped[int] = mapped_column(sa.Integer)
    has_text_layer: Mapped[bool] = mapped_column(sa.Boolean)
    tables_found: Mapped[int] = mapped_column(sa.Integer)
    images: Mapped[int] = mapped_column(sa.Integer)
    read_status: Mapped[str] = mapped_column(_enum("read_status", READ_STATUSES), default="pending")
    run_id: Mapped[Optional[int]] = mapped_column(sa.ForeignKey("pipeline_runs.id"))
