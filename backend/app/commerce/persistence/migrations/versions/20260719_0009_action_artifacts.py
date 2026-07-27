"""Persist real internal Action Connector artifacts."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260719_0009"
down_revision: str | None = "20260719_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "commerce_action_artifacts",
        sa.Column("action_id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("case_id", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("artifact_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "version >= 1",
            name="ck_commerce_action_artifacts_version_positive",
        ),
        sa.PrimaryKeyConstraint("action_id"),
    )
    for index_name, columns in (
        ("ix_commerce_action_artifacts_workspace_id", ["workspace_id"]),
        ("ix_commerce_action_artifacts_case_id", ["case_id"]),
        ("ix_commerce_action_artifacts_kind", ["kind"]),
        ("ix_commerce_action_artifacts_status", ["status"]),
        (
            "ix_commerce_action_artifacts_workspace_case_updated",
            ["workspace_id", "case_id", "updated_at"],
        ),
    ):
        op.create_index(index_name, "commerce_action_artifacts", columns)


def downgrade() -> None:
    op.drop_table("commerce_action_artifacts")
