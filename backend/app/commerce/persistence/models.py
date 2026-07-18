"""SQLite/PostgreSQL-compatible Commerce ORM rows."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.commerce.persistence.base import CommerceBase


class CaseRow(CommerceBase):
    __tablename__ = "commerce_cases"

    case_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    summary: Mapped[str | None] = mapped_column(Text)
    evidence_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    hypothesis_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    action_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint("version >= 1", name="ck_commerce_cases_version_positive"),
        Index(
            "ix_commerce_cases_workspace_status_updated",
            "workspace_id",
            "status",
            "updated_at",
        ),
    )


class DomainEventRow(CommerceBase):
    __tablename__ = "commerce_domain_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    case_id: Mapped[str | None] = mapped_column(String(64), index=True)
    run_id: Mapped[str | None] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    case_sequence: Mapped[int | None] = mapped_column(Integer)
    run_sequence: Mapped[int | None] = mapped_column(Integer)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    causation_event_id: Mapped[str | None] = mapped_column(String(64))
    actor: Mapped[str] = mapped_column(String(20), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "case_id",
            "case_sequence",
            name="uq_commerce_event_case_sequence",
        ),
        UniqueConstraint(
            "run_id",
            "run_sequence",
            name="uq_commerce_event_run_sequence",
        ),
        CheckConstraint(
            "(case_id IS NOT NULL AND case_sequence IS NOT NULL) OR "
            "(case_id IS NULL AND case_sequence IS NULL)",
            name="ck_commerce_event_case_sequence_presence",
        ),
        CheckConstraint(
            "(run_id IS NOT NULL AND run_sequence IS NOT NULL) OR "
            "(run_id IS NULL AND run_sequence IS NULL)",
            name="ck_commerce_event_run_sequence_presence",
        ),
        CheckConstraint(
            "case_id IS NOT NULL OR run_id IS NOT NULL",
            name="ck_commerce_event_has_aggregate",
        ),
        Index(
            "ix_commerce_events_workspace_case_sequence",
            "workspace_id",
            "case_id",
            "case_sequence",
        ),
        Index(
            "ix_commerce_events_workspace_run_sequence",
            "workspace_id",
            "run_id",
            "run_sequence",
        ),
    )
