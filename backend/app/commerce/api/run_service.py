"""Application service for idempotent Investigation Run creation and reads."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.commerce.domain.enums import PathType, RunPhase, RunStatus, RunType
from app.commerce.domain.events import DomainEventActor, DomainEventEnvelope
from app.commerce.domain.ids import CaseId, CorrelationId, RunId, TraceId, WorkspaceId
from app.commerce.domain.models import CommerceModel
from app.commerce.domain.runs import CommerceRun
from app.commerce.persistence.events import SqlDomainEventStore
from app.commerce.persistence.repositories import DuplicateEntityError, SqlCaseRepository
from app.commerce.persistence.runs import (
    RunCheckpointRecord,
    SqlRunCheckpointRepository,
    SqlRunRepository,
)
from app.commerce.persistence.unit_of_work import SqlCommerceUnitOfWork


class InvestigationCaseNotFoundError(LookupError):
    pass


class InvestigationIdempotencyConflictError(ValueError):
    pass


class ReplanParentNotFoundError(LookupError):
    pass


class ReplanParentStateError(ValueError):
    pass


class InvestigationStartResult(CommerceModel):
    run: CommerceRun
    created: bool


class CommerceRunService:
    """Create honest queued Runs and read their authoritative state."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._cases = SqlCaseRepository(session_factory)
        self._runs = SqlRunRepository(session_factory)
        self._checkpoints = SqlRunCheckpointRepository(session_factory)
        self._events = SqlDomainEventStore(session_factory)
        self._uow = SqlCommerceUnitOfWork(session_factory)
        self._clock = clock or (lambda: datetime.now(UTC))

    async def start_investigation(
        self,
        workspace_id: WorkspaceId,
        case_id: CaseId,
        *,
        goal: str,
        idempotency_key: str,
    ) -> InvestigationStartResult:
        case = await self._cases.get(workspace_id, case_id)
        if case is None:
            raise InvestigationCaseNotFoundError(str(case_id))
        key_sha256 = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
        existing = await self._runs.get_by_idempotency_key(
            workspace_id,
            case_id,
            key_sha256,
        )
        if existing is not None:
            return self._resolve_idempotent(
                existing,
                goal=goal,
                run_type=RunType.CASE_INVESTIGATION,
            )

        now = self._clock()
        run = CommerceRun(
            workspace_id=workspace_id,
            case_id=case_id,
            run_type=RunType.CASE_INVESTIGATION,
            phase=RunPhase.PLANNING,
            goal=goal,
            idempotency_key_sha256=key_sha256,
            created_at=now,
            updated_at=now,
        )
        try:
            await self._uow.create_run(
                run,
                trace_id=TraceId.new(),
                correlation_id=CorrelationId.new(),
                actor=DomainEventActor.USER,
            )
            return InvestigationStartResult(run=run, created=True)
        except DuplicateEntityError:
            concurrent = await self._runs.get_by_idempotency_key(
                workspace_id,
                case_id,
                key_sha256,
            )
            if concurrent is None:
                raise
            return self._resolve_idempotent(
                concurrent,
                goal=goal,
                run_type=RunType.CASE_INVESTIGATION,
            )

    async def start_replan(
        self,
        workspace_id: WorkspaceId,
        parent_run_id: RunId,
        *,
        goal: str,
        requested_paths: tuple[PathType, ...],
        idempotency_key: str,
    ) -> InvestigationStartResult:
        parent = await self._runs.get(workspace_id, parent_run_id)
        if parent is None:
            raise ReplanParentNotFoundError(str(parent_run_id))
        resumable_tool_failure = (
            parent.status is RunStatus.FAILED
            and parent.stop_reason == "tool_failure"
        )
        if parent.run_type not in {
            RunType.CASE_INVESTIGATION,
            RunType.REPLAN,
        } or (
            parent.status not in {RunStatus.COMPLETED, RunStatus.BLOCKED}
            and not resumable_tool_failure
        ):
            raise ReplanParentStateError(
                "Replan parent must be a completed, blocked, or a tool failure Investigation Run"
            )
        key_sha256 = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
        existing = await self._runs.get_by_idempotency_key(
            workspace_id,
            parent.case_id,
            key_sha256,
        )
        if existing is not None:
            return self._resolve_idempotent(
                existing,
                goal=goal,
                run_type=RunType.REPLAN,
                parent_run_id=parent.id,
                requested_paths=requested_paths,
            )

        now = self._clock()
        run = CommerceRun(
            workspace_id=workspace_id,
            case_id=parent.case_id,
            run_type=RunType.REPLAN,
            phase=RunPhase.PLANNING,
            goal=goal,
            idempotency_key_sha256=key_sha256,
            parent_run_id=parent.id,
            requested_paths=requested_paths,
            created_at=now,
            updated_at=now,
        )
        parent_events = await self._events.list_run(workspace_id, parent.id)
        causation_event_id = parent_events[-1].id if parent_events else None
        try:
            await self._uow.create_run(
                run,
                trace_id=TraceId.new(),
                correlation_id=CorrelationId.new(),
                actor=DomainEventActor.USER,
                causation_event_id=causation_event_id,
            )
            return InvestigationStartResult(run=run, created=True)
        except DuplicateEntityError:
            concurrent = await self._runs.get_by_idempotency_key(
                workspace_id,
                parent.case_id,
                key_sha256,
            )
            if concurrent is None:
                raise
            return self._resolve_idempotent(
                concurrent,
                goal=goal,
                run_type=RunType.REPLAN,
                parent_run_id=parent.id,
                requested_paths=requested_paths,
            )

    @staticmethod
    def _resolve_idempotent(
        existing: CommerceRun,
        *,
        goal: str,
        run_type: RunType,
        parent_run_id: RunId | None = None,
        requested_paths: tuple[PathType, ...] = (),
    ) -> InvestigationStartResult:
        if existing.goal != goal and existing.run_type is run_type:
            raise InvestigationIdempotencyConflictError("Idempotency key was reused for another goal")
        if existing.run_type is not run_type or existing.parent_run_id != parent_run_id or existing.requested_paths != requested_paths:
            raise InvestigationIdempotencyConflictError("Idempotency key was reused for another Run request")
        return InvestigationStartResult(run=existing, created=False)

    async def get_run(
        self,
        workspace_id: WorkspaceId,
        run_id: RunId,
    ) -> CommerceRun | None:
        return await self._runs.get(workspace_id, run_id)

    async def list_case_runs(
        self,
        workspace_id: WorkspaceId,
        case_id: CaseId,
        *,
        limit: int,
        offset: int,
    ) -> tuple[CommerceRun, ...]:
        case = await self._cases.get(workspace_id, case_id)
        if case is None:
            raise InvestigationCaseNotFoundError(str(case_id))
        return await self._runs.list_case(
            workspace_id,
            case_id,
            limit=limit,
            offset=offset,
        )

    async def get_latest_checkpoint(
        self,
        workspace_id: WorkspaceId,
        run_id: RunId,
    ) -> RunCheckpointRecord | None:
        return await self._checkpoints.get_latest(workspace_id, run_id)

    async def list_run_checkpoints(
        self,
        workspace_id: WorkspaceId,
        run_id: RunId,
    ) -> tuple[RunCheckpointRecord, ...]:
        return await self._checkpoints.list_run(workspace_id, run_id)

    async def list_run_events(
        self,
        workspace_id: WorkspaceId,
        run_id: RunId,
    ) -> tuple[DomainEventEnvelope, ...]:
        return await self._events.list_run(workspace_id, run_id)
