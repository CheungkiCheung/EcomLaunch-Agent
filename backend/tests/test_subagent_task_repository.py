"""SQL persistence and restart behavior for durable SubagentTask state."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from deerflow.persistence.subagent_task import SubagentTaskRepository
from deerflow.subagents.tasks import (
    ContextPacket,
    SubagentTaskManager,
    SubagentTaskStatus,
    TaskVersionConflictError,
)


async def _make_repository(tmp_path):
    from deerflow.persistence.engine import get_session_factory, init_engine

    url = f"sqlite+aiosqlite:///{tmp_path / 'subagent-tasks.db'}"
    await init_engine("sqlite", url=url, sqlite_dir=str(tmp_path))
    return SubagentTaskRepository(get_session_factory())


async def _cleanup():
    from deerflow.persistence.engine import close_engine

    await close_engine()


def _context(goal: str = "Inspect data") -> ContextPacket:
    return ContextPacket(goal=goal, source_refs=("dataset:orders",))


@pytest.mark.anyio
async def test_sql_repository_survives_manager_recreation(tmp_path):
    repository = await _make_repository(tmp_path)
    manager_a = SubagentTaskManager(repository)
    created = await manager_a.create(
        task_id="task-1",
        thread_id="thread-1",
        run_id="run-1",
        subagent_type="explore",
        description="Inspect data",
        context_packet=_context(),
    )
    running = await manager_a.transition("task-1", SubagentTaskStatus.running, expected_version=created.version)

    manager_b = SubagentTaskManager(SubagentTaskRepository(repository.session_factory))
    restored = await manager_b.get("task-1")
    events = await manager_b.list_events("task-1")

    assert restored == running
    assert [event.event_type for event in events] == ["task.created", "task.running"]
    await _cleanup()


@pytest.mark.anyio
async def test_sql_repository_preserves_lineage_and_lists_inflight(tmp_path):
    repository = await _make_repository(tmp_path)
    manager = SubagentTaskManager(repository)
    await manager.create(
        task_id="parent",
        thread_id="thread-1",
        run_id="run-1",
        subagent_type="analyst",
        description="Analyze",
        context_packet=_context("Analyze"),
    )
    await manager.create(
        task_id="child",
        thread_id="thread-1",
        run_id="run-1",
        parent_task_id="parent",
        subagent_type="verifier",
        description="Verify",
        context_packet=_context("Verify"),
    )

    assert [task.task_id for task in await manager.list_children("parent")] == ["child"]
    assert [task.task_id for task in await manager.list_inflight()] == ["parent", "child"]
    await _cleanup()


@pytest.mark.anyio
async def test_sql_optimistic_version_allows_only_one_concurrent_transition(tmp_path):
    repository = await _make_repository(tmp_path)
    manager_a = SubagentTaskManager(repository)
    manager_b = SubagentTaskManager(SubagentTaskRepository(repository.session_factory))
    await manager_a.create(
        task_id="task-1",
        thread_id="thread-1",
        run_id="run-1",
        subagent_type="explore",
        description="Inspect data",
        context_packet=_context(),
    )

    outcomes = await asyncio.gather(
        manager_a.transition("task-1", SubagentTaskStatus.running, expected_version=0),
        manager_b.transition("task-1", SubagentTaskStatus.cancelled, expected_version=0),
        return_exceptions=True,
    )

    assert sum(not isinstance(outcome, Exception) for outcome in outcomes) == 1
    assert sum(isinstance(outcome, TaskVersionConflictError) for outcome in outcomes) == 1
    assert (await manager_a.get("task-1")).version == 1
    await _cleanup()


@pytest.mark.anyio
async def test_sql_event_idempotency_survives_restart(tmp_path):
    repository = await _make_repository(tmp_path)
    manager = SubagentTaskManager(repository)
    await manager.create(
        task_id="task-1",
        thread_id="thread-1",
        run_id="run-1",
        subagent_type="explore",
        description="Inspect data",
        context_packet=_context(),
    )
    first = await manager.append_event(
        "task-1",
        "task.progress",
        {"step": "schema"},
        idempotency_key="progress:schema",
    )

    restarted = SubagentTaskManager(SubagentTaskRepository(repository.session_factory))
    second = await restarted.append_event(
        "task-1",
        "task.progress",
        {"step": "schema"},
        idempotency_key="progress:schema",
    )

    assert second == first
    assert len(await restarted.list_events("task-1")) == 2
    await _cleanup()


@pytest.mark.anyio
async def test_sql_restart_reconciliation_blocks_expired_running_task(tmp_path):
    repository = await _make_repository(tmp_path)
    manager = SubagentTaskManager(repository)
    now = datetime(2026, 7, 24, 10, 0, tzinfo=UTC)
    await manager.create(
        task_id="task-1",
        thread_id="thread-1",
        run_id="run-1",
        subagent_type="explore",
        description="Inspect data",
        context_packet=_context(),
        created_at=now,
    )
    lease = await manager.acquire_lease("task-1", owner="worker-a", ttl=timedelta(seconds=5), now=now)
    await manager.transition("task-1", SubagentTaskStatus.running, lease_token=lease.token, now=now)

    restarted = SubagentTaskManager(SubagentTaskRepository(repository.session_factory))
    reconciled = await restarted.reconcile_orphaned_inflight(
        before=now + timedelta(seconds=6),
        reason="Process restarted.",
    )

    assert [task.status for task in reconciled] == [SubagentTaskStatus.blocked]
    assert (await restarted.get("task-1")).lease_owner is None
    await _cleanup()
