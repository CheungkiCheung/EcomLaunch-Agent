"""Create fenced Commerce Run execution leases."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260719_0004"
down_revision: str | None = "20260719_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "commerce_run_leases",
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("case_id", sa.String(length=64), nullable=False),
        sa.Column("worker_id", sa.String(length=128), nullable=False),
        sa.Column("lease_token_sha256", sa.String(length=64), nullable=False),
        sa.Column("fencing_token", sa.Integer(), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "fencing_token >= 1",
            name="ck_commerce_run_lease_fencing_positive",
        ),
        sa.PrimaryKeyConstraint("run_id"),
    )
    for index_name, columns in (
        ("ix_commerce_run_leases_workspace_id", ["workspace_id"]),
        ("ix_commerce_run_leases_case_id", ["case_id"]),
        ("ix_commerce_run_leases_worker_id", ["worker_id"]),
        (
            "ix_commerce_run_leases_workspace_expiry",
            ["workspace_id", "expires_at"],
        ),
    ):
        op.create_index(index_name, "commerce_run_leases", columns)


def downgrade() -> None:
    op.drop_table("commerce_run_leases")
