"""Fail-closed reconciliation for unknown external Path outcomes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.commerce.agents.budget import BudgetSnapshot, BudgetUsage
from app.commerce.agents.contracts import AgentBudgetLimit
from app.commerce.agents.goal_loop import GoalLoopCheckpoint
from app.commerce.agents.resume import ResumeDisposition, RunResumeClassifier
from app.commerce.api.dependencies import get_commerce_run_reconciliation_service
from app.commerce.api.router import router
from app.commerce.api.run_reconciliation_service import CommerceRunReconciliationService
from app.commerce.api.run_service import CommerceRunService
from app.commerce.domain.enums import CaseSeverity, RunStatus, SemanticStatus
from app.commerce.domain.events import DomainEventActor, NewDomainEvent
from app.commerce.domain.ids import (
    AgentTaskId,
    CheckpointId,
    CorrelationId,
    EventId,
    EvidenceId,
    MetricObservationId,
    TraceId,
    WorkspaceId,
)
from app.commerce.domain.models import Case, Evidence, EvidenceRelation
from app.commerce.persistence.runs import SqlRunLeaseRepository
from app.commerce.persistence.schema import create_commerce_schema
from app.commerce.persistence.unit_of_work import SqlCommerceUnitOfWork


async def _seed_unknown_outcome(
    factory,
    *,
    now: datetime,
    lease_ttl: timedelta,
    include_partial_evidence: bool = False,
):
    workspace_id = WorkspaceId.new()
    case = Case(
        workspace_id=workspace_id,
        title="Unknown provider outcome",
        severity=CaseSeverity.HIGH,
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
    started = await CommerceRunService(factory, clock=lambda: now).start_investigation(
        workspace_id,
        case.id,
        goal="Explain the fulfillment anomaly",
        idempotency_key="unknown-outcome-run-001",
    )
    grant = await SqlRunLeaseRepository(factory).acquire(
        workspace_id,
        started.run.id,
        worker_id="crashed-worker",
        ttl=lease_ttl,
        acquired_at=now,
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
    )
    task_id = AgentTaskId.new()
    started_event_id = EventId.new()
    checkpoint = GoalLoopCheckpoint(
        workspace_id=workspace_id,
        run_id=started.run.id,
        case_id=case.id,
        goal=started.run.goal,
        loop_iteration=0,
        budget_snapshot=BudgetSnapshot(
            limit=AgentBudgetLimit(),
            usage=BudgetUsage(),
        ),
        active_path_task_ids=(task_id,),
        context_sha256="a" * 64,
    )
    await uow.append_run_checkpoint_with_events(
        checkpoint,
        prior_events=(
            NewDomainEvent(
                id=started_event_id,
                workspace_id=workspace_id,
                case_id=case.id,
                run_id=started.run.id,
                event_type="path.started",
                occurred_at=now,
                trace_id=TraceId.new(),
                correlation_id=CorrelationId.new(),
                actor=DomainEventActor.AGENT,
                payload={
                    "task_id": str(task_id),
                    "path_type": "fulfillment",
                    "context_sha256": "a" * 64,
                },
            ),
        ),
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
        actor=DomainEventActor.AGENT,
        checkpoint_id=CheckpointId.new(),
        checkpoint_event_id=EventId.new(),
        lease=grant.credentials,
        lease_checked_at=now,
    )
    evidence_id = None
    if include_partial_evidence:
        evidence = Evidence(
            workspace_id=workspace_id,
            case_id=case.id,
            summary="A provider Tool result was persisted before the process crashed",
            relation=EvidenceRelation.CONTEXT,
            semantic_status=SemanticStatus.DERIVED,
            confidence=0.7,
            metric_observation_ids=(MetricObservationId.new(),),
        )
        updated_case = case.model_copy(
            update={
                "evidence_ids": (evidence.id,),
                "version": case.version + 1,
            }
        )
        await uow.append_evidence(
            updated_case,
            evidence,
            expected_version=case.version,
            trace_id=TraceId.new(),
            correlation_id=CorrelationId.new(),
            actor=DomainEventActor.AGENT,
            causation_event_id=started_event_id,
            run_id=started.run.id,
            lease=grant.credentials,
            lease_checked_at=now,
        )
        evidence_id = EvidenceId(evidence.id)
    return workspace_id, case, started.run, task_id, evidence_id


@pytest.mark.anyio
async def test_unknown_external_outcome_is_reconciled_without_blind_retry_and_replays_safely(
    tmp_path,
):
    now = datetime(2026, 7, 20, 15, 0, tzinfo=UTC)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'reconciliation.db'}")
    await create_commerce_schema(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    workspace_id, _case, run, task_id, _evidence_id = await _seed_unknown_outcome(
        factory,
        now=now,
        lease_ttl=timedelta(seconds=1),
    )
    service = CommerceRunReconciliationService(
        factory,
        clock=lambda: now + timedelta(seconds=2),
        lease_ttl=timedelta(minutes=5),
    )
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_commerce_run_reconciliation_service] = lambda: service
    headers = {
        "X-Commerce-Workspace-Id": str(workspace_id),
        "X-Commerce-Actor-Id": "incident-reviewer-a",
    }
    body = {
        "decision": "abandon_unknown_outcome",
        "reason": "The provider result cannot be recovered or verified",
        "idempotency_key": "reconcile-unknown-001",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        reconciled = await client.post(
            f"/api/commerce/runs/{run.id}/reconciliations",
            headers=headers,
            json=body,
        )
        replayed = await client.post(
            f"/api/commerce/runs/{run.id}/reconciliations",
            headers=headers,
            json=body,
        )
        conflict = await client.post(
            f"/api/commerce/runs/{run.id}/reconciliations",
            headers=headers,
            json={**body, "reason": "A different resolution"},
        )

    assert reconciled.status_code == 200, reconciled.text
    assert reconciled.json()["run"]["status"] == RunStatus.BLOCKED.value
    assert reconciled.json()["run"]["stop_reason"] == "external_outcome_unknown"
    assert reconciled.json()["latest_checkpoint"]["checkpoint"]["active_path_task_ids"] == []
    assert reconciled.json()["latest_checkpoint"]["checkpoint"]["loop_iteration"] == 1
    assert reconciled.json()["disposition"] == "blocked_for_replan"
    assert reconciled.json()["replayed"] is False
    assert replayed.status_code == 200
    assert replayed.json() == {**reconciled.json(), "replayed": True}
    assert conflict.status_code == 409
    assert "idempotency" in conflict.json()["detail"].lower()

    events = await CommerceRunService(factory).list_run_events(workspace_id, run.id)
    assert [event.event_type for event in events].count("path.blocked") == 1
    blocked = next(event for event in events if event.event_type == "path.blocked")
    assert blocked.payload["task_id"] == str(task_id)
    assert blocked.payload["error_code"] == "external_outcome_unknown"
    assert blocked.payload["retry_requires_new_run"] is True
    assert blocked.payload["actor_id"] == "incident-reviewer-a"
    assert all(event.event_type != "model.assignment" for event in events)

    latest = await CommerceRunService(factory).get_latest_checkpoint(workspace_id, run.id)
    assert latest is not None
    plan = RunResumeClassifier().classify(
        latest_checkpoint=latest,
        run_events=events,
    )
    assert plan.disposition is ResumeDisposition.CONTINUE_AFTER_TERMINAL_PATH
    assert plan.blocked_task_ids == (task_id,)
    await engine.dispose()


@pytest.mark.anyio
async def test_unknown_outcome_reconciliation_refuses_to_steal_a_live_lease(tmp_path):
    now = datetime(2026, 7, 20, 16, 0, tzinfo=UTC)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'live-lease.db'}")
    await create_commerce_schema(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    workspace_id, _case, run, _task_id, _evidence_id = await _seed_unknown_outcome(
        factory,
        now=now,
        lease_ttl=timedelta(minutes=5),
    )
    service = CommerceRunReconciliationService(
        factory,
        clock=lambda: now + timedelta(seconds=1),
        lease_ttl=timedelta(minutes=5),
    )

    with pytest.raises(ValueError, match="owned by another Worker"):
        await service.reconcile_unknown_outcome(
            workspace_id,
            run.id,
            actor_id="incident-reviewer-a",
            reason="The provider result cannot be recovered or verified",
            idempotency_key="reconcile-live-lease-001",
        )
    await engine.dispose()


@pytest.mark.anyio
async def test_partial_evidence_is_verified_and_preserved_when_unknown_outcome_is_reconciled(
    tmp_path,
):
    now = datetime(2026, 7, 20, 17, 0, tzinfo=UTC)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'partial.db'}")
    await create_commerce_schema(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    workspace_id, _case, run, _task_id, evidence_id = await _seed_unknown_outcome(
        factory,
        now=now,
        lease_ttl=timedelta(seconds=1),
        include_partial_evidence=True,
    )
    assert evidence_id is not None

    result = await CommerceRunReconciliationService(
        factory,
        clock=lambda: now + timedelta(seconds=2),
    ).reconcile_unknown_outcome(
        workspace_id,
        run.id,
        actor_id="incident-reviewer-a",
        reason="Preserve partial Evidence but do not infer a completed Path result",
        idempotency_key="reconcile-partial-001",
    )

    assert result.latest_checkpoint.checkpoint.evidence_ids == (evidence_id,)
    events = await CommerceRunService(factory).list_run_events(workspace_id, run.id)
    reconciled = next(event for event in events if event.event_type == "run.reconciled")
    assert reconciled.payload["partial_evidence_ids"] == [str(evidence_id)]
    assert all(event.event_type != "path.completed" for event in events)
    await engine.dispose()


@pytest.mark.anyio
async def test_reconciliation_recovers_after_checkpoint_commit_but_before_run_projection_update(
    tmp_path,
    monkeypatch,
):
    now = datetime(2026, 7, 20, 18, 0, tzinfo=UTC)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'fault.db'}")
    await create_commerce_schema(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    workspace_id, _case, run, task_id, _evidence_id = await _seed_unknown_outcome(
        factory,
        now=now,
        lease_ttl=timedelta(seconds=1),
    )
    first = CommerceRunReconciliationService(
        factory,
        clock=lambda: now + timedelta(seconds=2),
        lease_ttl=timedelta(seconds=1),
    )

    async def fail_projection_update(*args, **kwargs):
        raise RuntimeError("injected projection failure")

    monkeypatch.setattr(first._uow, "save_run", fail_projection_update)
    command = {
        "actor_id": "incident-reviewer-a",
        "reason": "The provider result cannot be recovered or verified",
        "idempotency_key": "reconcile-fault-001",
    }
    with pytest.raises(RuntimeError, match="injected projection failure"):
        await first.reconcile_unknown_outcome(
            workspace_id,
            run.id,
            **command,
        )

    partially_persisted = await CommerceRunService(factory).get_run(
        workspace_id,
        run.id,
    )
    assert partially_persisted is not None
    assert partially_persisted.status is RunStatus.RUNNING
    events_after_failure = await CommerceRunService(factory).list_run_events(
        workspace_id,
        run.id,
    )
    assert [event.event_type for event in events_after_failure].count("run.reconciled") == 1
    assert [event.event_type for event in events_after_failure].count("path.blocked") == 1

    recovered = await CommerceRunReconciliationService(
        factory,
        clock=lambda: now + timedelta(seconds=4),
        lease_ttl=timedelta(minutes=5),
    ).reconcile_unknown_outcome(
        workspace_id,
        run.id,
        **command,
    )

    assert recovered.run.status is RunStatus.BLOCKED
    assert recovered.replayed is True
    final_events = await CommerceRunService(factory).list_run_events(
        workspace_id,
        run.id,
    )
    assert [event.event_type for event in final_events].count("run.reconciled") == 1
    assert [event.event_type for event in final_events].count("path.blocked") == 1
    blocked = next(event for event in final_events if event.event_type == "path.blocked")
    assert blocked.payload["task_id"] == str(task_id)
    await engine.dispose()
