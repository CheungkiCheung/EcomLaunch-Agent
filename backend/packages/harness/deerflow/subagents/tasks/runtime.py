"""Runtime bridge from durable tasks to the legacy in-process executor.

``SubagentTask`` is the authoritative state.  ``SubagentExecutor`` remains an
execution adapter while DeerFlow transitions away from its process-local
``_background_tasks`` registry.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import Callable, Sequence
from datetime import timedelta
from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict

from .exceptions import TaskAlreadyExistsError, TaskNotFoundError, TaskTransitionError
from .manager import SubagentTaskManager
from .models import ContextPacket, SubagentTask, SubagentTaskStatus, utc_now

logger = logging.getLogger(__name__)


class BackgroundSubagentExecutor(Protocol):
    """Small executor surface required by the durable runtime."""

    config: Any

    def execute_async(self, task: str, task_id: str | None = None) -> str: ...


class BackgroundSubagentResult(Protocol):
    task_id: str
    trace_id: str
    status: Any
    result: str | None
    error: str | None
    token_usage_records: list[dict[str, Any]]


class TaskWaitMode(StrEnum):
    one = "one"
    any = "any"
    all = "all"


class TaskWaitResult(BaseModel):
    """Structured result returned by a single durable wait operation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: TaskWaitMode
    ready: bool
    timed_out: bool
    tasks: tuple[SubagentTask, ...]


_SETTLED_STATUSES = {
    SubagentTaskStatus.waiting,
    SubagentTaskStatus.waiting_approval,
    SubagentTaskStatus.blocked,
    SubagentTaskStatus.completed,
    SubagentTaskStatus.failed,
    SubagentTaskStatus.cancelled,
    SubagentTaskStatus.timed_out,
}

_EXECUTOR_TO_DURABLE_STATUS = {
    "completed": SubagentTaskStatus.completed,
    "failed": SubagentTaskStatus.failed,
    "cancelled": SubagentTaskStatus.cancelled,
    "timed_out": SubagentTaskStatus.timed_out,
}


def _summarize_token_usage(records: Sequence[dict[str, Any]]) -> dict[str, int]:
    return {
        "input_tokens": sum(int(record.get("input_tokens", 0) or 0) for record in records),
        "output_tokens": sum(int(record.get("output_tokens", 0) or 0) for record in records),
        "total_tokens": sum(int(record.get("total_tokens", 0) or 0) for record in records),
    }


def _model_call_evidence(records: Sequence[dict[str, Any]]) -> list[dict[str, str]]:
    allowed = (
        "source_run_id",
        "caller",
        "actual_model_identity",
        "provider_request_id",
        "provider_response_id",
        "stop_reason",
        "system_fingerprint",
    )
    return [{key: str(record[key]) for key in allowed if record.get(key) is not None} for record in records]


def _render_context_packet(context_packet: ContextPacket) -> str:
    """Render only explicit delegated inputs, never implicit parent history."""
    source_snapshots = context_packet.metadata.get("source_snapshots")
    if not source_snapshots:
        return context_packet.goal
    return f"{context_packet.goal}\n\n以下是 ContextPacket 中显式授权的来源快照；不要假设存在其他父级上下文：\n{json.dumps(source_snapshots, ensure_ascii=False, sort_keys=True)}"


def _message_content_preview(message: Any, *, max_chars: int = 1_000) -> str:
    """Extract user-visible text without persisting reasoning metadata."""
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        return content[:max_chars]
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "\n".join(parts)[:max_chars]
    return ""


def _sanitized_tool_event(event: Any, *, event_index: int) -> dict[str, Any]:
    if not isinstance(event, dict):
        return {"event_index": event_index, "kind": "tool.result"}
    allowed = {
        "kind",
        "tool_call_id",
        "tool_name",
        "status",
        "request_sha256",
        "response_sha256",
        "latency_ms",
        "error_code",
    }
    return {
        "event_index": event_index,
        **{key: event[key] for key in allowed if key in event},
    }


