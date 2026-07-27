"""Versioned contracts for durable Parent–Subagent tasks."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


def _require_aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        raise ValueError("datetime values must be timezone-aware")
    return value


class SubagentTaskStatus(StrEnum):
    """Durable lifecycle states exposed to Parent, UI, and recovery."""

    queued = "queued"
    running = "running"
    waiting = "waiting"
    waiting_approval = "waiting_approval"
    blocked = "blocked"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"
    timed_out = "timed_out"

    @property
    def is_terminal(self) -> bool:
        return self in {
            type(self).completed,
            type(self).failed,
            type(self).cancelled,
            type(self).timed_out,
        }


class ContextPacket(BaseModel):
    """Minimal, versioned context delegated to a subagent."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "deerflow.subagent-context@1.0.0"
    goal: str = Field(min_length=1, max_length=8_000)
    source_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    constraints: dict[str, Any] = Field(default_factory=dict)
    available_skills: tuple[str, ...] = ()
    available_tools: tuple[str, ...] = ()
    budget: dict[str, Any] = Field(default_factory=dict)
    expected_output_schema: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("schema_version", "goal")
    @classmethod
    def _non_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value


class SubagentTask(BaseModel):
    """Immutable snapshot of one durable subagent task."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str = Field(min_length=1, max_length=64)
    thread_id: str = Field(min_length=1, max_length=64)
    run_id: str = Field(min_length=1, max_length=64)
    user_id: str | None = Field(default=None, max_length=64)
    parent_task_id: str | None = Field(default=None, max_length=64)
    subagent_type: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=512)
    context_packet: ContextPacket
    tool_policy: dict[str, Any] = Field(default_factory=dict)
    depends_on: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    status: SubagentTaskStatus = SubagentTaskStatus.queued
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    checkpoint: dict[str, Any] | None = None
    telemetry: dict[str, Any] = Field(default_factory=dict)
    wait_reason: str | None = Field(default=None, max_length=2_000)

    version: int = Field(default=0, ge=0)
    event_seq: int = Field(default=1, ge=1)
    attempt: int = Field(default=1, ge=1)
    max_attempts: int = Field(default=1, ge=1)
    priority: int = Field(default=0, ge=-100, le=100)

    lease_owner: str | None = Field(default=None, max_length=128)
    lease_token: int = Field(default=0, ge=0)
    lease_expires_at: datetime | None = None

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @field_validator("task_id", "thread_id", "run_id", "subagent_type", "description")
    @classmethod
    def _identity_non_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value

    @field_validator("created_at", "updated_at", "started_at", "completed_at", "lease_expires_at")
    @classmethod
    def _timezone_aware(cls, value: datetime | None) -> datetime | None:
        return _require_aware(value)

    @model_validator(mode="after")
    def _validate_lineage(self) -> SubagentTask:
        if self.parent_task_id == self.task_id:
            raise ValueError("task cannot be its own parent")
        if self.task_id in self.depends_on:
            raise ValueError("task cannot depend on itself")
        if len(set(self.depends_on)) != len(self.depends_on):
            raise ValueError("task dependencies must be unique")
        if self.attempt > self.max_attempts:
            raise ValueError("attempt cannot exceed max_attempts")
        return self

    @property
    def is_terminal(self) -> bool:
        return self.status.is_terminal


class SubagentTaskEvent(BaseModel):
    """Append-only event emitted by the durable task lifecycle."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str
    thread_id: str
    run_id: str
    seq: int = Field(ge=1)
    event_type: str = Field(min_length=1, max_length=64)
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, max_length=256)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at")
    @classmethod
    def _event_time_aware(cls, value: datetime) -> datetime:
        return _require_aware(value)  # type: ignore[return-value]


class TaskLease(BaseModel):
    """Fencing lease granted to one worker."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str
    owner: str
    token: int = Field(ge=1)
    expires_at: datetime
    task_version: int = Field(ge=1)

    @field_validator("expires_at")
    @classmethod
    def _lease_time_aware(cls, value: datetime) -> datetime:
        return _require_aware(value)  # type: ignore[return-value]
