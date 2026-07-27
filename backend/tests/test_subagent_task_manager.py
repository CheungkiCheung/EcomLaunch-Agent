"""Durable SubagentTask manager behavior over the in-memory store."""

from datetime import UTC, datetime, timedelta

import pytest

from deerflow.subagents.tasks import (
    ContextPacket,
    MemorySubagentTaskStore,
    SubagentTaskManager,
    SubagentTaskStatus,
    TaskLeaseConflictError,
    TaskTransitionError,
    TaskVersionConflictError,
)


def _context(goal: str = "Inspect the uploaded order data") -> ContextPacket:
    return ContextPacket(
        goal=goal,
        source_refs=("dataset:orders",),
        available_tools=("dataset_schema",),
        budget={"max_turns": 8},
    )


@pytest.fixture
def manager() -> SubagentTaskManager:
    return SubagentTaskManager(MemorySubagentTaskStore())


@pytest.mark.anyio
async def test_create_persists_task_and_append_only_created_event(manager):
    task = await manager.create(
        task_id="task-1",
        thread_id="thread-1",
        run_id="run-1",
        subagent_type="explore",
        description="Inspect data",
        context_packet=_context(),
    )

    assert task.status is SubagentTaskStatus.queued
    assert task.version == 0
    assert task.event_seq == 1
    assert (await manager.get("task-1")) == task
    events = await manager.list_events("task-1")
    assert [(event.seq, event.event_type) for event in events] == [(1, "task.created")]


@pytest.mark.anyio
async def test_parent_child_lineage_and_dependencies_are_queryable(manager):
    await manager.create(
        task_id="parent",
        thread_id="thread-1",
        run_id="run-1",
        subagent_type="analyst",
        description="Lead analysis",
        context_packet=_context("Lead analysis"),
    )
    await manager.create(
        task_id="child",
        thread_id="thread-1",
        run_id="run-1",
        parent_task_id="parent",
        depends_on=("parent",),
        subagent_type="verifier",
        description="Verify analysis",
        context_packet=_context("Verify analysis"),
    )

    children = await manager.list_children("parent")
    run_tasks = await manager.list_by_run("run-1")

    assert [task.task_id for task in children] == ["child"]
    assert [task.task_id for task in run_tasks] == ["parent", "child"]
    assert children[0].depends_on == ("parent",)


@pytest.mark.anyio
async def test_parent_child_lineage_can_cross_runs_within_one_thread(manager):
    await manager.create(
        task_id="parent",
        thread_id="thread-1",
        run_id="run-1",
        user_id="user-1",
        subagent_type="analyst",
        description="Lead analysis",
        context_packet=_context(),
    )

    child = await manager.create(
        task_id="child",
        thread_id="thread-1",
        run_id="run-2",
        user_id="user-1",
        parent_task_id="parent",
        subagent_type="verifier",
        description="Verify analysis",
        context_packet=_context(),
    )

    assert child.parent_task_id == "parent"
    assert child.run_id == "run-2"


@pytest.mark.anyio
async def test_create_rejects_cross_thread_parent(manager):
    await manager.create(
        task_id="parent",
        thread_id="thread-1",
        run_id="run-1",
        user_id="user-1",
        subagent_type="analyst",
        description="Lead analysis",
        context_packet=_context(),
    )

    with pytest.raises(ValueError, match="same thread and user"):
        await manager.create(
            task_id="child",
            thread_id="thread-2",
            run_id="run-2",
            user_id="user-1",
            parent_task_id="parent",
            subagent_type="verifier",
            description="Verify analysis",
            context_packet=_context(),
        )


@pytest.mark.anyio
async def test_resume_increments_attempt_under_a_new_fencing_lease(manager):
    now = datetime(2026, 7, 24, 10, 0, tzinfo=UTC)
    await manager.create(
        task_id="task-1",
        thread_id="thread-1",
        run_id="run-1",
        subagent_type="analyst",
        description="Analyze data",
        context_packet=_context(),
        max_attempts=2,
        created_at=now,
    )
    first_lease = await manager.acquire_lease(
        "task-1",
        owner="worker-a",
        ttl=timedelta(seconds=10),
        now=now,
    )
    await manager.transition(
        "task-1",
        SubagentTaskStatus.running,
        lease_token=first_lease.token,
        now=now,
    )
    await manager.reconcile_orphaned_inflight(
        before=now + timedelta(seconds=11),
        reason="worker lost",
    )
    second_lease = await manager.acquire_lease(
        "task-1",
        owner="worker-b",
        ttl=timedelta(seconds=10),
        now=now + timedelta(seconds=12),
    )

    resumed = await manager.resume(
        "task-1",
        lease_token=second_lease.token,
        now=now + timedelta(seconds=12),
    )

    assert resumed.status is SubagentTaskStatus.running
    assert resumed.attempt == 2
    assert resumed.lease_token == first_lease.token + 1
    assert (await manager.list_events("task-1"))[-1].event_type == "task.resumed"

    blocked = await manager.transition(
        "task-1",
        SubagentTaskStatus.blocked,
        lease_token=second_lease.token,
        wait_reason="retry requested",
        now=now + timedelta(seconds=13),
    )
    assert blocked.status is SubagentTaskStatus.blocked
    with pytest.raises(TaskTransitionError, match="attempt budget"):
        await manager.resume(
            "task-1",
            lease_token=second_lease.token,
            now=now + timedelta(seconds=13),
        )


