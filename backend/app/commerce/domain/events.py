"""Versioned Commerce Domain Event envelopes and deterministic projections."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Self

from pydantic import Field, model_validator

from app.commerce.domain.enums import CaseSeverity, CaseStatus
from app.commerce.domain.ids import (
    CaseId,
    CorrelationId,
    EventId,
    RunId,
    TraceId,
    WorkspaceId,
)
from app.commerce.domain.models import CommerceModel


class DomainEventActor(StrEnum):
    SYSTEM = "system"
    USER = "user"
    AGENT = "agent"
    POLICY = "policy"


class NewDomainEvent(CommerceModel):
    """Caller-supplied event data before aggregate sequences are allocated."""

    id: EventId = Field(default_factory=EventId.new)
    workspace_id: WorkspaceId
    case_id: CaseId | None = None
    run_id: RunId | None = None
    event_type: str = Field(pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+$")
    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    trace_id: TraceId
    correlation_id: CorrelationId
    causation_event_id: EventId | None = None
    actor: DomainEventActor
    payload: dict[str, Any]

    @model_validator(mode="after")
    def require_aggregate(self) -> Self:
        if self.case_id is None and self.run_id is None:
            raise ValueError("Domain Event requires case_id or run_id")
        return self


class DomainEventEnvelope(NewDomainEvent):
    """Persisted append-only event with monotonic aggregate sequences."""

    case_sequence: int | None = Field(default=None, ge=1)
    run_sequence: int | None = Field(default=None, ge=1)
    recorded_at: datetime

    @model_validator(mode="after")
    def require_matching_sequences(self) -> Self:
        if (self.case_id is None) != (self.case_sequence is None):
            raise ValueError("case_sequence presence must match case_id presence")
        if (self.run_id is None) != (self.run_sequence is None):
            raise ValueError("run_sequence presence must match run_id presence")
        return self


class CaseProjection(CommerceModel):
    workspace_id: WorkspaceId
    case_id: CaseId
    title: str = Field(min_length=1)
    severity: CaseSeverity
    status: CaseStatus
    version: int = Field(ge=1)
    last_case_sequence: int = Field(ge=1)


def replay_case_projection(events: tuple[DomainEventEnvelope, ...]) -> CaseProjection:
    """Rebuild a Case projection from its authoritative event stream."""

    if not events:
        raise ValueError("Case projection requires at least one event")
    first = events[0]
    if first.case_id is None or first.case_sequence != 1 or first.event_type != "case.created":
        raise ValueError("Case projection must start with case.created at case_sequence=1")

    expected_sequence = 1
    workspace_id = first.workspace_id
    case_id = first.case_id
    projection: CaseProjection | None = None
    for event in events:
        if event.workspace_id != workspace_id or event.case_id != case_id:
            raise ValueError("Case projection events must belong to one workspace and case")
        if event.case_sequence != expected_sequence:
            raise ValueError("Case event sequences must be contiguous and ordered")
        expected_sequence += 1

        if event.event_type == "case.created":
            projection = CaseProjection(
                workspace_id=workspace_id,
                case_id=case_id,
                title=event.payload["title"],
                severity=CaseSeverity(event.payload["severity"]),
                status=CaseStatus(event.payload["status"]),
                version=int(event.payload["version"]),
                last_case_sequence=event.case_sequence,
            )
            continue
        if projection is None:
            raise ValueError("Case projection is missing case.created")
        if event.event_type in {"case.status_changed", "case.reopened", "case.updated"}:
            projection = projection.model_copy(
                update={
                    "title": event.payload.get("title", projection.title),
                    "severity": CaseSeverity(
                        event.payload.get("severity", projection.severity.value)
                    ),
                    "status": CaseStatus(
                        event.payload.get(
                            "to_status",
                            event.payload.get("status", projection.status.value),
                        )
                    ),
                    "version": int(event.payload["version"]),
                    "last_case_sequence": event.case_sequence,
                }
            )
        else:
            projection = projection.model_copy(
                update={"last_case_sequence": event.case_sequence}
            )

    if projection is None:
        raise ValueError("Case projection is missing case.created")
    return projection
