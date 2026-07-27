"""SQLAlchemy rows for durable subagent tasks and append-only events."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from deerflow.persistence.base import Base


class SubagentTaskRow(Base):
    __tablename__ = "subagent_tasks"

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    thread_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    parent_task_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    subagent_type: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(String(512), nullable=False)
    context_packet_json: Mapped[dict] = mapped_column(JSON, default=dict)
    tool_policy_json: Mapped[dict] = mapped_column(JSON, default=dict)
    depends_on_json: Mapped[list] = mapped_column(JSON, default=list)
    task_metadata: Mapped[dict] = mapped_column(JSON, default=dict)

    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    checkpoint_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    telemetry_json: Mapped[dict] = mapped_column(JSON, default=dict)
    wait_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    version: Mapped[int] = mapped_column(default=0, nullable=False)
    event_seq: Mapped[int] = mapped_column(default=1, nullable=False)
    attempt: Mapped[int] = mapped_column(default=1, nullable=False)
    max_attempts: Mapped[int] = mapped_column(default=1, nullable=False)
    priority: Mapped[int] = mapped_column(default=0, nullable=False)

    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_token: Mapped[int] = mapped_column(default=0, nullable=False)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_subagent_tasks_run_status", "run_id", "status"),
        Index("ix_subagent_tasks_thread_status", "thread_id", "status"),
    )


class SubagentTaskEventRow(Base):
    __tablename__ = "subagent_task_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("subagent_tasks.task_id", ondelete="CASCADE"),
        nullable=False,
    )
    thread_id: Mapped[str] = mapped_column(String(64), nullable=False)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    seq: Mapped[int] = mapped_column(nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    idempotency_key: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    __table_args__ = (
        UniqueConstraint("task_id", "seq", name="uq_subagent_task_event_seq"),
        UniqueConstraint("task_id", "idempotency_key", name="uq_subagent_task_event_idempotency"),
        Index("ix_subagent_task_events_task_seq", "task_id", "seq"),
        Index("ix_subagent_task_events_run", "run_id", "task_id", "seq"),
    )
