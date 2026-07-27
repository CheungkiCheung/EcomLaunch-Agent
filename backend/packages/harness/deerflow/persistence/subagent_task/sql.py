"""SQLAlchemy implementation of the durable SubagentTask store."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from deerflow.persistence.subagent_task.model import SubagentTaskEventRow, SubagentTaskRow
from deerflow.subagents.tasks.exceptions import (
    TaskAlreadyExistsError,
    TaskLeaseConflictError,
    TaskNotFoundError,
    TaskVersionConflictError,
)
from deerflow.subagents.tasks.models import ContextPacket, SubagentTask, SubagentTaskEvent, SubagentTaskStatus, utc_now
from deerflow.subagents.tasks.store.base import SubagentTaskStore

_INFLIGHT_STATUS_VALUES = (
    SubagentTaskStatus.queued.value,
    SubagentTaskStatus.running.value,
    SubagentTaskStatus.waiting.value,
    SubagentTaskStatus.waiting_approval.value,
    SubagentTaskStatus.blocked.value,
)


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


class SubagentTaskRepository(SubagentTaskStore):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        if session_factory is None:
            raise ValueError("SubagentTaskRepository requires a SQLAlchemy session factory")
        self._sf = session_factory

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        return self._sf

    @staticmethod
    def _row_to_task(row: SubagentTaskRow) -> SubagentTask:
        return SubagentTask(
            task_id=row.task_id,
            thread_id=row.thread_id,
            run_id=row.run_id,
            user_id=row.user_id,
            parent_task_id=row.parent_task_id,
            subagent_type=row.subagent_type,
            description=row.description,
            context_packet=ContextPacket.model_validate(row.context_packet_json or {}),
            tool_policy=row.tool_policy_json or {},
            depends_on=tuple(row.depends_on_json or ()),
            metadata=row.task_metadata or {},
            status=SubagentTaskStatus(row.status),
            result=row.result_json,
            error=row.error_json,
            checkpoint=row.checkpoint_json,
            telemetry=row.telemetry_json or {},
            wait_reason=row.wait_reason,
            version=row.version,
            event_seq=row.event_seq,
            attempt=row.attempt,
            max_attempts=row.max_attempts,
            priority=row.priority,
            lease_owner=row.lease_owner,
            lease_token=row.lease_token,
            lease_expires_at=_aware(row.lease_expires_at),
            created_at=_aware(row.created_at),
            updated_at=_aware(row.updated_at),
            started_at=_aware(row.started_at),
            completed_at=_aware(row.completed_at),
        )

    @staticmethod
    def _row_to_event(row: SubagentTaskEventRow) -> SubagentTaskEvent:
        return SubagentTaskEvent(
            task_id=row.task_id,
            thread_id=row.thread_id,
            run_id=row.run_id,
            seq=row.seq,
            event_type=row.event_type,
            payload=row.payload_json or {},
            idempotency_key=row.idempotency_key,
            created_at=_aware(row.created_at),
        )

    @staticmethod
    def _task_row(task: SubagentTask) -> SubagentTaskRow:
        return SubagentTaskRow(
            task_id=task.task_id,
            thread_id=task.thread_id,
            run_id=task.run_id,
            user_id=task.user_id,
            parent_task_id=task.parent_task_id,
            subagent_type=task.subagent_type,
            description=task.description,
            context_packet_json=task.context_packet.model_dump(mode="json"),
            tool_policy_json=task.tool_policy,
            depends_on_json=list(task.depends_on),
            task_metadata=task.metadata,
            status=task.status.value,
            result_json=task.result,
            error_json=task.error,
            checkpoint_json=task.checkpoint,
            telemetry_json=task.telemetry,
            wait_reason=task.wait_reason,
            version=task.version,
            event_seq=task.event_seq,
            attempt=task.attempt,
            max_attempts=task.max_attempts,
            priority=task.priority,
            lease_owner=task.lease_owner,
            lease_token=task.lease_token,
            lease_expires_at=task.lease_expires_at,
            created_at=task.created_at,
            updated_at=task.updated_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
        )

    @staticmethod
    def _db_changes(changes: dict[str, Any]) -> dict[str, Any]:
        mapping = {
            "context_packet": "context_packet_json",
            "tool_policy": "tool_policy_json",
            "depends_on": "depends_on_json",
            "metadata": "task_metadata",
            "result": "result_json",
            "error": "error_json",
            "checkpoint": "checkpoint_json",
            "telemetry": "telemetry_json",
        }
        result: dict[str, Any] = {}
        for key, value in changes.items():
            db_key = mapping.get(key, key)
            if isinstance(value, SubagentTaskStatus):
                value = value.value
            elif isinstance(value, ContextPacket):
                value = value.model_dump(mode="json")
            elif key == "depends_on":
                value = list(value)
            result[db_key] = value
        return result

    async def create(self, task: SubagentTask) -> SubagentTask:
        event = SubagentTaskEventRow(
            task_id=task.task_id,
            thread_id=task.thread_id,
            run_id=task.run_id,
            seq=1,
            event_type="task.created",
            payload_json={
                "status": task.status.value,
                "subagent_type": task.subagent_type,
                "parent_task_id": task.parent_task_id,
                "depends_on": list(task.depends_on),
            },
            idempotency_key="task.created",
            created_at=task.created_at,
        )
        try:
            async with self._sf() as session:
                async with session.begin():
                    session.add(self._task_row(task))
                    # No ORM relationship is declared between the rows because
                    # repositories load them independently. Flush the parent
                    # explicitly so SQLite's immediate FK check cannot observe
                    # the append-only event before its task exists.
                    await session.flush()
                    session.add(event)
        except IntegrityError as exc:
            raise TaskAlreadyExistsError(f"Subagent task already exists: {task.task_id}") from exc
        return task

    async def get(self, task_id: str) -> SubagentTask | None:
        async with self._sf() as session:
            row = await session.get(SubagentTaskRow, task_id)
            return self._row_to_task(row) if row is not None else None

    async def list_by_run(self, run_id: str) -> list[SubagentTask]:
        stmt = select(SubagentTaskRow).where(SubagentTaskRow.run_id == run_id).order_by(SubagentTaskRow.created_at, SubagentTaskRow.task_id)
        async with self._sf() as session:
            result = await session.execute(stmt)
            return [self._row_to_task(row) for row in result.scalars()]

    async def list_children(self, parent_task_id: str) -> list[SubagentTask]:
        stmt = select(SubagentTaskRow).where(SubagentTaskRow.parent_task_id == parent_task_id).order_by(SubagentTaskRow.created_at, SubagentTaskRow.task_id)
        async with self._sf() as session:
            result = await session.execute(stmt)
            return [self._row_to_task(row) for row in result.scalars()]

    async def list_inflight(self, *, before: datetime | None = None) -> list[SubagentTask]:
        cutoff = before or utc_now()
        stmt = (
            select(SubagentTaskRow)
            .where(
                SubagentTaskRow.status.in_(_INFLIGHT_STATUS_VALUES),
                SubagentTaskRow.created_at <= cutoff,
            )
            .order_by(SubagentTaskRow.created_at, SubagentTaskRow.task_id)
        )
        async with self._sf() as session:
            result = await session.execute(stmt)
            return [self._row_to_task(row) for row in result.scalars()]

    async def _idempotent_event(
        self,
        session: AsyncSession,
        task_id: str,
        idempotency_key: str | None,
    ) -> SubagentTaskEventRow | None:
        if idempotency_key is None:
            return None
        stmt = select(SubagentTaskEventRow).where(
            SubagentTaskEventRow.task_id == task_id,
            SubagentTaskEventRow.idempotency_key == idempotency_key,
        )
        return await session.scalar(stmt)

    async def mutate(
        self,
        task_id: str,
        *,
        expected_version: int,
        changes: dict[str, Any],
        event_type: str,
        event_payload: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
        required_lease_token: int | None = None,
        event_created_at: datetime | None = None,
    ) -> SubagentTask:
        now = event_created_at or utc_now()
        async with self._sf() as session:
            async with session.begin():
                existing_event = await self._idempotent_event(session, task_id, idempotency_key)
                if existing_event is not None:
                    row = await session.get(SubagentTaskRow, task_id)
                    if row is None:
                        raise TaskNotFoundError(f"Subagent task not found: {task_id}")
                    return self._row_to_task(row)

                stmt = update(SubagentTaskRow).where(
                    SubagentTaskRow.task_id == task_id,
                    SubagentTaskRow.version == expected_version,
                )
                if required_lease_token is not None:
                    stmt = stmt.where(SubagentTaskRow.lease_token == required_lease_token)
                stmt = stmt.values(
                    **self._db_changes(changes),
                    version=expected_version + 1,
                    event_seq=SubagentTaskRow.event_seq + 1,
                ).returning(SubagentTaskRow.event_seq)
                new_seq = await session.scalar(stmt)
                if new_seq is None:
                    row = await session.get(SubagentTaskRow, task_id)
                    if row is None:
                        raise TaskNotFoundError(f"Subagent task not found: {task_id}")
                    if required_lease_token is not None and row.lease_token != required_lease_token:
                        raise TaskLeaseConflictError(f"Subagent task {task_id} lease token is stale")
                    raise TaskVersionConflictError(f"Subagent task {task_id} version conflict: expected {expected_version}, found {row.version}")
                row = await session.get(SubagentTaskRow, task_id)
                session.add(
                    SubagentTaskEventRow(
                        task_id=task_id,
                        thread_id=row.thread_id,
                        run_id=row.run_id,
                        seq=new_seq,
                        event_type=event_type,
                        payload_json=event_payload or {},
                        idempotency_key=idempotency_key,
                        created_at=now,
                    )
                )
            refreshed = await session.get(SubagentTaskRow, task_id)
            return self._row_to_task(refreshed)

    async def append_event(
        self,
        task_id: str,
        *,
        event_type: str,
        payload: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
        required_lease_token: int | None = None,
        created_at: datetime | None = None,
    ) -> SubagentTaskEvent:
        now = created_at or utc_now()
        for _attempt in range(3):
            async with self._sf() as session:
                async with session.begin():
                    existing = await self._idempotent_event(session, task_id, idempotency_key)
                    if existing is not None:
                        return self._row_to_event(existing)
                    row = await session.get(SubagentTaskRow, task_id)
                    if row is None:
                        raise TaskNotFoundError(f"Subagent task not found: {task_id}")
                    expected_version = row.version
                    stmt = update(SubagentTaskRow).where(
                        SubagentTaskRow.task_id == task_id,
                        SubagentTaskRow.version == expected_version,
                    )
                    if required_lease_token is not None:
                        stmt = stmt.where(SubagentTaskRow.lease_token == required_lease_token)
                    stmt = stmt.values(
                        version=expected_version + 1,
                        event_seq=SubagentTaskRow.event_seq + 1,
                        updated_at=now,
                    ).returning(SubagentTaskRow.event_seq)
                    new_seq = await session.scalar(stmt)
                    if new_seq is None:
                        continue
                    event = SubagentTaskEventRow(
                        task_id=task_id,
                        thread_id=row.thread_id,
                        run_id=row.run_id,
                        seq=new_seq,
                        event_type=event_type,
                        payload_json=payload or {},
                        idempotency_key=idempotency_key,
                        created_at=now,
                    )
                    session.add(event)
                return self._row_to_event(event)
        raise TaskVersionConflictError(f"Subagent task {task_id} changed while appending an event")

    async def list_events(self, task_id: str) -> list[SubagentTaskEvent]:
        stmt = select(SubagentTaskEventRow).where(SubagentTaskEventRow.task_id == task_id).order_by(SubagentTaskEventRow.seq)
        async with self._sf() as session:
            result = await session.execute(stmt)
            return [self._row_to_event(row) for row in result.scalars()]
