"""Versioned application-layer contracts for Commerce Agent orchestration."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Self, cast

from pydantic import Field, model_validator

from app.commerce.data.capabilities import (
    CapabilityName,
    CapabilityProfile,
    CapabilityStatus,
)
from app.commerce.domain.enums import (
    CaseSeverity,
    CaseStatus,
    PathType,
    SemanticStatus,
)
from app.commerce.domain.ids import (
    AgentTaskId,
    AnomalyId,
    CaseId,
    DatasetId,
    EntityId,
    EvidenceId,
    FactId,
    HypothesisId,
    MetricObservationId,
    RunId,
    WorkspaceId,
)
from app.commerce.domain.models import CommerceModel
from app.commerce.metrics.anomaly import AnomalyDirection, AnomalySeverity
from app.commerce.metrics.registry import MetricName, MetricWindow, PeerCohortPolicy


class CaseTriggerType(StrEnum):
    DETECTED_ANOMALY = "detected_anomaly"
    EXPLICIT_USER = "explicit_user_request"


class CaseTriggerDigest(CommerceModel):
    """Persisted routing intent without storing the user's raw prompt."""

    trigger_type: CaseTriggerType
    requested_paths: tuple[PathType, ...] = ()
    peer_policy: PeerCohortPolicy | None = None

    @model_validator(mode="after")
    def validate_trigger(self) -> Self:
        if len(self.requested_paths) != len(set(self.requested_paths)):
            raise ValueError("Case trigger requested Paths must be unique")
        if self.trigger_type is CaseTriggerType.EXPLICIT_USER:
            if not self.requested_paths:
                raise ValueError(
                    "Explicit user Case trigger requires at least one requested Path"
                )
        elif self.requested_paths or self.peer_policy is not None:
            raise ValueError(
                "Detected anomaly Case trigger cannot carry explicit Path settings"
            )
        if PathType.SELLER_PEER in self.requested_paths and self.peer_policy is None:
            raise ValueError(
                "seller_peer requested Path requires an outcome-agnostic peer_policy"
            )
        if (
            self.peer_policy is not None
            and PathType.SELLER_PEER not in self.requested_paths
        ):
            raise ValueError("peer_policy is only valid for the seller_peer Path")
        return self


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


class MetricObservationDigest(CommerceModel):
    """Compact metric context; source rows stay queryable by Tool instead of in prompts."""

    metric_observation_id: MetricObservationId
    metric_name: str = Field(min_length=1)
    semantic_status: SemanticStatus
    value: int | float | Decimal | None = None
    unit: str | None = Field(default=None, min_length=1)
    formula_version: str | None = Field(default=None, min_length=1)
    window_start: datetime | None = None
    window_end: datetime | None = None
    sample_size: int | None = Field(default=None, ge=0)
    numerator: int | Decimal | None = None
    denominator: int | Decimal | None = None
    source_fact_count: int = Field(ge=0)
    unknown_reason: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def keep_metric_window_complete(self) -> Self:
        if (self.window_start is None) != (self.window_end is None):
            raise ValueError("Metric digest window requires both start and end")
        return self


class AnomalyDigest(CommerceModel):
    anomaly_id: AnomalyId
    metric_name: MetricName
    baseline_observation_id: MetricObservationId
    current_observation_id: MetricObservationId
    baseline_value: Decimal
    current_value: Decimal
    absolute_change: Decimal
    relative_change: Decimal | None
    direction: AnomalyDirection
    severity: AnomalySeverity
    confidence: float = Field(ge=0.0, le=1.0)
    baseline_sample_size: int = Field(ge=0)
    current_sample_size: int = Field(ge=0)
    sample_adequate: bool
    reason: str = Field(min_length=1)


