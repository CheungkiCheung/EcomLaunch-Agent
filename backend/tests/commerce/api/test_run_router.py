"""Investigation Start, Run detail, Checkpoint, and Event HTTP contracts."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.commerce.agents.budget import BudgetSnapshot, BudgetUsage
from app.commerce.agents.contracts import AgentBudgetLimit, PathType
from app.commerce.agents.goal_loop import GoalLoopCheckpoint
from app.commerce.api.dependencies import get_commerce_run_service
from app.commerce.api.router import router
from app.commerce.api.run_service import (
    CommerceRunService,
    ReplanParentStateError,
)
from app.commerce.domain.enums import (
    CaseSeverity,
    RunPhase,
    RunStatus,
    RunType,
)
from app.commerce.domain.events import DomainEventActor
from app.commerce.domain.ids import CorrelationId, RunId, TraceId, WorkspaceId
from app.commerce.domain.models import Case
from app.commerce.persistence.runs import SqlRunRepository
from app.commerce.persistence.schema import create_commerce_schema
from app.commerce.persistence.unit_of_work import SqlCommerceUnitOfWork


async def _app(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'commerce-run-api.db'}")
    await create_commerce_schema(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_commerce_run_service] = lambda: CommerceRunService(factory)
    return app, engine, factory


async def _seed_case(factory, workspace_id: WorkspaceId) -> Case:
    now = datetime(2026, 7, 19, 10, 0, tzinfo=UTC)
    case = Case(
        workspace_id=workspace_id,
        title="Delivery anomaly",
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
    return case


@pytest.mark.anyio
async def test_start_investigation_is_queued_idempotent_and_auditable(tmp_path):
    app, engine, factory = await _app(tmp_path)
    workspace_id = WorkspaceId.new()
    case = await _seed_case(factory, workspace_id)
    headers = {"X-Commerce-Workspace-Id": str(workspace_id)}
    body = {
        "goal": "Explain the delivery anomaly with traceable evidence",
        "idempotency_key": "case-detail-start-001",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        first = await client.post(
            f"/api/commerce/cases/{case.id}/investigations",
            headers=headers,
            json=body,
        )
        second = await client.post(
            f"/api/commerce/cases/{case.id}/investigations",
            headers=headers,
            json=body,
        )
        run_id = first.json()["run"]["id"]
        persisted_run = await SqlRunRepository(factory).get(
            workspace_id,
            RunId(run_id),
        )
        assert persisted_run is not None
        await SqlCommerceUnitOfWork(factory).append_run_checkpoint(
            GoalLoopCheckpoint(
                workspace_id=workspace_id,
                run_id=persisted_run.id,
                case_id=case.id,
                goal=persisted_run.goal,
                loop_iteration=0,
                budget_snapshot=BudgetSnapshot(
                    limit=AgentBudgetLimit(),
                    usage=BudgetUsage(),
                ),
                context_sha256="a" * 64,
                resume_token_sha256="b" * 64,
            ),
            trace_id=TraceId.new(),
            correlation_id=CorrelationId.new(),
            actor=DomainEventActor.AGENT,
        )
        detail = await client.get(
            f"/api/commerce/runs/{run_id}",
            headers=headers,
        )
        events = await client.get(
            f"/api/commerce/runs/{run_id}/events",
            headers=headers,
        )
        checkpoints = await client.get(
            f"/api/commerce/runs/{run_id}/checkpoints",
            headers=headers,
        )
        case_runs = await client.get(
            f"/api/commerce/cases/{case.id}/runs",
            headers=headers,
        )

    assert first.status_code == 201
    assert first.json()["created"] is True
    assert first.json()["run"]["status"] == "queued"
    assert first.json()["run"]["phase"] == "planning"
    assert first.json()["run"]["subject_action_id"] is None
    assert first.json()["run"]["started_at"] is None
    assert first.json()["latest_checkpoint"] is None
    assert second.status_code == 201
    assert second.json()["created"] is False
    assert second.json()["run"]["id"] == run_id
    assert detail.status_code == 200
    assert detail.json()["latest_checkpoint"]["sequence"] == 1
    assert checkpoints.status_code == 200
    assert checkpoints.json()["items"][0]["checkpoint"]["loop_iteration"] == 0
    assert events.status_code == 200
    assert [item["event_type"] for item in events.json()["items"]] == [
        "run.created",
        "run.checkpoint_saved",
    ]
    assert case_runs.status_code == 200
    assert [item["id"] for item in case_runs.json()["items"]] == [run_id]
    await engine.dispose()


@pytest.mark.anyio
async def test_start_rejects_idempotency_key_reuse_with_different_goal(tmp_path):
    app, engine, factory = await _app(tmp_path)
    workspace_id = WorkspaceId.new()
    case = await _seed_case(factory, workspace_id)
    headers = {"X-Commerce-Workspace-Id": str(workspace_id)}

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        first = await client.post(
            f"/api/commerce/cases/{case.id}/investigations",
            headers=headers,
            json={
                "goal": "Explain fulfillment",
                "idempotency_key": "same-start-key",
            },
        )
        conflict = await client.post(
            f"/api/commerce/cases/{case.id}/investigations",
            headers=headers,
            json={
                "goal": "Explain reviews instead",
                "idempotency_key": "same-start-key",
            },
        )

    assert first.status_code == 201
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == "Idempotency key was reused for another goal"
    await engine.dispose()


@pytest.mark.anyio
async def test_start_replan_is_independent_idempotent_and_parent_scoped(tmp_path):
    app, engine, factory = await _app(tmp_path)
    workspace_id = WorkspaceId.new()
    case = await _seed_case(factory, workspace_id)
    service = CommerceRunService(factory)
    parent = await service.start_investigation(
        workspace_id,
        case.id,
        goal="Explain the initial fulfillment anomaly",
        idempotency_key="parent-investigation-key",
    )
    with pytest.raises(ReplanParentStateError):
        await service.start_replan(
            workspace_id,
            parent.run.id,
            goal="Investigate matched peers",
            requested_paths=(PathType.SELLER_PEER,),
            idempotency_key="replan-idempotency-key",
        )

    running = parent.run.transition_to(
        RunStatus.RUNNING,
        occurred_at=parent.run.created_at,
    )
    await SqlRunRepository(factory).save(
        running,
        expected_version=parent.run.version,
    )
    completed = running.transition_to(
        RunStatus.COMPLETED,
        phase=RunPhase.VERIFYING,
        stop_reason="goal_achieved",
        occurred_at=running.updated_at,
    )
    await SqlRunRepository(factory).save(
        completed,
        expected_version=running.version,
    )

    first = await service.start_replan(
        workspace_id,
        parent.run.id,
        goal="Investigate matched peers",
        requested_paths=(PathType.SELLER_PEER,),
        idempotency_key="replan-idempotency-key",
    )
    second = await service.start_replan(
        workspace_id,
        parent.run.id,
        goal="Investigate matched peers",
        requested_paths=(PathType.SELLER_PEER,),
        idempotency_key="replan-idempotency-key",
    )

    assert first.created is True
    assert second.created is False
    assert second.run.id == first.run.id
    assert first.run.run_type is RunType.REPLAN
    assert first.run.parent_run_id == parent.run.id
    assert first.run.requested_paths == (PathType.SELLER_PEER,)
    assert first.run.status is RunStatus.QUEUED
    events = await service.list_run_events(workspace_id, first.run.id)
    assert events[0].event_type == "run.created"
    assert events[0].payload["parent_run_id"] == str(parent.run.id)
    assert events[0].payload["requested_paths"] == [PathType.SELLER_PEER.value]

    headers = {"X-Commerce-Workspace-Id": str(workspace_id)}
    body = {
        "goal": "Investigate reviews as a separate angle",
        "requested_paths": [PathType.REVIEW_EXPERIENCE.value],
        "idempotency_key": "replan-http-idempotency-key",
    }
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        http_first = await client.post(
            f"/api/commerce/runs/{parent.run.id}/replans",
            headers=headers,
            json=body,
        )
        http_second = await client.post(
            f"/api/commerce/runs/{parent.run.id}/replans",
            headers=headers,
            json=body,
        )

    assert http_first.status_code == 201
    assert http_first.json()["created"] is True
    assert http_first.json()["run"]["run_type"] == RunType.REPLAN.value
    assert http_first.json()["run"]["parent_run_id"] == str(parent.run.id)
    assert http_first.json()["run"]["requested_paths"] == [PathType.REVIEW_EXPERIENCE.value]
    assert http_second.status_code == 201
    assert http_second.json()["created"] is False
    assert http_second.json()["run"]["id"] == http_first.json()["run"]["id"]
    await engine.dispose()


@pytest.mark.anyio
async def test_tool_failure_resumes_as_a_new_replan_run_without_resurrecting_parent(
    tmp_path,
):
    _app_instance, engine, factory = await _app(tmp_path)
    workspace_id = WorkspaceId.new()
    case = await _seed_case(factory, workspace_id)
    service = CommerceRunService(factory)
    parent = await service.start_investigation(
        workspace_id,
        case.id,
        goal="Explain fulfillment",
        idempotency_key="tool-failure-parent-001",
    )
    running = parent.run.transition_to(
        RunStatus.RUNNING,
        phase=RunPhase.INVESTIGATING,
        occurred_at=parent.run.created_at,
    )
    await SqlRunRepository(factory).save(
        running,
        expected_version=parent.run.version,
    )
    failed = running.transition_to(
        RunStatus.FAILED,
        stop_reason="tool_failure",
        occurred_at=running.updated_at,
    )
    await SqlRunRepository(factory).save(
        failed,
        expected_version=running.version,
    )

    resumed = await service.start_replan(
        workspace_id,
        failed.id,
        goal="Retry fulfillment after repairing the deterministic Tool",
        requested_paths=(PathType.FULFILLMENT,),
        idempotency_key="tool-failure-replan-001",
    )

    assert resumed.created is True
    assert resumed.run.status is RunStatus.QUEUED
    assert resumed.run.parent_run_id == failed.id
    assert resumed.run.requested_paths == (PathType.FULFILLMENT,)
    assert await service.get_run(workspace_id, failed.id) == failed
    await engine.dispose()


@pytest.mark.anyio
async def test_non_tool_failed_run_is_not_eligible_for_resume_replan(tmp_path):
    _app_instance, engine, factory = await _app(tmp_path)
    workspace_id = WorkspaceId.new()
    case = await _seed_case(factory, workspace_id)
    service = CommerceRunService(factory)
    parent = await service.start_investigation(
        workspace_id,
        case.id,
        goal="Explain fulfillment",
        idempotency_key="generic-failure-parent-001",
    )
    running = parent.run.transition_to(
        RunStatus.RUNNING,
        occurred_at=parent.run.created_at,
    )
    await SqlRunRepository(factory).save(
        running,
        expected_version=parent.run.version,
    )
    failed = running.transition_to(
        RunStatus.FAILED,
        stop_reason="invalid_internal_state",
        occurred_at=running.updated_at,
    )
    await SqlRunRepository(factory).save(
        failed,
        expected_version=running.version,
    )

    with pytest.raises(ReplanParentStateError, match="completed, blocked, or a tool failure"):
        await service.start_replan(
            workspace_id,
            failed.id,
            goal="Retry without a classified failure",
            requested_paths=(PathType.FULFILLMENT,),
            idempotency_key="generic-failure-replan-001",
        )
    await engine.dispose()


@pytest.mark.anyio
async def test_run_api_enforces_workspace_case_and_missing_boundaries(tmp_path):
    app, engine, factory = await _app(tmp_path)
    workspace_id = WorkspaceId.new()
    case = await _seed_case(factory, workspace_id)
    headers = {"X-Commerce-Workspace-Id": str(workspace_id)}
    other_headers = {"X-Commerce-Workspace-Id": str(WorkspaceId.new())}

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        started = await client.post(
            f"/api/commerce/cases/{case.id}/investigations",
            headers=headers,
            json={
                "goal": "Explain fulfillment",
                "idempotency_key": "workspace-boundary-key",
            },
        )
        run_id = started.json()["run"]["id"]
        hidden = await client.get(
            f"/api/commerce/runs/{run_id}",
            headers=other_headers,
        )
        hidden_events = await client.get(
            f"/api/commerce/runs/{run_id}/events",
            headers=other_headers,
        )
        hidden_case_runs = await client.get(
            f"/api/commerce/cases/{case.id}/runs",
            headers=other_headers,
        )
        missing_case = await client.post(
            "/api/commerce/cases/case_00000000000000000000000000000000/investigations",
            headers=headers,
            json={
                "goal": "Investigate",
                "idempotency_key": "missing-case-key",
            },
        )

    assert hidden.status_code == 404
    assert hidden_events.status_code == 404
    assert hidden_case_runs.status_code == 404
    assert missing_case.status_code == 404
    await engine.dispose()
