"""Concurrency-safe Checkpoint accounting for parallel Commerce Paths."""

from __future__ import annotations

import threading

from app.commerce.agents.budget import BudgetManager, BudgetUsage
from app.commerce.agents.goal_loop import GoalLoopCheckpoint, SkillVersionRef
from app.commerce.agents.subagent_adapter import (
    CommerceAgentTask,
    CommerceSubagentOutcome,
)


class FanoutCheckpointError(ValueError):
    """Raised when parallel Path checkpoint state is inconsistent."""


class FanoutCheckpointLedger:
    """Remove completed tasks and accumulate usage exactly once per Path."""

    def __init__(
        self,
        *,
        base: GoalLoopCheckpoint,
        tasks: tuple[CommerceAgentTask, ...],
    ) -> None:
        if len(tasks) > 3:
            raise FanoutCheckpointError("Fan-out checkpoint supports at most three Paths")
        task_ids = tuple(task.task_id for task in tasks)
        if len(task_ids) != len(set(task_ids)):
            raise FanoutCheckpointError("Fan-out checkpoint Task IDs must be unique")
        path_types = tuple(task.path_type for task in tasks)
        if len(path_types) != len(set(path_types)):
            raise FanoutCheckpointError("Fan-out checkpoint Path types must be unique")
        if base.active_path_task_ids:
            raise FanoutCheckpointError("Base fan-out checkpoint must have no active Paths")
        if len(tasks) > base.budget_snapshot.limit.max_path_agents:
            raise FanoutCheckpointError("Selected Paths exceed the Run path-agent budget")
        if tasks:
            identity = (base.workspace_id, base.case_id, base.run_id)
            if any(
                (task.workspace_id, task.case_id, task.run_id) != identity
                for task in tasks
            ):
                raise FanoutCheckpointError(
                    "Fan-out tasks must match the base Workspace, Case and Run"
                )
        self._base = base
        self._tasks = {task.task_id: task for task in tasks}
        self._active = list(task_ids)
        self._usage = base.budget_snapshot.usage
        self._completed: dict[object, GoalLoopCheckpoint] = {}
        self._assignments = tuple(task.model_assignment for task in tasks)
        self._skills = tuple(
            SkillVersionRef(skill_id=task.skill_id, version=task.skill_version)
            for task in tasks
        )
        self._lock = threading.Lock()

    def pre_checkpoint(self, task: CommerceAgentTask) -> GoalLoopCheckpoint:
        """Return a Path-scoped pre-call checkpoint with all tasks active."""

        self._require_task(task)
        return self._checkpoint(task)

    def post_checkpoint_builder(self, task: CommerceAgentTask):
        """Return the Supervisor callback for one Path task."""

        self._require_task(task)
        return lambda outcome: self.complete(task, outcome)

    def complete(
        self,
        task: CommerceAgentTask,
        outcome: CommerceSubagentOutcome,
    ) -> GoalLoopCheckpoint:
        """Atomically consume terminal usage and remove one active task."""

        self._require_task(task)
        if outcome.task_id != task.task_id or outcome.path_type is not task.path_type:
            raise FanoutCheckpointError("Outcome identity does not match fan-out task")
        with self._lock:
            existing = self._completed.get(task.task_id)
            if existing is not None:
                return existing
            if task.task_id not in self._active:
                raise FanoutCheckpointError("Fan-out task is not active")

            result = outcome.result
            tokens = (
                result.cost.input_tokens + result.cost.output_tokens if result else 0
            )
            wall_time_seconds = result.cost.latency_ms / 1000 if result else 0.0
            tool_calls = len(outcome.tool_events) + (
                result.cost.tool_call_count if result else 0
            )
            values = self._usage.model_dump()
            values.update(
                {
                    "path_agents": self._usage.path_agents + 1,
                    "tool_calls": self._usage.tool_calls + tool_calls,
                    "tokens": self._usage.tokens + tokens,
                    "wall_time_seconds": (
                        self._usage.wall_time_seconds + wall_time_seconds
                    ),
                }
            )
            usage = BudgetUsage.model_validate(values)
            snapshot = BudgetManager(
                self._base.budget_snapshot.limit,
                initial_usage=usage,
            ).snapshot
            self._usage = usage
            self._active.remove(task.task_id)
            checkpoint = self._checkpoint(task, budget_snapshot=snapshot)
            self._completed[task.task_id] = checkpoint
            return checkpoint

    def _checkpoint(
        self,
        task: CommerceAgentTask,
        *,
        budget_snapshot=None,
    ) -> GoalLoopCheckpoint:
        return self._base.model_copy(
            update={
                "budget_snapshot": budget_snapshot or BudgetManager(
                    self._base.budget_snapshot.limit,
                    initial_usage=self._usage,
                ).snapshot,
                "active_path_task_ids": tuple(self._active),
                "model_assignments": self._assignments,
                "skill_versions": self._skills,
                "context_sha256": task.context_sha256,
            }
        )

    def _require_task(self, task: CommerceAgentTask) -> None:
        if self._tasks.get(task.task_id) != task:
            raise FanoutCheckpointError("Task is not registered in this fan-out")
