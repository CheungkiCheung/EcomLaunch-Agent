"""Fenced Action Execution Runs, real artifacts, failures, and rollback."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.commerce.actions.artifacts import ActionArtifactStatus
from app.commerce.actions.contracts import (
    ActionDraft,
    ActionKind,
    ExternalMutationParameters,
    ExternalOperation,
    InternalTaskParameters,
    MetricComparison,
    MetricMonitorParameters,
    ValidatedActionDraft,
)
from app.commerce.actions.execution import (
    ActionExecutionError,
    ActionExecutionService,
)
from app.commerce.actions.internal_connectors import (
    ConnectorStateError,
    InternalConnectorRegistry,
)
from app.commerce.actions.policy import (
    ActionPolicyGate,
    ConnectorPolicy,
)
from app.commerce.domain.enums import (
    ActionRunOperation,
    ActionStatus,
    CaseSeverity,
    CaseStatus,
    RunStatus,
)
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
from app.commerce.persistence.action_artifacts import SqlActionArtifactRepository
from app.commerce.persistence.actions import ActionRecord, SqlActionRepository
from app.commerce.persistence.events import SqlDomainEventStore
from app.commerce.persistence.runs import SqlRunRepository
from app.commerce.persistence.schema import create_commerce_schema
from app.commerce.persistence.unit_of_work import SqlCommerceUnitOfWork


def _rollback() -> RollbackPlan:
    return RollbackPlan(
        strategy="Cancel or disable the internal artifact",
        trigger="An operator requests rollback or a guardrail fails",
        verification="Read back the persisted artifact state",
    )


async def _database(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'action-execution.db'}")
    await create_commerce_schema(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, factory


async def _seed_action(factory, parameters, *, policy_gate=None) -> ActionRecord:
    workspace_id = WorkspaceId.new()
    now = datetime(2026, 7, 19, 17, 0, tzinfo=UTC)
    evidence_id = EvidenceId.new()
    draft = ActionDraft(
        workspace_id=workspace_id,
        case_id=CaseId.new(),
        title=f"Execute {parameters.kind.value}",
        description="Execute one evidence-backed bounded operation.",
        evidence_ids=(evidence_id,),
        hypothesis_ids=(HypothesisId.new(),),
        expected_signal_metric_ids=(MetricObservationId.new(),),
        parameters=parameters,
        rollback_plan=_rollback(),
    )
    decision = (policy_gate or ActionPolicyGate()).evaluate(
        ValidatedActionDraft(
            draft=draft,
            validation_sha256="a" * 64,
        )
    )
    record = ActionRecord.from_policy(decision, occurred_at=now)
    case = Case(
        id=draft.case_id,
        workspace_id=workspace_id,
        title="Late-delivery anomaly",
        severity=CaseSeverity.HIGH,
        status=CaseStatus.INVESTIGATING,
        evidence_ids=(evidence_id,),
        opened_at=now,
        updated_at=now,
    )
    uow = SqlCommerceUnitOfWork(factory)
    await uow.create_case(
        case,
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
        actor=DomainEventActor.SYSTEM,
    )
    updated_case = case.model_copy(
        update={
            "action_ids": (record.action.id,),
            "version": case.version + 1,
        }
    )
    await uow.create_action(
        updated_case,
        record,
        approval=None,
        expected_case_version=case.version,
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
        actor=DomainEventActor.AGENT,
    )
    return record


@pytest.mark.anyio
async def test_execution_run_is_idempotent_fenced_verified_and_replayable(tmp_path):
    engine, factory = await _database(tmp_path)
    record = await _seed_action(
        factory,
        InternalTaskParameters(
            kind=ActionKind.CREATE_INTERNAL_TASK,
            owner_role="seller-operations",
            due_days=3,
            checklist=("Contact carrier", "Attach route evidence"),
        ),
    )
    times = iter(
        (
            datetime(2026, 7, 19, 17, 1, tzinfo=UTC),
            datetime(2026, 7, 19, 17, 2, tzinfo=UTC),
        )
    )
    service = ActionExecutionService(
        factory,
        storage_root=tmp_path,
        clock=lambda: next(times),
        lease_ttl=timedelta(seconds=30),
    )

    started = await service.start(
        record.action.workspace_id,
        record.action.id,
        operation=ActionRunOperation.EXECUTE,
        idempotency_key="execute-task-001",
        actor_id="operator-a",
    )
    replayed_start = await service.start(
        record.action.workspace_id,
        record.action.id,
        operation=ActionRunOperation.EXECUTE,
        idempotency_key="execute-task-001",
        actor_id="operator-a",
    )
    executed = await service.execute(
        record.action.workspace_id,
        started.run.id,
        worker_id="action-worker-1",
    )
    replayed_execution = await service.execute(
        record.action.workspace_id,
        started.run.id,
        worker_id="action-worker-2",
    )

    assert started.created is True
    assert replayed_start.created is False
    assert replayed_start.run.id == started.run.id
    assert started.run.subject_action_id == record.action.id
    assert started.run.action_operation is ActionRunOperation.EXECUTE
    assert executed.run.status is RunStatus.COMPLETED
    assert executed.record.action.status is ActionStatus.SUCCEEDED
    assert executed.artifact is not None
    assert executed.artifact.status is ActionArtifactStatus.OPEN
    assert executed.error_message is None
    assert replayed_execution.replayed is True
    assert replayed_execution.artifact == executed.artifact

    run_events = await SqlDomainEventStore(factory).list_run(
        record.action.workspace_id,
        started.run.id,
    )
    assert [event.event_type for event in run_events] == [
        "run.created",
        "run.status_changed",
        "action.status_changed",
        "action.artifact_created",
        "action.status_changed",
        "case.status_changed",
        "run.status_changed",
        "run.lease_released",
    ]
    persisted_artifact = await SqlActionArtifactRepository(factory).get(
        record.action.workspace_id,
        record.action.id,
    )
    assert persisted_artifact is not None
    assert persisted_artifact == executed.artifact
    await engine.dispose()


@pytest.mark.anyio
async def test_monitor_execution_enters_monitoring_then_rollback_disables_artifact(
    tmp_path,
):
    engine, factory = await _database(tmp_path)
    metric_id = MetricObservationId.new()
    record = await _seed_action(
        factory,
        MetricMonitorParameters(
            kind=ActionKind.CREATE_METRIC_MONITOR,
            metric_name="late_delivery_rate",
            metric_observation_ids=(metric_id,),
            comparison=MetricComparison.LESS_THAN_OR_EQUAL,
            threshold="0.15",
            cadence_hours=24,
            follow_up_after_days=7,
        ),
    )
    times = iter(
        (
            datetime(2026, 7, 19, 17, 1, tzinfo=UTC),
            datetime(2026, 7, 19, 17, 2, tzinfo=UTC),
            datetime(2026, 7, 19, 17, 3, tzinfo=UTC),
            datetime(2026, 7, 19, 17, 4, tzinfo=UTC),
        )
    )
    service = ActionExecutionService(
        factory,
        storage_root=tmp_path,
        clock=lambda: next(times),
    )
    execute_run = await service.start(
        record.action.workspace_id,
        record.action.id,
        operation=ActionRunOperation.EXECUTE,
        idempotency_key="execute-monitor-001",
        actor_id="operator-a",
    )
    executed = await service.execute(
        record.action.workspace_id,
        execute_run.run.id,
        worker_id="action-worker-1",
    )
    rollback_run = await service.start(
        record.action.workspace_id,
        record.action.id,
        operation=ActionRunOperation.ROLLBACK,
        idempotency_key="rollback-monitor-001",
        actor_id="operator-a",
    )
    rolled_back = await service.execute(
        record.action.workspace_id,
        rollback_run.run.id,
        worker_id="action-worker-2",
    )

    assert executed.record.action.status is ActionStatus.MONITORING
    assert executed.artifact.status is ActionArtifactStatus.ACTIVE
    assert rolled_back.run.status is RunStatus.COMPLETED
    assert rolled_back.record.action.status is ActionStatus.ROLLED_BACK
    assert rolled_back.artifact.status is ActionArtifactStatus.DISABLED
    persisted = await SqlActionRepository(factory).get(
        record.action.workspace_id,
        record.action.id,
    )
    assert persisted is not None
    assert persisted.action.status is ActionStatus.ROLLED_BACK
    await engine.dispose()


class _FailingConnectorRegistry(InternalConnectorRegistry):
    def execute(self, *args, **kwargs):
        del args, kwargs
        raise ConnectorStateError("deterministic connector verification failed")


@pytest.mark.anyio
async def test_connector_failure_marks_action_and_run_failed_and_releases_lease(
    tmp_path,
):
    engine, factory = await _database(tmp_path)
    record = await _seed_action(
        factory,
        InternalTaskParameters(
            kind=ActionKind.CREATE_INTERNAL_TASK,
            owner_role="seller-operations",
            due_days=3,
            checklist=("Contact carrier",),
        ),
    )
    times = iter(
        (
            datetime(2026, 7, 19, 17, 1, tzinfo=UTC),
            datetime(2026, 7, 19, 17, 2, tzinfo=UTC),
        )
    )
    service = ActionExecutionService(
        factory,
        storage_root=tmp_path,
        connector_registry=_FailingConnectorRegistry(),
        clock=lambda: next(times),
    )
    started = await service.start(
        record.action.workspace_id,
        record.action.id,
        operation=ActionRunOperation.EXECUTE,
        idempotency_key="execute-failing-task-001",
        actor_id="operator-a",
    )

    result = await service.execute(
        record.action.workspace_id,
        started.run.id,
        worker_id="action-worker-1",
    )

    assert result.run.status is RunStatus.FAILED
    assert result.record.action.status is ActionStatus.FAILED
    assert result.artifact is None
    assert "verification failed" in result.error_message
    events = await SqlDomainEventStore(factory).list_run(
        record.action.workspace_id,
        started.run.id,
    )
    assert events[-1].event_type == "run.lease_released"
    assert "action.execution_failed" in [event.event_type for event in events]
    await engine.dispose()


@pytest.mark.anyio
async def test_external_connector_execution_remains_fail_closed(tmp_path):
    engine, factory = await _database(tmp_path)
    policy = ActionPolicyGate(connector_policy=ConnectorPolicy(allowed_operations={"merchant_ads": frozenset({ExternalOperation.UPDATE_CAMPAIGN_BUDGET})}))
    record = await _seed_action(
        factory,
        ExternalMutationParameters(
            kind=ActionKind.EXTERNAL_MUTATION,
            connector_id="merchant_ads",
            operation=ExternalOperation.UPDATE_CAMPAIGN_BUDGET,
            target_ref_sha256="d" * 64,
            reversible=True,
            dry_run=False,
        ),
        policy_gate=policy,
    )
    service = ActionExecutionService(factory, storage_root=tmp_path)

    with pytest.raises(ActionExecutionError, match="external Connector"):
        await service.start(
            record.action.workspace_id,
            record.action.id,
            operation=ActionRunOperation.EXECUTE,
            idempotency_key="external-execute-001",
            actor_id="operator-a",
        )
    assert (
        await SqlRunRepository(factory).list_case(
            record.action.workspace_id,
            record.action.case_id,
        )
        == ()
    )
    await engine.dispose()
