"""Fenced Commerce Run acquisition, heartbeat, and Checkpoint write contracts."""

from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.commerce.agents.budget import BudgetSnapshot, BudgetUsage
from app.commerce.agents.contracts import AgentBudgetLimit, ModelProfile
from app.commerce.agents.goal_loop import GoalLoopCheckpoint
from app.commerce.agents.model_router import (
    ModelAssignment,
    ModelEffort,
    ModelRole,
    ModelRouteReasonCode,
    build_model_assignment_event,
)
from app.commerce.domain.enums import (
    CaseSeverity,
    HypothesisStatus,
    RunPhase,
    RunType,
    SemanticStatus,
)
from app.commerce.domain.events import DomainEventActor, NewDomainEvent
from app.commerce.domain.ids import (
    CorrelationId,
    EvidenceId,
    HypothesisId,
    MetricObservationId,
    TraceId,
    WorkspaceId,
)
from app.commerce.domain.models import Case, Evidence, EvidenceRelation, Hypothesis
from app.commerce.domain.runs import CommerceRun
from app.commerce.persistence.events import SqlDomainEventStore
from app.commerce.persistence.models import RunLeaseRow
from app.commerce.persistence.repositories import SqlCaseRepository
from app.commerce.persistence.runs import (
    RunLeaseConflictError,
    RunLeaseLostError,
    SqlRunCheckpointRepository,
    SqlRunLeaseRepository,
    SqlRunRepository,
)
from app.commerce.persistence.schema import create_commerce_schema
from app.commerce.persistence.unit_of_work import SqlCommerceUnitOfWork
from app.commerce.persistence.work_records import SqlHypothesisRepository


async def _storage(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'commerce-leases.db'}")
    await create_commerce_schema(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, factory


async def _seed(factory, now: datetime) -> CommerceRun:
    workspace_id = WorkspaceId.new()
    case = Case(
        workspace_id=workspace_id,
        title="Delivery anomaly",
        severity=CaseSeverity.HIGH,
        opened_at=now,
        updated_at=now,
    )
    run = CommerceRun(
        workspace_id=workspace_id,
        case_id=case.id,
        run_type=RunType.CASE_INVESTIGATION,
        phase=RunPhase.PLANNING,
        goal="Explain the anomaly",
        idempotency_key_sha256="a" * 64,
        created_at=now,
        updated_at=now,
    )
    uow = SqlCommerceUnitOfWork(factory)
    trace_id = TraceId.new()
    correlation_id = CorrelationId.new()
    await uow.create_case(
        case,
        trace_id=trace_id,
        correlation_id=correlation_id,
        actor=DomainEventActor.SYSTEM,
    )
    await uow.create_run(
        run,
        trace_id=trace_id,
        correlation_id=correlation_id,
        actor=DomainEventActor.USER,
    )
    return run


def _checkpoint(run: CommerceRun, iteration: int) -> GoalLoopCheckpoint:
    return GoalLoopCheckpoint(
        workspace_id=run.workspace_id,
        run_id=run.id,
        case_id=run.case_id,
        goal=run.goal,
        loop_iteration=iteration,
        budget_snapshot=BudgetSnapshot(
            limit=AgentBudgetLimit(),
            usage=BudgetUsage(iterations=iteration),
        ),
        context_sha256="b" * 64,
        resume_token_sha256="c" * 64,
    )


@pytest.mark.anyio
async def test_first_acquisition_transitions_run_and_stores_only_token_hash(tmp_path):
    engine, factory = await _storage(tmp_path)
    now = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)
    queued = await _seed(factory, now)
    leases = SqlRunLeaseRepository(factory)

    grant = await leases.acquire(
        queued.workspace_id,
        queued.id,
        worker_id="commerce-worker-1",
        ttl=timedelta(seconds=30),
        acquired_at=now + timedelta(seconds=1),
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
    )

    assert grant.run.status.value == "running"
    assert grant.credentials.fencing_token == 1
    assert grant.reacquired is False
    assert grant.latest_checkpoint is None
    stored = await SqlRunRepository(factory).get(queued.workspace_id, queued.id)
    assert stored == grant.run
    raw_token = grant.credentials.lease_token.get_secret_value()
    async with factory() as session:
        row = await session.scalar(
            select(RunLeaseRow).where(RunLeaseRow.run_id == str(queued.id))
        )
    assert row is not None
    assert row.lease_token_sha256 == hashlib.sha256(raw_token.encode()).hexdigest()
    assert row.lease_token_sha256 != raw_token
    events = await SqlDomainEventStore(factory).list_run(queued.workspace_id, queued.id)
    assert [event.event_type for event in events] == [
        "run.created",
        "run.status_changed",
    ]
    await engine.dispose()


