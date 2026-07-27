"""Heartbeat, polling and fail-closed terminal supervision for Path Subagents."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from app.commerce.agents.goal_loop import GoalLoopCheckpoint
from app.commerce.agents.subagent_adapter import (
    CommerceAgentTask,
    CommerceSubagentAdapter,
    CommerceSubagentOutcome,
    CommerceSubagentStatus,
)
from app.commerce.agents.subagent_committer import (
    CommerceSubagentCommitReceipt,
    CommerceSubagentCommitter,
)
from app.commerce.domain.ids import AgentTaskId
from app.commerce.domain.models import CommerceModel
from app.commerce.persistence.runs import RunLeaseCredentials, SqlRunLeaseRepository


class CommerceSubagentSupervisionError(RuntimeError):
    """Raised when a Harness task remains unresolved after cancellation."""


class CommerceSubagentSupervisionResult(CommerceModel):
    task_id: AgentTaskId
    outcome: CommerceSubagentOutcome
    started_commit: CommerceSubagentCommitReceipt
    terminal_commit: CommerceSubagentCommitReceipt
    heartbeat_count: int


class CommerceSubagentSupervisor:
    """Keep a lease alive while a bounded Harness task reaches a real terminal state."""

    def __init__(
        self,
        *,
        adapter: CommerceSubagentAdapter,
        committer: CommerceSubagentCommitter,
        leases: SqlRunLeaseRepository,
        lease_ttl: timedelta,
        poll_interval_seconds: float = 0.25,
        max_polls: int = 1_200,
        clock: Callable[[], datetime] | None = None,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if lease_ttl.total_seconds() <= 0:
            raise ValueError("Subagent supervisor lease TTL must be positive")
        if poll_interval_seconds < 0:
            raise ValueError("Subagent supervisor poll interval cannot be negative")
        if max_polls < 1:
            raise ValueError("Subagent supervisor max_polls must be positive")
        self._adapter = adapter
        self._committer = committer
        self._leases = leases
        self._lease_ttl = lease_ttl
        self._poll_interval_seconds = poll_interval_seconds
        self._max_polls = max_polls
        self._clock = clock or (lambda: datetime.now(UTC))
        self._sleeper = sleeper

    async def run(
        self,
        task: CommerceAgentTask,
        *,
        context: Any,
        manifest: Any,
        pre_checkpoint: Any,
        post_checkpoint_builder: Callable[[CommerceSubagentOutcome], GoalLoopCheckpoint],
        lease: RunLeaseCredentials,
    ) -> CommerceSubagentSupervisionResult:
        started_commit = await self._committer.commit_started(
            task,
            pre_checkpoint,
            lease=lease,
            checked_at=self._checked_at(),
        )
        self._adapter.start(task, context)
        heartbeat_count = 0
        outcome: CommerceSubagentOutcome | None = None

        for poll_number in range(self._max_polls):
            await self._heartbeat(task, lease)
            heartbeat_count += 1
            outcome = self._adapter.poll(task)
            if outcome.status not in {
                CommerceSubagentStatus.PENDING,
                CommerceSubagentStatus.RUNNING,
            }:
                break
            if poll_number + 1 < self._max_polls:
                await self._sleeper(self._poll_interval_seconds)

        if outcome is None or outcome.status in {
            CommerceSubagentStatus.PENDING,
            CommerceSubagentStatus.RUNNING,
        }:
            self._adapter.cancel(task)
            await self._heartbeat(task, lease)
            heartbeat_count += 1
            outcome = self._adapter.poll(task)
            if outcome.status in {
                CommerceSubagentStatus.PENDING,
                CommerceSubagentStatus.RUNNING,
            }:
                raise CommerceSubagentSupervisionError(
                    "Harness outcome remains unresolved after cancellation"
                )

        post_checkpoint = post_checkpoint_builder(outcome)
        terminal_commit = await self._committer.commit_outcome(
            task,
            outcome,
            manifest,
            post_checkpoint,
            lease=lease,
            checked_at=self._checked_at(),
            causation_event_id=started_commit.lifecycle_event_id,
        )
        self._adapter.cleanup(task)
        return CommerceSubagentSupervisionResult(
            task_id=task.task_id,
            outcome=outcome,
            started_commit=started_commit,
            terminal_commit=terminal_commit,
            heartbeat_count=heartbeat_count,
        )

    async def _heartbeat(
        self,
        task: CommerceAgentTask,
        lease: RunLeaseCredentials,
    ) -> None:
        await self._leases.heartbeat(
            task.workspace_id,
            task.run_id,
            lease,
            ttl=self._lease_ttl,
            heartbeat_at=self._checked_at(),
        )

    def _checked_at(self) -> datetime:
        checked_at = self._clock()
        if checked_at.tzinfo is None:
            return checked_at.replace(tzinfo=UTC)
        return checked_at.astimezone(UTC)
