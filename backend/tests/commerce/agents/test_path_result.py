"""Structured PathResult evidence, unknown, cost, and trace contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.commerce.agents.contracts import ModelProfile, PathType
from app.commerce.agents.model_router import (
    ModelAssignment,
    ModelEffort,
    ModelRole,
    ModelRouteReasonCode,
)
from app.commerce.agents.path_result import (
    ModelExecutionTrace,
    PathCost,
    PathEvidenceItem,
    PathObservation,
    PathResult,
    PathUnknown,
    ToolCallStatus,
    ToolCallTrace,
)
from app.commerce.domain.enums import SemanticStatus
from app.commerce.domain.ids import (
    EvidenceId,
    HypothesisId,
    MetricObservationId,
    TraceId,
)
from app.commerce.domain.models import EvidenceRelation


def _assignment() -> ModelAssignment:
    return ModelAssignment(
        role=ModelRole.PATH,
        base_profile=ModelProfile.BALANCED_TOOL_USER,
        profile=ModelProfile.BALANCED_TOOL_USER,
        model_alias="deepseek-reasoner",
        effort=ModelEffort.MEDIUM,
        max_output_tokens=4_000,
        timeout_seconds=120,
        reason_codes=frozenset({ModelRouteReasonCode.PROFILE_BINDING}),
        escalation_count=0,
    )


def _execution() -> ModelExecutionTrace:
    return ModelExecutionTrace(
        provider_request_id="provider-request-1",
        actual_model_identity="deepseek-v4-flash",
        retry_count=0,
        stop_reason="stop",
        prompt_version="commerce.fulfillment@1.0.0",
        context_version="commerce-context@1.0.0",
    )


def test_path_result_requires_traceable_structured_evidence_and_call_audit():
    hypothesis_id = HypothesisId.new()
    metric_id = MetricObservationId.new()
    tool_call = ToolCallTrace(
        tool_name="metric_query",
        status=ToolCallStatus.SUCCEEDED,
        request_sha256="a" * 64,
        response_sha256="b" * 64,
        latency_ms=25,
    )

    result = PathResult(
        path_type=PathType.FULFILLMENT,
        observations=(
            PathObservation(
                summary="Transit time increased in the current window",
                semantic_status=SemanticStatus.DERIVED,
                confidence=0.93,
                metric_observation_ids=(metric_id,),
            ),
        ),
        evidence=(
            PathEvidenceItem(
                evidence_id=EvidenceId.new(),
                summary="Transit deterioration supports the delivery-chain hypothesis",
                relation=EvidenceRelation.SUPPORTS,
                semantic_status=SemanticStatus.DERIVED,
                confidence=0.9,
                hypothesis_ids=(hypothesis_id,),
                metric_observation_ids=(metric_id,),
            ),
        ),
        supported_hypothesis_ids=(hypothesis_id,),
        unknowns=(
            PathUnknown(
                question="Carrier scan detail is unavailable",
                reason="The uploaded dataset has no carrier event table",
            ),
        ),
        suggested_next_paths=(PathType.SELLER_PEER,),
        tool_calls=(tool_call,),
        cost=PathCost(
            input_tokens=300,
            output_tokens=120,
            latency_ms=900,
            tool_call_count=1,
        ),
        trace_id=TraceId.new(),
        model_assignment=_assignment(),
        model_execution=_execution(),
        skill_version="commerce.fulfillment-investigation@1.0.0",
        context_sha256="c" * 64,
    )

    assert result.supported_hypothesis_ids == (hypothesis_id,)
    assert result.evidence[0].metric_observation_ids == (metric_id,)
    assert result.model_execution.actual_model_identity == "deepseek-v4-flash"


def test_path_evidence_rejects_untraceable_inputs():
    with pytest.raises(ValidationError, match="Fact or MetricObservation"):
        PathEvidenceItem(
            evidence_id=EvidenceId.new(),
            summary="Unsupported narrative",
            relation=EvidenceRelation.CONTEXT,
            semantic_status=SemanticStatus.HYPOTHESIS,
            confidence=0.4,
        )


def test_path_result_rejects_supported_hypothesis_without_supporting_evidence():
    with pytest.raises(ValidationError, match="Supported Hypothesis IDs"):
        PathResult(
            path_type=PathType.FULFILLMENT,
            supported_hypothesis_ids=(HypothesisId.new(),),
            unknowns=(
                PathUnknown(
                    question="What changed?",
                    reason="No traceable evidence was returned",
                ),
            ),
            cost=PathCost(
                input_tokens=20,
                output_tokens=10,
                latency_ms=100,
                tool_call_count=0,
            ),
            trace_id=TraceId.new(),
            model_assignment=_assignment(),
            model_execution=_execution(),
            skill_version="commerce.fulfillment-investigation@1.0.0",
            context_sha256="d" * 64,
        )


def test_path_result_rejects_hypothesis_marked_supported_and_contradicted():
    hypothesis_id = HypothesisId.new()
    metric_id = MetricObservationId.new()
    common = {
        "semantic_status": SemanticStatus.DERIVED,
        "confidence": 0.8,
        "hypothesis_ids": (hypothesis_id,),
        "metric_observation_ids": (metric_id,),
    }

    with pytest.raises(ValidationError, match="both supported and contradicted"):
        PathResult(
            path_type=PathType.FULFILLMENT,
            evidence=(
                PathEvidenceItem(
                    evidence_id=EvidenceId.new(),
                    summary="Supporting metric",
                    relation=EvidenceRelation.SUPPORTS,
                    **common,
                ),
                PathEvidenceItem(
                    evidence_id=EvidenceId.new(),
                    summary="Contradicting metric",
                    relation=EvidenceRelation.CONTRADICTS,
                    **common,
                ),
            ),
            supported_hypothesis_ids=(hypothesis_id,),
            contradicted_hypothesis_ids=(hypothesis_id,),
            cost=PathCost(
                input_tokens=20,
                output_tokens=10,
                latency_ms=100,
                tool_call_count=0,
            ),
            trace_id=TraceId.new(),
            model_assignment=_assignment(),
            model_execution=_execution(),
            skill_version="commerce.fulfillment-investigation@1.0.0",
            context_sha256="e" * 64,
        )


def test_path_result_rejects_cost_mismatch_and_raw_tool_payloads():
    with pytest.raises(ValidationError):
        ToolCallTrace(
            tool_name="metric_query",
            status=ToolCallStatus.SUCCEEDED,
            request_sha256="a" * 64,
            response_sha256="b" * 64,
            latency_ms=25,
            raw_response={"secret": "must not enter trace"},
        )

    with pytest.raises(ValidationError, match="tool_call_count"):
        PathResult(
            path_type=PathType.FULFILLMENT,
            unknowns=(
                PathUnknown(
                    question="What changed?",
                    reason="No usable tool response",
                ),
            ),
            tool_calls=(
                ToolCallTrace(
                    tool_name="metric_query",
                    status=ToolCallStatus.FAILED,
                    request_sha256="a" * 64,
                    latency_ms=25,
                    error_code="permanent_tool_error",
                ),
            ),
            cost=PathCost(
                input_tokens=20,
                output_tokens=10,
                latency_ms=100,
                tool_call_count=0,
            ),
            trace_id=TraceId.new(),
            model_assignment=_assignment(),
            model_execution=_execution(),
            skill_version="commerce.fulfillment-investigation@1.0.0",
            context_sha256="f" * 64,
        )
