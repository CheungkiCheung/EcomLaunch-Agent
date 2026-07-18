"""Append-only SQL Domain Event Store with aggregate-local sequencing."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.commerce.domain.events import DomainEventEnvelope, NewDomainEvent
from app.commerce.domain.ids import CaseId, RunId, WorkspaceId
from app.commerce.persistence.models import DomainEventRow


class DuplicateEventError(ValueError):
    """An Event ID was reused for different immutable event data."""


class EventSequenceConflictError(RuntimeError):
    """A concurrent writer claimed the same aggregate sequence."""


class EventStreamInvariantError(ValueError):
    """The event would make an aggregate stream impossible to replay."""


@runtime_checkable
class DomainEventStore(Protocol):
    async def append(self, event: NewDomainEvent) -> DomainEventEnvelope: ...

    async def list_case(
        self,
        workspace_id: WorkspaceId,
        case_id: CaseId,
    ) -> tuple[DomainEventEnvelope, ...]: ...

    async def list_run(
        self,
        workspace_id: WorkspaceId,
        run_id: RunId,
    ) -> tuple[DomainEventEnvelope, ...]: ...


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _row_to_event(row: DomainEventRow) -> DomainEventEnvelope:
    return DomainEventEnvelope.model_validate(
        {
            "id": row.event_id,
            "workspace_id": row.workspace_id,
            "case_id": row.case_id,
            "run_id": row.run_id,
            "event_type": row.event_type,
            "schema_version": row.schema_version,
            "case_sequence": row.case_sequence,
            "run_sequence": row.run_sequence,
            "occurred_at": _utc(row.occurred_at),
            "recorded_at": _utc(row.recorded_at),
            "trace_id": row.trace_id,
            "correlation_id": row.correlation_id,
            "causation_event_id": row.causation_event_id,
            "actor": row.actor,
            "payload": row.payload_json,
        }
    )


def _event_identity(event: NewDomainEvent | DomainEventEnvelope) -> dict:
    return {
        "id": event.id,
        "workspace_id": event.workspace_id,
        "case_id": event.case_id,
        "run_id": event.run_id,
        "event_type": event.event_type,
        "schema_version": event.schema_version,
        "occurred_at": event.occurred_at,
        "trace_id": event.trace_id,
        "correlation_id": event.correlation_id,
        "causation_event_id": event.causation_event_id,
        "actor": event.actor,
        "payload": event.payload,
    }


class SqlDomainEventStore:
    """Short-session event store; mutation transactions may reuse its internal append."""

    MAX_SEQUENCE_RETRIES = 20

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def append(self, event: NewDomainEvent) -> DomainEventEnvelope:
        last_error: IntegrityError | None = None
        for attempt in range(self.MAX_SEQUENCE_RETRIES):
            try:
                async with self._session_factory() as session, session.begin():
                    return await self.append_in_session(session, event)
            except IntegrityError as exc:
                last_error = exc
                await asyncio.sleep(0.001 * (attempt + 1))
        raise EventSequenceConflictError(
            "Concurrent Domain Event sequence allocation exceeded retry budget"
        ) from last_error

    async def list_case(
        self,
        workspace_id: WorkspaceId,
        case_id: CaseId,
    ) -> tuple[DomainEventEnvelope, ...]:
        statement = (
            select(DomainEventRow)
            .where(
                DomainEventRow.workspace_id == str(workspace_id),
                DomainEventRow.case_id == str(case_id),
            )
            .order_by(DomainEventRow.case_sequence.asc())
        )
        async with self._session_factory() as session:
            rows = (await session.scalars(statement)).all()
            return tuple(_row_to_event(row) for row in rows)

    async def list_run(
        self,
        workspace_id: WorkspaceId,
        run_id: RunId,
    ) -> tuple[DomainEventEnvelope, ...]:
        statement = (
            select(DomainEventRow)
            .where(
                DomainEventRow.workspace_id == str(workspace_id),
                DomainEventRow.run_id == str(run_id),
            )
            .order_by(DomainEventRow.run_sequence.asc())
        )
        async with self._session_factory() as session:
            rows = (await session.scalars(statement)).all()
            return tuple(_row_to_event(row) for row in rows)

    @staticmethod
    async def append_in_session(
        session: AsyncSession,
        event: NewDomainEvent,
    ) -> DomainEventEnvelope:
        existing_row = await session.get(DomainEventRow, str(event.id))
        if existing_row is not None:
            existing = _row_to_event(existing_row)
            if _event_identity(existing) != _event_identity(event):
                raise DuplicateEventError(
                    f"Event ID {event.id} already exists with different immutable data"
                )
            return existing

        case_sequence = None
        if event.case_id is not None:
            case_sequence = await SqlDomainEventStore._next_sequence(
                session,
                workspace_id=event.workspace_id,
                aggregate_column=DomainEventRow.case_id,
                aggregate_id=str(event.case_id),
                sequence_column=DomainEventRow.case_sequence,
            )
        run_sequence = None
        if event.run_id is not None:
            run_sequence = await SqlDomainEventStore._next_sequence(
                session,
                workspace_id=event.workspace_id,
                aggregate_column=DomainEventRow.run_id,
                aggregate_id=str(event.run_id),
                sequence_column=DomainEventRow.run_sequence,
            )

        if case_sequence == 1 and event.event_type != "case.created":
            raise EventStreamInvariantError(
                "The first event in a Case stream must be case.created"
            )
        if case_sequence is not None and case_sequence > 1 and event.event_type == "case.created":
            raise EventStreamInvariantError(
                "case.created can appear only once at the start of a Case stream"
            )

        recorded_at = datetime.now(UTC)
        payload = event.model_dump(mode="json")["payload"]
        row = DomainEventRow(
            event_id=str(event.id),
            workspace_id=str(event.workspace_id),
            case_id=str(event.case_id) if event.case_id is not None else None,
            run_id=str(event.run_id) if event.run_id is not None else None,
            event_type=event.event_type,
            schema_version=event.schema_version,
            case_sequence=case_sequence,
            run_sequence=run_sequence,
            occurred_at=event.occurred_at,
            recorded_at=recorded_at,
            trace_id=str(event.trace_id),
            correlation_id=str(event.correlation_id),
            causation_event_id=(
                str(event.causation_event_id)
                if event.causation_event_id is not None
                else None
            ),
            actor=event.actor.value,
            payload_json=payload,
        )
        session.add(row)
        await session.flush()
        return _row_to_event(row)

    @staticmethod
    async def _next_sequence(
        session: AsyncSession,
        *,
        workspace_id: WorkspaceId,
        aggregate_column,
        aggregate_id: str,
        sequence_column,
    ) -> int:
        current = await session.scalar(
            select(func.max(sequence_column)).where(
                DomainEventRow.workspace_id == str(workspace_id),
                aggregate_column == aggregate_id,
            )
        )
        return int(current or 0) + 1
