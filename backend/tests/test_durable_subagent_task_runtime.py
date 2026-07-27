"""Durable runtime bridge between Parent task tools and SubagentExecutor."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from threading import Lock

import pytest

from deerflow.subagents.tasks import (
    ContextPacket,
    DurableSubagentTaskRuntime,
    MemorySubagentTaskStore,
    SubagentTaskManager,
    SubagentTaskStatus,
    TaskWaitMode,
)


class SubagentStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"

    @property
    def is_terminal(self) -> bool:
        return self is not type(self).RUNNING


@dataclass
class SubagentResult:
    task_id: str
    trace_id: str
    status: SubagentStatus
    result: str | None = None
    error: str | None = None
    token_usage_records: list[dict] | None = None
    ai_messages: list[dict] | None = None
    execution_events: list[dict] | None = None

    def __post_init__(self) -> None:
        self.token_usage_records = self.token_usage_records or []
        self.ai_messages = self.ai_messages or []
        self.execution_events = self.execution_events or []
        self._lock = Lock()

    def try_set_terminal(
        self,
        status: SubagentStatus,
        *,
        result: str | None = None,
        error: str | None = None,
        token_usage_records: list[dict] | None = None,
    ) -> bool:
        with self._lock:
            if self.status.is_terminal:
                return False
            self.status = status
            self.result = result
            self.error = error
            if token_usage_records is not None:
                self.token_usage_records = token_usage_records
            return True


@dataclass
class _FakeConfig:
    timeout_seconds: int = 30


class _FakeExecutor:
    def __init__(self, results: dict[str, SubagentResult]) -> None:
        self.config = _FakeConfig()
        self.results = results
        self.calls: list[tuple[str, str | None]] = []

    def execute_async(self, prompt: str, task_id: str | None = None) -> str:
        self.calls.append((prompt, task_id))
        assert task_id is not None
        self.results[task_id] = SubagentResult(
            task_id=task_id,
            trace_id=f"trace-{task_id}",
            status=SubagentStatus.RUNNING,
        )
        return task_id


@pytest.fixture
def runtime_components():
    results: dict[str, SubagentResult] = {}
    cancelled: list[str] = []
    cleaned: list[str] = []
    manager = SubagentTaskManager(MemorySubagentTaskStore())
    runtime = DurableSubagentTaskRuntime(
        manager,
        worker_id="test-worker",
        poll_interval_seconds=0.001,
        result_getter=results.get,
        cancel_requester=cancelled.append,
        cleanup=cleaned.append,
    )
    return runtime, manager, results, cancelled, cleaned


def _context(goal: str) -> ContextPacket:
    return ContextPacket(
        goal=goal,
        available_skills=("fulfillment-investigation",),
        available_tools=("dataset_schema",),
        expected_output_schema={"type": "object"},
    )


@pytest.mark.anyio
async def test_spawn_returns_running_task_without_waiting_for_executor(runtime_components):
    runtime, manager, results, _cancelled, _cleaned = runtime_components
    executor = _FakeExecutor(results)

    task = await runtime.spawn(
        task_id="task-1",
        thread_id="thread-1",
        run_id="run-1",
        user_id="user-1",
        subagent_type="analyst",
        description="分析履约异常",
        context_packet=_context("定位延迟履约率上升的原因"),
        executor=executor,
    )

    assert task.status is SubagentTaskStatus.running
    assert executor.calls == [("定位延迟履约率上升的原因", "task-1")]
    assert (await manager.get("task-1")).status is SubagentTaskStatus.running

    await runtime.shutdown(reason="test cleanup")


@pytest.mark.anyio
async def test_monitor_persists_completed_result_and_usage(runtime_components):
    runtime, manager, results, _cancelled, cleaned = runtime_components
    executor = _FakeExecutor(results)
    await runtime.spawn(
        task_id="task-1",
        thread_id="thread-1",
        run_id="run-1",
        user_id="user-1",
        subagent_type="analyst",
        description="分析履约异常",
        context_packet=_context("定位延迟履约率上升的原因"),
        executor=executor,
    )
    results["task-1"].try_set_terminal(
        SubagentStatus.COMPLETED,
        result="承运运输阶段是主要贡献来源。",
        token_usage_records=[
            {
                "input_tokens": 100,
                "output_tokens": 20,
                "total_tokens": 120,
                "actual_model_identity": "deepseek-v4-flash",
                "provider_request_id": "request-1",
                "stop_reason": "stop",
            }
        ],
    )

    waited = await runtime.wait(
        ["task-1"],
        mode=TaskWaitMode.all,
        timeout_seconds=1,
    )

    assert waited.ready is True
    assert waited.tasks[0].status is SubagentTaskStatus.completed
    assert waited.tasks[0].result == {
        "output": "承运运输阶段是主要贡献来源。",
        "stop_reason": "completed",
    }
    assert waited.tasks[0].telemetry["token_usage"] == {
        "input_tokens": 100,
        "output_tokens": 20,
        "total_tokens": 120,
    }
    assert waited.tasks[0].telemetry["actual_model_identities"] == ["deepseek-v4-flash"]
    assert waited.tasks[0].telemetry["provider_request_ids"] == ["request-1"]
    assert waited.tasks[0].telemetry["stop_reasons"] == ["stop"]
    assert waited.tasks[0].telemetry["usage_records"] == [
        {
            "input_tokens": 100,
            "output_tokens": 20,
            "total_tokens": 120,
            "actual_model_identity": "deepseek-v4-flash",
            "provider_request_id": "request-1",
            "stop_reason": "stop",
        }
    ]
    assert waited.tasks[0].lease_owner is None
    assert cleaned == ["task-1"]
    assert [event.event_type for event in await manager.list_events("task-1")][-1] == "task.completed"

    await runtime.shutdown(reason="test cleanup")


@pytest.mark.anyio
async def test_monitor_appends_sanitized_progress_and_tool_events(runtime_components):
    runtime, manager, results, _cancelled, _cleaned = runtime_components
    executor = _FakeExecutor(results)
    await runtime.spawn(
        task_id="task-1",
        thread_id="thread-1",
        run_id="run-1",
        user_id="user-1",
        subagent_type="analyst",
        description="分析履约异常",
        context_packet=_context("定位原因"),
        executor=executor,
    )
    results["task-1"].ai_messages.append(
        {
            "content": "正在计算承运阶段贡献。",
            "additional_kwargs": {"reasoning_content": "不得进入事件"},
        }
    )
    results["task-1"].execution_events.append(
        {
            "kind": "tool.result",
            "tool_call_id": "call-1",
            "tool_name": "metric_query",
            "status": "succeeded",
            "request_sha256": "a" * 64,
            "response_sha256": "b" * 64,
            "latency_ms": 12.5,
            "raw_args": {"secret": "不得进入事件"},
        }
    )
    for _ in range(100):
        events = await manager.list_events("task-1")
        if any(event.event_type == "task.tool_result" for event in events):
            break
        await asyncio.sleep(0.001)

    events = await manager.list_events("task-1")
    message = next(event for event in events if event.event_type == "task.message")
    tool_result = next(event for event in events if event.event_type == "task.tool_result")
    assert message.payload == {
        "message_index": 1,
        "content_preview": "正在计算承运阶段贡献。",
    }
    assert "reasoning_content" not in json.dumps(message.payload, ensure_ascii=False)
    assert tool_result.payload["tool_name"] == "metric_query"
    assert "raw_args" not in tool_result.payload

    await runtime.shutdown(reason="test cleanup")


@pytest.mark.anyio
async def test_wait_any_returns_when_first_task_settles(runtime_components):
    runtime, _manager, results, _cancelled, _cleaned = runtime_components
    first = _FakeExecutor(results)
    second = _FakeExecutor(results)
    for task_id, executor in (("task-1", first), ("task-2", second)):
        await runtime.spawn(
            task_id=task_id,
            thread_id="thread-1",
            run_id="run-1",
            user_id="user-1",
            subagent_type="explore",
            description=f"检查 {task_id}",
            context_packet=_context(f"检查 {task_id}"),
            executor=executor,
        )

    results["task-2"].try_set_terminal(SubagentStatus.COMPLETED, result="done")
    waited = await runtime.wait(
        ["task-1", "task-2"],
        mode=TaskWaitMode.any,
        timeout_seconds=1,
    )

    assert waited.ready is True
    assert [task.task_id for task in waited.tasks] == ["task-2"]

    await runtime.shutdown(reason="test cleanup")


@pytest.mark.anyio
async def test_cancel_is_durable_and_requests_cooperative_executor_stop(runtime_components):
    runtime, manager, results, cancelled, _cleaned = runtime_components
    executor = _FakeExecutor(results)
    await runtime.spawn(
        task_id="task-1",
        thread_id="thread-1",
        run_id="run-1",
        user_id="user-1",
        subagent_type="explore",
        description="检查数据",
        context_packet=_context("检查数据"),
        executor=executor,
    )

    task = await runtime.cancel("task-1", reason="用户取消")

    assert task.status is SubagentTaskStatus.cancelled
    assert task.lease_owner is None
    assert cancelled == ["task-1"]
    assert (await manager.get("task-1")).status is SubagentTaskStatus.cancelled

    results["task-1"].try_set_terminal(SubagentStatus.CANCELLED, error="Cancelled by user")
    await asyncio.sleep(0.01)
    await runtime.shutdown(reason="test cleanup")


@pytest.mark.anyio
async def test_repeated_spawn_with_same_task_id_is_idempotent(runtime_components):
    runtime, _manager, results, _cancelled, _cleaned = runtime_components
    executor = _FakeExecutor(results)
    kwargs = {
        "task_id": "task-1",
        "thread_id": "thread-1",
        "run_id": "run-1",
        "user_id": "user-1",
        "subagent_type": "analyst",
        "description": "分析履约异常",
        "context_packet": _context("定位延迟履约率上升的原因"),
        "executor": executor,
    }

    first = await runtime.spawn(**kwargs)
    second = await runtime.spawn(**kwargs)

    assert first.task_id == second.task_id
    assert len(executor.calls) == 1

    await runtime.shutdown(reason="test cleanup")


@pytest.mark.anyio
async def test_resume_reassigns_blocked_task_with_new_attempt(runtime_components):
    runtime, manager, results, _cancelled, _cleaned = runtime_components
    await manager.create(
        task_id="task-1",
        thread_id="thread-1",
        run_id="run-1",
        user_id="user-1",
        subagent_type="analyst",
        description="分析履约异常",
        context_packet=_context("继续定位履约异常"),
        max_attempts=2,
    )
    await manager.transition("task-1", SubagentTaskStatus.running)
    await manager.transition(
        "task-1",
        SubagentTaskStatus.blocked,
        wait_reason="worker lost",
    )
    executor = _FakeExecutor(results)

    resumed = await runtime.resume("task-1", executor=executor)

    assert resumed.status is SubagentTaskStatus.running
    assert resumed.attempt == 2
    assert executor.calls == [("继续定位履约异常", "task-1")]

    await runtime.shutdown(reason="test cleanup")


@pytest.mark.anyio
async def test_dependency_task_waits_then_dispatches_after_dependency_completes(
    runtime_components,
):
    runtime, manager, results, _cancelled, _cleaned = runtime_components
    await manager.create(
        task_id="dependency",
        thread_id="thread-1",
        run_id="run-1",
        user_id="user-1",
        subagent_type="explore",
        description="检查数据",
        context_packet=_context("检查数据"),
    )
    await manager.transition("dependency", SubagentTaskStatus.running)
    executor = _FakeExecutor(results)

    waiting = await runtime.spawn(
        task_id="dependent",
        thread_id="thread-1",
        run_id="run-1",
        user_id="user-1",
        subagent_type="analyst",
        description="分析数据",
        context_packet=_context("分析数据"),
        executor=executor,
        depends_on=("dependency",),
    )

    assert waiting.status is SubagentTaskStatus.waiting
    assert executor.calls == []

    await manager.transition(
        "dependency",
        SubagentTaskStatus.completed,
        result={"output": "schema ready"},
    )
    for _ in range(100):
        if executor.calls:
            break
        await asyncio.sleep(0.001)

    assert executor.calls == [("分析数据", "dependent")]
    assert (await manager.get("dependent")).status is SubagentTaskStatus.running

    await runtime.shutdown(reason="test cleanup")


@pytest.mark.anyio
async def test_failed_dependency_blocks_dependent_without_dispatch(runtime_components):
    runtime, manager, results, _cancelled, _cleaned = runtime_components
    await manager.create(
        task_id="dependency",
        thread_id="thread-1",
        run_id="run-1",
        user_id="user-1",
        subagent_type="explore",
        description="检查数据",
        context_packet=_context("检查数据"),
    )
    await manager.transition("dependency", SubagentTaskStatus.running)
    await manager.transition(
        "dependency",
        SubagentTaskStatus.failed,
        error={"type": "DataError", "message": "bad input"},
    )
    executor = _FakeExecutor(results)

    blocked = await runtime.spawn(
        task_id="dependent",
        thread_id="thread-1",
        run_id="run-1",
        user_id="user-1",
        subagent_type="analyst",
        description="分析数据",
        context_packet=_context("分析数据"),
        executor=executor,
        depends_on=("dependency",),
    )

    assert blocked.status is SubagentTaskStatus.blocked
    assert "dependency" in (blocked.wait_reason or "")
    assert executor.calls == []

    await runtime.shutdown(reason="test cleanup")


@pytest.mark.anyio
async def test_runtime_periodically_blocks_expired_orphan_lease():
    manager = SubagentTaskManager(MemorySubagentTaskStore())
    cancelled: list[str] = []
    now = datetime(2020, 7, 24, 10, 0, tzinfo=UTC)
    await manager.create(
        task_id="orphan",
        thread_id="thread-1",
        run_id="run-1",
        user_id="user-1",
        subagent_type="analyst",
        description="分析数据",
        context_packet=_context("分析数据"),
        created_at=now,
    )
    lease = await manager.acquire_lease(
        "orphan",
        owner="lost-worker",
        ttl=timedelta(seconds=1),
        now=now,
    )
    await manager.transition(
        "orphan",
        SubagentTaskStatus.running,
        lease_token=lease.token,
        now=now,
    )
    runtime = DurableSubagentTaskRuntime(
        manager,
        worker_id="test-worker",
        poll_interval_seconds=0.001,
        reconcile_interval_seconds=0.001,
        result_getter=lambda _task_id: None,
        cancel_requester=cancelled.append,
        cleanup=lambda _task_id: None,
    )

    await runtime.start()
    for _ in range(100):
        if (await manager.get("orphan")).status is SubagentTaskStatus.blocked:
            break
        await asyncio.sleep(0.001)

    orphan = await manager.get("orphan")
    assert orphan.status is SubagentTaskStatus.blocked
    assert orphan.lease_owner is None
    assert cancelled == ["orphan"]

    await runtime.shutdown(reason="test cleanup")