class CaseAnalysisDigest(CommerceModel):
    """Reproducible deterministic analysis slice supplied to the Lead Agent."""

    dataset_id: DatasetId
    seller_entity_id: EntityId
    seller_external_key: str = Field(min_length=1)
    baseline_window: MetricWindow
    current_window: MetricWindow
    baseline_metrics: tuple[MetricObservationDigest, ...] = ()
    current_metrics: tuple[MetricObservationDigest, ...] = ()
    supplemental_metrics: tuple[MetricObservationDigest, ...] = ()
    anomalies: tuple[AnomalyDigest, ...] = ()
    trigger: CaseTriggerDigest = Field(
        default_factory=lambda: CaseTriggerDigest(
            trigger_type=CaseTriggerType.DETECTED_ANOMALY
        )
    )
    @model_validator(mode="after")
    def keep_analysis_references_unique(self) -> Self:
        metric_ids = tuple(
            item.metric_observation_id
            for item in (
                *self.baseline_metrics,
                *self.current_metrics,
                *self.supplemental_metrics,
            )
        )
        if not metric_ids:
            raise ValueError("Case analysis requires at least one MetricObservation")
        if len(metric_ids) != len(set(metric_ids)):
            raise ValueError("Analysis metric observation IDs must be unique")
        anomaly_ids = tuple(item.anomaly_id for item in self.anomalies)
        if len(anomaly_ids) != len(set(anomaly_ids)):
            raise ValueError("Analysis Anomaly IDs must be unique")
        return self


class ContextManifest(CommerceModel):
    context_version: str = Field(min_length=1)
    workspace_id: WorkspaceId
    case_id: CaseId
    dataset_id: DatasetId
    source_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    estimated_tokens: int = Field(ge=0)
    included_evidence_ids: tuple[EvidenceId, ...] = ()
    included_fact_ids: tuple[FactId, ...] = ()
    included_metric_observation_ids: tuple[MetricObservationId, ...] = ()
    included_anomaly_ids: tuple[AnomalyId, ...] = ()
    redactions: tuple[str, ...] = ()

    @model_validator(mode="after")
    def keep_manifest_references_unique(self) -> Self:
        for label, values in (
            ("Evidence", self.included_evidence_ids),
            ("Fact", self.included_fact_ids),
            ("MetricObservation", self.included_metric_observation_ids),
            ("Anomaly", self.included_anomaly_ids),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"ContextManifest {label} IDs must be unique")
        return self


class PathEvidenceScope(CommerceModel):
    """Persistable ID-only boundary for one terminal Path execution."""

    schema_version: str = "commerce.path-evidence-scope@1.0.0"
    workspace_id: WorkspaceId
    case_id: CaseId
    run_id: RunId
    task_id: AgentTaskId
    path_type: PathType
    dataset_id: DatasetId
    context_version: str = Field(min_length=1)
    context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_ids: tuple[EvidenceId, ...] = ()
    included_fact_ids: tuple[FactId, ...] = ()
    included_metric_observation_ids: tuple[MetricObservationId, ...] = ()
    included_anomaly_ids: tuple[AnomalyId, ...] = ()

    @model_validator(mode="after")
    def keep_scope_references_unique(self) -> Self:
        for label, values in (
            ("Evidence", self.evidence_ids),
            ("Fact", self.included_fact_ids),
            ("MetricObservation", self.included_metric_observation_ids),
            ("Anomaly", self.included_anomaly_ids),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"PathEvidenceScope {label} IDs must be unique")
        return self

    @classmethod
    def from_manifest(
        cls,
        manifest: ContextManifest,
        *,
        run_id: RunId,
        task_id: AgentTaskId,
        path_type: PathType,
        evidence_ids: tuple[EvidenceId, ...],
    ) -> Self:
        return cls(
            workspace_id=manifest.workspace_id,
            case_id=manifest.case_id,
            run_id=run_id,
            task_id=task_id,
            path_type=path_type,
            dataset_id=manifest.dataset_id,
            context_version=manifest.context_version,
            context_sha256=manifest.context_sha256,
            source_artifact_sha256=manifest.source_artifact_sha256,
            evidence_ids=evidence_ids,
            included_fact_ids=manifest.included_fact_ids,
            included_metric_observation_ids=(
                manifest.included_metric_observation_ids
            ),
            included_anomaly_ids=manifest.included_anomaly_ids,
        )


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


def hidden_evaluation_label_paths(value: Any, *, path: str = "$") -> tuple[str, ...]:
    """Return nested JSON paths whose keys would leak hidden evaluation answers."""

    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if str(key).casefold() in _HIDDEN_LABEL_KEYS:
                found.append(child_path)
            found.extend(hidden_evaluation_label_paths(child, path=child_path))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            found.extend(
                hidden_evaluation_label_paths(child, path=f"{path}[{index}]")
            )
    return tuple(found)


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
        if self.case.workspace_id != self.manifest.workspace_id:
            raise ValueError("ContextManifest Workspace must match packet Case")
        leaked = hidden_evaluation_label_paths(self.metadata, path="$.metadata")
        if leaked:
            raise ValueError(
                "Context metadata contains hidden evaluation label keys: "
                f"{', '.join(leaked)}"
            )
        return self


