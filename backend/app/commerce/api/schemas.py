"""Versioned JSON contracts for the Commerce Case read workspace."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.commerce.actions.approval import (
    ApprovalDecisionCommand,
    ApprovalRequest,
)
from app.commerce.actions.artifacts import ActionExecutionArtifact
from app.commerce.actions.contracts import ActionParameters
from app.commerce.actions.follow_up_contracts import FollowUpRecord
from app.commerce.actions.planner import ActionPlanningResult
from app.commerce.agents.contracts import (
    CaseTriggerDigest,
    CaseTriggerType,
    PathType,
)
from app.commerce.agents.goal_loop import GoalLoopCheckpoint
from app.commerce.agents.resume import (
    ResumeExecutionDisposition,
    ResumeResolutionDecision,
)
from app.commerce.data.capabilities import CapabilityProfile
from app.commerce.data.intake import DataBundleManifest
from app.commerce.data.profiler import DatasetProfile
from app.commerce.data.semantic_mapper import (
    SemanticConfirmation,
    SemanticField,
    SemanticMappingProfile,
)
from app.commerce.domain.enums import ActionRunOperation
from app.commerce.domain.ids import (
    DatasetId,
    EvidenceId,
    ExperimentId,
    HypothesisId,
    MetricObservationId,
)
from app.commerce.domain.models import RollbackPlan
from app.commerce.evaluation.experiment import ExperimentDefinition, ExperimentReport
from app.commerce.evaluation.skill_evolution import ActiveSkillPointer, SkillCandidate
from app.commerce.metrics.anomaly import AnomalySignal
from app.commerce.metrics.registry import MetricWindow, PeerCohortPolicy
from app.commerce.persistence.actions import ActionRecord


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


class CaseLineageResponse(CommerceResponse):
    schema_version: str
    workspace_id: str
    case_id: str
    dataset_id: str
    seller_entity_id: str
    seller_external_key: str
    baseline_start: datetime
    baseline_end: datetime
    current_start: datetime
    current_end: datetime
    anomaly_ids: list[str]
    metric_observation_ids: list[str]
    analysis_artifact_relative_path: str
    analysis_artifact_sha256: str
    created_at: datetime


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


class MetricObservationResponse(CommerceResponse):
    id: str
    metric_name: str
    semantic_status: str
    value: str | None
    unit: str | None
    formula_version: str | None
    window_start: datetime | None
    window_end: datetime | None
    sample_size: int | None = Field(default=None, ge=0)
    numerator: str | None
    denominator: str | None
    source_fact_count: int = Field(ge=0)
    unknown_reason: str | None


class CaseAnomalyResponse(CommerceResponse):
    id: str
    metric_name: str
    baseline_observation_id: str
    current_observation_id: str
    baseline_value: str
    current_value: str
    absolute_change: str
    relative_change: str | None
    direction: str
    severity: str
    confidence: float = Field(ge=0.0, le=1.0)
    baseline_sample_size: int = Field(ge=0)
    current_sample_size: int = Field(ge=0)
    sample_adequate: bool
    reason: str


class CaseAnalysisResponse(CommerceResponse):
    status: Literal["available", "unavailable"]
    unavailable_reason: str | None
    baseline_metrics: list[MetricObservationResponse]
    current_metrics: list[MetricObservationResponse]
    anomalies: list[CaseAnomalyResponse]

    @model_validator(mode="after")
    def keep_availability_explicit(self):
        if self.status == "available" and self.unavailable_reason is not None:
            raise ValueError("Available Case analysis cannot have an unavailable reason")
        if self.status == "unavailable" and self.unavailable_reason is None:
            raise ValueError("Unavailable Case analysis requires a reason")
        return self


class CaseActionSummaryResponse(CommerceResponse):
    id: str
    title: str
    description: str
    kind: str
    status: str
    risk_level: str
    policy_level: str
    approval_required: bool
    approval_status: str
    evidence_ids: list[str]
    created_at: datetime
    updated_at: datetime
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
    lineage: CaseLineageResponse | None
    evidence: list[EvidenceResponse]
    hypotheses: list[HypothesisResponse]
    analysis: CaseAnalysisResponse
    actions: list[CaseActionSummaryResponse]


class EvidenceListResponse(CommerceResponse):
    items: list[EvidenceResponse]


class HypothesisListResponse(CommerceResponse):
    items: list[HypothesisResponse]


class DomainEventListResponse(CommerceResponse):
    items: list[DomainEventResponse]


class InvestigationStartRequest(CommerceResponse):
    goal: str = Field(min_length=1, max_length=2_000)
    idempotency_key: str = Field(min_length=8, max_length=128)


class ReplanStartRequest(InvestigationStartRequest):
    requested_paths: list[PathType] = Field(min_length=1, max_length=3)

    @model_validator(mode="after")
    def require_unique_paths(self):
        if len(self.requested_paths) != len(set(self.requested_paths)):
            raise ValueError("Replan requested Paths must be unique")
        return self


class RunResponse(CommerceResponse):
    id: str
    workspace_id: str
    case_id: str
    run_type: str
    status: str
    phase: str
    goal: str
    parent_run_id: str | None
    subject_action_id: str | None
    action_operation: ActionRunOperation | None
    requested_paths: list[PathType]
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


class RunReconciliationRequest(CommerceResponse):
    decision: ResumeResolutionDecision
    reason: str = Field(min_length=1, max_length=2_000)
    idempotency_key: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def require_non_blank_reconciliation_reason(self):
        if not self.reason.strip():
            raise ValueError("Reconciliation reason cannot be blank")
        return self


class RunReconciliationResponse(CommerceResponse):
    run: RunResponse
    latest_checkpoint: RunCheckpointResponse
    disposition: ResumeExecutionDisposition
    replayed: bool


class DatasetIntakeResponse(CommerceResponse):
    manifest: DataBundleManifest
    profile: DatasetProfile
    mappings: SemanticMappingProfile
    capabilities: CapabilityProfile


class DatasetFileSummaryResponse(CommerceResponse):
    original_name: str
    format: str
    size_bytes: int = Field(ge=0)
    sha256: str
    archive_member: str | None


class DatasetCheckSummaryResponse(CommerceResponse):
    file_count: int = Field(ge=1)
    table_count: int = Field(ge=1)
    row_count: int = Field(ge=0)
    confirmed_mapping_count: int = Field(ge=0)
    unresolved_mapping_count: int = Field(ge=0)
    available_capability_count: int = Field(ge=0)
    partial_capability_count: int = Field(ge=0)
    unavailable_capability_count: int = Field(ge=0)


class DatasetListItemResponse(CommerceResponse):
    dataset_id: str
    workspace_id: str
    created_at: datetime
    files: list[DatasetFileSummaryResponse]
    checks: DatasetCheckSummaryResponse
    integrity_status: Literal["verified"]


class DatasetListResponse(CommerceResponse):
    items: list[DatasetListItemResponse]
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


class DatasetDetailResponse(CommerceResponse):
    manifest: DataBundleManifest
    profile: DatasetProfile
    mappings: SemanticMappingProfile
    capabilities: CapabilityProfile
    confirmations: list[SemanticConfirmation]
    checks: DatasetCheckSummaryResponse
    integrity_status: Literal["verified"]


class SemanticConfirmationRequest(CommerceResponse):
    table_name: str = Field(min_length=1)
    column_name: str = Field(min_length=1)
    semantic_field: SemanticField


class MappingResumeRequest(CommerceResponse):
    confirmations: tuple[SemanticConfirmationRequest, ...] = Field(
        min_length=1,
        max_length=100,
    )
    idempotency_key: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def require_unique_mapping_columns(self):
        keys = tuple((item.table_name, item.column_name) for item in self.confirmations)
        if len(keys) != len(set(keys)):
            raise ValueError("Semantic confirmation columns must be unique")
        return self


class MappingResumeResponse(CommerceResponse):
    confirmations: list[SemanticConfirmation]
    mappings: SemanticMappingProfile
    capabilities: CapabilityProfile
    created: bool
    replayed: bool


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


class ExplicitCaseRequest(CommerceResponse):
    seller_id: str = Field(min_length=1)
    baseline_window: MetricWindow
    current_window: MetricWindow
    requested_paths: list[PathType] = Field(min_length=1, max_length=3)
    peer_policy: PeerCohortPolicy | None = None

    @model_validator(mode="after")
    def validate_explicit_trigger(self):
        if self.baseline_window.end > self.current_window.start:
            raise ValueError("Baseline window must end no later than current window start")
        CaseTriggerDigest(
            trigger_type=CaseTriggerType.EXPLICIT_USER,
            requested_paths=tuple(self.requested_paths),
            peer_policy=self.peer_policy,
        )
        return self


class ExplicitCaseResponse(CommerceResponse):
    case: CaseResponse
    trigger: CaseTriggerDigest
    baseline_window: MetricWindow
    current_window: MetricWindow


class ActionProposalFields(CommerceResponse):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2_000)
    evidence_ids: tuple[EvidenceId, ...] = Field(min_length=1)
    hypothesis_ids: tuple[HypothesisId, ...] = Field(min_length=1)
    expected_signal_metric_ids: tuple[MetricObservationId, ...] = Field(min_length=1)
    parameters: ActionParameters
    rollback_plan: RollbackPlan

    @model_validator(mode="after")
    def require_unique_action_references(self):
        for label, values in (
            ("Evidence", self.evidence_ids),
            ("Hypothesis", self.hypothesis_ids),
            ("expected MetricObservation", self.expected_signal_metric_ids),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"Action {label} references must be unique")
        return self


class ActionProposalRequest(ActionProposalFields):
    idempotency_key: str = Field(min_length=8, max_length=128)


class AgentActionPlanRequest(CommerceResponse):
    idempotency_key: str = Field(min_length=8, max_length=128)


class ActionReplacementRequest(ActionProposalFields):
    pass


class ApprovalCommandRequest(CommerceResponse):
    idempotency_key: str = Field(min_length=8, max_length=128)
    reason: str | None = Field(default=None, min_length=1, max_length=1_000)


class ApprovalModifyRequest(ApprovalCommandRequest):
    replacement_idempotency_key: str = Field(min_length=8, max_length=128)
    replacement: ActionReplacementRequest


class ActionProposalResponse(CommerceResponse):
    record: ActionRecord
    approval: ApprovalRequest | None
    created: bool


class AgentActionPlanResponse(CommerceResponse):
    planning: ActionPlanningResult | None
    record: ActionRecord
    approval: ApprovalRequest | None
    created: bool


class ActionDetailResponse(CommerceResponse):
    record: ActionRecord
    approval: ApprovalRequest | None
    artifact: ActionExecutionArtifact | None
    follow_ups: list[FollowUpRecord]


class ActionRecordListResponse(CommerceResponse):
    items: list[ActionRecord]


class ApprovalDecisionResponse(CommerceResponse):
    record: ActionRecord
    approval: ApprovalRequest
    command: ApprovalDecisionCommand
    replayed: bool


class ActionExecutionRequest(CommerceResponse):
    operation: ActionRunOperation
    idempotency_key: str = Field(min_length=8, max_length=128)


class ActionExecutionResponse(CommerceResponse):
    run: RunResponse
    record: ActionRecord
    artifact: ActionExecutionArtifact | None
    created: bool
    replayed: bool
    error_message: str | None


class FollowUpStartRequest(CommerceResponse):
    dataset_id: DatasetId
    evaluation_window: MetricWindow
    idempotency_key: str = Field(min_length=8, max_length=128)


class FollowUpEvaluationResponse(CommerceResponse):
    run: RunResponse
    follow_up: FollowUpRecord
    record: ActionRecord
    case: CaseResponse
    created: bool
    replayed: bool


class FollowUpListResponse(CommerceResponse):
    items: list[FollowUpRecord]


class SkillCandidateProposalRequest(CommerceResponse):
    skill_name: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    base_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    candidate_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    content: str = Field(min_length=1, max_length=20_000)
    source_failure_codes: tuple[str, ...] = Field(min_length=1, max_length=50)
    experiment_id: ExperimentId
    idempotency_key: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def require_unique_failure_codes(self):
        if len(self.source_failure_codes) != len(set(self.source_failure_codes)):
            raise ValueError("Skill Candidate failure codes must be unique")
        return self


class SkillCandidateProposalResponse(CommerceResponse):
    candidate: SkillCandidate
    created: bool


class SkillCandidateListResponse(CommerceResponse):
    items: list[SkillCandidate]


class SkillCandidateEvidenceResponse(CommerceResponse):
    candidate: SkillCandidate
    experiment_role: Literal["offline_evaluation", "source_proposal"] | None
    definition: ExperimentDefinition | None
    report: ExperimentReport | None
    active_pointer: ActiveSkillPointer | None


class SkillCandidatePromotionRequest(CommerceResponse):
    idempotency_key: str = Field(min_length=8, max_length=128)


class SkillCandidateRollbackRequest(CommerceResponse):
    idempotency_key: str = Field(min_length=8, max_length=128)
    reason: str = Field(min_length=1, max_length=2_000)

    @model_validator(mode="after")
    def require_non_blank_reason(self):
        if not self.reason.strip():
            raise ValueError("Skill rollback reason cannot be blank")
        return self


class SkillCandidateTransitionResponse(CommerceResponse):
    candidate: SkillCandidate
    active_pointer: ActiveSkillPointer
    replayed: bool
