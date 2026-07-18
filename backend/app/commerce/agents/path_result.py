"""Normalized structured output contract for Commerce Path Agents."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from app.commerce.agents.contracts import PathType
from app.commerce.agents.model_router import ModelAssignment, ModelRole
from app.commerce.domain.enums import SemanticStatus
from app.commerce.domain.ids import (
    EvidenceId,
    FactId,
    HypothesisId,
    MetricObservationId,
    TraceId,
)
from app.commerce.domain.models import CommerceModel, EvidenceRelation


class PathObservation(CommerceModel):
    summary: str = Field(min_length=1)
    semantic_status: SemanticStatus
    confidence: float = Field(ge=0.0, le=1.0)
    fact_ids: tuple[FactId, ...] = ()
    metric_observation_ids: tuple[MetricObservationId, ...] = ()

    @model_validator(mode="after")
    def require_traceable_input(self) -> Self:
        if not self.fact_ids and not self.metric_observation_ids:
            raise ValueError("PathObservation requires Fact or MetricObservation IDs")
        return self


class PathEvidenceItem(CommerceModel):
    evidence_id: EvidenceId
    summary: str = Field(min_length=1)
    relation: EvidenceRelation
    semantic_status: SemanticStatus
    confidence: float = Field(ge=0.0, le=1.0)
    hypothesis_ids: tuple[HypothesisId, ...] = ()
    fact_ids: tuple[FactId, ...] = ()
    metric_observation_ids: tuple[MetricObservationId, ...] = ()

    @model_validator(mode="after")
    def require_traceable_relation(self) -> Self:
        if not self.fact_ids and not self.metric_observation_ids:
            raise ValueError("PathEvidenceItem requires Fact or MetricObservation IDs")
        if (
            self.relation in {EvidenceRelation.SUPPORTS, EvidenceRelation.CONTRADICTS}
            and not self.hypothesis_ids
        ):
            raise ValueError("Supporting or contradicting Evidence requires Hypothesis IDs")
        return self


class PathUnknown(CommerceModel):
    question: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    missing_capabilities: tuple[str, ...] = ()


class ToolCallStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DENIED = "denied"
    TIMEOUT = "timeout"


class ToolCallTrace(CommerceModel):
    tool_name: str = Field(min_length=1)
    status: ToolCallStatus
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    response_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    latency_ms: float = Field(ge=0)
    error_code: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def keep_status_and_audit_consistent(self) -> Self:
        if self.status is ToolCallStatus.SUCCEEDED:
            if self.response_sha256 is None:
                raise ValueError("Successful ToolCallTrace requires response_sha256")
            if self.error_code is not None:
                raise ValueError("Successful ToolCallTrace cannot carry error_code")
        elif self.error_code is None:
            raise ValueError("Unsuccessful ToolCallTrace requires error_code")
        return self


class PathCost(CommerceModel):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    latency_ms: float = Field(ge=0)
    tool_call_count: int = Field(ge=0)


class ModelExecutionTrace(CommerceModel):
    provider_request_id: str = Field(min_length=1)
    actual_model_identity: str = Field(min_length=1)
    retry_count: int = Field(ge=0)
    stop_reason: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    context_version: str = Field(min_length=1)


class PathResult(CommerceModel):
    schema_version: str = "commerce.path_result@1.0.0"
    path_type: PathType
    observations: tuple[PathObservation, ...] = ()
    evidence: tuple[PathEvidenceItem, ...] = ()
    supported_hypothesis_ids: tuple[HypothesisId, ...] = ()
    contradicted_hypothesis_ids: tuple[HypothesisId, ...] = ()
    unknowns: tuple[PathUnknown, ...] = ()
    suggested_next_paths: tuple[PathType, ...] = ()
    tool_calls: tuple[ToolCallTrace, ...] = ()
    cost: PathCost
    trace_id: TraceId
    model_assignment: ModelAssignment
    model_execution: ModelExecutionTrace
    skill_version: str = Field(min_length=1)
    context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def enforce_evidence_chain(self) -> Self:
        if not self.evidence and not self.unknowns:
            raise ValueError("PathResult requires Evidence or explicit Unknowns")
        if self.model_assignment.role is not ModelRole.PATH:
            raise ValueError("PathResult model assignment must belong to the Path role")
        if self.cost.tool_call_count != len(self.tool_calls):
            raise ValueError("PathCost tool_call_count must match ToolCallTrace count")

        evidence_ids = [item.evidence_id for item in self.evidence]
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("PathResult Evidence IDs must be unique")

        supported = set(self.supported_hypothesis_ids)
        contradicted = set(self.contradicted_hypothesis_ids)
        if supported & contradicted:
            raise ValueError("A Hypothesis cannot be both supported and contradicted")

        evidence_supported = {
            hypothesis_id
            for item in self.evidence
            if item.relation is EvidenceRelation.SUPPORTS
            for hypothesis_id in item.hypothesis_ids
        }
        evidence_contradicted = {
            hypothesis_id
            for item in self.evidence
            if item.relation is EvidenceRelation.CONTRADICTS
            for hypothesis_id in item.hypothesis_ids
        }
        if supported != evidence_supported:
            raise ValueError(
                "Supported Hypothesis IDs must exactly match supporting Evidence"
            )
        if contradicted != evidence_contradicted:
            raise ValueError(
                "Contradicted Hypothesis IDs must exactly match contradicting Evidence"
            )
        if len(set(self.suggested_next_paths)) != len(self.suggested_next_paths):
            raise ValueError("Suggested next Path values must be unique")
        return self
