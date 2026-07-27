"""Bounded parallel execution and Evidence Barrier join for Commerce Paths."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from app.commerce.agents.contracts import PathType
from app.commerce.agents.evidence_barrier import (
    EvidenceBarrier,
    EvidenceBarrierResult,
)
from app.commerce.agents.goal_loop import GoalLoopCheckpoint
from app.commerce.agents.subagent_adapter import (
    CommerceAgentTask,
    CommerceSubagentOutcome,
    CommerceSubagentStatus,
)
from app.commerce.agents.subagent_committer import (
    CommerceSubagentCommitReceipt,
)
from app.commerce.domain.ids import AgentTaskId
from app.commerce.domain.models import CommerceModel
from app.commerce.persistence.runs import RunLeaseCredentials

PostCheckpointBuilder = Callable[[CommerceSubagentOutcome], GoalLoopCheckpoint]


@dataclass(frozen=True)
class CommerceSubagentFanoutEntry:
    """All state required to execute one independent Path task."""

    task: CommerceAgentTask
    context: Any
    manifest: Any
    pre_checkpoint: GoalLoopCheckpoint
    post_checkpoint_builder: PostCheckpointBuilder
    lease: RunLeaseCredentials
    supervisor: Any


class CommerceSubagentFanoutPath(CommerceModel):
    task_id: AgentTaskId
    path_type: PathType
    outcome_status: CommerceSubagentStatus | None = None
    commit_status: CommerceSubagentStatus | None = None
    wall_time_ms: float
    model_latency_ms: float = 0.0
    total_tokens: int = 0
    tool_turn_count: int = 0
    error_type: str | None = None


class CommerceSubagentFanoutResult(CommerceModel):
    selected_task_ids: tuple[AgentTaskId, ...]
    paths: tuple[CommerceSubagentFanoutPath, ...]
    outcomes: tuple[CommerceSubagentOutcome, ...]
    receipts: tuple[CommerceSubagentCommitReceipt, ...]
    barrier: EvidenceBarrierResult
    wall_time_ms: float
    critical_path_ms: float


class CommerceSubagentFanout:
    """Run at most three Path Supervisors concurrently and join durably."""

    MAX_PATHS = 3

    def __init__(self, *, barrier: EvidenceBarrier) -> None:
        self._barrier = barrier

    async def run(
        self,
        entries: Sequence[CommerceSubagentFanoutEntry],
    ) -> CommerceSubagentFanoutResult:
        selected = tuple(entries)
        if len(selected) > self.MAX_PATHS:
            raise ValueError("Commerce Subagent fan-out supports at most three Paths")
        self._validate_entries(selected)
        started = time.perf_counter()

        async def execute(entry: CommerceSubagentFanoutEntry):
            path_started = time.perf_counter()
            try:
                supervised = await entry.supervisor.run(
                    entry.task,
                    context=entry.context,
                    manifest=entry.manifest,
                    pre_checkpoint=entry.pre_checkpoint,
                    post_checkpoint_builder=entry.post_checkpoint_builder,
                    lease=entry.lease,
                )
            except Exception as exc:
                return (
                    CommerceSubagentFanoutPath(
                        task_id=entry.task.task_id,
                        path_type=entry.task.path_type,
                        wall_time_ms=(time.perf_counter() - path_started) * 1000,
                        error_type=type(exc).__name__,
                    ),
                    None,
                    None,
                )

            outcome = supervised.outcome
            result = outcome.result
            return (
                CommerceSubagentFanoutPath(
                    task_id=entry.task.task_id,
                    path_type=entry.task.path_type,
                    outcome_status=outcome.status,
                    commit_status=supervised.terminal_commit.status,
                    wall_time_ms=(time.perf_counter() - path_started) * 1000,
                    model_latency_ms=(result.cost.latency_ms if result else 0.0),
                    total_tokens=(
                        result.cost.input_tokens + result.cost.output_tokens
                        if result
                        else 0
                    ),
                    tool_turn_count=len(outcome.tool_events),
                ),
                outcome,
                supervised.terminal_commit,
            )

        path_results = tuple(await asyncio.gather(*(execute(entry) for entry in selected)))
        paths = tuple(item[0] for item in path_results)
        outcomes = tuple(item[1] for item in path_results if item[1] is not None)
        receipts = tuple(item[2] for item in path_results if item[2] is not None)
        barrier = await self._barrier.evaluate(
            tasks=tuple(entry.task for entry in selected),
            outcomes=outcomes,
            receipts=receipts,
        )
        wall_time_ms = (time.perf_counter() - started) * 1000
        critical_path_ms = max((item.wall_time_ms for item in paths), default=0.0)
        return CommerceSubagentFanoutResult(
            selected_task_ids=tuple(entry.task.task_id for entry in selected),
            paths=paths,
            outcomes=outcomes,
            receipts=receipts,
            barrier=barrier,
            wall_time_ms=wall_time_ms,
            critical_path_ms=critical_path_ms,
        )

    @staticmethod
    def _validate_entries(entries: tuple[CommerceSubagentFanoutEntry, ...]) -> None:
        task_ids = tuple(entry.task.task_id for entry in entries)
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("Fan-out Task IDs must be unique")
        path_types = tuple(entry.task.path_type for entry in entries)
        if len(path_types) != len(set(path_types)):
            raise ValueError("Fan-out Path types must be unique")
        if entries:
            identity = (
                entries[0].task.workspace_id,
                entries[0].task.case_id,
                entries[0].task.run_id,
            )
            if any(
                (
                    entry.task.workspace_id,
                    entry.task.case_id,
                    entry.task.run_id,
                )
                != identity
                for entry in entries[1:]
            ):
                raise ValueError("Fan-out entries must share one Workspace, Case and Run")
