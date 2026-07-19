"""Bounded Commerce Run aggregate and lifecycle transitions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Self

from pydantic import Field, model_validator

from app.commerce.domain.enums import RunPhase, RunStatus, RunType
from app.commerce.domain.ids import CaseId, RunId, WorkspaceId
from app.commerce.domain.models import CommerceModel


class InvalidRunTransitionError(ValueError):
    """The requested Run status change is not legal."""


_TERMINAL_RUN_STATUSES = frozenset(
    {
        RunStatus.COMPLETED,
        RunStatus.FAILED,
        RunStatus.TIMEOUT,
        RunStatus.CANCELLED,
        RunStatus.BLOCKED,
    }
)

_ALLOWED_RUN_TRANSITIONS = {
    RunStatus.QUEUED: frozenset(
        {RunStatus.RUNNING, RunStatus.CANCELLED, RunStatus.BLOCKED}
    ),
    RunStatus.RUNNING: frozenset(
        {
            RunStatus.WAITING,
            RunStatus.COMPLETED,
            RunStatus.FAILED,
            RunStatus.TIMEOUT,
            RunStatus.CANCELLED,
            RunStatus.BLOCKED,
        }
    ),
    RunStatus.WAITING: frozenset(
        {
            RunStatus.RUNNING,
            RunStatus.TIMEOUT,
            RunStatus.CANCELLED,
            RunStatus.BLOCKED,
        }
    ),
    RunStatus.COMPLETED: frozenset(),
    RunStatus.FAILED: frozenset(),
    RunStatus.TIMEOUT: frozenset(),
    RunStatus.CANCELLED: frozenset(),
    RunStatus.BLOCKED: frozenset(),
}


class CommerceRun(CommerceModel):
    """A bounded, auditable execution attached to a long-lived Case."""

    id: RunId = Field(default_factory=RunId.new)
    workspace_id: WorkspaceId
    case_id: CaseId
    run_type: RunType
    status: RunStatus = RunStatus.QUEUED
    phase: RunPhase
    goal: str = Field(min_length=1)
    idempotency_key_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    wait_reason: str | None = Field(default=None, min_length=1)
    stop_reason: str | None = Field(default=None, min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    ended_at: datetime | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    version: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def keep_status_and_timestamps_consistent(self) -> Self:
        if self.updated_at < self.created_at:
            raise ValueError("Run updated_at cannot precede created_at")
        if self.started_at is not None and self.started_at < self.created_at:
            raise ValueError("Run started_at cannot precede created_at")
        terminal = self.status in _TERMINAL_RUN_STATUSES
        if terminal:
            if self.ended_at is None:
                raise ValueError("terminal Run requires ended_at")
            if self.stop_reason is None:
                raise ValueError("terminal Run requires stop_reason")
        else:
            if self.ended_at is not None:
                raise ValueError("non-terminal Run cannot carry ended_at")
            if self.stop_reason is not None:
                raise ValueError("non-terminal Run cannot carry stop_reason")
        if self.ended_at is not None:
            lower_bound = self.started_at or self.created_at
            if self.ended_at < lower_bound:
                raise ValueError("Run ended_at cannot precede its start")
        if self.status in {RunStatus.RUNNING, RunStatus.WAITING}:
            if self.started_at is None:
                raise ValueError("active Run requires started_at")
        elif self.status is RunStatus.QUEUED and self.started_at is not None:
            raise ValueError("queued Run cannot carry started_at")
        if self.status is RunStatus.WAITING:
            if self.wait_reason is None:
                raise ValueError("waiting Run requires wait_reason")
        elif self.wait_reason is not None:
            raise ValueError("only waiting Run can carry wait_reason")
        return self

    def transition_to(
        self,
        target: RunStatus,
        *,
        phase: RunPhase | None = None,
        wait_reason: str | None = None,
        stop_reason: str | None = None,
        occurred_at: datetime | None = None,
    ) -> Self:
        if target not in _ALLOWED_RUN_TRANSITIONS[self.status]:
            raise InvalidRunTransitionError(
                f"Run cannot transition from {self.status.value} to {target.value}"
            )
        occurred = occurred_at or datetime.now(UTC)
        if occurred < self.updated_at:
            raise ValueError("Run transition time cannot precede updated_at")
        if target is RunStatus.WAITING and wait_reason is None:
            raise ValueError("Waiting transition requires wait_reason")
        if target in _TERMINAL_RUN_STATUSES and stop_reason is None:
            raise ValueError("Terminal transition requires stop_reason")

        started_at = self.started_at
        if target is RunStatus.RUNNING and started_at is None:
            started_at = occurred
        ended_at = occurred if target in _TERMINAL_RUN_STATUSES else None
        return self.model_copy(
            update={
                "status": target,
                "phase": phase or self.phase,
                "wait_reason": wait_reason if target is RunStatus.WAITING else None,
                "stop_reason": (
                    stop_reason if target in _TERMINAL_RUN_STATUSES else None
                ),
                "started_at": started_at,
                "ended_at": ended_at,
                "updated_at": occurred,
                "version": self.version + 1,
            }
        )