class LeadContextPacket(ContextPacket):
    capabilities: frozenset[CapabilityName] = frozenset()
    capability_profile: CapabilityProfile
    analysis: CaseAnalysisDigest
    evidence: tuple[EvidenceDigest, ...] = ()
    hypotheses: tuple[HypothesisDigest, ...] = ()

    @model_validator(mode="after")
    def match_analysis_identity_and_capabilities(self) -> Self:
        if self.capability_profile.workspace_id != self.case.workspace_id:
            raise ValueError("Capability Profile Workspace must match packet Case")
        if self.capability_profile.dataset_id != self.manifest.dataset_id:
            raise ValueError("Capability Profile Dataset must match ContextManifest")
        if self.analysis.dataset_id != self.manifest.dataset_id:
            raise ValueError("Analysis Dataset must match ContextManifest")
        if not self.analysis.baseline_metrics or not self.analysis.current_metrics:
            raise ValueError(
                "Lead context requires baseline and current deterministic metrics"
            )
        routable = frozenset(
            assessment.name
            for assessment in self.capability_profile.capabilities
            if assessment.status
            in {CapabilityStatus.AVAILABLE, CapabilityStatus.PARTIAL}
        )
        if self.capabilities != routable:
            raise ValueError("Lead capabilities must match routable Capability Profile")
        return self


class PathContextPacket(ContextPacket):
    path_type: PathType
    required_capabilities: frozenset[CapabilityName] = Field(min_length=1)
    capability_profile: CapabilityProfile
    analysis: CaseAnalysisDigest
    evidence: tuple[EvidenceDigest, ...] = ()
    allowed_tools: frozenset[str] = Field(min_length=1)
    forbidden_claims: tuple[str, ...] = ()
    output_schema: str = Field(min_length=1)

    @model_validator(mode="after")
    def require_available_path_capabilities(self) -> Self:
        if self.capability_profile.workspace_id != self.case.workspace_id:
            raise ValueError("Path Capability Profile Workspace must match packet Case")
        if self.capability_profile.dataset_id != self.manifest.dataset_id:
            raise ValueError("Path Capability Profile Dataset must match ContextManifest")
        if self.analysis.dataset_id != self.manifest.dataset_id:
            raise ValueError("Path Analysis Dataset must match ContextManifest")
        if not self.analysis.baseline_metrics or not self.analysis.current_metrics:
            raise ValueError(
                "Path context requires baseline and current deterministic metrics"
            )
        unavailable = tuple(
            name
            for name in self.required_capabilities
            if self.capability_profile.capability(name).status
            is CapabilityStatus.UNAVAILABLE
        )
        if unavailable:
            names = ", ".join(name.value for name in unavailable)
            raise ValueError(f"Path required capabilities are unavailable: {names}")
        return self


def bind_context_to_case[ContextPacketT: ContextPacket](
    packet: ContextPacketT,
    case: CaseHeader,
    *,
    source_artifact_sha256: str | None = None,
) -> ContextPacketT:
    """Bind a prepared Path packet to one persisted Case lineage and rehash it."""

    if case.workspace_id != packet.case.workspace_id:
        raise ValueError("Context can only bind to a Case in the same Workspace")
    manifest = packet.manifest.model_copy(
        update={
            "workspace_id": case.workspace_id,
            "case_id": case.case_id,
            "source_artifact_sha256": (
                source_artifact_sha256
                or packet.manifest.source_artifact_sha256
            ),
            "context_sha256": "0" * 64,
            "estimated_tokens": 0,
        }
    )
    rebound = type(packet).model_validate(
        packet.model_copy(
            update={"case": case, "manifest": manifest}
        ).model_dump(mode="python")
    )
    estimated_tokens = estimate_context_tokens(rebound)
    if estimated_tokens > rebound.budget.max_tokens:
        raise ValueError(
            f"Rebound Context {estimated_tokens} exceeds token budget"
        )
    final = rebound.model_copy(
        update={
            "manifest": rebound.manifest.model_copy(
                update={
                    "estimated_tokens": estimated_tokens,
                    "context_sha256": canonical_context_sha256(rebound),
                }
            )
        }
    )
    return cast(ContextPacketT, type(packet).model_validate(final.model_dump(mode="python")))


