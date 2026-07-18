"""Deterministic context and PathAgentSpec contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.commerce.agents.contracts import (
    AgentBudgetLimit,
    CaseHeader,
    ContextManifest,
    EvidenceDigest,
    LeadContextPacket,
    ModelProfile,
    PathContextPacket,
    PathType,
    VerificationPacket,
    default_path_agent_specs,
)
from app.commerce.data.capabilities import CapabilityName
from app.commerce.domain.enums import CaseSeverity, CaseStatus, SemanticStatus
from app.commerce.domain.ids import CaseId, EvidenceId, FactId, WorkspaceId


def _manifest(case_id: CaseId) -> ContextManifest:
    return ContextManifest(
        context_version="commerce-context@1.0.0",
        case_id=case_id,
        context_sha256="a" * 64,
        estimated_tokens=200,
    )


def _header(workspace_id: WorkspaceId, case_id: CaseId) -> CaseHeader:
    return CaseHeader(
        workspace_id=workspace_id,
        case_id=case_id,
        title="Delivery anomaly",
        severity=CaseSeverity.HIGH,
        status=CaseStatus.INVESTIGATING,
        version=3,
    )


def test_context_packets_reject_hidden_label_metadata_and_reasoning_history():
    workspace_id = WorkspaceId.new()
    case_id = CaseId.new()
    common = {
        "case": _header(workspace_id, case_id),
        "goal": "Explain the delivery anomaly",
        "manifest": _manifest(case_id),
        "budget": AgentBudgetLimit(),
    }

    with pytest.raises(ValidationError, match="hidden evaluation label"):
        LeadContextPacket(
            **common,
            metadata={"expected_behavior": "hidden gold answer"},
        )
    with pytest.raises(ValidationError):
        VerificationPacket(
            **common,
            claims=("Transit time worsened",),
            capability_boundaries=("profit not observed",),
            lead_reasoning="private chain of thought",
        )


def test_path_packet_keeps_minimum_evidence_tools_and_forbidden_claims():
    workspace_id = WorkspaceId.new()
    case_id = CaseId.new()
    evidence_id = EvidenceId.new()

    packet = PathContextPacket(
        case=_header(workspace_id, case_id),
        goal="Determine whether transit or handling worsened",
        path_type=PathType.FULFILLMENT,
        required_capabilities=frozenset({CapabilityName.FULFILLMENT_DIAGNOSIS}),
        evidence=(
            EvidenceDigest(
                evidence_id=evidence_id,
                summary="Late delivery rate increased",
                semantic_status=SemanticStatus.DERIVED,
                confidence=0.9,
                fact_ids=(FactId.new(),),
            ),
        ),
        allowed_tools=frozenset({"metric_query", "source_fact_lookup"}),
        forbidden_claims=("Do not attribute correlation to seller causality",),
        output_schema="commerce.path_result@1.0.0",
        manifest=_manifest(case_id),
        budget=AgentBudgetLimit(max_tool_calls=4, max_tokens=2000),
    )

    assert packet.path_type is PathType.FULFILLMENT
    assert packet.evidence[0].evidence_id == evidence_id
    assert packet.allowed_tools == frozenset({"metric_query", "source_fact_lookup"})


def test_default_path_specs_are_three_versioned_bounded_specs():
    specs = default_path_agent_specs()

    assert {spec.path_type for spec in specs} == {
        PathType.FULFILLMENT,
        PathType.SELLER_PEER,
        PathType.REVIEW_EXPERIENCE,
    }
    assert all(spec.skill_version for spec in specs)
    assert all(spec.allowed_tools for spec in specs)
    assert all(spec.output_schema == "commerce.path_result@1.0.0" for spec in specs)
    assert all(spec.default_model_profile is ModelProfile.BALANCED_TOOL_USER for spec in specs)
