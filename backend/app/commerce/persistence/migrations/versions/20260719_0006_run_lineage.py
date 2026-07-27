"""Add parent lineage and requested Path scope to Commerce Runs."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260719_0006"
down_revision: str | None = "20260719_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "commerce_runs",
        sa.Column("parent_run_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "commerce_runs",
        sa.Column(
            "requested_paths_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    op.create_index(
        "ix_commerce_runs_parent_run_id",
        "commerce_runs",
        ["parent_run_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_commerce_runs_parent_run_id",
        table_name="commerce_runs",
    )
    op.drop_column("commerce_runs", "requested_paths_json")
    op.drop_column("commerce_runs", "parent_run_id")
