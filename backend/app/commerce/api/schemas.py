"""Versioned JSON contracts for the Commerce Case read workspace."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.commerce.agents.goal_loop import GoalLoopCheckpoint
from app.commerce.data.capabilities import CapabilityProfile
from app.commerce.data.intake import DataBundleManifest
from app.commerce.data.profiler import DatasetProfile
from app.commerce.data.semantic_mapper import (
    SemanticField,
    SemanticMappingProfile,
)
from app.commerce.metrics.anomaly import AnomalySignal
from app.commerce.metrics.registry import MetricWindow


class CommerceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CaseResponse(CommerceResponse):
    id: str
    workspace_id: str
    title: str
    severity: str
    status: str
    summary: str | None
    evidence_ids: list[str]
    hypothesis_ids: list[str]
    action_ids: list[str]
    opened_at: datetime
    updated_at: datetime
    version: int = Field(ge=1)


class EvidenceResponse(CommerceResponse):
    id: str
    workspace_id: str
    case_id: str
    summary: str
    relation: str
    semantic_status: str
    confidence: float = Field(ge=0.0, le=1.0)
    fact_ids: list[str]
    metric_observation_ids: list[str]


class HypothesisResponse(CommerceResponse):
    id: str
    workspace_id: str
    case_id: str
    statement: str
    status: str
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_evidence_ids: list[str]
    contradicting_evidence_ids: list[str]
    version: int = Field(ge=1)


class DomainEventResponse(CommerceResponse):
    id: str
    workspace_id: str
    case_id: str | None
    run_id: str | None
    event_type: str
    schema_version: str
    case_sequence: int | None
    run_sequence: int | None
    occurred_at: datetime
    recorded_at: datetime
    trace_id: str
    correlation_id: str
    causation_event_id: str | None
    actor: str
    payload: dict[str, Any]


class CaseListResponse(CommerceResponse):
    items: list[CaseResponse]
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


class CaseDetailResponse(CommerceResponse):
    case: CaseResponse
    evidence: list[EvidenceResponse]
    hypotheses: list[HypothesisResponse]


class EvidenceListResponse(CommerceResponse):
    items: list[EvidenceResponse]


class HypothesisListResponse(CommerceResponse):
    items: list[HypothesisResponse]


class DomainEventListResponse(CommerceResponse):
    items: list[DomainEventResponse]


class InvestigationStartRequest(CommerceResponse):
    goal: str = Field(min_length=1, max_length=2_000)
    idempotency_key: str = Field(min_length=8, max_length=128)


class RunResponse(CommerceResponse):
    id: str
    workspace_id: str
    case_id: str
    run_type: str
    status: str
    phase: str
    goal: str
    wait_reason: str | None
    stop_reason: str | None
    created_at: datetime
    started_at: datetime | None
    ended_at: datetime | None
    updated_at: datetime
    version: int = Field(ge=1)


class RunCheckpointResponse(CommerceResponse):
    id: str
    sequence: int = Field(ge=1)
    checkpoint: GoalLoopCheckpoint
    created_at: datetime


class InvestigationStartResponse(CommerceResponse):
    run: RunResponse
    created: bool
    latest_checkpoint: RunCheckpointResponse | None


class RunDetailResponse(CommerceResponse):
    run: RunResponse
    latest_checkpoint: RunCheckpointResponse | None


class RunListResponse(CommerceResponse):
    items: list[RunResponse]
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


class RunCheckpointListResponse(CommerceResponse):
    items: list[RunCheckpointResponse]


class DatasetIntakeResponse(CommerceResponse):
    manifest: DataBundleManifest
    profile: DatasetProfile
    mappings: SemanticMappingProfile
    capabilities: CapabilityProfile


class SemanticConfirmationRequest(CommerceResponse):
    table_name: str = Field(min_length=1)
    column_name: str = Field(min_length=1)
    semantic_field: SemanticField


class AnalysisRequest(CommerceResponse):
    baseline_window: MetricWindow
    current_window: MetricWindow
    seller_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def require_ordered_windows(self):
        if self.baseline_window.end > self.current_window.start:
            raise ValueError("Baseline window must end no later than current window start")
        return self


class AnalysisSkipResponse(CommerceResponse):
    seller_id: str
    reason: str


class AnalysisResponse(CommerceResponse):
    dataset_id: str
    workspace_id: str
    baseline_window: MetricWindow
    current_window: MetricWindow
    signals: list[AnomalySignal]
    cases: list[CaseResponse]
    skipped_sellers: list[AnalysisSkipResponse]