@pytest.mark.anyio
async def test_transition_records_versioned_state_and_event(manager):
    await manager.create(
        task_id="task-1",
        thread_id="thread-1",
        run_id="run-1",
        subagent_type="explore",
        description="Inspect data",
        context_packet=_context(),
    )

    running = await manager.transition("task-1", SubagentTaskStatus.running, expected_version=0)
    completed = await manager.transition(
        "task-1",
        SubagentTaskStatus.completed,
        expected_version=running.version,
        result={"findings": ["schema profiled"]},
    )

    assert running.version == 1
    assert running.started_at is not None
    assert completed.version == 2
    assert completed.result == {"findings": ["schema profiled"]}
    assert completed.completed_at is not None
    events = await manager.list_events("task-1")
    assert [event.event_type for event in events] == [
        "task.created",
        "task.running",
        "task.completed",
    ]


@pytest.mark.anyio
async def test_invalid_transition_and_terminal_mutation_fail_closed(manager):
    await manager.create(
        task_id="task-1",
        thread_id="thread-1",
        run_id="run-1",
        subagent_type="explore",
        description="Inspect data",
        context_packet=_context(),
    )

    with pytest.raises(TaskTransitionError):
        await manager.transition("task-1", SubagentTaskStatus.completed, result={"ok": True})

    running = await manager.transition("task-1", SubagentTaskStatus.running)
    completed = await manager.transition(
        "task-1",
        SubagentTaskStatus.completed,
        expected_version=running.version,
        result={"ok": True},
    )
    with pytest.raises(TaskTransitionError):
        await manager.transition("task-1", SubagentTaskStatus.running, expected_version=completed.version)


@pytest.mark.anyio
async def test_completed_and_failed_require_structured_payload(manager):
    await manager.create(
        task_id="task-1",
        thread_id="thread-1",
        run_id="run-1",
        subagent_type="explore",
        description="Inspect data",
        context_packet=_context(),
    )
    running = await manager.transition("task-1", SubagentTaskStatus.running)

    with pytest.raises(TaskTransitionError, match="result"):
        await manager.transition("task-1", SubagentTaskStatus.completed, expected_version=running.version)
    with pytest.raises(TaskTransitionError, match="error"):
        await manager.transition("task-1", SubagentTaskStatus.failed, expected_version=running.version)


@pytest.mark.anyio
async def test_expected_version_prevents_lost_update(manager):
    await manager.create(
        task_id="task-1",
        thread_id="thread-1",
        run_id="run-1",
        subagent_type="explore",
        description="Inspect data",
        context_packet=_context(),
    )
    await manager.transition("task-1", SubagentTaskStatus.running, expected_version=0)

    with pytest.raises(TaskVersionConflictError):
        await manager.transition("task-1", SubagentTaskStatus.cancelled, expected_version=0)


@pytest.mark.anyio
async def test_custom_event_is_idempotent(manager):
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
        {"step": "profile"},
        idempotency_key="progress:profile",
    )
    second = await manager.append_event(
        "task-1",
        "task.progress",
        {"step": "profile"},
        idempotency_key="progress:profile",
    )

    assert second == first
    assert len(await manager.list_events("task-1")) == 2
    assert (await manager.get("task-1")).version == 1


@pytest.mark.anyio
async def test_lease_fencing_rejects_stale_worker(manager):
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

    lease_1 = await manager.acquire_lease("task-1", owner="worker-a", ttl=timedelta(seconds=30), now=now)
    with pytest.raises(TaskLeaseConflictError):
        await manager.acquire_lease("task-1", owner="worker-b", ttl=timedelta(seconds=30), now=now)

    lease_2 = await manager.acquire_lease(
        "task-1",
        owner="worker-b",
        ttl=timedelta(seconds=30),
        now=now + timedelta(seconds=31),
    )

    assert lease_2.token == lease_1.token + 1
    with pytest.raises(TaskLeaseConflictError):
        await manager.transition(
            "task-1",
            SubagentTaskStatus.running,
            lease_token=lease_1.token,
            now=now + timedelta(seconds=32),
        )

    running = await manager.transition(
        "task-1",
        SubagentTaskStatus.running,
        lease_token=lease_2.token,
        now=now + timedelta(seconds=32),
    )
    assert running.status is SubagentTaskStatus.running


@pytest.mark.anyio
async def test_restart_reconciliation_blocks_orphaned_running_task(manager):
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
    lease = await manager.acquire_lease("task-1", owner="worker-a", ttl=timedelta(seconds=10), now=now)
    await manager.transition("task-1", SubagentTaskStatus.running, lease_token=lease.token, now=now)

    reconciled = await manager.reconcile_orphaned_inflight(
        before=now + timedelta(seconds=11),
        reason="Gateway restarted while the worker was running.",
    )

    assert [task.task_id for task in reconciled] == ["task-1"]
    assert reconciled[0].status is SubagentTaskStatus.blocked
    assert reconciled[0].wait_reason == "Gateway restarted while the worker was running."
    assert reconciled[0].lease_owner is None
    assert (await manager.list_events("task-1"))[-1].event_type == "task.recovery_blocked"