@pytest.mark.anyio
async def test_concurrent_acquisition_has_exactly_one_winner(tmp_path):
    engine, factory = await _storage(tmp_path)
    now = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)
    queued = await _seed(factory, now)
    leases = SqlRunLeaseRepository(factory)

    results = await asyncio.gather(
        *(
            leases.acquire(
                queued.workspace_id,
                queued.id,
                worker_id=f"worker-{index}",
                ttl=timedelta(seconds=30),
                acquired_at=now + timedelta(seconds=1),
                trace_id=TraceId.new(),
                correlation_id=CorrelationId.new(),
            )
            for index in range(10)
        ),
        return_exceptions=True,
    )

    winners = [result for result in results if not isinstance(result, Exception)]
    conflicts = [result for result in results if isinstance(result, RunLeaseConflictError)]
    assert len(winners) == 1
    assert len(conflicts) == 9
    await engine.dispose()


@pytest.mark.anyio
async def test_expired_lease_reacquires_with_fencing_and_restores_latest_checkpoint(tmp_path):
    engine, factory = await _storage(tmp_path)
    now = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)
    queued = await _seed(factory, now)
    leases = SqlRunLeaseRepository(factory)
    uow = SqlCommerceUnitOfWork(factory)
    first = await leases.acquire(
        queued.workspace_id,
        queued.id,
        worker_id="worker-old",
        ttl=timedelta(seconds=30),
        acquired_at=now,
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
    )
    await uow.append_run_checkpoint(
        _checkpoint(first.run, 0),
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
        actor=DomainEventActor.AGENT,
        lease=first.credentials,
        lease_checked_at=now + timedelta(seconds=1),
    )

    second = await leases.acquire(
        queued.workspace_id,
        queued.id,
        worker_id="worker-new",
        ttl=timedelta(seconds=30),
        acquired_at=now + timedelta(seconds=31),
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
    )

    assert second.reacquired is True
    assert second.credentials.fencing_token == 2
    assert second.latest_checkpoint is not None
    assert second.latest_checkpoint.sequence == 1
    assert second.latest_checkpoint.checkpoint.loop_iteration == 0

    with pytest.raises(RunLeaseLostError):
        await leases.heartbeat(
            queued.workspace_id,
            queued.id,
            first.credentials,
            ttl=timedelta(seconds=30),
            heartbeat_at=now + timedelta(seconds=32),
        )
    with pytest.raises(RunLeaseLostError):
        await uow.append_run_checkpoint(
            _checkpoint(second.run, 1),
            trace_id=TraceId.new(),
            correlation_id=CorrelationId.new(),
            actor=DomainEventActor.AGENT,
            lease=first.credentials,
            lease_checked_at=now + timedelta(seconds=32),
        )
    assert len(
        await SqlRunCheckpointRepository(factory).list_run(
            queued.workspace_id,
            queued.id,
        )
    ) == 1

    heartbeat = await leases.heartbeat(
        queued.workspace_id,
        queued.id,
        second.credentials,
        ttl=timedelta(seconds=30),
        heartbeat_at=now + timedelta(seconds=32),
    )
    assert heartbeat.expires_at == now + timedelta(seconds=62)
    await engine.dispose()