class VerificationReferenceKind(StrEnum):
    FACT = "fact"
    METRIC_OBSERVATION = "metric_observation"


class VerificationClaimInput(CommerceModel):
    """One Lead claim bound to its original persisted supporting Evidence."""

    schema_version: str = "commerce.verification-claim-input@1.0.0"
    claim_index: int = Field(ge=0)
    statement: str = Field(min_length=1)
    evidence_ids: tuple[EvidenceId, ...] = Field(min_length=1)
    required_reference_kinds: frozenset[VerificationReferenceKind] = Field(
        min_length=1
    )

    @model_validator(mode="after")
    def keep_evidence_unique(self) -> Self:
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("Verification Claim Evidence IDs must be unique")
        return self


class VerificationPacket(ContextPacket):
    claims: tuple[VerificationClaimInput, ...] = Field(min_length=1)
    capability_profile: CapabilityProfile
    analysis: CaseAnalysisDigest
    evidence: tuple[EvidenceDigest, ...] = ()
    capability_boundaries: tuple[str, ...] = ()
    policy_constraints: tuple[str, ...] = ()

    @model_validator(mode="after")
    def match_verification_context_identity(self) -> Self:
        if self.capability_profile.workspace_id != self.case.workspace_id:
            raise ValueError("Verification Capability Workspace must match Case")
        if self.capability_profile.dataset_id != self.manifest.dataset_id:
            raise ValueError("Verification Capability Dataset must match Manifest")
        if self.analysis.dataset_id != self.manifest.dataset_id:
            raise ValueError("Verification Analysis Dataset must match Manifest")

        indices = tuple(item.claim_index for item in self.claims)
        if indices != tuple(range(len(self.claims))):
            raise ValueError(
                "Verification Claim indices must be unique, ordered, and contiguous"
            )
        evidence_by_id = {item.evidence_id: item for item in self.evidence}
        if len(evidence_by_id) != len(self.evidence):
            raise ValueError("Verification Evidence IDs must be unique")
        manifest_evidence_ids = set(self.manifest.included_evidence_ids)
        for claim in self.claims:
            missing = set(claim.evidence_ids) - set(evidence_by_id)
            if missing or not set(claim.evidence_ids).issubset(
                manifest_evidence_ids
            ):
                raise ValueError(
                    "Verification Claim references Evidence outside fresh context"
                )
            referenced = tuple(evidence_by_id[value] for value in claim.evidence_ids)
            expected_kinds = frozenset(
                kind
                for kind, present in (
                    (
                        VerificationReferenceKind.FACT,
                        any(item.fact_ids for item in referenced),
                    ),
                    (
                        VerificationReferenceKind.METRIC_OBSERVATION,
                        any(item.metric_observation_ids for item in referenced),
                    ),
                )
                if present
            )
            if claim.required_reference_kinds != expected_kinds:
                raise ValueError(
                    "Verification Claim reference requirements must be derived "
                    "from its supporting Evidence"
                )
        return self


def canonical_context_bytes(packet: ContextPacket) -> bytes:
    """Canonical packet content excluding self-referential hash/size fields."""

    payload = packet.model_dump(mode="python")
    manifest = payload["manifest"]
    manifest.pop("context_sha256", None)
    manifest.pop("estimated_tokens", None)
    return json.dumps(
        _canonical_json_value(payload),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _canonical_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _canonical_json_value(child) for key, child in value.items()}
    if isinstance(value, (set, frozenset)):
        children = [_canonical_json_value(child) for child in value]
        return sorted(
            children,
            key=lambda child: json.dumps(
                child,
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ),
        )
    if isinstance(value, (list, tuple)):
        return [_canonical_json_value(child) for child in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, StrEnum):
        return value.value
    return value


def canonical_context_sha256(packet: ContextPacket) -> str:
    return hashlib.sha256(canonical_context_bytes(packet)).hexdigest()


def estimate_context_tokens(packet: ContextPacket) -> int:
    """Conservative deterministic estimate used before provider tokenization."""

    return math.ceil(len(canonical_context_bytes(packet)) / 4)


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
                {
                    "metric_query",
                    "peer_cohort_query",
                    "geographic_order_count_query",
                    "source_fact_lookup",
                }
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
