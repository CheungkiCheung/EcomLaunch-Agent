"""Workspace-scoped Run, Checkpoint, and atomic Event persistence contracts."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.commerce.agents.budget import BudgetSnapshot, BudgetUsage
from app.commerce.agents.contracts import AgentBudgetLimit
from app.commerce.agents.goal_loop import GoalLoopCheckpoint
from app.commerce.domain.enums import (
    CaseSeverity,
    RunPhase,
    RunStatus,
    RunType,
)
from app.commerce.domain.events import DomainEventActor
from app.commerce.domain.ids import (
    CaseId,
    CorrelationId,
    RunId,
    TraceId,
    WorkspaceId,
)
from app.commerce.domain.models import Case
from app.commerce.domain.runs import CommerceRun
from app.commerce.persistence.events import SqlDomainEventStore
from app.commerce.persistence.repositories import (
    DuplicateEntityError,
    OptimisticConcurrencyError,
)
from app.commerce.persistence.runs import (
    SqlRunCheckpointRepository,
    SqlRunRepository,
)
from app.commerce.persistence.schema import create_commerce_schema
from app.commerce.persistence.unit_of_work import SqlCommerceUnitOfWork


async def _storage(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'commerce-runs.db'}")
    await create_commerce_schema(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, factory


def _case(workspace_id: WorkspaceId, now: datetime) -> Case:
    return Case(
        workspace_id=workspace_id,
        title="Delivery anomaly",
        severity=CaseSeverity.HIGH,
        opened_at=now,
        updated_at=now,
    )


def _run(
    case: Case,
    now: datetime,
    *,
    run_id: RunId | None = None,
    idempotency_key_sha256: str = "a" * 64,
) -> CommerceRun:
    return CommerceRun(
        id=run_id or RunId.new(),
        workspace_id=case.workspace_id,
        case_id=case.id,
        run_type=RunType.CASE_INVESTIGATION,
        phase=RunPhase.PLANNING,
        goal="Explain the anomaly with traceable evidence",
        idempotency_key_sha256=idempotency_key_sha256,
        created_at=now,
        updated_at=now,
    )


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


@pytest.mark.anyio
async def test_run_repository_round_trips_workspace_scope_and_concurrency(tmp_path):
    engine, factory = await _storage(tmp_path)
    now = datetime(2026, 7, 19, 10, 0, tzinfo=UTC)
    case = _case(WorkspaceId.new(), now)
    run = _run(case, now)
    repository = SqlRunRepository(factory)

    await repository.create(run)

    assert await repository.get(run.workspace_id, run.id) == run
    assert await repository.get(WorkspaceId.new(), run.id) is None
    assert await repository.list_case(run.workspace_id, run.case_id) == (run,)
    assert (
        await repository.get_by_idempotency_key(
            run.workspace_id,
            run.case_id,
            run.idempotency_key_sha256,
        )
        == run
    )

    running = run.transition_to(
        RunStatus.RUNNING,
        phase=RunPhase.INVESTIGATING,
        occurred_at=now + timedelta(minutes=1),
    )
    await repository.save(running, expected_version=1)
    with pytest.raises(OptimisticConcurrencyError):
        await repository.save(running, expected_version=1)
    assert await repository.get(run.workspace_id, run.id) == running
    await engine.dispose()


@pytest.mark.anyio
async def test_run_and_created_event_commit_atomically_with_idempotency_guard(tmp_path):
    engine, factory = await _storage(tmp_path)
    now = datetime(2026, 7, 19, 10, 0, tzinfo=UTC)
    workspace_id = WorkspaceId.new()
    case = _case(workspace_id, now)
    run = _run(case, now)
    uow = SqlCommerceUnitOfWork(factory)
    trace_id = TraceId.new()
    correlation_id = CorrelationId.new()
    await uow.create_case(
        case,
        trace_id=trace_id,
        correlation_id=correlation_id,
        actor=DomainEventActor.SYSTEM,
    )

    created = await uow.create_run(
        run,
        trace_id=trace_id,
        correlation_id=correlation_id,
        actor=DomainEventActor.USER,
    )

    assert created.event_type == "run.created"
    assert created.case_sequence == 2
    assert created.run_sequence == 1
    assert await SqlRunRepository(factory).get(workspace_id, run.id) == run
    assert [
        event.event_type
        for event in await SqlDomainEventStore(factory).list_run(workspace_id, run.id)
    ] == ["run.created"]

    duplicate = _run(case, now, run_id=RunId.new())
    with pytest.raises(DuplicateEntityError):
        await uow.create_run(
            duplicate,
            trace_id=trace_id,
            correlation_id=correlation_id,
            actor=DomainEventActor.USER,
        )
    assert await SqlRunRepository(factory).get(workspace_id, duplicate.id) is None
    assert await SqlDomainEventStore(factory).list_run(workspace_id, duplicate.id) == ()
    await engine.dispose()


@pytest.mark.anyio
async def test_checkpoint_and_event_are_append_only_atomic_and_workspace_scoped(tmp_path):
    engine, factory = await _storage(tmp_path)
    now = datetime(2026, 7, 19, 10, 0, tzinfo=UTC)
    workspace_id = WorkspaceId.new()
    case = _case(workspace_id, now)
    run = _run(case, now)
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

    first_record, first_event = await uow.append_run_checkpoint(
        _checkpoint(run, iteration=0),
        trace_id=trace_id,
        correlation_id=correlation_id,
        actor=DomainEventActor.AGENT,
    )
    second_record, second_event = await uow.append_run_checkpoint(
        _checkpoint(run, iteration=1),
        trace_id=trace_id,
        correlation_id=correlation_id,
        actor=DomainEventActor.AGENT,
        causation_event_id=first_event.id,
    )

    checkpoints = SqlRunCheckpointRepository(factory)
    assert first_record.sequence == 1
    assert second_record.sequence == 2
    assert second_event.event_type == "run.checkpoint_saved"
    assert second_event.run_sequence == 3
    assert await checkpoints.get_latest(workspace_id, run.id) == second_record
    assert await checkpoints.list_run(workspace_id, run.id) == (
        first_record,
        second_record,
    )
    assert await checkpoints.list_run(WorkspaceId.new(), run.id) == ()

    mismatched = _checkpoint(run, iteration=2).model_copy(
        update={"case_id": CaseId.new()}
    )
    with pytest.raises(ValueError, match="Checkpoint Case"):
        await uow.append_run_checkpoint(
            mismatched,
            trace_id=trace_id,
            correlation_id=correlation_id,
            actor=DomainEventActor.AGENT,
        )
    assert len(await checkpoints.list_run(workspace_id, run.id)) == 2
    assert len(await SqlDomainEventStore(factory).list_run(workspace_id, run.id)) == 3
    await engine.dispose()


@pytest.mark.anyio
async def test_concurrent_run_creation_preserves_case_and_run_event_sequences(tmp_path):
    engine, factory = await _storage(tmp_path)
    now = datetime(2026, 7, 19, 10, 0, tzinfo=UTC)
    workspace_id = WorkspaceId.new()
    case = _case(workspace_id, now)
    uow = SqlCommerceUnitOfWork(factory)
    trace_id = TraceId.new()
    correlation_id = CorrelationId.new()
    await uow.create_case(
        case,
        trace_id=trace_id,
        correlation_id=correlation_id,
        actor=DomainEventActor.SYSTEM,
    )
    runs = tuple(
        _run(
            case,
            now + timedelta(seconds=index),
            idempotency_key_sha256=f"{index + 1:064x}",
        )
        for index in range(8)
    )

    created = await asyncio.gather(
        *(
            uow.create_run(
                run,
                trace_id=trace_id,
                correlation_id=correlation_id,
                actor=DomainEventActor.USER,
            )
            for run in runs
        )
    )

    assert all(event.run_sequence == 1 for event in created)
    case_events = await SqlDomainEventStore(factory).list_case(workspace_id, case.id)
    assert tuple(event.case_sequence for event in case_events) == tuple(range(1, 10))
    await engine.dispose()
