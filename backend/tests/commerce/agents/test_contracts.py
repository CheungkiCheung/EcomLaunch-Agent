"""Deterministic context and PathAgentSpec contracts."""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.commerce.agents.contracts import (
    AgentBudgetLimit,
    AnomalyDigest,
    CaseAnalysisDigest,
    CaseHeader,
    ContextManifest,
    EvidenceDigest,
    LeadContextPacket,
    MetricObservationDigest,
    ModelProfile,
    PathContextPacket,
    PathType,
    VerificationClaimInput,
    VerificationPacket,
    VerificationReferenceKind,
    canonical_context_bytes,
    default_path_agent_specs,
)
from app.commerce.agents.verification import (
    VerificationEngine,
    verification_max_output_tokens,
)
from app.commerce.data.capabilities import (
    CapabilityAssessment,
    CapabilityName,
    CapabilityProfile,
    CapabilityReasonCode,
    CapabilityStatus,
)
from app.commerce.domain.enums import CaseSeverity, CaseStatus, SemanticStatus
from app.commerce.domain.ids import (
    AnomalyId,
    CaseId,
    DatasetId,
    EntityId,
    EvidenceId,
    FactId,
    MetricObservationId,
    WorkspaceId,
)
from app.commerce.metrics.anomaly import AnomalyDirection, AnomalySeverity
from app.commerce.metrics.registry import MetricName, MetricWindow


