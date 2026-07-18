"""Deterministic Domain Event envelope and Case projection contracts."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.commerce.domain.enums import CaseSeverity, CaseStatus
from app.commerce.domain.events import (
    DomainEventActor,
    DomainEventEnvelope,
    NewDomainEvent,
    replay_case_projection,
)
from app.commerce.domain.ids import (
    CaseId,
    CorrelationId,
    EventId,
    RunId,
    TraceId,
    WorkspaceId,
)


def _event(
    *,
    event_type: str,
    case_id: CaseId,
    sequence: int,
    payload: dict,
) -> DomainEventEnvelope:
    return DomainEventEnvelope(
        id=EventId.new(),
        workspace_id=WorkspaceId("wsp_0123456789abcdef0123456789abcdef"),
        case_id=case_id,
        event_type=event_type,
        schema_version="1.0",
        case_sequence=sequence,
        occurred_at=datetime(2026, 7, 18, 12, sequence, tzinfo=UTC),
        recorded_at=datetime(2026, 7, 18, 12, sequence, tzinfo=UTC),
        trace_id=TraceId("trace_0123456789abcdef0123456789abcdef"),
        correlation_id=CorrelationId("corr_0123456789abcdef0123456789abcdef"),
        actor=DomainEventActor.SYSTEM,
        payload=payload,
    )


def test_new_domain_event_requires_a_case_or_run_aggregate():
    with pytest.raises(ValidationError, match="case_id or run_id"):
        NewDomainEvent(
            workspace_id=WorkspaceId.new(),
            event_type="case.created",
            trace_id=TraceId.new(),
            correlation_id=CorrelationId.new(),
            actor=DomainEventActor.SYSTEM,
            payload={},
        )


def test_event_sequence_presence_must_match_aggregate_presence():
    with pytest.raises(ValidationError, match="case_sequence"):
        DomainEventEnvelope(
            id=EventId.new(),
            workspace_id=WorkspaceId.new(),
            run_id=RunId.new(),
            event_type="case.created",
            case_sequence=1,
            occurred_at=datetime.now(UTC),
            recorded_at=datetime.now(UTC),
            trace_id=TraceId.new(),
            correlation_id=CorrelationId.new(),
            actor=DomainEventActor.SYSTEM,
            payload={},
        )


def test_replay_case_projection_requires_contiguous_ordered_events():
    case_id = CaseId.new()
    created = _event(
        event_type="case.created",
        case_id=case_id,
        sequence=1,
        payload={
            "title": "Delivery outlier",
            "severity": "high",
            "status": "new",
            "version": 1,
        },
    )
    triaged = _event(
        event_type="case.status_changed",
        case_id=case_id,
        sequence=2,
        payload={"from_status": "new", "to_status": "triaged", "version": 2},
    )

    projection = replay_case_projection((created, triaged))

    assert projection.case_id == case_id
    assert projection.title == "Delivery outlier"
    assert projection.severity is CaseSeverity.HIGH
    assert projection.status is CaseStatus.TRIAGED
    assert projection.version == 2
    assert projection.last_case_sequence == 2

    with pytest.raises(ValueError, match="contiguous"):
        replay_case_projection((created, triaged.model_copy(update={"case_sequence": 3})))
