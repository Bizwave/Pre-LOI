"""Core tables: customers, deals, deal_events, documents, pipeline_runs, pages (P2).

Revision ID: 0001_core
Revises:
Create Date: 2026-11-06

Written by hand. The column definitions are a frozen copy of models.py as of P2 (migrations never import
the live models). Constraint names are NOT frozen here: op.create_table applies the naming convention of
the environment's target metadata (models.NAMING_CONVENTION). That convention and the names this revision
creates are therefore pinned by tests/test_db.py (test_first_migration_constraint_names_are_pinned):
changing the convention would give fresh and existing databases different names. Later changes go in new
revisions; never edit this one after it is merged.
"""
import sqlalchemy as sa
from alembic import op

revision = "0001_core"
down_revision = None
branch_labels = None
depends_on = None

STATUSES = ("created", "awaiting_payment", "awaiting_documents", "ready", "processing", "in_review",
            "approved", "delivered", "on_hold", "cancelled")


def _enum(name, values):
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True, length=30)


def _dt():
    return sa.DateTime(timezone=True)


def _create_tables() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("firm", sa.String(200)),
        sa.Column("referred_by", sa.String(200)),
        sa.Column("created_at", _dt(), nullable=False),
    )
    op.create_table(
        "deals",
        sa.Column("id", sa.String(41), primary_key=True),
        sa.Column("customer_id", sa.Integer, sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("tier", _enum("tier", ("instant", "flash", "flash_qoe")), nullable=False),
        sa.Column("status", _enum("deal_status", STATUSES), nullable=False),
        sa.Column("list_price_cents", sa.Integer),
        sa.Column("asking_price", sa.String(40)),
        sa.Column("proposed_price", sa.String(40)),
        sa.Column("industry", sa.String(120)),
        sa.Column("offer_deadline", _dt()),
        sa.Column("package_complete_at", _dt()),
        sa.Column("due_at", _dt()),
        sa.Column("delivered_at", _dt()),
        sa.Column("verdict", _enum("verdict", ("pursue", "pursue_with_conditions", "pass"))),
        sa.Column("buyer_decision", sa.String(200)),
        sa.Column("buyer_decision_at", _dt()),
        sa.Column("created_at", _dt(), nullable=False),
        sa.Column("updated_at", _dt(), nullable=False),
    )
    op.create_table(
        "deal_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("deal_id", sa.String(41), sa.ForeignKey("deals.id"), nullable=False),
        sa.Column("at", _dt(), nullable=False),
        sa.Column("kind", _enum("event_kind", ("status_change", "sla_pause", "sla_resume", "note")),
                  nullable=False),
        sa.Column("from_status", sa.String(30)),
        sa.Column("to_status", sa.String(30)),
        sa.Column("by", sa.String(80), nullable=False),
        sa.Column("detail", sa.Text),
    )
    op.create_index("ix_deal_events_deal_id_at", "deal_events", ["deal_id", "at"])
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("deal_id", sa.String(41), sa.ForeignKey("deals.id"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("kind", _enum("document_kind", ("cim", "recast", "p_and_l", "balance_sheet", "other")),
                  nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("page_count", sa.Integer),
        sa.Column("stored_path", sa.String(1024), nullable=False),
        sa.Column("received_at", _dt(), nullable=False),
        sa.UniqueConstraint("deal_id", "sha256"),
        sa.UniqueConstraint("deal_id", "stored_path", name="uq_documents_deal_id_stored_path"),
    )
    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("deal_id", sa.String(41), sa.ForeignKey("deals.id"), nullable=False),
        sa.Column("started_at", _dt(), nullable=False),
        sa.Column("finished_at", _dt()),
        sa.Column("status", _enum("run_status", ("running", "succeeded", "failed")), nullable=False),
        sa.Column("git_sha", sa.String(40)),
        sa.Column("rules_hash", sa.String(64), nullable=False),
        sa.Column("llm_mode", _enum("llm_mode", ("on", "off")), nullable=False),
        sa.Column("stages", sa.JSON, nullable=False),
        sa.Column("error", sa.Text),
    )
    op.create_table(
        "pages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("document_id", sa.Integer, sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("page_no", sa.Integer, nullable=False),
        sa.Column("chars", sa.Integer, nullable=False),
        sa.Column("has_text_layer", sa.Boolean, nullable=False),
        sa.Column("tables_found", sa.Integer, nullable=False),
        sa.Column("images", sa.Integer, nullable=False),
        sa.Column("read_status", _enum("read_status", ("pending", "text", "table", "claude", "manual",
                                                       "unread", "skipped")), nullable=False),
        sa.Column("run_id", sa.Integer, sa.ForeignKey("pipeline_runs.id")),
        sa.UniqueConstraint("document_id", "page_no"),
        sa.CheckConstraint("page_no >= 1", name="page_no_positive"),
    )


def upgrade() -> None:
    _create_tables()            # parents before children


def downgrade() -> None:
    op.drop_index("ix_deal_events_deal_id_at", table_name="deal_events")
    for name in ("pages", "pipeline_runs", "documents", "deal_events", "deals", "customers"):
        op.drop_table(name)