def _manifest(
    workspace_id: WorkspaceId,
    case_id: CaseId,
    dataset_id: DatasetId,
) -> ContextManifest:
    return ContextManifest(
        context_version="commerce-context@1.0.0",
        workspace_id=workspace_id,
        case_id=case_id,
        dataset_id=dataset_id,
        source_artifact_sha256="b" * 64,
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


def _analysis(dataset_id: DatasetId) -> CaseAnalysisDigest:
    baseline_id = MetricObservationId.new()
    current_id = MetricObservationId.new()
    baseline_window = MetricWindow(
        start=datetime(2026, 1, 1),
        end=datetime(2026, 2, 1),
    )
    current_window = MetricWindow(
        start=datetime(2026, 2, 1),
        end=datetime(2026, 3, 1),
    )
    common_metric = {
        "metric_name": MetricName.LATE_DELIVERY_RATE.value,
        "semantic_status": SemanticStatus.DERIVED,
        "unit": "ratio",
        "formula_version": "late_delivery_rate@1.0.0",
        "sample_size": 100,
        "denominator": 100,
        "source_fact_count": 200,
    }
    return CaseAnalysisDigest(
        dataset_id=dataset_id,
        seller_entity_id=EntityId.new(),
        seller_external_key="seller-a",
        baseline_window=baseline_window,
        current_window=current_window,
        baseline_metrics=(
            MetricObservationDigest(
                metric_observation_id=baseline_id,
                value=Decimal("0.1"),
                numerator=10,
                window_start=baseline_window.start,
                window_end=baseline_window.end,
                **common_metric,
            ),
        ),
        current_metrics=(
            MetricObservationDigest(
                metric_observation_id=current_id,
                value=Decimal("0.3"),
                numerator=30,
                window_start=current_window.start,
                window_end=current_window.end,
                **common_metric,
            ),
        ),
        anomalies=(
            AnomalyDigest(
                anomaly_id=AnomalyId.new(),
                metric_name=MetricName.LATE_DELIVERY_RATE,
                baseline_observation_id=baseline_id,
                current_observation_id=current_id,
                baseline_value=Decimal("0.1"),
                current_value=Decimal("0.3"),
                absolute_change=Decimal("0.2"),
                relative_change=Decimal("2"),
                direction=AnomalyDirection.INCREASE,
                severity=AnomalySeverity.HIGH,
                confidence=0.9,
                baseline_sample_size=100,
                current_sample_size=100,
                sample_adequate=True,
                reason="late delivery rate increased",
            ),
        ),
    )


def _fulfillment_capabilities(
    workspace_id: WorkspaceId,
    dataset_id: DatasetId,
) -> CapabilityProfile:
    return CapabilityProfile(
        dataset_id=dataset_id,
        workspace_id=workspace_id,
        capabilities=(
            CapabilityAssessment(
                name=CapabilityName.FULFILLMENT_DIAGNOSIS,
                path_agent="FulfillmentPathAgent",
                status=CapabilityStatus.AVAILABLE,
                reason_codes=frozenset({CapabilityReasonCode.AVAILABLE}),
                available_fields=frozenset(),
                missing_required_fields=frozenset(),
                missing_optional_fields=frozenset(),
            ),
        ),
    )


def _verification_packet() -> tuple[
    VerificationPacket,
    EvidenceDigest,
    EvidenceDigest,
]:
    workspace_id = WorkspaceId.new()
    case_id = CaseId.new()
    dataset_id = DatasetId.new()
    analysis = _analysis(dataset_id)
    metric_ids = tuple(
        item.metric_observation_id
        for item in (*analysis.baseline_metrics, *analysis.current_metrics)
    )
    metric_evidence = EvidenceDigest(
        evidence_id=EvidenceId.new(),
        summary="Late-delivery rate increased in the current window.",
        semantic_status=SemanticStatus.DERIVED,
        confidence=0.96,
        metric_observation_ids=metric_ids,
    )
    fact_evidence = EvidenceDigest(
        evidence_id=EvidenceId.new(),
        summary="A review reports that the shipment did not arrive.",
        semantic_status=SemanticStatus.OBSERVED,
        confidence=0.72,
        fact_ids=(FactId.new(),),
    )
    manifest = _manifest(workspace_id, case_id, dataset_id).model_copy(
        update={
            "included_evidence_ids": (
                fact_evidence.evidence_id,
                metric_evidence.evidence_id,
            ),
            "included_fact_ids": fact_evidence.fact_ids,
            "included_metric_observation_ids": metric_ids,
        }
    )
    packet = VerificationPacket(
        case=_header(workspace_id, case_id),
        goal="Verify the two claims against their original supporting Evidence.",
        manifest=manifest,
        budget=AgentBudgetLimit(),
        claims=(
            VerificationClaimInput(
                claim_index=0,
                statement="A low-rating review reports non-receipt.",
                evidence_ids=(fact_evidence.evidence_id,),
                required_reference_kinds=frozenset(
                    {VerificationReferenceKind.FACT}
                ),
            ),
            VerificationClaimInput(
                claim_index=1,
                statement="Late-delivery rate increased in the current window.",
                evidence_ids=(metric_evidence.evidence_id,),
                required_reference_kinds=frozenset(
                    {VerificationReferenceKind.METRIC_OBSERVATION}
                ),
            ),
        ),
        capability_profile=_fulfillment_capabilities(workspace_id, dataset_id),
        analysis=analysis,
        evidence=(fact_evidence, metric_evidence),
    )
    return packet, fact_evidence, metric_evidence


def _valid_verification_payload(
    fact_evidence: EvidenceDigest,
    metric_evidence: EvidenceDigest,
) -> dict[str, object]:
    return {
        "claims": [
            {
                "claim_index": 0,
                "verdict": "pass",
                "issue_codes": [],
                "reason": "The supplied review Fact supports this VOC statement.",
                "evidence_ids": [str(fact_evidence.evidence_id)],
                "fact_ids": [str(fact_evidence.fact_ids[0])],
                "metric_observation_ids": [],
            },
            {
                "claim_index": 1,
                "verdict": "pass",
                "issue_codes": [],
                "reason": "The supplied deterministic Metrics support the change.",
                "evidence_ids": [str(metric_evidence.evidence_id)],
                "fact_ids": [],
                "metric_observation_ids": [
                    str(value)
                    for value in metric_evidence.metric_observation_ids
                ],
            },
        ]
    }


def test_verification_accepts_fact_and_metric_claim_references():
    packet, fact_evidence, metric_evidence = _verification_packet()

    parsed = VerificationEngine._parse(
        json.dumps(_valid_verification_payload(fact_evidence, metric_evidence)),
        packet,
    )

    assert parsed[0].evidence_ids == (fact_evidence.evidence_id,)
    assert parsed[0].fact_ids == fact_evidence.fact_ids
    assert parsed[0].metric_observation_ids == ()
    assert parsed[1].evidence_ids == (metric_evidence.evidence_id,)
    assert parsed[1].fact_ids == ()
    assert parsed[1].metric_observation_ids == (
        metric_evidence.metric_observation_ids
    )


def test_verification_derives_evidence_lineage_from_valid_source_references():
    packet, fact_evidence, metric_evidence = _verification_packet()
    payload = _valid_verification_payload(fact_evidence, metric_evidence)
    claims = payload["claims"]
    assert isinstance(claims, list)
    for claim in claims:
        assert isinstance(claim, dict)
        claim["evidence_ids"] = []

    parsed = VerificationEngine._parse(json.dumps(payload), packet)

    assert parsed[0].evidence_ids == (fact_evidence.evidence_id,)
    assert parsed[1].evidence_ids == (metric_evidence.evidence_id,)


def test_verification_derives_source_lineage_from_valid_evidence_references():
    packet, fact_evidence, metric_evidence = _verification_packet()
    payload = _valid_verification_payload(fact_evidence, metric_evidence)
    claims = payload["claims"]
    assert isinstance(claims, list)
    for claim in claims:
        assert isinstance(claim, dict)
        claim["fact_ids"] = []
        claim["metric_observation_ids"] = []

    parsed = VerificationEngine._parse(json.dumps(payload), packet)

    assert parsed[0].fact_ids == fact_evidence.fact_ids
    assert parsed[0].metric_observation_ids == ()
    assert parsed[1].fact_ids == ()
    assert parsed[1].metric_observation_ids == (
        metric_evidence.metric_observation_ids
    )


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("metric_without_metric_reference", "original supporting Evidence"),
        ("evidence_outside_claim", "original supporting Evidence"),
        ("fact_outside_evidence", "Fact outside cited Evidence"),
        ("metric_outside_evidence", "Metric outside cited Evidence"),
        ("empty_references", "schema validation"),
        ("duplicate_claim_index", "each claim index exactly once"),
    ),
)
def test_verification_rejects_untraceable_or_cross_bound_references(
    mutation: str,
    message: str,
):
    packet, fact_evidence, metric_evidence = _verification_packet()
    payload = _valid_verification_payload(fact_evidence, metric_evidence)
    claims = payload["claims"]
    assert isinstance(claims, list)
    fact_claim = claims[0]
    metric_claim = claims[1]
    assert isinstance(fact_claim, dict)
    assert isinstance(metric_claim, dict)

    if mutation == "metric_without_metric_reference":
        metric_claim["evidence_ids"] = []
        metric_claim["metric_observation_ids"] = []
        metric_claim["fact_ids"] = [str(fact_evidence.fact_ids[0])]
    elif mutation == "evidence_outside_claim":
        fact_claim["evidence_ids"] = [str(metric_evidence.evidence_id)]
        fact_claim["fact_ids"] = []
        fact_claim["metric_observation_ids"] = [
            str(metric_evidence.metric_observation_ids[0])
        ]
    elif mutation == "fact_outside_evidence":
        fact_claim["fact_ids"] = [str(FactId.new())]
    elif mutation == "metric_outside_evidence":
        metric_claim["metric_observation_ids"] = [
            str(MetricObservationId.new())
        ]
    elif mutation == "empty_references":
        fact_claim["evidence_ids"] = []
        fact_claim["fact_ids"] = []
        fact_claim["metric_observation_ids"] = []
    elif mutation == "duplicate_claim_index":
        metric_claim["claim_index"] = 0
    else:  # pragma: no cover - parametrization is exhaustive
        raise AssertionError(f"Unexpected mutation: {mutation}")

    with pytest.raises(ValueError, match=message):
        VerificationEngine._parse(json.dumps(payload), packet)


