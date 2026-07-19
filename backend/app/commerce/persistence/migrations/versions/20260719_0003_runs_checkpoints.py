"""Create Commerce Run projections and append-only Checkpoints."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260719_0003"
down_revision: str | None = "20260718_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "commerce_runs",
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("case_id", sa.String(length=64), nullable=False),
        sa.Column("run_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("phase", sa.String(length=32), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("idempotency_key_sha256", sa.String(length=64), nullable=False),
        sa.Column("wait_reason", sa.Text(), nullable=True),
        sa.Column("stop_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("version >= 1", name="ck_commerce_runs_version_positive"),
        sa.PrimaryKeyConstraint("run_id"),
        sa.UniqueConstraint(
            "workspace_id",
            "case_id",
            "idempotency_key_sha256",
            name="uq_commerce_runs_workspace_case_idempotency",
        ),
    )
    for index_name, columns in (
        ("ix_commerce_runs_workspace_id", ["workspace_id"]),
        ("ix_commerce_runs_case_id", ["case_id"]),
        ("ix_commerce_runs_status", ["status"]),
        (
            "ix_commerce_runs_workspace_case_updated",
            ["workspace_id", "case_id", "updated_at"],
        ),
        (
            "ix_commerce_runs_workspace_status_updated",
            ["workspace_id", "status", "updated_at"],
        ),
    ):
        op.create_index(index_name, "commerce_runs", columns)

    op.create_table(
        "commerce_run_checkpoints",
        sa.Column("checkpoint_id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("case_id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(length=64), nullable=False),
        sa.Column("checkpoint_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "sequence >= 1",
            name="ck_commerce_run_checkpoint_sequence_positive",
        ),
        sa.PrimaryKeyConstraint("checkpoint_id"),
        sa.UniqueConstraint(
            "run_id",
            "sequence",
            name="uq_commerce_run_checkpoint_sequence",
        ),
    )
    for index_name, columns in (
        ("ix_commerce_run_checkpoints_workspace_id", ["workspace_id"]),
        ("ix_commerce_run_checkpoints_case_id", ["case_id"]),
        ("ix_commerce_run_checkpoints_run_id", ["run_id"]),
        (
            "ix_commerce_run_checkpoints_workspace_run_sequence",
            ["workspace_id", "run_id", "sequence"],
        ),
    ):
        op.create_index(index_name, "commerce_run_checkpoints", columns)


def downgrade() -> None:
    op.drop_table("commerce_run_checkpoints")
    op.drop_table("commerce_runs")
