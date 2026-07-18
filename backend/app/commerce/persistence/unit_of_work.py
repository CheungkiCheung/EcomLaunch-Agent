"""Atomic Commerce mutations that keep Case rows and Domain Events aligned."""

from __future__ import annotations

import asyncio

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.commerce.domain.enums import CaseStatus
from app.commerce.domain.events import (
    DomainEventActor,
    DomainEventEnvelope,
    NewDomainEvent,
)
from app.commerce.domain.ids import CorrelationId, EventId, TraceId
from app.commerce.domain.models import Case
from app.commerce.persistence.events import (
    EventSequenceConflictError,
    SqlDomainEventStore,
)
from app.commerce.persistence.repositories import (
    DuplicateEntityError,
    SqlCaseRepository,
)


class SqlCommerceUnitOfWork:
    """Use one SQL transaction for every state mutation and authoritative event."""

    MAX_SEQUENCE_RETRIES = 20

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_case(
        self,
        case: Case,
        *,
        trace_id: TraceId,
        correlation_id: CorrelationId,
        actor: DomainEventActor,
        causation_event_id: EventId | None = None,
    ) -> DomainEventEnvelope:
        event = NewDomainEvent(
            workspace_id=case.workspace_id,
            case_id=case.id,
            event_type="case.created",
            occurred_at=case.opened_at,
            trace_id=trace_id,
            correlation_id=correlation_id,
            causation_event_id=causation_event_id,
            actor=actor,
            payload={
                "title": case.title,
                "severity": case.severity.value,
                "status": case.status.value,
                "version": case.version,
            },
        )
        try:
            async with self._session_factory() as session, session.begin():
                await SqlCaseRepository.create_in_session(session, case)
                return await SqlDomainEventStore.append_in_session(session, event)
        except IntegrityError as exc:
            raise DuplicateEntityError(f"Case already exists: {case.id}") from exc

    async def save_case(
        self,
        case: Case,
        *,
        expected_version: int,
        trace_id: TraceId,
        correlation_id: CorrelationId,
        actor: DomainEventActor,
        causation_event_id: EventId | None = None,
    ) -> DomainEventEnvelope:
        last_error: IntegrityError | None = None
        for attempt in range(self.MAX_SEQUENCE_RETRIES):
            try:
                async with self._session_factory() as session, session.begin():
                    previous_status = await SqlCaseRepository.save_in_session(
                        session,
                        case,
                        expected_version=expected_version,
                    )
                    event_type = self._case_event_type(previous_status, case.status)
                    event = NewDomainEvent(
                        workspace_id=case.workspace_id,
                        case_id=case.id,
                        event_type=event_type,
                        occurred_at=case.updated_at,
                        trace_id=trace_id,
                        correlation_id=correlation_id,
                        causation_event_id=causation_event_id,
                        actor=actor,
                        payload={
                            "title": case.title,
                            "severity": case.severity.value,
                            "from_status": previous_status.value,
                            "to_status": case.status.value,
                            "version": case.version,
                        },
                    )
                    return await SqlDomainEventStore.append_in_session(session, event)
            except IntegrityError as exc:
                last_error = exc
                await asyncio.sleep(0.001 * (attempt + 1))
        raise EventSequenceConflictError(
            "Atomic Case/Event mutation exceeded sequence retry budget"
        ) from last_error

    @staticmethod
    def _case_event_type(previous: CaseStatus, current: CaseStatus) -> str:
        if current is CaseStatus.REOPENED and previous is CaseStatus.RESOLVED:
            return "case.reopened"
        if previous is not current:
            return "case.status_changed"
        return "case.updated"
