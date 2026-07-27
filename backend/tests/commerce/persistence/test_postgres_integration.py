"""Real PostgreSQL migration and restart/recovery gate for Commerce state."""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta

import pytest
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
from app.commerce.persistence.migrations import upgrade_commerce_schema
from app.commerce.persistence.runs import SqlRunCheckpointRepository, SqlRunLeaseRepository, SqlRunRepository
from app.commerce.persistence.unit_of_work import SqlCommerceUnitOfWork


def _postgres_url() -> str:
    value = os.environ.get("COMMERCE_TEST_POSTGRES_URL", "").strip()
    if not value:
        pytest.skip("COMMERCE_TEST_POSTGRES_URL is required for the real PostgreSQL gate")
    if not value.startswith("postgresql+"):
        raise AssertionError("COMMERCE_TEST_POSTGRES_URL must use an explicit SQLAlchemy async PostgreSQL driver")
    return value


def _checkpoint(run: CommerceRun, *, iteration: int) -> GoalLoopCheckpoint:
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


@pytest.mark.postgres_integration
@pytest.mark.anyio
async def test_postgres_migration_and_restart_recovers_commerce_run_state():
    """Migrate a real PostgreSQL DB, persist a leased Run, dispose the process
    connection, then recover the latest checkpoint and take over an expired
    lease with a higher fencing token.
    """

    database_url = _postgres_url()
    await asyncio.to_thread(upgrade_commerce_schema, database_url)
    now = datetime.now(UTC).replace(microsecond=0)
    workspace_id = WorkspaceId.new()
    case = Case(
        workspace_id=workspace_id,
        title="PostgreSQL restart recovery gate",
        severity=CaseSeverity.HIGH,
        opened_at=now,
        updated_at=now,
    )
    run = CommerceRun(
        workspace_id=workspace_id,
        case_id=case.id,
        run_type=RunType.CASE_INVESTIGATION,
        phase=RunPhase.PLANNING,
        goal="Recover a durable Commerce Run after a process restart",
        idempotency_key_sha256=("a" * 63) + "1",
        created_at=now,
        updated_at=now,
    )

    engine = create_async_engine(database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
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

    lease = await SqlRunLeaseRepository(factory).acquire(
        workspace_id,
        run.id,
        worker_id="postgres-worker-a",
        ttl=timedelta(seconds=5),
        acquired_at=now + timedelta(seconds=1),
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
    )
    checkpoint, checkpoint_event = await uow.append_run_checkpoint(
        _checkpoint(lease.run, iteration=1),
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
        actor=DomainEventActor.AGENT,
        lease=lease.credentials,
        lease_checked_at=now + timedelta(seconds=2),
    )
    assert checkpoint.sequence == 1
    assert checkpoint_event.event_type == "run.checkpoint_saved"
    await engine.dispose()

    restarted_engine = create_async_engine(database_url, pool_pre_ping=True)
    restarted_factory = async_sessionmaker(restarted_engine, expire_on_commit=False)
    recovered_run = await SqlRunRepository(restarted_factory).get(workspace_id, run.id)
    recovered_checkpoint = await SqlRunCheckpointRepository(restarted_factory).get_latest(workspace_id, run.id)
    recovered_events = await SqlDomainEventStore(restarted_factory).list_run(workspace_id, run.id)

    assert recovered_run is not None
    assert recovered_run.status.value == "running"
    assert recovered_checkpoint == checkpoint
    assert [event.event_type for event in recovered_events] == [
        "run.created",
        "run.status_changed",
        "run.checkpoint_saved",
    ]

    takeover = await SqlRunLeaseRepository(restarted_factory).acquire(
        workspace_id,
        run.id,
        worker_id="postgres-worker-b",
        ttl=timedelta(seconds=5),
        acquired_at=now + timedelta(seconds=7),
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
    )

    assert takeover.reacquired is True
    assert takeover.credentials.fencing_token == 2
    assert takeover.latest_checkpoint == checkpoint
    await restarted_engine.dispose()
