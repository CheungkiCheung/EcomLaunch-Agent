"""Fenced Commerce Run acquisition, heartbeat, and Checkpoint write contracts."""

from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.commerce.agents.budget import BudgetSnapshot, BudgetUsage
from app.commerce.agents.contracts import AgentBudgetLimit
from app.commerce.agents.goal_loop import GoalLoopCheckpoint
from app.commerce.domain.enums import CaseSeverity, RunPhase, RunType
from app.commerce.domain.events import DomainEventActor
from app.commerce.domain.ids import CorrelationId, TraceId, WorkspaceId
from app.commerce.domain.models import Case
from app.commerce.domain.runs import CommerceRun
from app.commerce.persistence.events import SqlDomainEventStore
from app.commerce.persistence.models import RunLeaseRow
from app.commerce.persistence.runs import (
    RunLeaseConflictError,
    RunLeaseLostError,
    SqlRunCheckpointRepository,
    SqlRunLeaseRepository,
    SqlRunRepository,
)
from app.commerce.persistence.schema import create_commerce_schema
from app.commerce.persistence.unit_of_work import SqlCommerceUnitOfWork


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
