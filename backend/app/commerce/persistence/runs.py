"""Run projection and append-only Goal Loop Checkpoint repositories."""

from __future__ import annotations

import asyncio
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Protocol, runtime_checkable

from pydantic import Field, SecretStr, model_validator
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.commerce.agents.goal_loop import GoalLoopCheckpoint
from app.commerce.domain.enums import RunPhase, RunStatus
from app.commerce.domain.events import (
    DomainEventActor,
    DomainEventEnvelope,
    NewDomainEvent,
)
from app.commerce.domain.ids import (
    CaseId,
    CheckpointId,
    CorrelationId,
    RunId,
    TraceId,
    WorkspaceId,
)
from app.commerce.domain.models import CommerceModel
from app.commerce.domain.runs import CommerceRun
from app.commerce.persistence.events import SqlDomainEventStore
from app.commerce.persistence.models import RunCheckpointRow, RunLeaseRow, RunRow
from app.commerce.persistence.repositories import (
    DuplicateEntityError,
    EntityNotFoundError,
    OptimisticConcurrencyError,
)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _run_values(run: CommerceRun) -> dict:
    return {
        "workspace_id": str(run.workspace_id),
        "case_id": str(run.case_id),
        "run_type": run.run_type.value,
        "status": run.status.value,
        "phase": run.phase.value,
        "goal": run.goal,
        "idempotency_key_sha256": run.idempotency_key_sha256,
        "parent_run_id": str(run.parent_run_id) if run.parent_run_id else None,
        "subject_action_id": (str(run.subject_action_id) if run.subject_action_id else None),
        "action_operation": (run.action_operation.value if run.action_operation is not None else None),
        "requested_paths_json": [value.value for value in run.requested_paths],
        "wait_reason": run.wait_reason,
        "stop_reason": run.stop_reason,
        "created_at": run.created_at,
        "started_at": run.started_at,
        "ended_at": run.ended_at,
        "updated_at": run.updated_at,
        "version": run.version,
    }


def _row_to_run(row: RunRow) -> CommerceRun:
    return CommerceRun.model_validate(
        {
            "id": row.run_id,
            "workspace_id": row.workspace_id,
            "case_id": row.case_id,
            "run_type": row.run_type,
            "status": row.status,
            "phase": row.phase,
            "goal": row.goal,
            "idempotency_key_sha256": row.idempotency_key_sha256,
            "parent_run_id": row.parent_run_id,
            "subject_action_id": row.subject_action_id,
            "action_operation": row.action_operation,
            "requested_paths": tuple(row.requested_paths_json),
            "wait_reason": row.wait_reason,
            "stop_reason": row.stop_reason,
            "created_at": _utc(row.created_at),
            "started_at": _utc(row.started_at) if row.started_at else None,
            "ended_at": _utc(row.ended_at) if row.ended_at else None,
            "updated_at": _utc(row.updated_at),
            "version": row.version,
        }
    )


@runtime_checkable
class RunRepository(Protocol):
    async def create(self, run: CommerceRun) -> None: ...

    async def get(
        self,
        workspace_id: WorkspaceId,
        run_id: RunId,
    ) -> CommerceRun | None: ...


class SqlRunRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(self, run: CommerceRun) -> None:
        try:
            async with self._session_factory() as session, session.begin():
                await self.create_in_session(session, run)
        except IntegrityError as exc:
            raise DuplicateEntityError(f"Run or idempotency key already exists: {run.id}") from exc

    async def get(
        self,
        workspace_id: WorkspaceId,
        run_id: RunId,
    ) -> CommerceRun | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(RunRow).where(
                    RunRow.workspace_id == str(workspace_id),
                    RunRow.run_id == str(run_id),
                )
            )
            return _row_to_run(row) if row is not None else None

    @staticmethod
    async def get_in_session(
        session: AsyncSession,
        workspace_id: WorkspaceId,
        run_id: RunId,
    ) -> CommerceRun | None:
        row = await session.scalar(
            select(RunRow).where(
                RunRow.workspace_id == str(workspace_id),
                RunRow.run_id == str(run_id),
            )
        )
        return _row_to_run(row) if row is not None else None

    async def get_by_idempotency_key(
        self,
        workspace_id: WorkspaceId,
        case_id: CaseId,
        idempotency_key_sha256: str,
    ) -> CommerceRun | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(RunRow).where(
                    RunRow.workspace_id == str(workspace_id),
                    RunRow.case_id == str(case_id),
                    RunRow.idempotency_key_sha256 == idempotency_key_sha256,
                )
            )
            return _row_to_run(row) if row is not None else None

    async def list_case(
        self,
        workspace_id: WorkspaceId,
        case_id: CaseId,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[CommerceRun, ...]:
        if limit < 1 or limit > 500:
            raise ValueError("Run list limit must be between 1 and 500")
        if offset < 0:
            raise ValueError("Run list offset cannot be negative")
        statement = (
            select(RunRow)
            .where(
                RunRow.workspace_id == str(workspace_id),
                RunRow.case_id == str(case_id),
            )
            .order_by(RunRow.created_at.desc(), RunRow.run_id.asc())
            .limit(limit)
            .offset(offset)
        )
        async with self._session_factory() as session:
            rows = (await session.scalars(statement)).all()
            return tuple(_row_to_run(row) for row in rows)

    async def save(self, run: CommerceRun, *, expected_version: int) -> None:
        async with self._session_factory() as session, session.begin():
            await self.save_in_session(session, run, expected_version=expected_version)

    @staticmethod
    async def create_in_session(session: AsyncSession, run: CommerceRun) -> None:
        session.add(RunRow(run_id=str(run.id), **_run_values(run)))
        await session.flush()

    @staticmethod
    async def save_in_session(
        session: AsyncSession,
        run: CommerceRun,
        *,
        expected_version: int,
    ) -> tuple[RunStatus, RunPhase]:
        if expected_version < 1:
            raise ValueError("expected_version must be positive")
        if run.version != expected_version + 1:
            raise ValueError("Saved Run version must equal expected_version + 1")
        current = (
            await session.execute(
                select(RunRow.status, RunRow.phase, RunRow.version).where(
                    RunRow.workspace_id == str(run.workspace_id),
                    RunRow.run_id == str(run.id),
                )
            )
        ).one_or_none()
        if current is None:
            raise EntityNotFoundError(f"Run not found: {run.id}")
        if current.version != expected_version:
            raise OptimisticConcurrencyError(f"Run {run.id} expected version {expected_version}, found {current.version}")
        result = await session.execute(
            update(RunRow)
            .where(
                RunRow.workspace_id == str(run.workspace_id),
                RunRow.run_id == str(run.id),
                RunRow.version == expected_version,
            )
            .values(**_run_values(run))
        )
        if result.rowcount != 1:
            raise OptimisticConcurrencyError(f"Run {run.id} changed while saving version {run.version}")
        return RunStatus(current.status), RunPhase(current.phase)


class RunCheckpointRecord(CommerceModel):
    id: CheckpointId
    workspace_id: WorkspaceId
    case_id: CaseId
    run_id: RunId
    sequence: int = Field(ge=1)
    checkpoint: GoalLoopCheckpoint
    created_at: datetime

    @model_validator(mode="after")
    def match_checkpoint_identity(self):
        if self.workspace_id != self.checkpoint.workspace_id:
            raise ValueError("Checkpoint Record workspace must match payload")
        if self.case_id != self.checkpoint.case_id:
            raise ValueError("Checkpoint Record Case must match payload")
        if self.run_id != self.checkpoint.run_id:
            raise ValueError("Checkpoint Record Run must match payload")
        return self


def _row_to_checkpoint(row: RunCheckpointRow) -> RunCheckpointRecord:
    return RunCheckpointRecord(
        id=CheckpointId(row.checkpoint_id),
        workspace_id=WorkspaceId(row.workspace_id),
        case_id=CaseId(row.case_id),
        run_id=RunId(row.run_id),
        sequence=row.sequence,
        checkpoint=GoalLoopCheckpoint.model_validate(row.checkpoint_json),
        created_at=_utc(row.created_at),
    )


class SqlRunCheckpointRepository:
    MAX_SEQUENCE_RETRIES = 20

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def append(
        self,
        checkpoint: GoalLoopCheckpoint,
        *,
        checkpoint_id: CheckpointId | None = None,
    ) -> RunCheckpointRecord:
        selected_id = checkpoint_id or CheckpointId.new()
        last_error: IntegrityError | None = None
        for attempt in range(self.MAX_SEQUENCE_RETRIES):
            try:
                async with self._session_factory() as session, session.begin():
                    return await self.append_in_session(
                        session,
                        checkpoint,
                        checkpoint_id=selected_id,
                    )
            except IntegrityError as exc:
                last_error = exc
                await asyncio.sleep(0.001 * (attempt + 1))
        raise OptimisticConcurrencyError("Checkpoint sequence allocation exceeded retry budget") from last_error

    async def get_latest(
        self,
        workspace_id: WorkspaceId,
        run_id: RunId,
    ) -> RunCheckpointRecord | None:
        async with self._session_factory() as session:
            return await self.get_latest_in_session(session, workspace_id, run_id)

    @staticmethod
    async def get_latest_in_session(
        session: AsyncSession,
        workspace_id: WorkspaceId,
        run_id: RunId,
    ) -> RunCheckpointRecord | None:
        statement = (
            select(RunCheckpointRow)
            .where(
                RunCheckpointRow.workspace_id == str(workspace_id),
                RunCheckpointRow.run_id == str(run_id),
            )
            .order_by(RunCheckpointRow.sequence.desc())
            .limit(1)
        )
        row = await session.scalar(statement)
        return _row_to_checkpoint(row) if row is not None else None

    async def list_run(
        self,
        workspace_id: WorkspaceId,
        run_id: RunId,
    ) -> tuple[RunCheckpointRecord, ...]:
        statement = (
            select(RunCheckpointRow)
            .where(
                RunCheckpointRow.workspace_id == str(workspace_id),
                RunCheckpointRow.run_id == str(run_id),
            )
            .order_by(RunCheckpointRow.sequence.asc())
        )
        async with self._session_factory() as session:
            rows = (await session.scalars(statement)).all()
            return tuple(_row_to_checkpoint(row) for row in rows)

    @staticmethod
    async def append_in_session(
        session: AsyncSession,
        checkpoint: GoalLoopCheckpoint,
        *,
        checkpoint_id: CheckpointId,
    ) -> RunCheckpointRecord:
        existing_row = await session.get(RunCheckpointRow, str(checkpoint_id))
        if existing_row is not None:
            existing = _row_to_checkpoint(existing_row)
            if existing.checkpoint != checkpoint:
                raise DuplicateEntityError(f"Checkpoint ID reused with different data: {checkpoint_id}")
            return existing

        run_row = await session.scalar(
            select(RunRow).where(
                RunRow.workspace_id == str(checkpoint.workspace_id),
                RunRow.run_id == str(checkpoint.run_id),
            )
        )
        if run_row is None:
            raise EntityNotFoundError(f"Run not found: {checkpoint.run_id}")
        if run_row.case_id != str(checkpoint.case_id):
            raise ValueError("Checkpoint Case must match Run Case")
        if run_row.goal != checkpoint.goal:
            raise ValueError("Checkpoint Goal must match Run Goal")

        current = await session.scalar(
            select(func.max(RunCheckpointRow.sequence)).where(
                RunCheckpointRow.workspace_id == str(checkpoint.workspace_id),
                RunCheckpointRow.run_id == str(checkpoint.run_id),
            )
        )
        created_at = datetime.now(UTC)
        row = RunCheckpointRow(
            checkpoint_id=str(checkpoint_id),
            workspace_id=str(checkpoint.workspace_id),
            case_id=str(checkpoint.case_id),
            run_id=str(checkpoint.run_id),
            sequence=int(current or 0) + 1,
            schema_version=checkpoint.schema_version,
            checkpoint_json=checkpoint.model_dump(mode="json"),
            created_at=created_at,
        )
        session.add(row)
        await session.flush()
        return _row_to_checkpoint(row)


class RunLeaseConflictError(RuntimeError):
    """A live Worker already owns the Run or the Run cannot be acquired."""


class RunLeaseLostError(RuntimeError):
    """The Worker credential is stale, expired, or fenced by a newer owner."""


class RunLeaseCredentials(CommerceModel):
    worker_id: str = Field(min_length=1, max_length=128)
    lease_token: SecretStr
    fencing_token: int = Field(ge=1)


class RunLeaseSnapshot(CommerceModel):
    workspace_id: WorkspaceId
    case_id: CaseId
    run_id: RunId
    worker_id: str = Field(min_length=1, max_length=128)
    fencing_token: int = Field(ge=1)
    acquired_at: datetime
    heartbeat_at: datetime
    expires_at: datetime


class RunLeaseGrant(CommerceModel):
    run: CommerceRun
    credentials: RunLeaseCredentials
    acquired_at: datetime
    expires_at: datetime
    reacquired: bool
    latest_checkpoint: RunCheckpointRecord | None = None


def _row_to_lease(row: RunLeaseRow) -> RunLeaseSnapshot:
    return RunLeaseSnapshot(
        workspace_id=WorkspaceId(row.workspace_id),
        case_id=CaseId(row.case_id),
        run_id=RunId(row.run_id),
        worker_id=row.worker_id,
        fencing_token=row.fencing_token,
        acquired_at=_utc(row.acquired_at),
        heartbeat_at=_utc(row.heartbeat_at),
        expires_at=_utc(row.expires_at),
    )


def _token_sha256(credentials: RunLeaseCredentials) -> str:
    raw = credentials.lease_token.get_secret_value()
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class SqlRunLeaseRepository:
    """Acquire and heartbeat one fenced execution owner per Commerce Run."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def acquire(
        self,
        workspace_id: WorkspaceId,
        run_id: RunId,
        *,
        worker_id: str,
        ttl: timedelta,
        acquired_at: datetime,
        trace_id: TraceId,
        correlation_id: CorrelationId,
    ) -> RunLeaseGrant:
        if ttl.total_seconds() <= 0:
            raise ValueError("Run lease TTL must be positive")
        if not worker_id.strip():
            raise ValueError("Run lease worker_id cannot be blank")
        raw_token = secrets.token_urlsafe(32)
        last_error: IntegrityError | None = None
        for attempt in range(20):
            try:
                async with self._session_factory() as session, session.begin():
                    return await self._acquire_in_session(
                        session,
                        workspace_id,
                        run_id,
                        worker_id=worker_id,
                        raw_token=raw_token,
                        ttl=ttl,
                        acquired_at=acquired_at,
                        trace_id=trace_id,
                        correlation_id=correlation_id,
                    )
            except OptimisticConcurrencyError as exc:
                raise RunLeaseConflictError(f"Run is already acquired: {run_id}") from exc
            except IntegrityError as exc:
                last_error = exc
                await asyncio.sleep(0.001 * (attempt + 1))
        raise RunLeaseConflictError(f"Run lease acquisition exceeded retry budget: {run_id}") from last_error

    async def _acquire_in_session(
        self,
        session: AsyncSession,
        workspace_id: WorkspaceId,
        run_id: RunId,
        *,
        worker_id: str,
        raw_token: str,
        ttl: timedelta,
        acquired_at: datetime,
        trace_id: TraceId,
        correlation_id: CorrelationId,
    ) -> RunLeaseGrant:
        run = await SqlRunRepository.get_in_session(session, workspace_id, run_id)
        if run is None:
            raise EntityNotFoundError(f"Run not found: {run_id}")
        row = await session.get(RunLeaseRow, str(run_id))
        expires_at = acquired_at + ttl
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        reacquired = False

        if run.status is RunStatus.QUEUED:
            running = run.transition_to(
                RunStatus.RUNNING,
                occurred_at=acquired_at,
            )
            await SqlRunRepository.save_in_session(
                session,
                running,
                expected_version=run.version,
            )
            run = running
            fencing_token = (row.fencing_token + 1) if row is not None else 1
            event_type = "run.status_changed"
            payload = {
                "from_status": RunStatus.QUEUED.value,
                "to_status": RunStatus.RUNNING.value,
                "from_phase": run.phase.value,
                "to_phase": run.phase.value,
                "worker_id": worker_id,
                "fencing_token": fencing_token,
                "version": run.version,
            }
        elif run.status is RunStatus.WAITING:
            if row is None:
                raise RunLeaseConflictError(f"Waiting Run has no resumable lease record: {run_id}")
            if row.released_at is None and _utc(row.expires_at) > acquired_at:
                raise RunLeaseConflictError(f"Waiting Run lease has not been released: {run_id}")
            previous_phase = run.phase
            running = run.transition_to(
                RunStatus.RUNNING,
                occurred_at=acquired_at,
            )
            await SqlRunRepository.save_in_session(
                session,
                running,
                expected_version=run.version,
            )
            run = running
            fencing_token = row.fencing_token + 1
            reacquired = True
            event_type = "run.status_changed"
            payload = {
                "from_status": RunStatus.WAITING.value,
                "to_status": RunStatus.RUNNING.value,
                "from_phase": previous_phase.value,
                "to_phase": run.phase.value,
                "worker_id": worker_id,
                "fencing_token": fencing_token,
                "resumed_from_wait": True,
                "version": run.version,
            }
        elif run.status is RunStatus.RUNNING:
            if row is None or row.released_at is not None:
                raise RunLeaseConflictError(f"Running Run has no recoverable lease: {run_id}")
            if _utc(row.expires_at) > acquired_at:
                raise RunLeaseConflictError(f"Run lease is still active: {run_id}")
            fencing_token = row.fencing_token + 1
            reacquired = True
            event_type = "run.lease_reacquired"
            payload = {
                "previous_worker_id": row.worker_id,
                "worker_id": worker_id,
                "fencing_token": fencing_token,
                "resumed_from_expired_lease": True,
                "version": run.version,
            }
        else:
            raise RunLeaseConflictError(f"Run status {run.status.value} cannot be acquired")

        if row is None:
            row = RunLeaseRow(
                run_id=str(run_id),
                workspace_id=str(workspace_id),
                case_id=str(run.case_id),
                worker_id=worker_id,
                lease_token_sha256=token_hash,
                fencing_token=fencing_token,
                acquired_at=acquired_at,
                heartbeat_at=acquired_at,
                expires_at=expires_at,
                released_at=None,
            )
            session.add(row)
        else:
            row.worker_id = worker_id
            row.lease_token_sha256 = token_hash
            row.fencing_token = fencing_token
            row.acquired_at = acquired_at
            row.heartbeat_at = acquired_at
            row.expires_at = expires_at
            row.released_at = None
        await session.flush()

        event = NewDomainEvent(
            workspace_id=workspace_id,
            case_id=run.case_id,
            run_id=run.id,
            event_type=event_type,
            occurred_at=acquired_at,
            trace_id=trace_id,
            correlation_id=correlation_id,
            actor=DomainEventActor.SYSTEM,
            payload=payload,
        )
        await SqlDomainEventStore.append_in_session(session, event)
        latest = await SqlRunCheckpointRepository.get_latest_in_session(
            session,
            workspace_id,
            run_id,
        )
        return RunLeaseGrant(
            run=run,
            credentials=RunLeaseCredentials(
                worker_id=worker_id,
                lease_token=SecretStr(raw_token),
                fencing_token=fencing_token,
            ),
            acquired_at=acquired_at,
            expires_at=expires_at,
            reacquired=reacquired,
            latest_checkpoint=latest,
        )

    async def heartbeat(
        self,
        workspace_id: WorkspaceId,
        run_id: RunId,
        credentials: RunLeaseCredentials,
        *,
        ttl: timedelta,
        heartbeat_at: datetime,
    ) -> RunLeaseSnapshot:
        if ttl.total_seconds() <= 0:
            raise ValueError("Run lease TTL must be positive")
        async with self._session_factory() as session, session.begin():
            row = await self.require_valid_in_session(
                session,
                workspace_id,
                run_id,
                credentials,
                checked_at=heartbeat_at,
            )
            row.heartbeat_at = heartbeat_at
            row.expires_at = heartbeat_at + ttl
            await session.flush()
            return _row_to_lease(row)

    async def release(
        self,
        workspace_id: WorkspaceId,
        run_id: RunId,
        credentials: RunLeaseCredentials,
        *,
        released_at: datetime,
        trace_id: TraceId,
        correlation_id: CorrelationId,
    ) -> DomainEventEnvelope:
        """Release a waiting or terminal Run lease without exposing its token."""

        async with self._session_factory() as session, session.begin():
            row = await self.require_valid_in_session(
                session,
                workspace_id,
                run_id,
                credentials,
                checked_at=released_at,
            )
            run = await SqlRunRepository.get_in_session(
                session,
                workspace_id,
                run_id,
            )
            if run is None:
                raise EntityNotFoundError(f"Run not found: {run_id}")
            if run.status in {RunStatus.QUEUED, RunStatus.RUNNING}:
                raise RunLeaseConflictError("Lease can be released only after Run leaves active execution")
            row.released_at = released_at
            await session.flush()
            return await SqlDomainEventStore.append_in_session(
                session,
                NewDomainEvent(
                    workspace_id=workspace_id,
                    case_id=run.case_id,
                    run_id=run_id,
                    event_type="run.lease_released",
                    occurred_at=released_at,
                    trace_id=trace_id,
                    correlation_id=correlation_id,
                    actor=DomainEventActor.SYSTEM,
                    payload={
                        "worker_id": credentials.worker_id,
                        "fencing_token": credentials.fencing_token,
                        "run_status": run.status.value,
                    },
                ),
            )

    @staticmethod
    async def require_valid_in_session(
        session: AsyncSession,
        workspace_id: WorkspaceId,
        run_id: RunId,
        credentials: RunLeaseCredentials,
        *,
        checked_at: datetime,
    ) -> RunLeaseRow:
        row = await session.scalar(
            select(RunLeaseRow).where(
                RunLeaseRow.workspace_id == str(workspace_id),
                RunLeaseRow.run_id == str(run_id),
            )
        )
        valid = (
            row is not None
            and row.released_at is None
            and row.worker_id == credentials.worker_id
            and row.fencing_token == credentials.fencing_token
            and row.lease_token_sha256 == _token_sha256(credentials)
            and _utc(row.expires_at) > checked_at
        )
        if not valid:
            raise RunLeaseLostError(f"Run lease is stale or expired: {run_id}")
        return row
