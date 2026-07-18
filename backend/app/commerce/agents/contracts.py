"""Versioned application-layer contracts for Commerce Agent orchestration."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from app.commerce.data.capabilities import CapabilityName
from app.commerce.domain.enums import CaseSeverity, CaseStatus, SemanticStatus
from app.commerce.domain.ids import (
    CaseId,
    EvidenceId,
    FactId,
    HypothesisId,
    MetricObservationId,
    WorkspaceId,
)
from app.commerce.domain.models import CommerceModel


class PathType(StrEnum):
    FULFILLMENT = "fulfillment"
    SELLER_PEER = "seller_peer"
    REVIEW_EXPERIENCE = "review_experience"


class ModelProfile(StrEnum):
    FAST_STRUCTURED = "fast_structured"
    BALANCED_TOOL_USER = "balanced_tool_user"
    STRONG_SYNTHESIZER = "strong_synthesizer"
    STRONG_VERIFIER = "strong_verifier"
    OFFLINE_CANDIDATE_BUILDER = "offline_candidate_builder"


class AgentBudgetLimit(CommerceModel):
    max_iterations: int = Field(default=8, ge=1)
    max_tool_calls: int = Field(default=20, ge=0)
    max_path_agents: int = Field(default=3, ge=0, le=3)
    max_tokens: int = Field(default=16_000, ge=1)
    max_wall_time_seconds: float = Field(default=300.0, gt=0)
    max_model_escalations: int = Field(default=1, ge=0)
    max_verification_repairs: int = Field(default=2, ge=0)
    max_repeated_actions: int = Field(default=2, ge=0)
    max_consecutive_no_new_evidence: int = Field(default=2, ge=1)


class CaseHeader(CommerceModel):
    workspace_id: WorkspaceId
    case_id: CaseId
    title: str = Field(min_length=1)
    severity: CaseSeverity
    status: CaseStatus
    version: int = Field(ge=1)


class EvidenceDigest(CommerceModel):
    evidence_id: EvidenceId
    summary: str = Field(min_length=1)
    semantic_status: SemanticStatus
    confidence: float = Field(ge=0.0, le=1.0)
    fact_ids: tuple[FactId, ...] = ()
    metric_observation_ids: tuple[MetricObservationId, ...] = ()

    @model_validator(mode="after")
    def require_traceable_input(self) -> Self:
        if not self.fact_ids and not self.metric_observation_ids:
            raise ValueError("EvidenceDigest requires Fact or MetricObservation IDs")
        return self


class HypothesisDigest(CommerceModel):
    hypothesis_id: HypothesisId
    statement: str = Field(min_length=1)
    status: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ids: tuple[EvidenceId, ...] = ()


class ContextManifest(CommerceModel):
    context_version: str = Field(min_length=1)
    case_id: CaseId
    context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    estimated_tokens: int = Field(ge=0)
    included_evidence_ids: tuple[EvidenceId, ...] = ()
    included_fact_ids: tuple[FactId, ...] = ()
    included_metric_observation_ids: tuple[MetricObservationId, ...] = ()
    redactions: tuple[str, ...] = ()


_HIDDEN_LABEL_KEYS = frozenset(
    {
        "expected_behavior",
        "expected_facts",
        "hidden_labels",
        "gold_answer",
        "gold_label",
        "evaluation_answer",
    }
)


class ContextPacket(CommerceModel):
    schema_version: str = "1.0"
    case: CaseHeader
    goal: str = Field(min_length=1)
    manifest: ContextManifest
    budget: AgentBudgetLimit
    metadata: dict[str, str | int | float | bool] = Field(default_factory=dict)

    @model_validator(mode="after")
    def guard_context_boundary(self) -> Self:
        if self.case.case_id != self.manifest.case_id:
            raise ValueError("ContextManifest Case must match packet Case")
        leaked = sorted(key for key in self.metadata if key.casefold() in _HIDDEN_LABEL_KEYS)
        if leaked:
            raise ValueError(
                f"Context metadata contains hidden evaluation label keys: {', '.join(leaked)}"
            )
        return self


class LeadContextPacket(ContextPacket):
    capabilities: frozenset[CapabilityName] = frozenset()
    evidence: tuple[EvidenceDigest, ...] = ()
    hypotheses: tuple[HypothesisDigest, ...] = ()


class PathContextPacket(ContextPacket):
    path_type: PathType
    required_capabilities: frozenset[CapabilityName] = Field(min_length=1)
    evidence: tuple[EvidenceDigest, ...] = ()
    allowed_tools: frozenset[str] = Field(min_length=1)
    forbidden_claims: tuple[str, ...] = ()
    output_schema: str = Field(min_length=1)


class VerificationPacket(ContextPacket):
    claims: tuple[str, ...] = Field(min_length=1)
    evidence: tuple[EvidenceDigest, ...] = ()
    capability_boundaries: tuple[str, ...] = ()
    policy_constraints: tuple[str, ...] = ()


class PathAgentSpec(CommerceModel):
    path_type: PathType
    required_capabilities: frozenset[CapabilityName] = Field(min_length=1)
    optional_capabilities: frozenset[CapabilityName] = frozenset()
    supported_case_types: frozenset[str] = Field(min_length=1)
    allowed_tools: frozenset[str] = Field(min_length=1)
    skill_id: str = Field(min_length=1)
    skill_version: str = Field(min_length=1)
    output_schema: str = Field(min_length=1)
    default_model_profile: ModelProfile
    default_budget: AgentBudgetLimit
    forbidden_claims: tuple[str, ...] = ()


def default_path_agent_specs() -> tuple[PathAgentSpec, ...]:
    common_budget = AgentBudgetLimit(
        max_iterations=4,
        max_tool_calls=8,
        max_path_agents=0,
        max_tokens=6_000,
        max_wall_time_seconds=120,
        max_model_escalations=0,
        max_verification_repairs=1,
    )
    return (
        PathAgentSpec(
            path_type=PathType.FULFILLMENT,
            required_capabilities=frozenset(
                {CapabilityName.FULFILLMENT_DIAGNOSIS}
            ),
            supported_case_types=frozenset({"delivery", "fulfillment"}),
            allowed_tools=frozenset({"metric_query", "source_fact_lookup"}),
            skill_id="commerce.fulfillment-investigation",
            skill_version="1.0.0",
            output_schema="commerce.path_result@1.0.0",
            default_model_profile=ModelProfile.BALANCED_TOOL_USER,
            default_budget=common_budget,
            forbidden_claims=("Do not infer seller causality from correlation",),
        ),
        PathAgentSpec(
            path_type=PathType.SELLER_PEER,
            required_capabilities=frozenset(
                {CapabilityName.SELLER_PEER_COMPARISON}
            ),
            supported_case_types=frozenset({"seller_peer", "delivery"}),
            allowed_tools=frozenset(
                {"metric_query", "peer_cohort_query", "source_fact_lookup"}
            ),
            skill_id="commerce.seller-peer-investigation",
            skill_version="1.0.0",
            output_schema="commerce.path_result@1.0.0",
            default_model_profile=ModelProfile.BALANCED_TOOL_USER,
            default_budget=common_budget,
            forbidden_claims=("Peer gap is diagnostic and does not prove causality",),
        ),
        PathAgentSpec(
            path_type=PathType.REVIEW_EXPERIENCE,
            required_capabilities=frozenset(
                {CapabilityName.REVIEW_EXPERIENCE}
            ),
            supported_case_types=frozenset({"review", "product_experience"}),
            allowed_tools=frozenset(
                {"metric_query", "review_signal_query", "source_fact_lookup"}
            ),
            skill_id="commerce.review-experience-investigation",
            skill_version="1.0.0",
            output_schema="commerce.path_result@1.0.0",
            default_model_profile=ModelProfile.BALANCED_TOOL_USER,
            default_budget=common_budget,
            forbidden_claims=(
                "Review text cannot confirm fraud, counterfeiting, or illegality",
            ),
        ),
    )
