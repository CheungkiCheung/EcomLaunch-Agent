"""Create append-only Evidence and versioned Hypothesis tables."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260718_0002"
down_revision: str | None = "20260718_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "commerce_evidence",
        sa.Column("evidence_id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("case_id", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("relation", sa.String(length=20), nullable=False),
        sa.Column("semantic_status", sa.String(length=20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("fact_ids_json", sa.JSON(), nullable=False),
        sa.Column("metric_observation_ids_json", sa.JSON(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_commerce_evidence_confidence_range",
        ),
        sa.PrimaryKeyConstraint("evidence_id"),
    )
    op.create_index(
        "ix_commerce_evidence_workspace_id",
        "commerce_evidence",
        ["workspace_id"],
    )
    op.create_index(
        "ix_commerce_evidence_case_id",
        "commerce_evidence",
        ["case_id"],
    )
    op.create_index(
        "ix_commerce_evidence_workspace_case",
        "commerce_evidence",
        ["workspace_id", "case_id"],
    )

    op.create_table(
        "commerce_hypotheses",
        sa.Column("hypothesis_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("case_id", sa.String(length=64), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("supporting_evidence_ids_json", sa.JSON(), nullable=False),
        sa.Column("contradicting_evidence_ids_json", sa.JSON(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "version >= 1",
            name="ck_commerce_hypotheses_version_positive",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_commerce_hypotheses_confidence_range",
        ),
        sa.PrimaryKeyConstraint("hypothesis_id", "version"),
    )
    op.create_index(
        "ix_commerce_hypotheses_workspace_id",
        "commerce_hypotheses",
        ["workspace_id"],
    )
    op.create_index(
        "ix_commerce_hypotheses_case_id",
        "commerce_hypotheses",
        ["case_id"],
    )
    op.create_index(
        "ix_commerce_hypotheses_workspace_case",
        "commerce_hypotheses",
        ["workspace_id", "case_id"],
    )
    op.create_index(
        "ix_commerce_hypotheses_workspace_case_status",
        "commerce_hypotheses",
        ["workspace_id", "case_id", "status"],
    )


def downgrade() -> None:
    op.drop_table("commerce_hypotheses")
    op.drop_table("commerce_evidence")
