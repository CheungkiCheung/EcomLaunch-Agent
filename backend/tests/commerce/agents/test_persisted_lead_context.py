"""Persisted multi-Path Lead synthesis context contracts."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.commerce.agents.contracts import (
    AgentBudgetLimit,
    CaseAnalysisDigest,
    CaseHeader,
    ContextManifest,
    EvidenceDigest,
    HypothesisDigest,
    LeadContextPacket,
    MetricObservationDigest,
    PathEvidenceScope,
    PathType,
    canonical_context_sha256,
)
from app.commerce.agents.lead import (
    LeadSynthesisResult,
    LeadUnknown,
    build_persisted_lead_context,
)
from app.commerce.data.capabilities import CapabilityProfile
from app.commerce.domain.enums import CaseSeverity, CaseStatus, SemanticStatus
from app.commerce.domain.ids import (
    AgentTaskId,
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
from app.commerce.metrics.registry import MetricWindow


def _lead_packet():
    workspace_id = WorkspaceId.new()
    case_id = CaseId.new()
    dataset_id = DatasetId.new()
    baseline_window = MetricWindow(
        start=datetime(2026, 1, 1),
        end=datetime(2026, 2, 1),
    )
    current_window = MetricWindow(
        start=datetime(2026, 2, 1),
        end=datetime(2026, 3, 1),
    )
    baseline_id = MetricObservationId.new()
    current_id = MetricObservationId.new()
    fulfillment_metric_id = MetricObservationId.new()
    peer_metric_id = MetricObservationId.new()
    unscoped_metric_id = MetricObservationId.new()
    review_fact_id = FactId.new()
    fulfillment_evidence_id = EvidenceId.new()
    peer_evidence_id = EvidenceId.new()
    unscoped_evidence_id = EvidenceId.new()
    selected_hypothesis_id = HypothesisId.new()
    unscoped_hypothesis_id = HypothesisId.new()
    common_metric = {
        "metric_name": "late_delivery_rate",
        "semantic_status": SemanticStatus.DERIVED,
        "unit": "ratio",
        "formula_version": "late_delivery_rate@1.0.0",
        "sample_size": 100,
        "source_fact_count": 200,
    }
    analysis = CaseAnalysisDigest(
        dataset_id=dataset_id,
        seller_entity_id=EntityId.new(),
        seller_external_key="seller-a",
        baseline_window=baseline_window,
        current_window=current_window,
        baseline_metrics=(
            MetricObservationDigest(
                metric_observation_id=baseline_id,
                value=Decimal("0.10"),
                window_start=baseline_window.start,
                window_end=baseline_window.end,
                **common_metric,
            ),
        ),
        current_metrics=(
            MetricObservationDigest(
                metric_observation_id=current_id,
                value=Decimal("0.30"),
                window_start=current_window.start,
                window_end=current_window.end,
                **common_metric,
            ),
        ),
    )
    evidence = (
        EvidenceDigest(
            evidence_id=fulfillment_evidence_id,
            summary="Transit deterioration is concentrated in the current window",
            semantic_status=SemanticStatus.DERIVED,
            confidence=0.93,
            metric_observation_ids=(fulfillment_metric_id,),
        ),
        EvidenceDigest(
            evidence_id=peer_evidence_id,
            summary="The seller is above its deterministic peer late-delivery rate",
            semantic_status=SemanticStatus.DERIVED,
            confidence=0.88,
            metric_observation_ids=(peer_metric_id,),
        ),
        EvidenceDigest(
            evidence_id=unscoped_evidence_id,
            summary="Unrelated review signal from another investigation scope",
            semantic_status=SemanticStatus.DERIVED,
            confidence=0.7,
            fact_ids=(review_fact_id,),
            metric_observation_ids=(unscoped_metric_id,),
        ),
    )
    packet = LeadContextPacket(
        case=CaseHeader(
            workspace_id=workspace_id,
            case_id=case_id,
            title="Delivery anomaly",
            severity=CaseSeverity.HIGH,
            status=CaseStatus.INVESTIGATING,
            version=5,
        ),
        goal="Find the strongest traceable explanation",
        manifest=ContextManifest(
            context_version="commerce-context@1.0.0",
            workspace_id=workspace_id,
            case_id=case_id,
            dataset_id=dataset_id,
            source_artifact_sha256="a" * 64,
            context_sha256="b" * 64,
            estimated_tokens=1_000,
            included_evidence_ids=tuple(item.evidence_id for item in evidence),
            included_fact_ids=(review_fact_id,),
            included_metric_observation_ids=(
                baseline_id,
                current_id,
                fulfillment_metric_id,
                peer_metric_id,
                unscoped_metric_id,
            ),
        ),
        budget=AgentBudgetLimit(max_tokens=16_000),
        capabilities=frozenset(),
        capability_profile=CapabilityProfile(
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            capabilities=(),
        ),
        analysis=analysis,
        evidence=evidence,
        hypotheses=(
            HypothesisDigest(
                hypothesis_id=selected_hypothesis_id,
                statement="Fulfillment and peer Evidence describe the same anomaly",
                status="investigating",
                confidence=0.75,
                evidence_ids=(fulfillment_evidence_id, peer_evidence_id),
            ),
            HypothesisDigest(
                hypothesis_id=unscoped_hypothesis_id,
                statement="An unrelated review signal is involved",
                status="proposed",
                confidence=0.4,
                evidence_ids=(unscoped_evidence_id,),
            ),
        ),
    )
    ids = {
        "fulfillment_evidence": fulfillment_evidence_id,
        "peer_evidence": peer_evidence_id,
        "unscoped_evidence": unscoped_evidence_id,
        "fulfillment_metric": fulfillment_metric_id,
        "peer_metric": peer_metric_id,
        "review_fact": review_fact_id,
        "selected_hypothesis": selected_hypothesis_id,
    }
    return packet, ids


def _scope(
    packet: LeadContextPacket,
    *,
    path_type: PathType,
    evidence_ids: tuple[EvidenceId, ...],
    fact_ids: tuple[FactId, ...] = (),
    metric_ids: tuple[MetricObservationId, ...] = (),
) -> PathEvidenceScope:
    return PathEvidenceScope(
        workspace_id=packet.case.workspace_id,
        case_id=packet.case.case_id,
        run_id=RunId.new(),
        task_id=AgentTaskId.new(),
        path_type=path_type,
        dataset_id=packet.manifest.dataset_id,
        context_version=f"commerce-{path_type.value}-context@1.0.0",
        context_sha256=("c" if path_type is PathType.FULFILLMENT else "d") * 64,
        source_artifact_sha256=packet.manifest.source_artifact_sha256,
        evidence_ids=evidence_ids,
        included_fact_ids=fact_ids,
        included_metric_observation_ids=metric_ids,
    )


def test_builder_unions_multi_path_scope_and_excludes_unreleased_case_evidence():
    packet, ids = _lead_packet()
    scopes = (
        _scope(
            packet,
            path_type=PathType.FULFILLMENT,
            evidence_ids=(ids["fulfillment_evidence"],),
            metric_ids=(ids["fulfillment_metric"],),
        ),
        _scope(
            packet,
            path_type=PathType.SELLER_PEER,
            evidence_ids=(ids["peer_evidence"],),
            metric_ids=(ids["peer_metric"],),
        ),
    )

    context = build_persisted_lead_context(packet, path_scopes=scopes)

    assert context.path_scopes == scopes
    assert tuple(item.evidence_id for item in context.evidence) == (
        ids["fulfillment_evidence"],
        ids["peer_evidence"],
    )
    assert context.manifest.included_evidence_ids == (
        ids["fulfillment_evidence"],
        ids["peer_evidence"],
    )
    assert context.manifest.included_metric_observation_ids == (
        ids["fulfillment_metric"],
        ids["peer_metric"],
    )
    assert tuple(item.hypothesis_id for item in context.hypotheses) == (
        ids["selected_hypothesis"],
    )
    assert context.manifest.context_sha256 == canonical_context_sha256(context)
    assert "Path reasoning history excluded" in context.manifest.redactions
    assert ids["unscoped_evidence"] not in context.manifest.included_evidence_ids
    assert "analysis" not in context.model_dump()


def test_builder_fails_closed_when_evidence_is_missing_or_outside_path_scope():
    packet, ids = _lead_packet()
    missing = _scope(
        packet,
        path_type=PathType.FULFILLMENT,
        evidence_ids=(EvidenceId.new(),),
        metric_ids=(ids["fulfillment_metric"],),
    )
    with pytest.raises(ValueError, match="missing from reloaded Case Evidence"):
        build_persisted_lead_context(packet, path_scopes=(missing,))

    wrong_allowlist = _scope(
        packet,
        path_type=PathType.FULFILLMENT,
        evidence_ids=(ids["fulfillment_evidence"],),
        metric_ids=(MetricObservationId.new(),),
    )
    with pytest.raises(ValueError, match="outside its persisted Path scope"):
        build_persisted_lead_context(packet, path_scopes=(wrong_allowlist,))


def test_zero_path_context_supports_explicit_unknown_only_synthesis():
    packet, _ = _lead_packet()

    context = build_persisted_lead_context(packet, path_scopes=())
    result = LeadSynthesisResult(
        claims=(),
        unknowns=(
            LeadUnknown(
                question="Which evidence path can be evaluated?",
                reason="No capability-complete Path was selected",
            ),
        ),
        context_sha256=context.manifest.context_sha256,
    )

    assert context.evidence == ()
    assert context.path_scopes == ()
    assert result.claims == ()
    with pytest.raises(ValidationError, match="claim or explicit Unknown"):
        LeadSynthesisResult(
            claims=(),
            unknowns=(),
            context_sha256=context.manifest.context_sha256,
        )
