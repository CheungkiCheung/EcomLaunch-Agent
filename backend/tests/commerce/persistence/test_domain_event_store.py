"""Append-only event sequencing and transactional Case/Event contracts."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.commerce.domain.enums import CaseSeverity, CaseStatus
from app.commerce.domain.events import DomainEventActor, NewDomainEvent, replay_case_projection
from app.commerce.domain.ids import (
    CaseId,
    CorrelationId,
    RunId,
    TraceId,
    WorkspaceId,
)
from app.commerce.domain.models import Case
from app.commerce.persistence.events import (
    DuplicateEventError,
    EventStreamInvariantError,
    SqlDomainEventStore,
)
from app.commerce.persistence.repositories import OptimisticConcurrencyError, SqlCaseRepository
from app.commerce.persistence.schema import create_commerce_schema
from app.commerce.persistence.unit_of_work import SqlCommerceUnitOfWork


async def _storage(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'commerce-events.db'}")
    await create_commerce_schema(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, factory


def _new_event(
    workspace_id: WorkspaceId,
    *,
    case_id: CaseId | None = None,
    run_id: RunId | None = None,
    event_type: str = "case.note_added",
    payload: dict | None = None,
) -> NewDomainEvent:
    return NewDomainEvent(
        workspace_id=workspace_id,
        case_id=case_id,
        run_id=run_id,
        event_type=event_type,
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
        actor=DomainEventActor.SYSTEM,
        payload=payload or {"note": "evidence arrived"},
    )


@pytest.mark.anyio
async def test_event_store_allocates_independent_case_and_run_sequences(tmp_path):
    engine, factory = await _storage(tmp_path)
    store = SqlDomainEventStore(factory)
    workspace_id = WorkspaceId.new()
    case_id = CaseId.new()
    run_id = RunId.new()

    case_first = await store.append(
        _new_event(
            workspace_id,
            case_id=case_id,
            event_type="case.created",
            payload={"title": "Case", "severity": "high", "status": "new", "version": 1},
        )
    )
    both = await store.append(
        _new_event(
            workspace_id,
            case_id=case_id,
            run_id=run_id,
            event_type="run.created",
        )
    )
    run_second = await store.append(_new_event(workspace_id, run_id=run_id, event_type="run.progressed"))

    assert case_first.case_sequence == 1
    assert case_first.run_sequence is None
    assert both.case_sequence == 2
    assert both.run_sequence == 1
    assert run_second.case_sequence is None
    assert run_second.run_sequence == 2
    assert await store.list_case(workspace_id, case_id) == (case_first, both)
    assert await store.list_run(workspace_id, run_id) == (both, run_second)
    assert await store.list_case(WorkspaceId.new(), case_id) == ()
    await engine.dispose()


@pytest.mark.anyio
async def test_event_append_is_idempotent_only_for_the_same_payload(tmp_path):
    engine, factory = await _storage(tmp_path)
    store = SqlDomainEventStore(factory)
    workspace_id = WorkspaceId.new()
    event = _new_event(
        workspace_id,
        case_id=CaseId.new(),
        event_type="case.created",
        payload={"title": "Case", "severity": "high", "status": "new", "version": 1},
    )

    first = await store.append(event)
    same = await store.append(event)

    assert same == first
    with pytest.raises(DuplicateEventError):
        await store.append(event.model_copy(update={"payload": {"note": "different"}}))
    await engine.dispose()


@pytest.mark.anyio
async def test_concurrent_case_appends_preserve_unique_contiguous_sequences(tmp_path):
    engine, factory = await _storage(tmp_path)
    store = SqlDomainEventStore(factory)
    workspace_id = WorkspaceId.new()
    case_id = CaseId.new()
    created = await store.append(
        _new_event(
            workspace_id,
            case_id=case_id,
            event_type="case.created",
            payload={"title": "Case", "severity": "high", "status": "new", "version": 1},
        )
    )
    events = tuple(
        _new_event(
            workspace_id,
            case_id=case_id,
            payload={"note_index": index},
        )
        for index in range(8)
    )

    appended = await asyncio.gather(*(store.append(event) for event in events))

    assert created.case_sequence == 1
    assert sorted(event.case_sequence for event in appended) == list(range(2, 10))
    stored = await store.list_case(workspace_id, case_id)
    assert tuple(event.case_sequence for event in stored) == tuple(range(1, 10))
    await engine.dispose()


@pytest.mark.anyio
async def test_case_stream_cannot_start_without_case_created(tmp_path):
    engine, factory = await _storage(tmp_path)
    store = SqlDomainEventStore(factory)

    with pytest.raises(EventStreamInvariantError, match="first event"):
        await store.append(_new_event(WorkspaceId.new(), case_id=CaseId.new()))

    await engine.dispose()


@pytest.mark.anyio
async def test_run_stream_cannot_start_without_run_created(tmp_path):
    engine, factory = await _storage(tmp_path)
    store = SqlDomainEventStore(factory)

    with pytest.raises(EventStreamInvariantError, match="Run stream"):
        await store.append(
            _new_event(
                WorkspaceId.new(),
                run_id=RunId.new(),
                event_type="run.progressed",
            )
        )

    await engine.dispose()


@pytest.mark.anyio
async def test_unit_of_work_commits_case_and_domain_event_atomically(tmp_path):
    engine, factory = await _storage(tmp_path)
    workspace_id = WorkspaceId.new()
    case = Case(
        workspace_id=workspace_id,
        title="Delivery anomaly",
        severity=CaseSeverity.HIGH,
    )
    trace_id = TraceId.new()
    correlation_id = CorrelationId.new()
    uow = SqlCommerceUnitOfWork(factory)

    created_event = await uow.create_case(
        case,
        trace_id=trace_id,
        correlation_id=correlation_id,
        actor=DomainEventActor.SYSTEM,
    )
    triaged = case.transition_to(CaseStatus.TRIAGED)
    status_event = await uow.save_case(
        triaged,
        expected_version=1,
        trace_id=trace_id,
        correlation_id=correlation_id,
        actor=DomainEventActor.USER,
        causation_event_id=created_event.id,
    )

    repository = SqlCaseRepository(factory)
    event_store = SqlDomainEventStore(factory)
    assert await repository.get(workspace_id, case.id) == triaged
    events = await event_store.list_case(workspace_id, case.id)
    assert tuple(event.event_type for event in events) == (
        "case.created",
        "case.status_changed",
    )
    assert status_event.causation_event_id == created_event.id
    assert replay_case_projection(events).status is CaseStatus.TRIAGED

    with pytest.raises(OptimisticConcurrencyError):
        await uow.save_case(
            triaged.model_copy(update={"summary": "stale", "version": 2}),
            expected_version=1,
            trace_id=trace_id,
            correlation_id=correlation_id,
            actor=DomainEventActor.USER,
        )
    assert len(await event_store.list_case(workspace_id, case.id)) == 2
    await engine.dispose()


@pytest.mark.anyio
async def test_reopen_is_persisted_as_an_explicit_replayable_event(tmp_path):
    engine, factory = await _storage(tmp_path)
    workspace_id = WorkspaceId.new()
    case = Case(
        workspace_id=workspace_id,
        title="Recovered then regressed",
        severity=CaseSeverity.MEDIUM,
    )
    trace_id = TraceId.new()
    correlation_id = CorrelationId.new()
    uow = SqlCommerceUnitOfWork(factory)
    await uow.create_case(
        case,
        trace_id=trace_id,
        correlation_id=correlation_id,
        actor=DomainEventActor.SYSTEM,
    )

    current = case
    for status in (
        CaseStatus.TRIAGED,
        CaseStatus.INVESTIGATING,
        CaseStatus.RESOLVED,
        CaseStatus.REOPENED,
    ):
        previous_version = current.version
        current = current.transition_to(status)
        await uow.save_case(
            current,
            expected_version=previous_version,
            trace_id=trace_id,
            correlation_id=correlation_id,
            actor=DomainEventActor.SYSTEM,
        )

    events = await SqlDomainEventStore(factory).list_case(workspace_id, case.id)

    assert events[-1].event_type == "case.reopened"
    assert replay_case_projection(events).status is CaseStatus.REOPENED
    await engine.dispose()
