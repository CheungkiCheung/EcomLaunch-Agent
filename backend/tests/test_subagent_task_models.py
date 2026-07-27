"""Pure contracts for durable Parent–Subagent tasks."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from deerflow.subagents.tasks import ContextPacket, SubagentTask, SubagentTaskStatus


def _context() -> ContextPacket:
    return ContextPacket(
        goal="Inspect the uploaded order data",
        source_refs=("dataset:orders",),
        available_skills=("commerce-data-profile",),
        available_tools=("dataset_schema",),
        budget={"max_turns": 8, "max_tokens": 12_000},
        expected_output_schema={"type": "object"},
    )


def test_context_packet_is_versioned_and_immutable():
    packet = _context()

    assert packet.schema_version == "deerflow.subagent-context@1.0.0"
    with pytest.raises(ValidationError):
        packet.goal = "changed"


@pytest.mark.parametrize("goal", ["", "   "])
def test_context_packet_rejects_blank_goal(goal):
    with pytest.raises(ValidationError):
        ContextPacket(goal=goal)


def test_subagent_task_rejects_self_parent_and_dependency():
    with pytest.raises(ValidationError):
        SubagentTask(
            task_id="task-1",
            thread_id="thread-1",
            run_id="run-1",
            parent_task_id="task-1",
            subagent_type="explore",
            description="Inspect data",
            context_packet=_context(),
        )

    with pytest.raises(ValidationError):
        SubagentTask(
            task_id="task-1",
            thread_id="thread-1",
            run_id="run-1",
            subagent_type="explore",
            description="Inspect data",
            context_packet=_context(),
            depends_on=("task-1",),
        )


def test_subagent_task_rejects_duplicate_dependencies():
    with pytest.raises(ValidationError):
        SubagentTask(
            task_id="task-1",
            thread_id="thread-1",
            run_id="run-1",
            subagent_type="explore",
            description="Inspect data",
            context_packet=_context(),
            depends_on=("task-a", "task-a"),
        )


def test_terminal_status_contract_is_explicit():
    assert SubagentTaskStatus.completed.is_terminal is True
    assert SubagentTaskStatus.failed.is_terminal is True
    assert SubagentTaskStatus.cancelled.is_terminal is True
    assert SubagentTaskStatus.timed_out.is_terminal is True
    assert SubagentTaskStatus.queued.is_terminal is False
    assert SubagentTaskStatus.running.is_terminal is False
    assert SubagentTaskStatus.blocked.is_terminal is False


def test_task_timestamps_must_be_timezone_aware():
    with pytest.raises(ValidationError):
        SubagentTask(
            task_id="task-1",
            thread_id="thread-1",
            run_id="run-1",
            subagent_type="explore",
            description="Inspect data",
            context_packet=_context(),
            created_at=datetime(2026, 7, 24, 12, 0, 0),
        )

    task = SubagentTask(
        task_id="task-1",
        thread_id="thread-1",
        run_id="run-1",
        subagent_type="explore",
        description="Inspect data",
        context_packet=_context(),
        created_at=datetime(2026, 7, 24, 12, 0, 0, tzinfo=UTC),
    )
    assert task.created_at.tzinfo is not None
