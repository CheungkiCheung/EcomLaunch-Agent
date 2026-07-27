"""Immutable evidence-chain models for Commerce Case Agent."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.commerce.domain.enums import (
    ActionRiskLevel,
    ActionStatus,
    ApprovalStatus,
    CaseSeverity,
    CaseStatus,
    HypothesisStatus,
    SemanticStatus,
)
from app.commerce.domain.ids import (
    ActionId,
    ApprovalId,
    CaseId,
    DatasetId,
    DataSourceId,
    EntityId,
    EvidenceId,
    FactId,
    HypothesisId,
    MetricObservationId,
    WorkspaceId,
)
from app.commerce.domain.transitions import transition_case_status

ScalarValue = str | int | float | bool | Decimal | datetime | date
MetricValue = int | float | Decimal


class CommerceModel(BaseModel):
    """Strict immutable base for persisted domain values."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceRef(CommerceModel):
    """A precise locator back to an uploaded or public source record."""

    source_id: DataSourceId
    dataset_id: DatasetId | None = None
    table_name: str = Field(min_length=1)
    record_locator: str | None = Field(default=None, min_length=1)
    column_name: str | None = Field(default=None, min_length=1)


class Fact(CommerceModel):
    """A source-linked scalar fact or an explicit unknown."""

    id: FactId = Field(default_factory=FactId.new)
    workspace_id: WorkspaceId
    entity_id: EntityId | None = None
    name: str = Field(min_length=1)
    semantic_version: str = Field(default="commerce-semantics@1.0.0", min_length=1)
    semantic_status: SemanticStatus
    value: ScalarValue | None = None
    unit: str | None = Field(default=None, min_length=1)
    observed_at: datetime | None = None
    source: SourceRef | None = None
    unknown_reason: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_semantics(self) -> Self:
        if self.semantic_status in {SemanticStatus.UNKNOWN, SemanticStatus.BLOCKED}:
            if self.value is not None:
                raise ValueError("Unknown or blocked Fact cannot carry a value")
            if self.unknown_reason is None:
                raise ValueError("Unknown or blocked Fact requires unknown_reason")
            return self

        if self.value is None:
            raise ValueError("Known Fact requires a value")
        if self.semantic_status is SemanticStatus.OBSERVED and self.source is None:
            raise ValueError("Observed Fact requires source")
        return self


class MetricObservation(CommerceModel):
    """A versioned deterministic metric value or explicit unavailable metric."""

    id: MetricObservationId = Field(default_factory=MetricObservationId.new)
    workspace_id: WorkspaceId
    entity_id: EntityId | None = None
    metric_name: str = Field(min_length=1)
    semantic_status: SemanticStatus
    value: MetricValue | None = None
    unit: str | None = Field(default=None, min_length=1)
    formula_version: str | None = Field(default=None, min_length=1)
    source_fact_ids: tuple[FactId, ...] = Field(default_factory=tuple)
    window_start: datetime | None = None
    window_end: datetime | None = None
    sample_size: int | None = Field(default=None, ge=0)
    numerator: int | Decimal | None = None
    denominator: int | Decimal | None = None
    unknown_reason: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_semantics(self) -> Self:
        if (self.window_start is None) != (self.window_end is None):
            raise ValueError("MetricObservation window requires both start and end")
        if self.window_start is not None and self.window_end is not None and self.window_start >= self.window_end:
            raise ValueError("MetricObservation window start must be before end")
        if self.semantic_status in {SemanticStatus.UNKNOWN, SemanticStatus.BLOCKED}:
            if self.value is not None:
                raise ValueError("Unknown or blocked MetricObservation cannot carry a value")
            if self.unknown_reason is None:
                raise ValueError("Unknown or blocked MetricObservation requires unknown_reason")
            return self

        if self.value is None:
            raise ValueError("Known MetricObservation requires a value")
        if self.semantic_status is SemanticStatus.DERIVED:
            if self.formula_version is None:
                raise ValueError("Derived MetricObservation requires formula_version")
            if not self.source_fact_ids:
                raise ValueError("Derived MetricObservation requires source_fact_ids")
        return self


