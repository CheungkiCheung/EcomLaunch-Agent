"""Persist post-Action Follow-up requests and evaluations."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260719_0010"
down_revision: str | None = "20260719_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "commerce_follow_ups",
        sa.Column("follow_up_id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("case_id", sa.String(length=64), nullable=False),
        sa.Column("action_id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("dataset_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=True),
        sa.Column("follow_up_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "version >= 1",
            name="ck_commerce_follow_ups_version_positive",
        ),
        sa.PrimaryKeyConstraint("follow_up_id"),
        sa.UniqueConstraint("run_id"),
    )
    for index_name, columns in (
        ("ix_commerce_follow_ups_workspace_id", ["workspace_id"]),
        ("ix_commerce_follow_ups_case_id", ["case_id"]),
        ("ix_commerce_follow_ups_action_id", ["action_id"]),
        ("ix_commerce_follow_ups_dataset_id", ["dataset_id"]),
        ("ix_commerce_follow_ups_status", ["status"]),
        ("ix_commerce_follow_ups_outcome", ["outcome"]),
        (
            "ix_commerce_follow_ups_workspace_action_created",
            ["workspace_id", "action_id", "created_at"],
        ),
    ):
        op.create_index(index_name, "commerce_follow_ups", columns)


def downgrade() -> None:
    op.drop_table("commerce_follow_ups")
