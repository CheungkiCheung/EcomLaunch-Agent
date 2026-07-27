"""Create Commerce Action and Approval persistence."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260719_0007"
down_revision: str | None = "20260719_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "commerce_actions",
        sa.Column("action_id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("case_id", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("policy_level", sa.String(length=4), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("decision_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "version >= 1",
            name="ck_commerce_actions_version_positive",
        ),
        sa.PrimaryKeyConstraint("action_id"),
    )
    op.create_index(
        "ix_commerce_actions_workspace_id",
        "commerce_actions",
        ["workspace_id"],
    )
    op.create_index(
        "ix_commerce_actions_case_id",
        "commerce_actions",
        ["case_id"],
    )
    op.create_index(
        "ix_commerce_actions_kind",
        "commerce_actions",
        ["kind"],
    )
    op.create_index(
        "ix_commerce_actions_status",
        "commerce_actions",
        ["status"],
    )
    op.create_index(
        "ix_commerce_actions_workspace_case_created",
        "commerce_actions",
        ["workspace_id", "case_id", "created_at"],
    )

    op.create_table(
        "commerce_approval_requests",
        sa.Column("approval_id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("case_id", sa.String(length=64), nullable=False),
        sa.Column("action_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("request_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "version >= 1",
            name="ck_commerce_approval_requests_version_positive",
        ),
        sa.PrimaryKeyConstraint("approval_id"),
        sa.UniqueConstraint("action_id"),
    )
    for index_name, columns in (
        ("ix_commerce_approval_requests_workspace_id", ["workspace_id"]),
        ("ix_commerce_approval_requests_case_id", ["case_id"]),
        ("ix_commerce_approval_requests_status", ["status"]),
        (
            "ix_commerce_approval_requests_workspace_case_updated",
            ["workspace_id", "case_id", "updated_at"],
        ),
    ):
        op.create_index(index_name, "commerce_approval_requests", columns)

    op.create_table(
        "commerce_approval_decisions",
        sa.Column("decision_id", sa.String(length=64), nullable=False),
        sa.Column("approval_id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("case_id", sa.String(length=64), nullable=False),
        sa.Column("action_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key_sha256", sa.String(length=64), nullable=False),
        sa.Column("decision_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("decision_id"),
        sa.UniqueConstraint(
            "workspace_id",
            "action_id",
            "idempotency_key_sha256",
            name="uq_commerce_approval_decision_idempotency",
        ),
    )
    for index_name, columns in (
        ("ix_commerce_approval_decisions_approval_id", ["approval_id"]),
        ("ix_commerce_approval_decisions_workspace_id", ["workspace_id"]),
        ("ix_commerce_approval_decisions_case_id", ["case_id"]),
        ("ix_commerce_approval_decisions_action_id", ["action_id"]),
        (
            "ix_commerce_approval_decisions_approval_created",
            ["approval_id", "created_at"],
        ),
    ):
        op.create_index(index_name, "commerce_approval_decisions", columns)


def downgrade() -> None:
    op.drop_table("commerce_approval_decisions")
    op.drop_table("commerce_approval_requests")
    op.drop_table("commerce_actions")
