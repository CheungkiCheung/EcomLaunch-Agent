"""Bind Action Execution and Follow-up Runs to one Action."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260719_0008"
down_revision: str | None = "20260719_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "commerce_runs",
        sa.Column("subject_action_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "commerce_runs",
        sa.Column("action_operation", sa.String(length=16), nullable=True),
    )
    op.create_index(
        "ix_commerce_runs_subject_action_id",
        "commerce_runs",
        ["subject_action_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_commerce_runs_subject_action_id",
        table_name="commerce_runs",
    )
    op.drop_column("commerce_runs", "action_operation")
    op.drop_column("commerce_runs", "subject_action_id")