class DurableSubagentTaskRuntime:
    """Own monitor tasks that synchronize executor outcomes into durable state."""

    def __init__(
        self,
        manager: SubagentTaskManager,
        *,
        worker_id: str | None = None,
        poll_interval_seconds: float = 0.25,
        lease_ttl_seconds: float = 30.0,
        reconcile_interval_seconds: float = 5.0,
        result_getter: Callable[[str], BackgroundSubagentResult | None] | None = None,
        cancel_requester: Callable[[str], None] | None = None,
        cleanup: Callable[[str], None] | None = None,
    ) -> None:
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be positive")
        if lease_ttl_seconds <= 0:
            raise ValueError("lease_ttl_seconds must be positive")
        if reconcile_interval_seconds <= 0:
            raise ValueError("reconcile_interval_seconds must be positive")
        self.manager = manager
        self.worker_id = worker_id or f"gateway-{uuid.uuid4().hex[:12]}"
        self.poll_interval_seconds = poll_interval_seconds
        self.lease_ttl = timedelta(seconds=lease_ttl_seconds)
        self.reconcile_interval_seconds = reconcile_interval_seconds
        if result_getter is None or cancel_requester is None or cleanup is None:
            from deerflow.subagents.executor import (
                cleanup_background_task,
                get_background_task_result,
                request_cancel_background_task,
            )

            result_getter = result_getter or get_background_task_result
            cancel_requester = cancel_requester or request_cancel_background_task
            cleanup = cleanup or cleanup_background_task
        self._result_getter = result_getter
        self._cancel_requester = cancel_requester
        self._cleanup = cleanup
        self._monitors: dict[str, asyncio.Task[None]] = {}
        self._monitor_lock = asyncio.Lock()
        self._reconciler_task: asyncio.Task[None] | None = None
        self._closed = False

    async def start(self) -> None:
        """Start periodic runtime reconciliation once per Gateway lifespan."""
        if self._closed:
            raise RuntimeError("Durable subagent runtime is shutting down")
        if self._reconciler_task is not None and not self._reconciler_task.done():
            return
        self._reconciler_task = asyncio.create_task(
            self._reconcile_loop(),
            name="durable-subagent-reconciler",
        )

    async def _reconcile_loop(self) -> None:
        while True:
            reconciled = await self.manager.reconcile_orphaned_inflight(
                before=utc_now(),
                reason=("The active worker lease expired before the task reached a durable terminal state; explicit resume or reassignment is required."),
            )
            for task in reconciled:
                self._cancel_requester(task.task_id)
            await asyncio.sleep(self.reconcile_interval_seconds)

    @staticmethod
    def _assert_same_request(existing: SubagentTask, requested: dict[str, Any]) -> None:
        comparable = {
            "thread_id": existing.thread_id,
            "run_id": existing.run_id,
            "user_id": existing.user_id,
            "subagent_type": existing.subagent_type,
            "description": existing.description,
            "context_packet": existing.context_packet,
            "parent_task_id": existing.parent_task_id,
            "depends_on": existing.depends_on,
        }
        if comparable != requested:
            raise TaskAlreadyExistsError(f"Subagent task ID {existing.task_id} was reused with a different request")

    async def spawn(
        self,
        *,
        task_id: str,
        thread_id: str,
        run_id: str,
        user_id: str | None,
        subagent_type: str,
        description: str,
        context_packet: ContextPacket,
        executor: BackgroundSubagentExecutor,
        parent_task_id: str | None = None,
        depends_on: tuple[str, ...] = (),
        tool_policy: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        max_attempts: int = 1,
        priority: int = 0,
    ) -> SubagentTask:
        """Persist and start a task once, returning immediately after dispatch."""
        if self._closed:
            raise RuntimeError("Durable subagent runtime is shutting down")

        requested = {
            "thread_id": thread_id,
            "run_id": run_id,
            "user_id": user_id,
            "subagent_type": subagent_type,
            "description": description,
            "context_packet": context_packet,
            "parent_task_id": parent_task_id,
            "depends_on": depends_on,
        }
        try:
            durable_task = await self.manager.get(task_id)
        except TaskNotFoundError:
            durable_task = await self.manager.create(
                task_id=task_id,
                thread_id=thread_id,
                run_id=run_id,
                user_id=user_id,
                parent_task_id=parent_task_id,
                depends_on=depends_on,
                subagent_type=subagent_type,
                description=description,
                context_packet=context_packet,
                tool_policy=tool_policy,
                metadata=metadata,
                max_attempts=max_attempts,
                priority=priority,
            )
        else:
            self._assert_same_request(durable_task, requested)
            if durable_task.status is not SubagentTaskStatus.queued:
                return durable_task

        if depends_on:
            dependencies = tuple(await asyncio.gather(*(self.manager.get(dependency_id) for dependency_id in depends_on)))
            failed_dependencies = [dependency.task_id for dependency in dependencies if dependency.is_terminal and dependency.status is not SubagentTaskStatus.completed]
            if failed_dependencies:
                return await self.manager.transition(
                    task_id,
                    SubagentTaskStatus.blocked,
                    wait_reason=("Dependencies did not complete successfully: " + ", ".join(failed_dependencies)),
                )
            if any(dependency.status is not SubagentTaskStatus.completed for dependency in dependencies):
                waiting = await self.manager.transition(
                    task_id,
                    SubagentTaskStatus.waiting,
                    wait_reason="Waiting for dependencies: " + ", ".join(depends_on),
                )
                await self._start_dependency_monitor(task_id, executor)
                return waiting

        lease = await self.manager.acquire_lease(
            task_id,
            owner=self.worker_id,
            ttl=self.lease_ttl,
        )
        running = await self.manager.transition(
            task_id,
            SubagentTaskStatus.running,
            lease_token=lease.token,
        )
        try:
            executor_task_id = executor.execute_async(
                _render_context_packet(context_packet),
                task_id=task_id,
            )
            if executor_task_id != task_id:
                raise RuntimeError(f"SubagentExecutor returned task ID {executor_task_id!r}; expected {task_id!r}")
        except Exception as exc:
            failed = await self.manager.transition(
                task_id,
                SubagentTaskStatus.failed,
                lease_token=lease.token,
                error={
                    "type": exc.__class__.__name__,
                    "message": str(exc),
                    "stage": "dispatch",
                },
            )
            return failed

        await self._start_monitor(task_id, lease.token)
        return running

    async def _start_dependency_monitor(
        self,
        task_id: str,
        executor: BackgroundSubagentExecutor,
    ) -> None:
        async with self._monitor_lock:
            current = self._monitors.get(task_id)
            if current is not None and not current.done():
                return
            monitor = asyncio.create_task(
                self._wait_for_dependencies(task_id, executor),
                name=f"durable-subagent-dependencies:{task_id}",
            )
            self._monitors[task_id] = monitor
            monitor.add_done_callback(
                lambda completed, durable_task_id=task_id: self._monitor_done(
                    durable_task_id,
                    completed,
                )
            )

    async def _wait_for_dependencies(
        self,
        task_id: str,
        executor: BackgroundSubagentExecutor,
    ) -> None:
        while True:
            task = await self.manager.get(task_id)
            if task.is_terminal or task.status is not SubagentTaskStatus.waiting:
                return
            dependencies = tuple(await asyncio.gather(*(self.manager.get(dependency_id) for dependency_id in task.depends_on)))
            failed_dependencies = [dependency.task_id for dependency in dependencies if dependency.is_terminal and dependency.status is not SubagentTaskStatus.completed]
            if failed_dependencies:
                await self.manager.transition(
                    task_id,
                    SubagentTaskStatus.blocked,
                    wait_reason=("Dependencies did not complete successfully: " + ", ".join(failed_dependencies)),
                )
                return
            if all(dependency.status is SubagentTaskStatus.completed for dependency in dependencies):
                lease = await self.manager.acquire_lease(
                    task_id,
                    owner=self.worker_id,
                    ttl=self.lease_ttl,
                )
                await self.manager.transition(
                    task_id,
                    SubagentTaskStatus.running,
                    lease_token=lease.token,
                )
                try:
                    executor_task_id = executor.execute_async(
                        _render_context_packet(task.context_packet),
                        task_id=task_id,
                    )
                    if executor_task_id != task_id:
                        raise RuntimeError(f"SubagentExecutor returned task ID {executor_task_id!r}; expected {task_id!r}")
                except Exception as exc:
                    await self.manager.transition(
                        task_id,
                        SubagentTaskStatus.failed,
                        lease_token=lease.token,
                        error={
                            "type": exc.__class__.__name__,
                            "message": str(exc),
                            "stage": "dependency_dispatch",
                        },
                    )
                    return
                await self._monitor(task_id, lease.token)
                return
            await asyncio.sleep(self.poll_interval_seconds)

    async def resume(
        self,
        task_id: str,
        *,
        executor: BackgroundSubagentExecutor,
    ) -> SubagentTask:
        """Reassign a blocked/waiting task under a new fencing lease."""
        if self._closed:
            raise RuntimeError("Durable subagent runtime is shutting down")
        durable_task = await self.manager.get(task_id)
        if durable_task.depends_on:
            dependencies = tuple(await asyncio.gather(*(self.manager.get(dependency_id) for dependency_id in durable_task.depends_on)))
            incomplete = [dependency.task_id for dependency in dependencies if dependency.status is not SubagentTaskStatus.completed]
            if incomplete:
                raise TaskTransitionError(f"Subagent task {task_id} still waits for dependencies: " + ", ".join(incomplete))
        active_monitor = self._monitors.get(task_id)
        if active_monitor is not None and not active_monitor.done():
            raise TaskTransitionError(f"Subagent task {task_id} is already owned by the active scheduler")
        executor_result = self._result_getter(task_id)
        if executor_result is not None and not executor_result.status.is_terminal:
            raise TaskTransitionError(f"Subagent task {task_id} still has an active executor; cancel it before resume")
        if executor_result is not None:
            self._cleanup(task_id)

        lease = await self.manager.acquire_lease(
            task_id,
            owner=self.worker_id,
            ttl=self.lease_ttl,
        )
        resumed = await self.manager.resume(
            task_id,
            lease_token=lease.token,
            checkpoint=durable_task.checkpoint,
        )
        try:
            executor_task_id = executor.execute_async(
                _render_context_packet(durable_task.context_packet),
                task_id=task_id,
            )
            if executor_task_id != task_id:
                raise RuntimeError(f"SubagentExecutor returned task ID {executor_task_id!r}; expected {task_id!r}")
        except Exception as exc:
            return await self.manager.transition(
                task_id,
                SubagentTaskStatus.failed,
                lease_token=lease.token,
                error={
                    "type": exc.__class__.__name__,
                    "message": str(exc),
                    "stage": "resume_dispatch",
                },
            )

        await self._start_monitor(task_id, lease.token)
        return resumed

    async def _start_monitor(self, task_id: str, lease_token: int) -> None:
        async with self._monitor_lock:
            current = self._monitors.get(task_id)
            if current is not None and not current.done():
                return
            monitor = asyncio.create_task(
                self._monitor(task_id, lease_token),
                name=f"durable-subagent-monitor:{task_id}",
            )
            self._monitors[task_id] = monitor
            monitor.add_done_callback(
                lambda completed, durable_task_id=task_id: self._monitor_done(
                    durable_task_id,
                    completed,
                )
            )

    def _monitor_done(self, task_id: str, monitor: asyncio.Task[None]) -> None:
        current = self._monitors.get(task_id)
        if current is monitor:
            self._monitors.pop(task_id, None)
        if monitor.cancelled():
            return
        try:
            error = monitor.exception()
        except asyncio.CancelledError:
            return
        if error is not None:
            logger.exception(
                "Durable subagent monitor failed for task %s",
                task_id,
                exc_info=error,
            )

    async def _monitor(self, task_id: str, lease_token: int) -> None:
        missing_polls = 0
        reported_messages = 0
        reported_tool_events = 0
        renewal_deadline = time.monotonic() + self.lease_ttl.total_seconds() / 3
        try:
            while True:
                durable_task = await self.manager.get(task_id)
                result = self._result_getter(task_id)

                if durable_task.is_terminal:
                    if result is None or result.status.is_terminal:
                        self._cleanup(task_id)
                        return
                    if durable_task.status is SubagentTaskStatus.cancelled:
                        self._cancel_requester(task_id)
                    await asyncio.sleep(self.poll_interval_seconds)
                    continue

                if durable_task.status is SubagentTaskStatus.blocked:
                    self._cancel_requester(task_id)
                    if result is None or result.status.is_terminal:
                        self._cleanup(task_id)
                        return
                    await asyncio.sleep(self.poll_interval_seconds)
                    continue

                if result is None:
                    missing_polls += 1
                    if missing_polls >= 3:
                        await self.manager.transition(
                            task_id,
                            SubagentTaskStatus.failed,
                            lease_token=lease_token,
                            error={
                                "type": "ExecutorStateMissing",
                                "message": "Executor task disappeared before reaching a terminal state",
                                "stage": "monitor",
                            },
                        )
                        return
                else:
                    missing_polls = 0
                    ai_messages = list(getattr(result, "ai_messages", None) or ())
                    for index in range(reported_messages, len(ai_messages)):
                        preview = _message_content_preview(ai_messages[index])
                        if preview:
                            await self.manager.append_event(
                                task_id,
                                "task.message",
                                {
                                    "message_index": index + 1,
                                    "content_preview": preview,
                                },
                                idempotency_key=f"task.message:{index + 1}",
                                lease_token=lease_token,
                            )
                    reported_messages = len(ai_messages)

                    execution_events = list(getattr(result, "execution_events", None) or ())
                    for index in range(
                        reported_tool_events,
                        len(execution_events),
                    ):
                        await self.manager.append_event(
                            task_id,
                            "task.tool_result",
                            _sanitized_tool_event(
                                execution_events[index],
                                event_index=index + 1,
                            ),
                            idempotency_key=f"task.tool_result:{index + 1}",
                            lease_token=lease_token,
                        )
                    reported_tool_events = len(execution_events)

                    if result.status.is_terminal:
                        await self._persist_terminal_result(
                            task_id,
                            lease_token=lease_token,
                            result=result,
                        )
                        self._cleanup(task_id)
                        return

                if time.monotonic() >= renewal_deadline:
                    await self.manager.renew_lease(
                        task_id,
                        owner=self.worker_id,
                        token=lease_token,
                        ttl=self.lease_ttl,
                    )
                    renewal_deadline = time.monotonic() + self.lease_ttl.total_seconds() / 3

                await asyncio.sleep(self.poll_interval_seconds)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Failed to synchronize durable subagent task %s", task_id)
            raise

    async def _persist_terminal_result(
        self,
        task_id: str,
        *,
        lease_token: int,
        result: BackgroundSubagentResult,
    ) -> SubagentTask:
        executor_status = str(getattr(result.status, "value", result.status))
        status = _EXECUTOR_TO_DURABLE_STATUS[executor_status]
        usage = _summarize_token_usage(result.token_usage_records)
        model_calls = _model_call_evidence(result.token_usage_records)
        telemetry = {
            "trace_id": result.trace_id,
            "token_usage": usage,
            "usage_records": list(result.token_usage_records),
            "model_calls": model_calls,
            "provider_request_ids": list(dict.fromkeys(call["provider_request_id"] for call in model_calls if call.get("provider_request_id"))),
            "actual_model_identities": list(dict.fromkeys(call["actual_model_identity"] for call in model_calls if call.get("actual_model_identity"))),
            "stop_reasons": list(dict.fromkeys(call["stop_reason"] for call in model_calls if call.get("stop_reason"))),
        }
        if status is SubagentTaskStatus.completed:
            return await self.manager.transition(
                task_id,
                status,
                lease_token=lease_token,
                result={
                    "output": result.result or "",
                    "stop_reason": status.value,
                },
                telemetry=telemetry,
            )
        if status is SubagentTaskStatus.failed:
            return await self.manager.transition(
                task_id,
                status,
                lease_token=lease_token,
                error={
                    "type": "SubagentExecutionError",
                    "message": result.error or "Subagent execution failed",
                    "stage": "execution",
                },
                telemetry=telemetry,
            )
        return await self.manager.transition(
            task_id,
            status,
            lease_token=lease_token,
            error={
                "type": "SubagentStopped",
                "message": result.error or f"Subagent task {status.value}",
                "stage": "execution",
            },
            telemetry=telemetry,
        )

    async def wait(
        self,
        task_ids: Sequence[str],
        *,
        mode: TaskWaitMode,
        timeout_seconds: float = 30.0,
    ) -> TaskWaitResult:
        """Wait once for one/any/all tasks to settle without model-side polling."""
        unique_ids = tuple(dict.fromkeys(task_ids))
        if not unique_ids:
            raise ValueError("task_ids must not be empty")
        if mode is TaskWaitMode.one and len(unique_ids) != 1:
            raise ValueError("wait mode 'one' requires exactly one task ID")
        if timeout_seconds < 0 or timeout_seconds > 60:
            raise ValueError("timeout_seconds must be between 0 and 60")

        deadline = time.monotonic() + timeout_seconds
        while True:
            tasks = tuple(await asyncio.gather(*(self.manager.get(task_id) for task_id in unique_ids)))
            settled = tuple(task for task in tasks if task.status in _SETTLED_STATUSES)
            ready = bool(settled) if mode in {TaskWaitMode.one, TaskWaitMode.any} else len(settled) == len(tasks)
            if ready:
                selected = settled if mode is TaskWaitMode.any else tasks
                return TaskWaitResult(
                    mode=mode,
                    ready=True,
                    timed_out=False,
                    tasks=selected,
                )
            if time.monotonic() >= deadline:
                return TaskWaitResult(
                    mode=mode,
                    ready=False,
                    timed_out=True,
                    tasks=tasks,
                )
            await asyncio.sleep(self.poll_interval_seconds)

    async def cancel(self, task_id: str, *, reason: str) -> SubagentTask:
        """Request cooperative cancellation and persist it as the final state."""
        task = await self.manager.get(task_id)
        if task.is_terminal:
            return task
        self._cancel_requester(task_id)
        return await self.manager.transition(
            task_id,
            SubagentTaskStatus.cancelled,
            lease_token=task.lease_token if task.lease_owner is not None else None,
            error={
                "type": "TaskCancelled",
                "message": reason,
                "stage": "control",
            },
        )

    async def shutdown(self, *, reason: str) -> None:
        """Stop monitors and leave non-terminal work in an explicit blocked state."""
        if self._closed:
            return
        self._closed = True
        reconciler = self._reconciler_task
        self._reconciler_task = None
        if reconciler is not None:
            reconciler.cancel()
            await asyncio.gather(reconciler, return_exceptions=True)
        monitors = list(self._monitors.items())
        for task_id, _monitor in monitors:
            self._cancel_requester(task_id)
            try:
                task = await self.manager.get(task_id)
                if not task.is_terminal:
                    await self.manager.transition(
                        task_id,
                        SubagentTaskStatus.blocked,
                        lease_token=task.lease_token if task.lease_owner is not None else None,
                        wait_reason=reason,
                    )
            except (TaskNotFoundError, TaskTransitionError):
                logger.warning(
                    "Could not block subagent task %s during shutdown",
                    task_id,
                    exc_info=True,
                )
        for _task_id, monitor in monitors:
            monitor.cancel()
        if monitors:
            await asyncio.gather(
                *(monitor for _task_id, monitor in monitors),
                return_exceptions=True,
            )
        self._monitors.clear()
