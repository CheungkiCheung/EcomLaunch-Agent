"""Append-only Evidence and versioned Hypothesis persistence contracts."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.commerce.domain.enums import (
    CaseSeverity,
    HypothesisStatus,
    SemanticStatus,
)
from app.commerce.domain.events import DomainEventActor, replay_case_projection
from app.commerce.domain.ids import (
    CaseId,
    CorrelationId,
    EvidenceId,
    FactId,
    HypothesisId,
    MetricObservationId,
    TraceId,
    WorkspaceId,
)
from app.commerce.domain.models import (
    Case,
    Evidence,
    EvidenceRelation,
    Hypothesis,
)
from app.commerce.persistence.events import SqlDomainEventStore
from app.commerce.persistence.repositories import (
    OptimisticConcurrencyError,
    SqlCaseRepository,
)
from app.commerce.persistence.schema import create_commerce_schema
from app.commerce.persistence.unit_of_work import SqlCommerceUnitOfWork
from app.commerce.persistence.work_records import (
    HypothesisVersionConflictError,
    ImmutableRecordConflictError,
    SqlEvidenceRepository,
    SqlHypothesisRepository,
)


async def _storage(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'commerce-work.db'}")
    await create_commerce_schema(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, factory


def _case(workspace_id: WorkspaceId) -> Case:
    now = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
    return Case(
        workspace_id=workspace_id,
        title="Delivery anomaly",
        severity=CaseSeverity.HIGH,
        opened_at=now,
        updated_at=now,
    )


def _evidence(workspace_id: WorkspaceId, case_id: CaseId) -> Evidence:
    return Evidence(
        workspace_id=workspace_id,
        case_id=case_id,
        summary="Transit time increased while handling time did not",
        relation=EvidenceRelation.SUPPORTS,
        semantic_status=SemanticStatus.DERIVED,
        confidence=0.92,
        fact_ids=(FactId.new(),),
        metric_observation_ids=(MetricObservationId.new(),),
    )


def _hypothesis(
    workspace_id: WorkspaceId,
    case_id: CaseId,
    *,
    hypothesis_id: HypothesisId | None = None,
    version: int = 1,
    status: HypothesisStatus = HypothesisStatus.PROPOSED,
    supporting_evidence_ids: tuple[EvidenceId, ...] = (),
) -> Hypothesis:
    return Hypothesis(
        id=hypothesis_id or HypothesisId.new(),
        workspace_id=workspace_id,
        case_id=case_id,
        statement="Carrier transit degradation is the leading explanation",
        status=status,
        confidence=0.7,
        supporting_evidence_ids=supporting_evidence_ids,
        version=version,
    )


@pytest.mark.anyio
async def test_evidence_is_append_only_idempotent_and_workspace_scoped(tmp_path):
    engine, factory = await _storage(tmp_path)
    workspace_id = WorkspaceId.new()
    evidence = _evidence(workspace_id, CaseId.new())
    repository = SqlEvidenceRepository(factory)

    await repository.append(evidence)
    await repository.append(evidence)

    assert await repository.get(workspace_id, evidence.id) == evidence
    assert await repository.get(WorkspaceId.new(), evidence.id) is None
    assert await repository.list_case(workspace_id, evidence.case_id) == (evidence,)
    with pytest.raises(ImmutableRecordConflictError):
        await repository.append(evidence.model_copy(update={"summary": "rewritten"}))
    await engine.dispose()


@pytest.mark.anyio
async def test_hypothesis_versions_are_contiguous_and_latest_is_explicit(tmp_path):
    engine, factory = await _storage(tmp_path)
    workspace_id = WorkspaceId.new()
    case_id = CaseId.new()
    repository = SqlHypothesisRepository(factory)
    first = _hypothesis(workspace_id, case_id)
    second = _hypothesis(
        workspace_id,
        case_id,
        hypothesis_id=first.id,
        version=2,
        status=HypothesisStatus.INVESTIGATING,
    )

    await repository.append_version(first)
    await repository.append_version(second)

    assert await repository.list_versions(workspace_id, first.id) == (first, second)
    assert await repository.get_latest(workspace_id, first.id) == second
    with pytest.raises(HypothesisVersionConflictError, match="expected version 3"):
        await repository.append_version(second.model_copy(update={"version": 4}))
    with pytest.raises(ImmutableRecordConflictError):
        await repository.append_version(second.model_copy(update={"statement": "rewritten"}))
    await engine.dispose()


@pytest.mark.anyio
async def test_evidence_uow_updates_case_and_event_stream_atomically(tmp_path):
    engine, factory = await _storage(tmp_path)
    workspace_id = WorkspaceId.new()
    case = _case(workspace_id)
    evidence = _evidence(workspace_id, case.id)
    trace_id = TraceId.new()
    correlation_id = CorrelationId.new()
    uow = SqlCommerceUnitOfWork(factory)
    await uow.create_case(
        case,
        trace_id=trace_id,
        correlation_id=correlation_id,
        actor=DomainEventActor.SYSTEM,
    )
    updated_case = case.model_copy(
        update={
            "evidence_ids": (evidence.id,),
            "version": 2,
            "updated_at": datetime(2026, 7, 18, 12, 5, tzinfo=UTC),
        }
    )

    appended = await uow.append_evidence(
        updated_case,
        evidence,
        expected_version=1,
        trace_id=trace_id,
        correlation_id=correlation_id,
        actor=DomainEventActor.AGENT,
    )

    assert appended.event_type == "evidence.appended"
    assert await SqlCaseRepository(factory).get(workspace_id, case.id) == updated_case
    assert await SqlEvidenceRepository(factory).get(workspace_id, evidence.id) == evidence
    events = await SqlDomainEventStore(factory).list_case(workspace_id, case.id)
    assert replay_case_projection(events).version == 2
    await engine.dispose()


@pytest.mark.anyio
async def test_evidence_batch_uow_updates_case_once_and_emits_one_event_per_record(
    tmp_path,
):
    engine, factory = await _storage(tmp_path)
    workspace_id = WorkspaceId.new()
    case = _case(workspace_id)
    first = _evidence(workspace_id, case.id)
    second = _evidence(workspace_id, case.id)
    trace_id = TraceId.new()
    correlation_id = CorrelationId.new()
    uow = SqlCommerceUnitOfWork(factory)
    await uow.create_case(
        case,
        trace_id=trace_id,
        correlation_id=correlation_id,
        actor=DomainEventActor.SYSTEM,
    )
    updated_case = case.model_copy(
        update={
            "evidence_ids": (first.id, second.id),
            "version": case.version + 1,
            "updated_at": datetime(2026, 7, 18, 12, 5, tzinfo=UTC),
        }
    )

    appended = await uow.append_evidence_batch(
        updated_case,
        (first, second),
        expected_version=case.version,
        trace_id=trace_id,
        correlation_id=correlation_id,
        actor=DomainEventActor.AGENT,
    )

    assert [event.event_type for event in appended] == [
        "evidence.appended",
        "evidence.appended",
    ]
    assert [event.payload["evidence_id"] for event in appended] == [
        str(first.id),
        str(second.id),
    ]
    assert {event.payload["case_version"] for event in appended} == {
        updated_case.version
    }
    assert await SqlCaseRepository(factory).get(workspace_id, case.id) == updated_case
    assert await SqlEvidenceRepository(factory).list_case(workspace_id, case.id) == (
        first,
        second,
    )
    events = await SqlDomainEventStore(factory).list_case(workspace_id, case.id)
    assert replay_case_projection(events).version == updated_case.version
    await engine.dispose()


@pytest.mark.anyio
async def test_evidence_batch_uow_rolls_back_every_record_on_case_conflict(tmp_path):
    engine, factory = await _storage(tmp_path)
    workspace_id = WorkspaceId.new()
    case = _case(workspace_id)
    first = _evidence(workspace_id, case.id)
    second = _evidence(workspace_id, case.id)
    trace_id = TraceId.new()
    correlation_id = CorrelationId.new()
    uow = SqlCommerceUnitOfWork(factory)
    await uow.create_case(
        case,
        trace_id=trace_id,
        correlation_id=correlation_id,
        actor=DomainEventActor.SYSTEM,
    )
    invalid_update = case.model_copy(
        update={
            "evidence_ids": (first.id, second.id),
            "version": case.version + 2,
        }
    )

    with pytest.raises(ValueError, match="expected_version \+ 1"):
        await uow.append_evidence_batch(
            invalid_update,
            (first, second),
            expected_version=case.version,
            trace_id=trace_id,
            correlation_id=correlation_id,
            actor=DomainEventActor.AGENT,
        )

    assert await SqlEvidenceRepository(factory).list_case(workspace_id, case.id) == ()
    assert await SqlCaseRepository(factory).get(workspace_id, case.id) == case
    assert len(await SqlDomainEventStore(factory).list_case(workspace_id, case.id)) == 1
    await engine.dispose()


@pytest.mark.anyio
async def test_hypothesis_uow_appends_versions_and_preserves_case_membership(tmp_path):
    engine, factory = await _storage(tmp_path)
    workspace_id = WorkspaceId.new()
    case = _case(workspace_id)
    trace_id = TraceId.new()
    correlation_id = CorrelationId.new()
    uow = SqlCommerceUnitOfWork(factory)
    await uow.create_case(
        case,
        trace_id=trace_id,
        correlation_id=correlation_id,
        actor=DomainEventActor.SYSTEM,
    )
    evidence = _evidence(workspace_id, case.id)
    case_with_evidence = case.model_copy(
        update={"evidence_ids": (evidence.id,), "version": 2}
    )
    await uow.append_evidence(
        case_with_evidence,
        evidence,
        expected_version=1,
        trace_id=trace_id,
        correlation_id=correlation_id,
        actor=DomainEventActor.AGENT,
    )
    first = _hypothesis(
        workspace_id,
        case.id,
        supporting_evidence_ids=(evidence.id,),
    )
    case_with_hypothesis = case_with_evidence.model_copy(
        update={"hypothesis_ids": (first.id,), "version": 3}
    )
    await uow.append_hypothesis_version(
        case_with_hypothesis,
        first,
        expected_version=2,
        trace_id=trace_id,
        correlation_id=correlation_id,
        actor=DomainEventActor.AGENT,
    )
    second = first.model_copy(
        update={
            "version": 2,
            "status": HypothesisStatus.SUPPORTED,
            "confidence": 0.9,
        }
    )
    latest_case = case_with_hypothesis.model_copy(update={"version": 4})

    event = await uow.append_hypothesis_version(
        latest_case,
        second,
        expected_version=3,
        trace_id=trace_id,
        correlation_id=correlation_id,
        actor=DomainEventActor.AGENT,
    )

    assert event.event_type == "hypothesis.version_appended"
    assert await SqlHypothesisRepository(factory).get_latest(workspace_id, first.id) == second
    stored_case = await SqlCaseRepository(factory).get(workspace_id, case.id)
    assert stored_case.hypothesis_ids == (first.id,)
    assert stored_case.version == 4
    await engine.dispose()


@pytest.mark.anyio
async def test_evidence_uow_rolls_back_record_when_case_update_fails(tmp_path):
    engine, factory = await _storage(tmp_path)
    workspace_id = WorkspaceId.new()
    case = _case(workspace_id)
    evidence = _evidence(workspace_id, case.id)
    trace_id = TraceId.new()
    correlation_id = CorrelationId.new()
    uow = SqlCommerceUnitOfWork(factory)
    await uow.create_case(
        case,
        trace_id=trace_id,
        correlation_id=correlation_id,
        actor=DomainEventActor.SYSTEM,
    )

    updated_case = case.model_copy(
        update={"evidence_ids": (evidence.id,), "version": 3}
    )
    with pytest.raises(OptimisticConcurrencyError):
        await uow.append_evidence(
            updated_case,
            evidence,
            expected_version=2,
            trace_id=trace_id,
            correlation_id=correlation_id,
            actor=DomainEventActor.AGENT,
        )

    assert await SqlEvidenceRepository(factory).get(workspace_id, evidence.id) is None
    assert await SqlCaseRepository(factory).get(workspace_id, case.id) == case
    assert len(await SqlDomainEventStore(factory).list_case(workspace_id, case.id)) == 1
    await engine.dispose()