def test_verification_rejects_passing_causal_fact_claim():
    packet, fact_evidence, metric_evidence = _verification_packet()
    packet = packet.model_copy(
        update={
            "claims": (
                packet.claims[0].model_copy(
                    update={
                        "statement": "The review complaint caused the sales decline."
                    }
                ),
                packet.claims[1],
            )
        }
    )

    with pytest.raises(ValueError, match="unsupported causal language"):
        VerificationEngine._parse(
            json.dumps(
                _valid_verification_payload(fact_evidence, metric_evidence)
            ),
            packet,
        )


def test_verification_output_budget_scales_for_multi_claim_lineage():
    assert verification_max_output_tokens(1) == 1_600
    assert verification_max_output_tokens(2) == 1_600
    assert verification_max_output_tokens(8) == 4_000
    assert verification_max_output_tokens(20) == 5_000
    with pytest.raises(ValueError, match="positive Claim count"):
        verification_max_output_tokens(0)


def test_context_packets_reject_hidden_label_metadata_and_reasoning_history():
    workspace_id = WorkspaceId.new()
    case_id = CaseId.new()
    dataset_id = DatasetId.new()
    common = {
        "case": _header(workspace_id, case_id),
        "goal": "Explain the delivery anomaly",
        "manifest": _manifest(workspace_id, case_id, dataset_id),
        "budget": AgentBudgetLimit(),
    }

    with pytest.raises(ValidationError, match="hidden evaluation label"):
        LeadContextPacket(
            **common,
            capability_profile=CapabilityProfile(
                dataset_id=dataset_id,
                workspace_id=workspace_id,
                capabilities=(),
            ),
            analysis=_analysis(dataset_id),
            metadata={"expected_behavior": "hidden gold answer"},
        )
    with pytest.raises(ValidationError):
        VerificationPacket(
            **common,
            claims=("Transit time worsened",),
            capability_profile=CapabilityProfile(
                dataset_id=dataset_id,
                workspace_id=workspace_id,
                capabilities=(),
            ),
            analysis=_analysis(dataset_id),
            capability_boundaries=("profit not observed",),
            lead_reasoning="private chain of thought",
        )


def test_path_packet_keeps_minimum_evidence_tools_and_forbidden_claims():
    workspace_id = WorkspaceId.new()
    case_id = CaseId.new()
    dataset_id = DatasetId.new()
    evidence_id = EvidenceId.new()

    packet = PathContextPacket(
        case=_header(workspace_id, case_id),
        goal="Determine whether transit or handling worsened",
        path_type=PathType.FULFILLMENT,
        required_capabilities=frozenset({CapabilityName.FULFILLMENT_DIAGNOSIS}),
        capability_profile=_fulfillment_capabilities(workspace_id, dataset_id),
        analysis=_analysis(dataset_id),
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
        manifest=_manifest(workspace_id, case_id, dataset_id),
        budget=AgentBudgetLimit(max_tool_calls=4, max_tokens=2000),
    )

    assert packet.path_type is PathType.FULFILLMENT
    assert packet.evidence[0].evidence_id == evidence_id
    assert packet.allowed_tools == frozenset({"metric_query", "source_fact_lookup"})
    assert (
        b'"allowed_tools":["metric_query","source_fact_lookup"]'
        in canonical_context_bytes(packet)
    )


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