@pytest.mark.anyio
async def test_model_assignment_and_pre_call_checkpoint_commit_atomically_under_lease(
    tmp_path,
):
    engine, factory = await _storage(tmp_path)
    now = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)
    queued = await _seed(factory, now)
    grant = await SqlRunLeaseRepository(factory).acquire(
        queued.workspace_id,
        queued.id,
        worker_id="worker-planner",
        ttl=timedelta(seconds=30),
        acquired_at=now + timedelta(seconds=1),
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
    )
    trace_id = TraceId.new()
    correlation_id = CorrelationId.new()
    assignment = ModelAssignment(
        role=ModelRole.PATH,
        base_profile=ModelProfile.BALANCED_TOOL_USER,
        profile=ModelProfile.BALANCED_TOOL_USER,
        model_alias="deepseek-reasoner",
        effort=ModelEffort.MEDIUM,
        max_output_tokens=1_600,
        timeout_seconds=120,
        reason_codes=frozenset({ModelRouteReasonCode.PROFILE_BINDING}),
        escalation_count=0,
    )
    assigned = build_model_assignment_event(
        assignment,
        workspace_id=queued.workspace_id,
        case_id=queued.case_id,
        run_id=queued.id,
        trace_id=trace_id,
        correlation_id=correlation_id,
    )

    record, events = await SqlCommerceUnitOfWork(
        factory
    ).append_run_checkpoint_with_events(
        _checkpoint(grant.run, 0),
        prior_events=(assigned,),
        trace_id=trace_id,
        correlation_id=correlation_id,
        actor=DomainEventActor.AGENT,
        lease=grant.credentials,
        lease_checked_at=now + timedelta(seconds=2),
    )

    assert record.sequence == 1
    assert [event.event_type for event in events] == [
        "model.assigned",
        "run.checkpoint_saved",
    ]
    assert [
        event.event_type
        for event in await SqlDomainEventStore(factory).list_run(
            queued.workspace_id,
            queued.id,
        )
    ] == [
        "run.created",
        "run.status_changed",
        "model.assigned",
        "run.checkpoint_saved",
    ]
    await engine.dispose()


@pytest.mark.anyio
async def test_path_evidence_write_requires_current_fenced_lease(tmp_path):
    engine, factory = await _storage(tmp_path)
    now = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)
    queued = await _seed(factory, now)
    first = await SqlRunLeaseRepository(factory).acquire(
        queued.workspace_id,
        queued.id,
        worker_id="worker-evidence",
        ttl=timedelta(seconds=30),
        acquired_at=now + timedelta(seconds=1),
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
    )
    evidence = Evidence(
        id=EvidenceId.new(),
        workspace_id=queued.workspace_id,
        case_id=queued.case_id,
        summary="Transit time increased in the current window",
        relation=EvidenceRelation.CONTEXT,
        semantic_status=SemanticStatus.DERIVED,
        confidence=0.9,
        metric_observation_ids=(MetricObservationId.new(),),
    )
    case = await SqlCaseRepository(factory).get(queued.workspace_id, queued.case_id)
    assert case is not None
    updated_case = case.model_copy(
        update={"evidence_ids": (evidence.id,), "version": case.version + 1}
    )
    uow = SqlCommerceUnitOfWork(factory)

    with pytest.raises(RunLeaseLostError, match="requires a lease"):
        await uow.append_evidence(
            updated_case,
            evidence,
            expected_version=case.version,
            trace_id=TraceId.new(),
            correlation_id=CorrelationId.new(),
            actor=DomainEventActor.AGENT,
            run_id=queued.id,
        )

    second = await SqlRunLeaseRepository(factory).acquire(
        queued.workspace_id,
        queued.id,
        worker_id="worker-evidence-takeover",
        ttl=timedelta(seconds=30),
        acquired_at=now + timedelta(seconds=31),
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
    )
    with pytest.raises(RunLeaseLostError):
        await uow.append_evidence(
            updated_case,
            evidence,
            expected_version=case.version,
            trace_id=TraceId.new(),
            correlation_id=CorrelationId.new(),
            actor=DomainEventActor.AGENT,
            run_id=queued.id,
            lease=first.credentials,
            lease_checked_at=now + timedelta(seconds=32),
        )

    event = await uow.append_evidence(
        updated_case,
        evidence,
        expected_version=case.version,
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
        actor=DomainEventActor.AGENT,
        run_id=queued.id,
        lease=second.credentials,
        lease_checked_at=now + timedelta(seconds=32),
    )

    assert event.event_type == "evidence.appended"
    assert event.run_id == queued.id
    await engine.dispose()


