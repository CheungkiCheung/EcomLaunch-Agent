"""Explicit Case-to-Dataset analysis lineage contracts."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.commerce.domain.ids import (
    AnomalyId,
    CaseId,
    DatasetId,
    EntityId,
    MetricObservationId,
    WorkspaceId,
)
from app.commerce.domain.lineage import CaseLineage


def test_case_lineage_requires_ordered_windows_and_safe_artifact_reference():
    lineage = CaseLineage(
        workspace_id=WorkspaceId.new(),
        case_id=CaseId.new(),
        dataset_id=DatasetId.new(),
        seller_entity_id=EntityId.new(),
        seller_external_key="seller-1",
        baseline_start=datetime(2026, 1, 1, tzinfo=UTC),
        baseline_end=datetime(2026, 2, 1, tzinfo=UTC),
        current_start=datetime(2026, 2, 1, tzinfo=UTC),
        current_end=datetime(2026, 3, 1, tzinfo=UTC),
        anomaly_ids=(AnomalyId.new(),),
        metric_observation_ids=(MetricObservationId.new(),),
        analysis_artifact_relative_path="derived/case-context-a.json",
        analysis_artifact_sha256="a" * 64,
    )

    assert lineage.analysis_artifact_relative_path.startswith("derived/")

    with pytest.raises(ValidationError, match="relative derived path"):
        CaseLineage.model_validate(
            {
                **lineage.model_dump(),
                "analysis_artifact_relative_path": "../secret.json",
            }
        )


def test_case_lineage_rejects_overlapping_analysis_windows():
    with pytest.raises(ValidationError, match="Baseline window"):
        CaseLineage(
            workspace_id=WorkspaceId.new(),
            case_id=CaseId.new(),
            dataset_id=DatasetId.new(),
            seller_entity_id=EntityId.new(),
            seller_external_key="seller-1",
            baseline_start=datetime(2026, 1, 1, tzinfo=UTC),
            baseline_end=datetime(2026, 2, 2, tzinfo=UTC),
            current_start=datetime(2026, 2, 1, tzinfo=UTC),
            current_end=datetime(2026, 3, 1, tzinfo=UTC),
            anomaly_ids=(AnomalyId.new(),),
            metric_observation_ids=(MetricObservationId.new(),),
            analysis_artifact_relative_path="derived/case-context-a.json",
            analysis_artifact_sha256="a" * 64,
        )
