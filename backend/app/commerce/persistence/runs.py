"""Run projection and append-only Goal Loop Checkpoint repositories."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from pydantic import Field
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.commerce.agents.goal_loop import GoalLoopCheckpoint
from app.commerce.domain.enums import RunPhase, RunStatus
from app.commerce.domain.ids import (
    CaseId,
    CheckpointId,
    RunId,
    WorkspaceId,
)
from app.commerce.domain.models import CommerceModel
from app.commerce.domain.runs import CommerceRun
from app.commerce.persistence.models import RunCheckpointRow, RunRow
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
            raise DuplicateEntityError(
                f"Run or idempotency key already exists: {run.id}"
            ) from exc

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
            raise OptimisticConcurrencyError(
                f"Run {run.id} expected version {expected_version}, found {current.version}"
            )
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
            raise OptimisticConcurrencyError(
                f"Run {run.id} changed while saving version {run.version}"
            )
        return RunStatus(current.status), RunPhase(current.phase)


class RunCheckpointRecord(CommerceModel):
    id: CheckpointId
    workspace_id: WorkspaceId
    case_id: CaseId
    run_id: RunId
    sequence: int = Field(ge=1)
    checkpoint: GoalLoopCheckpoint
    created_at: datetime


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
        raise OptimisticConcurrencyError(
            "Checkpoint sequence allocation exceeded retry budget"
        ) from last_error

    async def get_latest(
        self,
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
        async with self._session_factory() as session:
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
                raise DuplicateEntityError(
                    f"Checkpoint ID reused with different data: {checkpoint_id}"
                )
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