@pytest.mark.anyio
async def test_lead_hypothesis_batch_and_completion_event_require_current_lease(
    tmp_path,
):
    engine, factory = await _storage(tmp_path)
    now = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)
    queued = await _seed(factory, now)
    leases = SqlRunLeaseRepository(factory)
    first = await leases.acquire(
        queued.workspace_id,
        queued.id,
        worker_id="worker-lead-old",
        ttl=timedelta(seconds=30),
        acquired_at=now + timedelta(seconds=1),
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
    )
    case = await SqlCaseRepository(factory).get(queued.workspace_id, queued.case_id)
    assert case is not None
    hypotheses = tuple(
        Hypothesis(
            id=HypothesisId.new(),
            workspace_id=queued.workspace_id,
            case_id=queued.case_id,
            statement=statement,
            status=HypothesisStatus.PROPOSED,
            confidence=confidence,
        )
        for statement, confidence in (
            ("Seller handling did not worsen", 0.9),
            ("Carrier transit time worsened", 0.94),
        )
    )
    updated_case = case.model_copy(
        update={
            "hypothesis_ids": tuple(item.id for item in hypotheses),
            "updated_at": now + timedelta(seconds=32),
            "version": case.version + 1,
        }
    )
    trace_id = TraceId.new()
    correlation_id = CorrelationId.new()
    lead_completed = NewDomainEvent(
        workspace_id=queued.workspace_id,
        case_id=queued.case_id,
        run_id=queued.id,
        event_type="lead.completed",
        trace_id=trace_id,
        correlation_id=correlation_id,
        actor=DomainEventActor.AGENT,
        payload={"result_sha256": "d" * 64, "claim_count": 2},
    )
    uow = SqlCommerceUnitOfWork(factory)

    with pytest.raises(RunLeaseLostError, match="requires a lease"):
        await uow.append_hypothesis_versions_with_events(
            updated_case,
            hypotheses,
            expected_version=case.version,
            prior_events=(lead_completed,),
            trace_id=trace_id,
            correlation_id=correlation_id,
            actor=DomainEventActor.AGENT,
            run_id=queued.id,
        )

    second = await leases.acquire(
        queued.workspace_id,
        queued.id,
        worker_id="worker-lead-new",
        ttl=timedelta(seconds=30),
        acquired_at=now + timedelta(seconds=31),
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
    )
    with pytest.raises(RunLeaseLostError):
        await uow.append_hypothesis_versions_with_events(
            updated_case,
            hypotheses,
            expected_version=case.version,
            prior_events=(lead_completed,),
            trace_id=trace_id,
            correlation_id=correlation_id,
            actor=DomainEventActor.AGENT,
            run_id=queued.id,
            lease=first.credentials,
            lease_checked_at=now + timedelta(seconds=32),
        )

    events = await uow.append_hypothesis_versions_with_events(
        updated_case,
        hypotheses,
        expected_version=case.version,
        prior_events=(lead_completed,),
        trace_id=trace_id,
        correlation_id=correlation_id,
        actor=DomainEventActor.AGENT,
        run_id=queued.id,
        lease=second.credentials,
        lease_checked_at=now + timedelta(seconds=32),
    )

    assert [event.event_type for event in events] == [
        "lead.completed",
        "hypothesis.version_appended",
        "hypothesis.version_appended",
    ]
    assert all(event.run_id == queued.id for event in events)
    assert await SqlCaseRepository(factory).get(
        queued.workspace_id, queued.case_id
    ) == updated_case
    repository = SqlHypothesisRepository(factory)
    assert tuple(
        await asyncio.gather(
            *(
                repository.get_latest(queued.workspace_id, item.id)
                for item in hypotheses
            )
        )
    ) == hypotheses
    await engine.dispose()
