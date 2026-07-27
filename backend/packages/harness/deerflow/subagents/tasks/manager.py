"""Lifecycle manager for durable Parent–Subagent tasks."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from .exceptions import (
    TaskLeaseConflictError,
    TaskNotFoundError,
    TaskTransitionError,
    TaskVersionConflictError,
)
from .models import ContextPacket, SubagentTask, SubagentTaskEvent, SubagentTaskStatus, TaskLease, utc_now
from .store.base import SubagentTaskStore

_ALLOWED_TRANSITIONS: dict[SubagentTaskStatus, set[SubagentTaskStatus]] = {
    SubagentTaskStatus.queued: {
        SubagentTaskStatus.running,
        SubagentTaskStatus.waiting,
        SubagentTaskStatus.blocked,
        SubagentTaskStatus.cancelled,
    },
    SubagentTaskStatus.running: {
        SubagentTaskStatus.waiting,
        SubagentTaskStatus.waiting_approval,
        SubagentTaskStatus.blocked,
        SubagentTaskStatus.completed,
        SubagentTaskStatus.failed,
        SubagentTaskStatus.cancelled,
        SubagentTaskStatus.timed_out,
    },
    SubagentTaskStatus.waiting: {
        SubagentTaskStatus.queued,
        SubagentTaskStatus.running,
        SubagentTaskStatus.blocked,
        SubagentTaskStatus.failed,
        SubagentTaskStatus.cancelled,
        SubagentTaskStatus.timed_out,
    },
    SubagentTaskStatus.waiting_approval: {
        SubagentTaskStatus.queued,
        SubagentTaskStatus.running,
        SubagentTaskStatus.blocked,
        SubagentTaskStatus.failed,
        SubagentTaskStatus.cancelled,
        SubagentTaskStatus.timed_out,
    },
    SubagentTaskStatus.blocked: {
        SubagentTaskStatus.queued,
        SubagentTaskStatus.running,
        SubagentTaskStatus.failed,
        SubagentTaskStatus.cancelled,
        SubagentTaskStatus.timed_out,
    },
    SubagentTaskStatus.completed: set(),
    SubagentTaskStatus.failed: set(),
    SubagentTaskStatus.cancelled: set(),
    SubagentTaskStatus.timed_out: set(),
}


class SubagentTaskManager:
    """Validates task state and delegates atomic persistence to a store."""

    def __init__(self, store: SubagentTaskStore) -> None:
        self.store = store

    async def create(
        self,
        *,
        thread_id: str,
        run_id: str,
        subagent_type: str,
        description: str,
        context_packet: ContextPacket,
        task_id: str | None = None,
        user_id: str | None = None,
        parent_task_id: str | None = None,
        depends_on: tuple[str, ...] = (),
        tool_policy: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        max_attempts: int = 1,
        priority: int = 0,
        created_at: datetime | None = None,
    ) -> SubagentTask:
        task_id = task_id or str(uuid.uuid4())
        if parent_task_id is not None:
            parent = await self.get(parent_task_id)
            if parent.thread_id != thread_id or parent.user_id != user_id:
                raise ValueError("parent task must belong to the same thread and user")
        for dependency_id in depends_on:
            dependency = await self.get(dependency_id)
            if dependency.thread_id != thread_id or dependency.run_id != run_id:
                raise ValueError("task dependencies must belong to the same thread and run")

        now = created_at or utc_now()
        task = SubagentTask(
            task_id=task_id,
            thread_id=thread_id,
            run_id=run_id,
            user_id=user_id,
            parent_task_id=parent_task_id,
            subagent_type=subagent_type,
            description=description,
            context_packet=context_packet,
            tool_policy=tool_policy or {},
            depends_on=depends_on,
            metadata=metadata or {},
            max_attempts=max_attempts,
            priority=priority,
            created_at=now,
            updated_at=now,
        )
        return await self.store.create(task)

    async def get(self, task_id: str) -> SubagentTask:
        task = await self.store.get(task_id)
        if task is None:
            raise TaskNotFoundError(f"Subagent task not found: {task_id}")
        return task

    async def list_by_run(self, run_id: str) -> list[SubagentTask]:
        return await self.store.list_by_run(run_id)

    async def list_children(self, parent_task_id: str) -> list[SubagentTask]:
        return await self.store.list_children(parent_task_id)

    async def list_inflight(self, *, before: datetime | None = None) -> list[SubagentTask]:
        return await self.store.list_inflight(before=before)

    @staticmethod
    def _validate_transition(task: SubagentTask, to_status: SubagentTaskStatus) -> None:
        if to_status not in _ALLOWED_TRANSITIONS[task.status]:
            raise TaskTransitionError(f"Invalid subagent task transition: {task.status.value} -> {to_status.value}")

    @staticmethod
    def _require_current_lease(task: SubagentTask, lease_token: int | None, now: datetime) -> int | None:
        if task.lease_owner is None:
            if lease_token is not None:
                raise TaskLeaseConflictError(f"Subagent task {task.task_id} has no active lease")
            return None
        if task.lease_expires_at is None or task.lease_expires_at <= now:
            raise TaskLeaseConflictError(f"Subagent task {task.task_id} lease has expired")
        if lease_token != task.lease_token:
            raise TaskLeaseConflictError(f"Subagent task {task.task_id} lease token is stale")
        return task.lease_token

    async def transition(
        self,
        task_id: str,
        to_status: SubagentTaskStatus,
        *,
        expected_version: int | None = None,
        lease_token: int | None = None,
        result: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
        checkpoint: dict[str, Any] | None = None,
        telemetry: dict[str, Any] | None = None,
        wait_reason: str | None = None,
        idempotency_key: str | None = None,
        now: datetime | None = None,
    ) -> SubagentTask:
        current = await self.get(task_id)
        if expected_version is not None and current.version != expected_version:
            raise TaskVersionConflictError(f"Subagent task {task_id} version conflict: expected {expected_version}, found {current.version}")
        self._validate_transition(current, to_status)
        if to_status is SubagentTaskStatus.completed and result is None:
            raise TaskTransitionError("completed subagent task requires a structured result")
        if to_status is SubagentTaskStatus.failed and error is None:
            raise TaskTransitionError("failed subagent task requires a structured error")

        transition_time = now or utc_now()
        required_lease_token = self._require_current_lease(current, lease_token, transition_time)
        changes: dict[str, Any] = {
            "status": to_status,
            "updated_at": transition_time,
        }
        if to_status is SubagentTaskStatus.running:
            changes["started_at"] = current.started_at or transition_time
            changes["wait_reason"] = None
        if to_status.is_terminal:
            changes["completed_at"] = transition_time
            changes["wait_reason"] = None
            changes["lease_owner"] = None
            changes["lease_expires_at"] = None
        if result is not None:
            changes["result"] = result
        if error is not None:
            changes["error"] = error
        if checkpoint is not None:
            changes["checkpoint"] = checkpoint
        if telemetry is not None:
            changes["telemetry"] = {**current.telemetry, **telemetry}
        if wait_reason is not None:
            changes["wait_reason"] = wait_reason

        return await self.store.mutate(
            task_id,
            expected_version=current.version,
            changes=changes,
            event_type=f"task.{to_status.value}",
            event_payload={
                "from_status": current.status.value,
                "to_status": to_status.value,
                "wait_reason": changes.get("wait_reason"),
            },
            idempotency_key=idempotency_key,
            required_lease_token=required_lease_token,
            event_created_at=transition_time,
        )

    async def resume(
        self,
        task_id: str,
        *,
        lease_token: int,
        checkpoint: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> SubagentTask:
        """Resume a paused task under a fresh fencing lease and attempt budget."""
        current = await self.get(task_id)
        if current.status not in {
            SubagentTaskStatus.waiting,
            SubagentTaskStatus.waiting_approval,
            SubagentTaskStatus.blocked,
        }:
            raise TaskTransitionError(
                f"Subagent task {task_id} cannot resume from {current.status.value}"
            )
        if current.attempt >= current.max_attempts:
            raise TaskTransitionError(
                f"Subagent task {task_id} exhausted its attempt budget "
                f"({current.attempt}/{current.max_attempts})"
            )

        resume_time = now or utc_now()
        required_lease_token = self._require_current_lease(
            current,
            lease_token,
            resume_time,
        )
        changes: dict[str, Any] = {
            "status": SubagentTaskStatus.running,
            "attempt": current.attempt + 1,
            "wait_reason": None,
            "updated_at": resume_time,
        }
        if checkpoint is not None:
            changes["checkpoint"] = checkpoint
        return await self.store.mutate(
            task_id,
            expected_version=current.version,
            changes=changes,
            event_type="task.resumed",
            event_payload={
                "from_status": current.status.value,
                "to_status": SubagentTaskStatus.running.value,
                "attempt": current.attempt + 1,
            },
            required_lease_token=required_lease_token,
            event_created_at=resume_time,
        )

    async def acquire_lease(
        self,
        task_id: str,
        *,
        owner: str,
        ttl: timedelta,
        now: datetime | None = None,
    ) -> TaskLease:
        if ttl <= timedelta(0):
            raise ValueError("lease ttl must be positive")
        lease_time = now or utc_now()
        current = await self.get(task_id)
        active = current.lease_owner is not None and current.lease_expires_at is not None and current.lease_expires_at > lease_time
        if active:
            if current.lease_owner != owner:
                raise TaskLeaseConflictError(f"Subagent task {task_id} is leased by {current.lease_owner}")
            return TaskLease(
                task_id=task_id,
                owner=owner,
                token=current.lease_token,
                expires_at=current.lease_expires_at,
                task_version=current.version,
            )

        token = current.lease_token + 1
        expires_at = lease_time + ttl
        try:
            updated = await self.store.mutate(
                task_id,
                expected_version=current.version,
                changes={
                    "lease_owner": owner,
                    "lease_token": token,
                    "lease_expires_at": expires_at,
                    "updated_at": lease_time,
                },
                event_type="task.lease_acquired",
                event_payload={"owner": owner, "token": token, "expires_at": expires_at.isoformat()},
                event_created_at=lease_time,
            )
        except TaskVersionConflictError as exc:
            raise TaskLeaseConflictError(f"Subagent task {task_id} lease was acquired concurrently") from exc
        return TaskLease(
            task_id=task_id,
            owner=owner,
            token=token,
            expires_at=expires_at,
            task_version=updated.version,
        )

    async def renew_lease(
        self,
        task_id: str,
        *,
        owner: str,
        token: int,
        ttl: timedelta,
        now: datetime | None = None,
    ) -> TaskLease:
        if ttl <= timedelta(0):
            raise ValueError("lease ttl must be positive")
        lease_time = now or utc_now()
        current = await self.get(task_id)
        if current.lease_owner != owner or current.lease_token != token or current.lease_expires_at is None or current.lease_expires_at <= lease_time:
            raise TaskLeaseConflictError(f"Subagent task {task_id} lease cannot be renewed")
        expires_at = lease_time + ttl
        updated = await self.store.mutate(
            task_id,
            expected_version=current.version,
            changes={"lease_expires_at": expires_at, "updated_at": lease_time},
            event_type="task.lease_renewed",
            event_payload={"owner": owner, "token": token, "expires_at": expires_at.isoformat()},
            required_lease_token=token,
            event_created_at=lease_time,
        )
        return TaskLease(task_id=task_id, owner=owner, token=token, expires_at=expires_at, task_version=updated.version)

    async def release_lease(
        self,
        task_id: str,
        *,
        owner: str,
        token: int,
        now: datetime | None = None,
    ) -> SubagentTask:
        release_time = now or utc_now()
        current = await self.get(task_id)
        if current.lease_owner != owner or current.lease_token != token:
            raise TaskLeaseConflictError(f"Subagent task {task_id} lease cannot be released")
        return await self.store.mutate(
            task_id,
            expected_version=current.version,
            changes={
                "lease_owner": None,
                "lease_expires_at": None,
                "updated_at": release_time,
            },
            event_type="task.lease_released",
            event_payload={"owner": owner, "token": token},
            required_lease_token=token,
            event_created_at=release_time,
        )

    async def append_event(
        self,
        task_id: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
        *,
        idempotency_key: str | None = None,
        lease_token: int | None = None,
        now: datetime | None = None,
    ) -> SubagentTaskEvent:
        event_time = now or utc_now()
        current = await self.get(task_id)
        required_lease_token = self._require_current_lease(current, lease_token, event_time)
        return await self.store.append_event(
            task_id,
            event_type=event_type,
            payload=payload,
            idempotency_key=idempotency_key,
            required_lease_token=required_lease_token,
            created_at=event_time,
        )

    async def list_events(self, task_id: str) -> list[SubagentTaskEvent]:
        return await self.store.list_events(task_id)

    async def reconcile_orphaned_inflight(
        self,
        *,
        before: datetime,
        reason: str,
    ) -> list[SubagentTask]:
        reconciled: list[SubagentTask] = []
        for task in await self.store.list_inflight(before=before):
            if task.status is not SubagentTaskStatus.running:
                continue
            if task.lease_expires_at is not None and task.lease_expires_at > before:
                continue
            try:
                updated = await self.store.mutate(
                    task.task_id,
                    expected_version=task.version,
                    changes={
                        "status": SubagentTaskStatus.blocked,
                        "wait_reason": reason,
                        "lease_owner": None,
                        "lease_expires_at": None,
                        "updated_at": before,
                    },
                    event_type="task.recovery_blocked",
                    event_payload={
                        "from_status": task.status.value,
                        "to_status": SubagentTaskStatus.blocked.value,
                        "reason": reason,
                        "previous_lease_token": task.lease_token,
                    },
                    event_created_at=before,
                )
            except TaskVersionConflictError:
                continue
            reconciled.append(updated)
        return reconciled
