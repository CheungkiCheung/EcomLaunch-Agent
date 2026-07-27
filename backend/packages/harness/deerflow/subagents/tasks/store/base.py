"""Storage contract for durable subagent tasks."""

from __future__ import annotations

import abc
from datetime import datetime
from typing import Any

from ..models import SubagentTask, SubagentTaskEvent


class SubagentTaskStore(abc.ABC):
    @abc.abstractmethod
    async def create(self, task: SubagentTask) -> SubagentTask:
        """Persist a task and its initial ``task.created`` event atomically."""

    @abc.abstractmethod
    async def get(self, task_id: str) -> SubagentTask | None:
        pass

    @abc.abstractmethod
    async def list_by_run(self, run_id: str) -> list[SubagentTask]:
        pass

    @abc.abstractmethod
    async def list_children(self, parent_task_id: str) -> list[SubagentTask]:
        pass

    @abc.abstractmethod
    async def list_inflight(self, *, before: datetime | None = None) -> list[SubagentTask]:
        pass

    @abc.abstractmethod
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
        """Atomically update a task revision and append one lifecycle event."""

    @abc.abstractmethod
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
        """Append an event and advance the task revision exactly once."""

    @abc.abstractmethod
    async def list_events(self, task_id: str) -> list[SubagentTaskEvent]:
        pass
