"""Explicit immutable lineage from a Case to its deterministic analysis context."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Self

from pydantic import Field, model_validator

from app.commerce.domain.ids import (
    AnomalyId,
    CaseId,
    DatasetId,
    EntityId,
    MetricObservationId,
    WorkspaceId,
)
from app.commerce.domain.models import CommerceModel


class CaseLineage(CommerceModel):
    schema_version: str = "commerce.case-lineage@1.0.0"
    workspace_id: WorkspaceId
    case_id: CaseId
    dataset_id: DatasetId
    seller_entity_id: EntityId
    seller_external_key: str = Field(min_length=1)
    baseline_start: datetime
    baseline_end: datetime
    current_start: datetime
    current_end: datetime
    anomaly_ids: tuple[AnomalyId, ...] = Field(min_length=1)
    metric_observation_ids: tuple[MetricObservationId, ...] = Field(min_length=1)
    analysis_artifact_relative_path: str = Field(min_length=1)
    analysis_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def validate_lineage(self) -> Self:
        if self.baseline_start >= self.baseline_end:
            raise ValueError("Baseline window start must precede end")
        if self.current_start >= self.current_end:
            raise ValueError("Current window start must precede end")
        if self.baseline_end > self.current_start:
            raise ValueError("Baseline window must end no later than current start")
        path = PurePosixPath(self.analysis_artifact_relative_path)
        if (
            path.is_absolute()
            or ".." in path.parts
            or len(path.parts) != 2
            or path.parts[0] != "derived"
        ):
            raise ValueError("Analysis artifact must use a relative derived path")
        if len(set(self.anomaly_ids)) != len(self.anomaly_ids):
            raise ValueError("Case lineage Anomaly IDs must be unique")
        if len(set(self.metric_observation_ids)) != len(
            self.metric_observation_ids
        ):
            raise ValueError("Case lineage MetricObservation IDs must be unique")
        return self
