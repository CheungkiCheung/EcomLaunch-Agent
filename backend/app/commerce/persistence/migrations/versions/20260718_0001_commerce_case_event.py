"""Create Commerce Case and Domain Event tables."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260718_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = ("commerce",)
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "commerce_cases",
        sa.Column("case_id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("evidence_ids_json", sa.JSON(), nullable=False),
        sa.Column("hypothesis_ids_json", sa.JSON(), nullable=False),
        sa.Column("action_ids_json", sa.JSON(), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "version >= 1",
            name="ck_commerce_cases_version_positive",
        ),
        sa.PrimaryKeyConstraint("case_id"),
    )
    op.create_index(
        "ix_commerce_cases_workspace_id",
        "commerce_cases",
        ["workspace_id"],
    )
    op.create_index(
        "ix_commerce_cases_status",
        "commerce_cases",
        ["status"],
    )
    op.create_index(
        "ix_commerce_cases_workspace_status_updated",
        "commerce_cases",
        ["workspace_id", "status", "updated_at"],
    )

    op.create_table(
        "commerce_domain_events",
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("case_id", sa.String(length=64), nullable=True),
        sa.Column("run_id", sa.String(length=64), nullable=True),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("case_sequence", sa.Integer(), nullable=True),
        sa.Column("run_sequence", sa.Integer(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=False),
        sa.Column("causation_event_id", sa.String(length=64), nullable=True),
        sa.Column("actor", sa.String(length=20), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "(case_id IS NOT NULL AND case_sequence IS NOT NULL) OR "
            "(case_id IS NULL AND case_sequence IS NULL)",
            name="ck_commerce_event_case_sequence_presence",
        ),
        sa.CheckConstraint(
            "(run_id IS NOT NULL AND run_sequence IS NOT NULL) OR "
            "(run_id IS NULL AND run_sequence IS NULL)",
            name="ck_commerce_event_run_sequence_presence",
        ),
        sa.CheckConstraint(
            "case_id IS NOT NULL OR run_id IS NOT NULL",
            name="ck_commerce_event_has_aggregate",
        ),
        sa.PrimaryKeyConstraint("event_id"),
        sa.UniqueConstraint(
            "case_id",
            "case_sequence",
            name="uq_commerce_event_case_sequence",
        ),
        sa.UniqueConstraint(
            "run_id",
            "run_sequence",
            name="uq_commerce_event_run_sequence",
        ),
    )
    for index_name, columns in (
        ("ix_commerce_domain_events_workspace_id", ["workspace_id"]),
        ("ix_commerce_domain_events_case_id", ["case_id"]),
        ("ix_commerce_domain_events_run_id", ["run_id"]),
        ("ix_commerce_domain_events_event_type", ["event_type"]),
        ("ix_commerce_domain_events_trace_id", ["trace_id"]),
        ("ix_commerce_domain_events_correlation_id", ["correlation_id"]),
        (
            "ix_commerce_events_workspace_case_sequence",
            ["workspace_id", "case_id", "case_sequence"],
        ),
        (
            "ix_commerce_events_workspace_run_sequence",
            ["workspace_id", "run_id", "run_sequence"],
        ),
    ):
        op.create_index(index_name, "commerce_domain_events", columns)


def downgrade() -> None:
    op.drop_table("commerce_domain_events")
    op.drop_table("commerce_cases")
