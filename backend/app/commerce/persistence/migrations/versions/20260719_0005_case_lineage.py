"""Create immutable Case-to-analysis lineage records."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260719_0005"
down_revision: str | None = "20260719_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "commerce_case_lineage",
        sa.Column("case_id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("dataset_id", sa.String(length=64), nullable=False),
        sa.Column("seller_entity_id", sa.String(length=64), nullable=False),
        sa.Column("seller_external_key", sa.String(length=256), nullable=False),
        sa.Column("baseline_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("baseline_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("anomaly_ids_json", sa.JSON(), nullable=False),
        sa.Column("metric_observation_ids_json", sa.JSON(), nullable=False),
        sa.Column("schema_version", sa.String(length=64), nullable=False),
        sa.Column("analysis_artifact_relative_path", sa.Text(), nullable=False),
        sa.Column("analysis_artifact_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("case_id"),
    )
    op.create_index(
        "ix_commerce_case_lineage_workspace_id",
        "commerce_case_lineage",
        ["workspace_id"],
    )
    op.create_index(
        "ix_commerce_case_lineage_dataset_id",
        "commerce_case_lineage",
        ["dataset_id"],
    )
    op.create_index(
        "ix_commerce_case_lineage_workspace_dataset",
        "commerce_case_lineage",
        ["workspace_id", "dataset_id"],
    )


def downgrade() -> None:
    op.drop_table("commerce_case_lineage")
