"""Persisted post-Action Follow-up request and outcome contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from app.commerce.actions.contracts import MetricComparison
from app.commerce.domain.enums import FollowUpOutcome
from app.commerce.domain.ids import (
    ActionId,
    CaseId,
    DatasetId,
    FollowUpId,
    RunId,
    WorkspaceId,
)
from app.commerce.domain.models import CommerceModel, MetricObservation
from app.commerce.metrics.registry import MetricWindow


class FollowUpStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"


class FollowUpComparisonBasis(StrEnum):
    METRIC_MONITOR_THRESHOLD = "metric_monitor_threshold"
    NO_RELIABLE_TARGET = "no_reliable_target"


class FollowUpSignalStatus(StrEnum):
    TARGET_MET = "target_met"
    TARGET_MISSED = "target_missed"
    UNAVAILABLE = "unavailable"


class FollowUpAttributionMethod(StrEnum):
    NONE = "none"
    CONTROLLED_COMPARISON = "controlled_comparison"


class FollowUpRecord(CommerceModel):
    schema_version: str = "commerce.follow-up@1.0.0"
    id: FollowUpId = Field(default_factory=FollowUpId.new)
    workspace_id: WorkspaceId
    case_id: CaseId
    action_id: ActionId
    run_id: RunId
    dataset_id: DatasetId
    evaluation_window: MetricWindow
    minimum_sample_size: int = Field(ge=1)
    status: FollowUpStatus = FollowUpStatus.PENDING
    comparison_basis: FollowUpComparisonBasis | None = None
    metric_name: str | None = Field(default=None, min_length=1)
    comparison: MetricComparison | None = None
    threshold: Decimal | None = None
    metric_observation: MetricObservation | None = None
    signal_status: FollowUpSignalStatus | None = None
    attribution_method: FollowUpAttributionMethod = FollowUpAttributionMethod.NONE
    outcome: FollowUpOutcome | None = None
    assessment: str | None = Field(default=None, min_length=1, max_length=2_000)
    limitations: tuple[str, ...] = ()
    causal_claim: Literal[False] = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    version: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def keep_projection_consistent(self) -> Self:
        if self.updated_at < self.created_at:
            raise ValueError("Follow-up updated_at cannot precede created_at")
        if self.status is FollowUpStatus.PENDING:
            if (
                any(
                    value is not None
                    for value in (
                        self.comparison_basis,
                        self.metric_name,
                        self.comparison,
                        self.threshold,
                        self.metric_observation,
                        self.signal_status,
                        self.outcome,
                        self.assessment,
                    )
                )
                or self.limitations
            ):
                raise ValueError("Pending Follow-up cannot carry an evaluation")
            return self
        if self.outcome not in {
            FollowUpOutcome.EFFECTIVE,
            FollowUpOutcome.INEFFECTIVE,
            FollowUpOutcome.INCONCLUSIVE,
        }:
            raise ValueError("Completed Follow-up requires a signal outcome")
        if self.signal_status is None:
            raise ValueError("Completed Follow-up requires a signal status")
        if self.attribution_method is FollowUpAttributionMethod.NONE and self.outcome is not FollowUpOutcome.INCONCLUSIVE:
            raise ValueError("Follow-up without controlled comparison must remain inconclusive")
        if self.assessment is None or not self.limitations:
            raise ValueError("Completed Follow-up requires assessment and limitations")
        if self.outcome in {
            FollowUpOutcome.EFFECTIVE,
            FollowUpOutcome.INEFFECTIVE,
        } and any(
            value is None
            for value in (
                self.metric_observation,
                self.metric_name,
                self.comparison,
                self.threshold,
            )
        ):
            raise ValueError("Conclusive Follow-up requires a metric threshold comparison")
        return self

    def complete(
        self,
        *,
        comparison_basis: FollowUpComparisonBasis,
        metric_name: str | None,
        comparison: MetricComparison | None,
        threshold: Decimal | None,
        metric_observation: MetricObservation | None,
        signal_status: FollowUpSignalStatus,
        attribution_method: FollowUpAttributionMethod,
        outcome: FollowUpOutcome,
        assessment: str,
        limitations: tuple[str, ...],
        occurred_at: datetime,
    ) -> Self:
        if self.status is not FollowUpStatus.PENDING:
            raise ValueError("Follow-up is already completed")
        return FollowUpRecord.model_validate(
            {
                **self.model_dump(mode="python"),
                "status": FollowUpStatus.COMPLETED,
                "comparison_basis": comparison_basis,
                "metric_name": metric_name,
                "comparison": comparison,
                "threshold": threshold,
                "metric_observation": metric_observation,
                "signal_status": signal_status,
                "attribution_method": attribution_method,
                "outcome": outcome,
                "assessment": assessment,
                "limitations": limitations,
                "updated_at": max(occurred_at, self.updated_at),
                "version": self.version + 1,
            }
        )
