"""Investigation Start, Run detail, Checkpoint, and Event HTTP contracts."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.commerce.agents.budget import BudgetSnapshot, BudgetUsage
from app.commerce.agents.contracts import AgentBudgetLimit
from app.commerce.agents.goal_loop import GoalLoopCheckpoint
from app.commerce.api.dependencies import get_commerce_run_service
from app.commerce.api.router import router
from app.commerce.api.run_service import CommerceRunService
from app.commerce.domain.enums import CaseSeverity
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