class EvidenceRelation(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    CONTEXT = "context"


class Evidence(CommerceModel):
    """A Case-scoped interpretation that only points to traceable inputs."""

    id: EvidenceId = Field(default_factory=EvidenceId.new)
    workspace_id: WorkspaceId
    case_id: CaseId
    summary: str = Field(min_length=1)
    relation: EvidenceRelation
    semantic_status: SemanticStatus
    confidence: float = Field(ge=0.0, le=1.0)
    fact_ids: tuple[FactId, ...] = Field(default_factory=tuple)
    metric_observation_ids: tuple[MetricObservationId, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def require_reference(self) -> Self:
        if not self.fact_ids and not self.metric_observation_ids:
            raise ValueError("Evidence must reference at least one Fact or MetricObservation")
        return self


class Case(CommerceModel):
    """Long-lived business object that owns an investigation lifecycle."""

    id: CaseId = Field(default_factory=CaseId.new)
    workspace_id: WorkspaceId
    title: str = Field(min_length=1)
    severity: CaseSeverity
    status: CaseStatus = CaseStatus.NEW
    summary: str | None = Field(default=None, min_length=1)
    evidence_ids: tuple[EvidenceId, ...] = Field(default_factory=tuple)
    hypothesis_ids: tuple[HypothesisId, ...] = Field(default_factory=tuple)
    action_ids: tuple[ActionId, ...] = Field(default_factory=tuple)
    opened_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    version: int = Field(default=1, ge=1)

    def transition_to(self, target: CaseStatus, *, occurred_at: datetime | None = None) -> Self:
        next_status = transition_case_status(self.status, target)
        next_time = occurred_at or datetime.now(UTC)
        return self.model_copy(
            update={
                "status": next_status,
                "updated_at": max(next_time, self.updated_at),
                "version": self.version + 1,
            }
        )


class Hypothesis(CommerceModel):
    """Versionable explanation candidate linked to supporting evidence."""

    id: HypothesisId = Field(default_factory=HypothesisId.new)
    workspace_id: WorkspaceId
    case_id: CaseId
    statement: str = Field(min_length=1)
    status: HypothesisStatus
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_evidence_ids: tuple[EvidenceId, ...] = Field(default_factory=tuple)
    contradicting_evidence_ids: tuple[EvidenceId, ...] = Field(default_factory=tuple)
    version: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def require_status_evidence(self) -> Self:
        if self.status is HypothesisStatus.SUPPORTED and not self.supporting_evidence_ids:
            raise ValueError("Supported Hypothesis requires supporting evidence")
        if self.status is HypothesisStatus.CONTRADICTED and not self.contradicting_evidence_ids:
            raise ValueError("Contradicted Hypothesis requires contradicting evidence")
        return self


class ApprovalRequirement(CommerceModel):
    """Embedded approval gate carried by every proposed Action."""

    required: bool
    status: ApprovalStatus
    approval_id: ApprovalId | None = None
    reason: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def keep_requirement_and_status_consistent(self) -> Self:
        if self.required and self.status is ApprovalStatus.NOT_REQUIRED:
            raise ValueError("Required approval cannot have not_required status")
        if not self.required and self.status is not ApprovalStatus.NOT_REQUIRED:
            raise ValueError("Optional approval must have not_required status")
        return self


class RollbackPlan(CommerceModel):
    """Concrete rollback or mitigation instructions for an Action."""

    strategy: str = Field(min_length=1)
    trigger: str = Field(min_length=1)
    verification: str = Field(min_length=1)


_APPROVAL_GATED_ACTION_STATUSES = frozenset(
    {
        ActionStatus.APPROVED,
        ActionStatus.EXECUTING,
        ActionStatus.SUCCEEDED,
        ActionStatus.MONITORING,
        ActionStatus.EFFECTIVE,
        ActionStatus.INEFFECTIVE,
        ActionStatus.INCONCLUSIVE,
        ActionStatus.ROLLING_BACK,
        ActionStatus.ROLLED_BACK,
    }
)


class Action(CommerceModel):
    """Evidence-backed, policy-gated operation with an explicit rollback plan."""

    id: ActionId = Field(default_factory=ActionId.new)
    workspace_id: WorkspaceId
    case_id: CaseId
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    status: ActionStatus
    evidence_ids: tuple[EvidenceId, ...] = Field(default_factory=tuple)
    risk_level: ActionRiskLevel
    approval: ApprovalRequirement
    rollback_plan: RollbackPlan

    @model_validator(mode="after")
    def enforce_traceability_and_gate(self) -> Self:
        if not self.evidence_ids:
            raise ValueError("Action requires at least one Evidence reference")

        high_risk = self.risk_level in {ActionRiskLevel.HIGH, ActionRiskLevel.CRITICAL}
        if high_risk and not self.approval.required:
            raise ValueError("High-risk Action requires approval")
        if high_risk and self.status in _APPROVAL_GATED_ACTION_STATUSES and self.approval.status is not ApprovalStatus.APPROVED:
            raise ValueError("High-risk Action cannot advance without an approved gate")
        return self
