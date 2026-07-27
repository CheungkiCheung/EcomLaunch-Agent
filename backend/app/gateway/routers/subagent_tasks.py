"""Read-only API for durable Subagent tasks and append-only events."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.gateway.authz import require_permission
from app.gateway.deps import get_run_store, get_subagent_task_manager
from deerflow.subagents.tasks import SubagentTask
from deerflow.subagents.tasks.exceptions import TaskNotFoundError

router = APIRouter(prefix="/api", tags=["subagent-tasks"])


async def _resolve_owned_run(run_id: str, request: Request) -> dict:
    run = await get_run_store(request).get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return run


async def _resolve_owned_task(task_id: str, request: Request) -> SubagentTask:
    manager = get_subagent_task_manager(request)
    try:
        task = await manager.get(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Subagent task {task_id} not found",
        ) from exc
    run = await _resolve_owned_run(task.run_id, request)
    if run.get("thread_id") != task.thread_id:
        raise HTTPException(
            status_code=404,
            detail=f"Subagent task {task_id} not found",
        )
    return task


def _serialize_task(task: SubagentTask) -> dict:
    return task.model_dump(mode="json")


@router.get("/runs/{run_id}/subagent-tasks")
@require_permission("runs", "read")
async def list_run_subagent_tasks(run_id: str, request: Request) -> dict:
    """List all durable Subagent tasks belonging to an owned Parent Run."""
    run = await _resolve_owned_run(run_id, request)
    tasks = await get_subagent_task_manager(request).list_by_run(run_id)
    data = [
        _serialize_task(task)
        for task in tasks
        if task.thread_id == run.get("thread_id")
    ]
    return {"data": data}


@router.get("/subagent-tasks/{task_id}")
@require_permission("runs", "read")
async def get_subagent_task(task_id: str, request: Request) -> dict:
    """Return one owned durable task with ContextPacket and telemetry."""
    return _serialize_task(await _resolve_owned_task(task_id, request))


@router.get("/subagent-tasks/{task_id}/events")
@require_permission("runs", "read")
async def list_subagent_task_events(
    task_id: str,
    request: Request,
    after_seq: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=500),
) -> dict:
    """Return append-only lifecycle events after a sequence cursor."""
    task = await _resolve_owned_task(task_id, request)
    events = await get_subagent_task_manager(request).list_events(task.task_id)
    data = [
        event.model_dump(mode="json")
        for event in events
        if event.seq > after_seq
    ][:limit]
    next_after_seq = data[-1]["seq"] if data else after_seq
    return {
        "data": data,
        "next_after_seq": next_after_seq,
        "has_more": any(event.seq > next_after_seq for event in events),
    }
