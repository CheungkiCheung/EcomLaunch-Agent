"""Read API for durable Subagent tasks and append-only events."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from _router_auth_helpers import make_authed_test_app
from fastapi.testclient import TestClient

from app.gateway.routers import subagent_tasks
from deerflow.subagents.tasks import (
    ContextPacket,
    MemorySubagentTaskStore,
    SubagentTaskManager,
    SubagentTaskStatus,
)


async def _seed(manager: SubagentTaskManager) -> None:
    await manager.create(
        task_id="task-1",
        thread_id="thread-1",
        run_id="run-1",
        user_id="user-1",
        subagent_type="analyst",
        description="分析履约异常",
        context_packet=ContextPacket(
            goal="定位履约异常",
            available_skills=("fulfillment-investigation",),
            available_tools=("metric_query",),
        ),
    )
    await manager.transition("task-1", SubagentTaskStatus.running)
    await manager.append_event(
        "task-1",
        "task.progress",
        {"message": "正在计算承运阶段贡献"},
    )


@pytest.fixture
def client():
    manager = SubagentTaskManager(MemorySubagentTaskStore())
    import anyio

    anyio.run(_seed, manager)
    app = make_authed_test_app()
    app.include_router(subagent_tasks.router)
    app.state.subagent_task_manager = manager
    run_store = MagicMock()
    run_store.get = AsyncMock(
        side_effect=lambda run_id: (
            {"run_id": "run-1", "thread_id": "thread-1"}
            if run_id == "run-1"
            else None
        )
    )
    app.state.run_store = run_store
    with TestClient(app) as test_client:
        yield test_client


def test_list_tasks_for_owned_run(client):
    response = client.get("/api/runs/run-1/subagent-tasks")

    assert response.status_code == 200
    body = response.json()
    assert body["data"][0]["task_id"] == "task-1"
    assert body["data"][0]["status"] == "running"
    assert body["data"][0]["context_packet"]["available_skills"] == [
        "fulfillment-investigation"
    ]


def test_get_task_and_incremental_events(client):
    detail = client.get("/api/subagent-tasks/task-1")
    events = client.get("/api/subagent-tasks/task-1/events?after_seq=2")

    assert detail.status_code == 200
    assert detail.json()["description"] == "分析履约异常"
    assert events.status_code == 200
    assert [event["event_type"] for event in events.json()["data"]] == [
        "task.progress"
    ]
    assert events.json()["next_after_seq"] == 3


def test_task_read_returns_404_when_parent_run_is_not_owned(client):
    client.app.state.run_store.get = AsyncMock(return_value=None)

    response = client.get("/api/subagent-tasks/task-1")

    assert response.status_code == 404
