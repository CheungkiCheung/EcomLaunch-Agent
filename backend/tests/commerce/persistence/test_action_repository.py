"""Action and Approval persistence contracts."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.commerce.actions.approval import (
    ApprovalDecisionCommand,
    ApprovalDecisionType,
    ApprovalRequest,
)
from app.commerce.actions.contracts import (
    ActionDraft,
    ActionKind,
    ExternalMutationParameters,
    ExternalOperation,
    MetricComparison,
    MetricMonitorParameters,
    ValidatedActionDraft,
)
from app.commerce.actions.policy import (
    ActionPolicyGate,
    ConnectorPolicy,
)
from app.commerce.domain.enums import CaseSeverity
from app.commerce.domain.events import DomainEventActor
from app.commerce.domain.ids import (
    CaseId,
    CorrelationId,
    EvidenceId,
    HypothesisId,
    MetricObservationId,
    TraceId,
    WorkspaceId,
)
from app.commerce.domain.models import Case, RollbackPlan
from app.commerce.persistence.actions import (
    ActionRecord,
    SqlActionRepository,
    SqlApprovalRepository,
)
from app.commerce.persistence.repositories import DuplicateEntityError
from app.commerce.persistence.schema import create_commerce_schema
from app.commerce.persistence.unit_of_work import SqlCommerceUnitOfWork


async def _database(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'actions.db'}")
    await create_commerce_schema(engine)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _case(factory):
    workspace_id = WorkspaceId.new()
    now = datetime(2026, 7, 19, 13, 0, tzinfo=UTC)
    case = Case(
        workspace_id=workspace_id,
        title="Late-delivery anomaly",
        severity=CaseSeverity.HIGH,
        opened_at=now,
        updated_at=now,
    )
    await SqlCommerceUnitOfWork(factory).create_case(
        case,
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
        actor=DomainEventActor.SYSTEM,
    )
    return workspace_id, case


def _rollback() -> RollbackPlan:
    return RollbackPlan(
        strategy="Disable or reverse the bounded operation",
        trigger="A guardrail fails or an operator requests rollback",
        verification="Read the internal or connector state after rollback",
    )


def _monitor_decision(workspace_id: WorkspaceId, case_id: CaseId):
    metric_id = MetricObservationId.new()
    draft = ActionDraft(
        workspace_id=workspace_id,
        case_id=case_id,
        title="Monitor late-delivery recovery",
        description="Create an internal metric monitor.",
        evidence_ids=(EvidenceId.new(),),
        hypothesis_ids=(HypothesisId.new(),),
        expected_signal_metric_ids=(metric_id,),
        parameters=MetricMonitorParameters(
            kind=ActionKind.CREATE_METRIC_MONITOR,
            metric_name="late_delivery_rate",
            metric_observation_ids=(metric_id,),
            comparison=MetricComparison.LESS_THAN_OR_EQUAL,
            threshold="0.15",
            cadence_hours=24,
            follow_up_after_days=7,
        ),
        rollback_plan=_rollback(),
    )
    return ActionPolicyGate().evaluate(
        ValidatedActionDraft(draft=draft, validation_sha256="a" * 64)
    )


def _external_decision(workspace_id: WorkspaceId, case_id: CaseId):
    draft = ActionDraft(
        workspace_id=workspace_id,
        case_id=case_id,
        title="Adjust campaign budget",
        description="Apply one reversible external write.",
        evidence_ids=(EvidenceId.new(),),
        hypothesis_ids=(HypothesisId.new(),),
        expected_signal_metric_ids=(MetricObservationId.new(),),
        parameters=ExternalMutationParameters(
            kind=ActionKind.EXTERNAL_MUTATION,
            connector_id="merchant_ads",
            operation=ExternalOperation.UPDATE_CAMPAIGN_BUDGET,
            target_ref_sha256="b" * 64,
            reversible=True,
            dry_run=False,
        ),
        rollback_plan=_rollback(),
    )
    return ActionPolicyGate(
        connector_policy=ConnectorPolicy(
            allowed_operations={
                "merchant_ads": frozenset(
                    {ExternalOperation.UPDATE_CAMPAIGN_BUDGET}
                )
            }
        )
    ).evaluate(ValidatedActionDraft(draft=draft, validation_sha256="c" * 64))


@pytest.mark.anyio
async def test_action_record_round_trips_and_remains_workspace_scoped(tmp_path):
    engine, factory = await _database(tmp_path)
    workspace_id, case = await _case(factory)
    decision = _monitor_decision(workspace_id, case.id)
    record = ActionRecord.from_policy(
        decision,
        occurred_at=datetime(2026, 7, 19, 13, 1, tzinfo=UTC),
    )
    repository = SqlActionRepository(factory)

    await repository.create(record)
    loaded = await repository.get(workspace_id, record.action.id)

    assert loaded == record
    assert await repository.get(WorkspaceId.new(), record.action.id) is None
    assert await repository.list_case(workspace_id, case.id) == (record,)
    with pytest.raises(DuplicateEntityError):
        await repository.create(record)
    await engine.dispose()


@pytest.mark.anyio
async def test_approval_request_and_idempotent_decision_round_trip(tmp_path):
    engine, factory = await _database(tmp_path)
    workspace_id, case = await _case(factory)
    decision = _external_decision(workspace_id, case.id)
    request = ApprovalRequest.from_policy(
        decision,
        occurred_at=datetime(2026, 7, 19, 13, 2, tzinfo=UTC),
    )
    repository = SqlApprovalRepository(factory)
    await repository.create(request)

    key = hashlib.sha256(b"approval-command-001").hexdigest()
    command = ApprovalDecisionCommand(
        workspace_id=workspace_id,
        case_id=case.id,
        action_id=decision.action.id,
        approval_id=request.id,
        decision=ApprovalDecisionType.APPROVE,
        actor_id="operator-a",
        idempotency_key_sha256=key,
        created_at=datetime(2026, 7, 19, 13, 3, tzinfo=UTC),
    )
    first = await repository.append_decision(command)
    replay = await repository.append_decision(command)

    assert await repository.get(workspace_id, request.id) == request
    assert await repository.get_by_action(
        workspace_id,
        decision.action.id,
    ) == request
    assert first == command
    assert replay == command
    assert await repository.get_decision_by_idempotency(
        workspace_id,
        decision.action.id,
        key,
    ) == command
    await engine.dispose()
