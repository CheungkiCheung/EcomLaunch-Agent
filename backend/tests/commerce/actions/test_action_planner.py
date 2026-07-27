"""Deterministic fixed-catalog contracts for the fresh Action Planner."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from app.commerce.actions.contracts import (
    ActionKind,
    MetricComparison,
    MetricMonitorParameters,
)
from app.commerce.actions.planner import (
    ActionCatalog,
    ActionPlannerModelOutput,
    ActionPlannerParseError,
    MetricMonitorPlanParameters,
    parse_action_planner_output,
)
from app.commerce.agents.contracts import (
    AgentBudgetLimit,
    CaseAnalysisDigest,
    CaseHeader,
    ContextManifest,
    EvidenceDigest,
    HypothesisDigest,
    LeadContextPacket,
    MetricObservationDigest,
)
from app.commerce.data.capabilities import CapabilityProfile
from app.commerce.domain.enums import (
    CaseSeverity,
    CaseStatus,
    HypothesisStatus,
    SemanticStatus,
)
from app.commerce.domain.ids import (
    ActionId,
    CaseId,
    DatasetId,
    EntityId,
    EvidenceId,
    HypothesisId,
    MetricObservationId,
    WorkspaceId,
)
from app.commerce.metrics.registry import MetricWindow


def _context() -> LeadContextPacket:
    workspace_id = WorkspaceId.new()
    case_id = CaseId.new()
    dataset_id = DatasetId.new()
    evidence_id = EvidenceId.new()
    hypothesis_id = HypothesisId.new()
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
    common = {
        "metric_name": "late_delivery_rate",
        "semantic_status": SemanticStatus.DERIVED,
        "unit": "ratio",
        "formula_version": "late_delivery_rate@1.0.0",
        "sample_size": 100,
        "source_fact_count": 100,
    }
    return LeadContextPacket(
        case=CaseHeader(
            workspace_id=workspace_id,
            case_id=case_id,
            title="Late-delivery anomaly",
            severity=CaseSeverity.HIGH,
            status=CaseStatus.INVESTIGATING,
            version=1,
        ),
        goal="Choose one bounded next Action",
        manifest=ContextManifest(
            context_version="commerce-context@1.0.0",
            workspace_id=workspace_id,
            case_id=case_id,
            dataset_id=dataset_id,
            source_artifact_sha256="a" * 64,
            context_sha256="b" * 64,
            estimated_tokens=1_000,
            included_evidence_ids=(evidence_id,),
            included_metric_observation_ids=(baseline_id, current_id),
        ),
        budget=AgentBudgetLimit(),
        capabilities=frozenset(),
        capability_profile=CapabilityProfile(
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            capabilities=(),
        ),
        analysis=CaseAnalysisDigest(
            dataset_id=dataset_id,
            seller_entity_id=EntityId.new(),
            seller_external_key="seller-a",
            baseline_window=baseline_window,
            current_window=current_window,
            baseline_metrics=(
                MetricObservationDigest(
                    metric_observation_id=baseline_id,
                    value=Decimal("0.10"),
                    numerator=10,
                    denominator=100,
                    window_start=baseline_window.start,
                    window_end=baseline_window.end,
                    **common,
                ),
            ),
            current_metrics=(
                MetricObservationDigest(
                    metric_observation_id=current_id,
                    value=Decimal("0.30"),
                    numerator=30,
                    denominator=100,
                    window_start=current_window.start,
                    window_end=current_window.end,
                    **common,
                ),
            ),
        ),
        evidence=(
            EvidenceDigest(
                evidence_id=evidence_id,
                summary="Late-delivery rate rose from 0.10 to 0.30",
                semantic_status=SemanticStatus.DERIVED,
                confidence=0.95,
                metric_observation_ids=(baseline_id, current_id),
            ),
        ),
        hypotheses=(
            HypothesisDigest(
                hypothesis_id=hypothesis_id,
                statement="The late-delivery signal requires monitoring",
                status=HypothesisStatus.SUPPORTED.value,
                confidence=0.9,
                evidence_ids=(evidence_id,),
            ),
        ),
    )


def test_action_catalog_derives_monitor_threshold_and_rollback_from_context():
    context = _context()
    output = ActionPlannerModelOutput(
        title="Monitor late-delivery recovery",
        description="Track the evidenced signal and reopen if it remains elevated.",
        evidence_ids=(context.evidence[0].evidence_id,),
        hypothesis_ids=(context.hypotheses[0].hypothesis_id,),
        expected_signal_metric_ids=(context.analysis.current_metrics[0].metric_observation_id,),
        parameters=MetricMonitorPlanParameters(
            metric_name="late_delivery_rate",
            metric_observation_ids=(context.analysis.current_metrics[0].metric_observation_id,),
            cadence_hours=24,
            follow_up_after_days=7,
        ),
    )

    validated = ActionCatalog().materialize(
        output,
        context,
        action_id=ActionId.new(),
    )

    parameters = validated.draft.parameters
    assert isinstance(parameters, MetricMonitorParameters)
    assert parameters.kind is ActionKind.CREATE_METRIC_MONITOR
    assert parameters.threshold == Decimal("0.10")
    assert parameters.comparison is MetricComparison.LESS_THAN_OR_EQUAL
    assert validated.draft.rollback_plan.strategy == "disable_metric_monitor"


def test_action_planner_parser_rejects_model_owned_policy_and_execution_fields():
    context = _context()
    payload = {
        "title": "Monitor signal",
        "description": "Monitor the evidenced metric.",
        "evidence_ids": [str(context.evidence[0].evidence_id)],
        "hypothesis_ids": [str(context.hypotheses[0].hypothesis_id)],
        "expected_signal_metric_ids": [str(context.analysis.current_metrics[0].metric_observation_id)],
        "parameters": {
            "kind": "create_metric_monitor",
            "metric_name": "late_delivery_rate",
            "metric_observation_ids": [str(context.analysis.current_metrics[0].metric_observation_id)],
            "cadence_hours": 24,
            "follow_up_after_days": 7,
        },
        "risk_level": "low",
        "policy_level": "L1",
        "execution_tool": "internal_metric_monitor.create",
    }

    with pytest.raises(ActionPlannerParseError):
        parse_action_planner_output(__import__("json").dumps(payload))
