"""In-memory durable-task store used in tests and memory deployments."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from ..exceptions import TaskAlreadyExistsError, TaskLeaseConflictError, TaskNotFoundError, TaskVersionConflictError
from ..models import SubagentTask, SubagentTaskEvent, SubagentTaskStatus, utc_now
from .base import SubagentTaskStore

_INFLIGHT_STATUSES = {
    SubagentTaskStatus.queued,
    SubagentTaskStatus.running,
    SubagentTaskStatus.waiting,
    SubagentTaskStatus.waiting_approval,
    SubagentTaskStatus.blocked,
}


class MemorySubagentTaskStore(SubagentTaskStore):
    def __init__(self) -> None:
        self._tasks: dict[str, SubagentTask] = {}
        self._events: dict[str, list[SubagentTaskEvent]] = {}
        self._idempotency: dict[tuple[str, str], SubagentTaskEvent] = {}
        self._lock = asyncio.Lock()

    async def create(self, task: SubagentTask) -> SubagentTask:
        async with self._lock:
            if task.task_id in self._tasks:
                raise TaskAlreadyExistsError(f"Subagent task already exists: {task.task_id}")
            event = SubagentTaskEvent(
                task_id=task.task_id,
                thread_id=task.thread_id,
                run_id=task.run_id,
                seq=1,
                event_type="task.created",
                payload={
                    "status": task.status.value,
                    "subagent_type": task.subagent_type,
                    "parent_task_id": task.parent_task_id,
                    "depends_on": list(task.depends_on),
                },
                idempotency_key="task.created",
                created_at=task.created_at,
            )
            self._tasks[task.task_id] = task
            self._events[task.task_id] = [event]
            self._idempotency[(task.task_id, "task.created")] = event
            return task

    async def get(self, task_id: str) -> SubagentTask | None:
        async with self._lock:
            return self._tasks.get(task_id)

    async def list_by_run(self, run_id: str) -> list[SubagentTask]:
        async with self._lock:
            return sorted(
                (task for task in self._tasks.values() if task.run_id == run_id),
                key=lambda task: (task.created_at, task.task_id),
            )

    async def list_children(self, parent_task_id: str) -> list[SubagentTask]:
        async with self._lock:
            return sorted(
                (task for task in self._tasks.values() if task.parent_task_id == parent_task_id),
                key=lambda task: (task.created_at, task.task_id),
            )

    async def list_inflight(self, *, before: datetime | None = None) -> list[SubagentTask]:
        cutoff = before or utc_now()
        async with self._lock:
            return sorted(
                (task for task in self._tasks.values() if task.status in _INFLIGHT_STATUSES and task.created_at <= cutoff),
                key=lambda task: (task.created_at, task.task_id),
            )

    async def mutate(
        self,
        task_id: str,
        *,
        expected_version: int,
        changes: dict[str, Any],
        event_type: str,
        event_payload: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
        required_lease_token: int | None = None,
        event_created_at: datetime | None = None,
    ) -> SubagentTask:
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise TaskNotFoundError(f"Subagent task not found: {task_id}")
            if idempotency_key and (task_id, idempotency_key) in self._idempotency:
                return task
            if task.version != expected_version:
                raise TaskVersionConflictError(f"Subagent task {task_id} version conflict: expected {expected_version}, found {task.version}")
            if required_lease_token is not None and task.lease_token != required_lease_token:
                raise TaskLeaseConflictError(f"Subagent task {task_id} lease token is stale")

            now = event_created_at or utc_now()
            next_task = task.model_copy(
                update={
                    **changes,
                    "version": task.version + 1,
                    "event_seq": task.event_seq + 1,
                    "updated_at": changes.get("updated_at", now),
                }
            )
            event = SubagentTaskEvent(
                task_id=task.task_id,
                thread_id=task.thread_id,
                run_id=task.run_id,
                seq=next_task.event_seq,
                event_type=event_type,
                payload=event_payload or {},
                idempotency_key=idempotency_key,
                created_at=now,
            )
            self._tasks[task_id] = next_task
            self._events[task_id].append(event)
            if idempotency_key:
                self._idempotency[(task_id, idempotency_key)] = event
            return next_task

    async def append_event(
        self,
        task_id: str,
        *,
        event_type: str,
        payload: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
        required_lease_token: int | None = None,
        created_at: datetime | None = None,
    ) -> SubagentTaskEvent:
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise TaskNotFoundError(f"Subagent task not found: {task_id}")
            if idempotency_key:
                existing = self._idempotency.get((task_id, idempotency_key))
                if existing is not None:
                    return existing
            if required_lease_token is not None and task.lease_token != required_lease_token:
                raise TaskLeaseConflictError(f"Subagent task {task_id} lease token is stale")

            now = created_at or utc_now()
            next_task = task.model_copy(
                update={
                    "version": task.version + 1,
                    "event_seq": task.event_seq + 1,
                    "updated_at": now,
                }
            )
            event = SubagentTaskEvent(
                task_id=task.task_id,
                thread_id=task.thread_id,
                run_id=task.run_id,
                seq=next_task.event_seq,
                event_type=event_type,
                payload=payload or {},
                idempotency_key=idempotency_key,
                created_at=now,
            )
            self._tasks[task_id] = next_task
            self._events[task_id].append(event)
            if idempotency_key:
                self._idempotency[(task_id, idempotency_key)] = event
            return event

    async def list_events(self, task_id: str) -> list[SubagentTaskEvent]:
        async with self._lock:
            return list(self._events.get(task_id, ()))
