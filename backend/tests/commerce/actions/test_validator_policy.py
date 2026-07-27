"""Deterministic Action Validator and L0-L5 policy contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.commerce.actions.approval import (
    ApprovalDecisionType,
)
from app.commerce.actions.contracts import (
    ActionDraft,
    ActionKind,
    ExternalMutationParameters,
    ExternalOperation,
    MetricComparison,
    MetricMonitorParameters,
)
from app.commerce.actions.policy import (
    ActionPolicyDisposition,
    ActionPolicyGate,
    ActionPolicyLevel,
    ConnectorPolicy,
    PolicyReasonCode,
)
from app.commerce.actions.service import (
    ActionProposalService,
    ApprovalDecisionService,
)
from app.commerce.actions.validator import (
    ActionValidationError,
    ActionValidationReason,
    ActionValidator,
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
    ActionRiskLevel,
    ActionStatus,
    ApprovalStatus,
    CaseSeverity,
    CaseStatus,
    SemanticStatus,
)
from app.commerce.domain.events import DomainEventActor
from app.commerce.domain.ids import (
    CaseId,
    CorrelationId,
    DatasetId,
    EntityId,
    EvidenceId,
    HypothesisId,
    MetricObservationId,
    TraceId,
    WorkspaceId,
)
from app.commerce.domain.models import Case, RollbackPlan
from app.commerce.metrics.registry import MetricWindow
from app.commerce.persistence.events import SqlDomainEventStore
from app.commerce.persistence.repositories import SqlCaseRepository
from app.commerce.persistence.schema import create_commerce_schema
from app.commerce.persistence.unit_of_work import SqlCommerceUnitOfWork


def _context():
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
    packet = LeadContextPacket(
        case=CaseHeader(
            workspace_id=workspace_id,
            case_id=case_id,
            title="Late-delivery anomaly",
            severity=CaseSeverity.HIGH,
            status=CaseStatus.INVESTIGATING,
            version=4,
        ),
        goal="Turn verified evidence into a bounded operation",
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
                summary="Late-delivery rate is elevated in the current window",
                semantic_status=SemanticStatus.DERIVED,
                confidence=0.95,
                metric_observation_ids=(baseline_id, current_id),
            ),
        ),
        hypotheses=(
            HypothesisDigest(
                hypothesis_id=hypothesis_id,
                statement="The current late-delivery rate requires monitoring",
                status="supported",
                confidence=0.9,
                evidence_ids=(evidence_id,),
            ),
        ),
    )
    return packet, evidence_id, hypothesis_id, current_id


def _monitor_draft(packet, evidence_id, hypothesis_id, current_id):
    return ActionDraft(
        workspace_id=packet.case.workspace_id,
        case_id=packet.case.case_id,
        title="Monitor late-delivery recovery",
        description="Create a reversible internal monitor for the verified metric.",
        evidence_ids=(evidence_id,),
        hypothesis_ids=(hypothesis_id,),
        expected_signal_metric_ids=(current_id,),
        parameters=MetricMonitorParameters(
            kind=ActionKind.CREATE_METRIC_MONITOR,
            metric_name="late_delivery_rate",
            metric_observation_ids=(current_id,),
            comparison=MetricComparison.LESS_THAN_OR_EQUAL,
            threshold=Decimal("0.15"),
            cadence_hours=24,
            follow_up_after_days=7,
        ),
        rollback_plan=RollbackPlan(
            strategy="Disable the internal monitor",
            trigger="The metric contract or seller scope changes",
            verification="Confirm no active monitor remains for this Action",
        ),
    )


def test_validated_internal_monitor_maps_to_l2_auto_execute():
    packet, evidence_id, hypothesis_id, current_id = _context()
    validated = ActionValidator().validate(
        _monitor_draft(packet, evidence_id, hypothesis_id, current_id),
        packet,
    )

    decision = ActionPolicyGate().evaluate(validated)

    assert validated.validation_sha256
    assert validated.draft.parameters.kind is ActionKind.CREATE_METRIC_MONITOR
    assert decision.level is ActionPolicyLevel.L2
    assert decision.disposition is ActionPolicyDisposition.AUTO_EXECUTE
    assert decision.execution_tool == "internal_metric_monitor.create"
    assert decision.action.status is ActionStatus.POLICY_CHECKED
    assert decision.action.risk_level is ActionRiskLevel.MEDIUM
    assert decision.action.approval.required is False
    assert decision.action.approval.status is ApprovalStatus.NOT_REQUIRED


def test_validator_rejects_unverified_hypothesis_and_metric_scope_escape():
    packet, evidence_id, hypothesis_id, current_id = _context()
    proposed = packet.model_copy(
        update={
            "hypotheses": (
                packet.hypotheses[0].model_copy(update={"status": "proposed"}),
            )
        }
    )
    with pytest.raises(ActionValidationError) as unsupported:
        ActionValidator().validate(
            _monitor_draft(packet, evidence_id, hypothesis_id, current_id),
            proposed,
        )
    assert unsupported.value.reason is ActionValidationReason.HYPOTHESIS_NOT_VERIFIED

    foreign_id = MetricObservationId.new()
    escaped = _monitor_draft(
        packet,
        evidence_id,
        hypothesis_id,
        current_id,
    ).model_copy(
        update={
            "expected_signal_metric_ids": (foreign_id,),
            "parameters": MetricMonitorParameters(
                kind=ActionKind.CREATE_METRIC_MONITOR,
                metric_name="late_delivery_rate",
                metric_observation_ids=(foreign_id,),
                comparison=MetricComparison.LESS_THAN_OR_EQUAL,
                threshold=Decimal("0.15"),
                cadence_hours=24,
                follow_up_after_days=7,
            ),
        }
    )
    with pytest.raises(ActionValidationError) as outside:
        ActionValidator().validate(escaped, packet)
    assert outside.value.reason is ActionValidationReason.METRIC_OUTSIDE_CONTEXT


def test_external_reversible_write_requires_l4_approval_and_allowlisted_connector():
    packet, evidence_id, hypothesis_id, current_id = _context()
    draft = ActionDraft(
        workspace_id=packet.case.workspace_id,
        case_id=packet.case.case_id,
        title="Reduce campaign budget",
        description="Apply a reversible external budget adjustment.",
        evidence_ids=(evidence_id,),
        hypothesis_ids=(hypothesis_id,),
        expected_signal_metric_ids=(current_id,),
        parameters=ExternalMutationParameters(
            kind=ActionKind.EXTERNAL_MUTATION,
            connector_id="merchant_ads",
            operation=ExternalOperation.UPDATE_CAMPAIGN_BUDGET,
            target_ref_sha256="c" * 64,
            reversible=True,
            dry_run=False,
        ),
        rollback_plan=RollbackPlan(
            strategy="Restore the prior campaign budget snapshot",
            trigger="Guardrail breach or explicit rollback request",
            verification="Read back the prior budget value from the connector",
        ),
    )
    validated = ActionValidator().validate(draft, packet)

    denied = ActionPolicyGate().evaluate(validated)
    assert denied.disposition is ActionPolicyDisposition.BLOCKED
    assert PolicyReasonCode.CONNECTOR_NOT_ALLOWED in denied.reason_codes

    approved_path = ActionPolicyGate(
        connector_policy=ConnectorPolicy(
            allowed_operations={
                "merchant_ads": frozenset(
                    {ExternalOperation.UPDATE_CAMPAIGN_BUDGET}
                )
            }
        )
    ).evaluate(validated)
    assert approved_path.level is ActionPolicyLevel.L4
    assert approved_path.disposition is ActionPolicyDisposition.APPROVAL_REQUIRED
    assert approved_path.required_approvals == 2
    assert approved_path.action.status is ActionStatus.AWAITING_APPROVAL
    assert approved_path.action.risk_level is ActionRiskLevel.HIGH
    assert approved_path.action.approval.status is ApprovalStatus.PENDING


def test_irreversible_financial_action_is_l5_blocked_even_when_connector_exists():
    packet, evidence_id, hypothesis_id, current_id = _context()
    draft = ActionDraft(
        workspace_id=packet.case.workspace_id,
        case_id=packet.case.case_id,
        title="Issue customer refund",
        description="Attempt an irreversible financial mutation.",
        evidence_ids=(evidence_id,),
        hypothesis_ids=(hypothesis_id,),
        expected_signal_metric_ids=(current_id,),
        parameters=ExternalMutationParameters(
            kind=ActionKind.EXTERNAL_MUTATION,
            connector_id="merchant_orders",
            operation=ExternalOperation.ISSUE_REFUND,
            target_ref_sha256="d" * 64,
            reversible=False,
            dry_run=False,
        ),
        rollback_plan=RollbackPlan(
            strategy="No reliable rollback exists",
            trigger="Never execute through this product version",
            verification="Confirm no connector mutation was attempted",
        ),
    )
    validated = ActionValidator().validate(draft, packet)
    decision = ActionPolicyGate(
        connector_policy=ConnectorPolicy(
            allowed_operations={
                "merchant_orders": frozenset({ExternalOperation.ISSUE_REFUND})
            }
        )
    ).evaluate(validated)

    assert decision.level is ActionPolicyLevel.L5
    assert decision.disposition is ActionPolicyDisposition.BLOCKED
    assert PolicyReasonCode.IRREVERSIBLE_OR_FINANCIAL in decision.reason_codes
    assert decision.action.status is ActionStatus.REJECTED
    assert decision.action.risk_level is ActionRiskLevel.CRITICAL
    assert decision.action.approval.status is ApprovalStatus.REJECTED


@pytest.mark.anyio
async def test_action_proposal_and_two_actor_approval_are_atomic_and_idempotent(
    tmp_path,
):
    packet, evidence_id, hypothesis_id, current_id = _context()
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'action-service.db'}")
    await create_commerce_schema(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        persisted_case = Case(
            id=packet.case.case_id,
            workspace_id=packet.case.workspace_id,
            title=packet.case.title,
            severity=packet.case.severity,
            status=packet.case.status,
            evidence_ids=(evidence_id,),
            hypothesis_ids=(hypothesis_id,),
            opened_at=datetime(2026, 7, 19, 14, 0, tzinfo=UTC),
            updated_at=datetime(2026, 7, 19, 14, 0, tzinfo=UTC),
            version=packet.case.version,
        )
        await SqlCommerceUnitOfWork(factory).create_case(
            persisted_case,
            trace_id=TraceId.new(),
            correlation_id=CorrelationId.new(),
            actor=DomainEventActor.SYSTEM,
        )
        monitor = _monitor_draft(
            packet,
            evidence_id,
            hypothesis_id,
            current_id,
        )
        proposal_service = ActionProposalService(
            factory,
            clock=lambda: datetime(2026, 7, 19, 14, 1, tzinfo=UTC),
        )
        created = await proposal_service.propose(
            monitor,
            packet,
            actor=DomainEventActor.AGENT,
            correlation_id=CorrelationId.new(),
        )
        replay = await proposal_service.propose(
            monitor,
            packet,
            actor=DomainEventActor.AGENT,
            correlation_id=CorrelationId.new(),
        )
        assert created.created is True
        assert created.approval is None
        assert replay.created is False
        case_after_monitor = await SqlCaseRepository(factory).get(
            packet.case.workspace_id,
            packet.case.case_id,
        )
        assert case_after_monitor is not None
        assert case_after_monitor.action_ids == (monitor.id,)

        packet_v5 = packet.model_copy(
            update={
                "case": packet.case.model_copy(
                    update={"version": case_after_monitor.version}
                )
            }
        )
        external = ActionDraft(
            workspace_id=packet.case.workspace_id,
            case_id=packet.case.case_id,
            title="Reduce campaign budget",
            description="Apply a reversible external budget adjustment.",
            evidence_ids=(evidence_id,),
            hypothesis_ids=(hypothesis_id,),
            expected_signal_metric_ids=(current_id,),
            parameters=ExternalMutationParameters(
                kind=ActionKind.EXTERNAL_MUTATION,
                connector_id="merchant_ads",
                operation=ExternalOperation.UPDATE_CAMPAIGN_BUDGET,
                target_ref_sha256="e" * 64,
                reversible=True,
                dry_run=False,
            ),
            rollback_plan=RollbackPlan(
                strategy="Restore the prior campaign budget snapshot",
                trigger="Approval is revoked or a guardrail fires",
                verification="Read back the prior connector value",
            ),
        )
        gated_service = ActionProposalService(
            factory,
            policy_gate=ActionPolicyGate(
                connector_policy=ConnectorPolicy(
                    allowed_operations={
                        "merchant_ads": frozenset(
                            {ExternalOperation.UPDATE_CAMPAIGN_BUDGET}
                        )
                    }
                )
            ),
            clock=lambda: datetime(2026, 7, 19, 14, 2, tzinfo=UTC),
        )
        gated = await gated_service.propose(
            external,
            packet_v5,
            actor=DomainEventActor.AGENT,
            correlation_id=CorrelationId.new(),
        )
        assert gated.approval is not None
        assert gated.record.action.approval.approval_id == gated.approval.id
        assert gated.record.action.status is ActionStatus.AWAITING_APPROVAL

        decision_times = iter(
            (
                datetime(2026, 7, 19, 14, 3, tzinfo=UTC),
                datetime(2026, 7, 19, 14, 4, tzinfo=UTC),
            )
        )
        approvals = ApprovalDecisionService(
            factory,
            clock=lambda: next(decision_times),
        )
        first = await approvals.decide(
            packet.case.workspace_id,
            external.id,
            decision=ApprovalDecisionType.APPROVE,
            actor_id="operator-a",
            idempotency_key="approval-operator-a",
            correlation_id=CorrelationId.new(),
        )
        first_replay = await approvals.decide(
            packet.case.workspace_id,
            external.id,
            decision=ApprovalDecisionType.APPROVE,
            actor_id="operator-a",
            idempotency_key="approval-operator-a",
            correlation_id=CorrelationId.new(),
        )
        second = await approvals.decide(
            packet.case.workspace_id,
            external.id,
            decision=ApprovalDecisionType.APPROVE,
            actor_id="operator-b",
            idempotency_key="approval-operator-b",
            correlation_id=CorrelationId.new(),
        )
        assert first.approval.status is ApprovalStatus.PENDING
        assert first.record.action.status is ActionStatus.AWAITING_APPROVAL
        assert first_replay.replayed is True
        assert second.approval.status is ApprovalStatus.APPROVED
        assert second.record.action.status is ActionStatus.APPROVED
        assert second.record.action.approval.status is ApprovalStatus.APPROVED

        events = await SqlDomainEventStore(factory).list_case(
            packet.case.workspace_id,
            packet.case.case_id,
        )
        event_types = [event.event_type for event in events]
        assert event_types.count("action.created") == 2
        assert event_types.count("approval.requested") == 1
        assert event_types.count("approval.approve") == 2
        assert event_types.count("action.status_changed") == 1
    finally:
        await engine.dispose()
