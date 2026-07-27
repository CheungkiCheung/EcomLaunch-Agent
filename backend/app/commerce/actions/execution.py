"""Fenced Action Execution and rollback orchestration over real internal Connectors."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.commerce.actions.artifacts import (
    ActionArtifactKind,
    ActionExecutionArtifact,
    AuditCohortRow,
)
from app.commerce.actions.contracts import ActionKind
from app.commerce.actions.internal_connectors import InternalConnectorRegistry
from app.commerce.domain.enums import (
    ActionRunOperation,
    ActionStatus,
    CaseStatus,
    RunPhase,
    RunStatus,
    RunType,
)
from app.commerce.domain.events import DomainEventActor
from app.commerce.domain.ids import (
    ActionId,
    CorrelationId,
    RunId,
    TraceId,
    WorkspaceId,
)
from app.commerce.domain.models import Action, CommerceModel
from app.commerce.domain.runs import CommerceRun
from app.commerce.persistence.action_artifacts import SqlActionArtifactRepository
from app.commerce.persistence.actions import ActionRecord, SqlActionRepository
from app.commerce.persistence.repositories import SqlCaseRepository
from app.commerce.persistence.runs import (
    SqlRunLeaseRepository,
    SqlRunRepository,
)
from app.commerce.persistence.unit_of_work import SqlCommerceUnitOfWork
from app.commerce.persistence.work_records import SqlEvidenceRepository


class ActionExecutionError(ValueError):
    pass


class ActionExecutionStartResult(CommerceModel):
    run: CommerceRun
    created: bool


class ActionExecutionResult(CommerceModel):
    run: CommerceRun
    record: ActionRecord
    artifact: ActionExecutionArtifact | None = None
    replayed: bool = False
    error_message: str | None = Field(default=None, min_length=1)


_ALLOWED_ACTION_TRANSITIONS = {
    ActionStatus.POLICY_CHECKED: frozenset({ActionStatus.EXECUTING}),
    ActionStatus.APPROVED: frozenset({ActionStatus.EXECUTING}),
    ActionStatus.EXECUTING: frozenset(
        {
            ActionStatus.SUCCEEDED,
            ActionStatus.MONITORING,
            ActionStatus.FAILED,
        }
    ),
    ActionStatus.SUCCEEDED: frozenset({ActionStatus.ROLLING_BACK}),
    ActionStatus.MONITORING: frozenset({ActionStatus.ROLLING_BACK}),
    ActionStatus.ROLLING_BACK: frozenset(
        {
            ActionStatus.ROLLED_BACK,
            ActionStatus.SUCCEEDED,
            ActionStatus.MONITORING,
        }
    ),
}


def _transition_action_record(
    record: ActionRecord,
    target: ActionStatus,
    *,
    occurred_at: datetime,
) -> ActionRecord:
    if target not in _ALLOWED_ACTION_TRANSITIONS.get(
        record.action.status,
        frozenset(),
    ):
        raise ActionExecutionError(f"Action cannot transition from {record.action.status.value} to {target.value}")
    action = Action.model_validate(
        {
            **record.action.model_dump(mode="python"),
            "status": target,
        }
    )
    return record.with_action(action, occurred_at=occurred_at)


def _run_identity(
    workspace_id: WorkspaceId,
    action_id: ActionId,
    operation: ActionRunOperation,
    idempotency_key_sha256: str,
) -> RunId:
    value = uuid5(
        NAMESPACE_URL,
        f"commerce.action-run@1:{workspace_id}:{action_id}:{operation.value}:{idempotency_key_sha256}",
    )
    return RunId(f"run_{value.hex}")


class ActionExecutionService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        storage_root: Path,
        connector_registry: InternalConnectorRegistry | None = None,
        clock: Callable[[], datetime] | None = None,
        lease_ttl: timedelta = timedelta(minutes=5),
    ) -> None:
        self._storage_root = storage_root
        self._connectors = connector_registry or InternalConnectorRegistry()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lease_ttl = lease_ttl
        self._actions = SqlActionRepository(session_factory)
        self._cases = SqlCaseRepository(session_factory)
        self._artifacts = SqlActionArtifactRepository(session_factory)
        self._evidence = SqlEvidenceRepository(session_factory)
        self._runs = SqlRunRepository(session_factory)
        self._leases = SqlRunLeaseRepository(session_factory)
        self._uow = SqlCommerceUnitOfWork(session_factory)

    async def start(
        self,
        workspace_id: WorkspaceId,
        action_id: ActionId,
        *,
        operation: ActionRunOperation,
        idempotency_key: str,
        actor_id: str,
    ) -> ActionExecutionStartResult:
        if len(idempotency_key) < 8 or len(idempotency_key) > 128:
            raise ActionExecutionError("Action Execution idempotency key must contain 8-128 characters")
        if not actor_id.strip():
            raise ActionExecutionError("Action Execution actor ID cannot be blank")
        record = await self._actions.get(workspace_id, action_id)
        if record is None:
            raise ActionExecutionError("Commerce Action was not found")
        key_sha256 = hashlib.sha256(f"{operation.value}:{idempotency_key}".encode()).hexdigest()
        existing = await self._runs.get_by_idempotency_key(
            workspace_id,
            record.action.case_id,
            key_sha256,
        )
        if existing is not None:
            if existing.run_type is not RunType.ACTION_EXECUTION or existing.subject_action_id != action_id or existing.action_operation is not operation:
                raise ActionExecutionError("Action Execution idempotency key was reused for another command")
            return ActionExecutionStartResult(run=existing, created=False)

        tool = record.decision.execution_tool
        if tool is not None and tool.startswith("connector:"):
            raise ActionExecutionError("Real external Connector execution is unavailable and remains fail-closed")
        if record.decision.validated.draft.kind is ActionKind.EXTERNAL_MUTATION:
            raise ActionExecutionError("Real external Connector execution is unavailable and remains fail-closed")
        artifact = await self._artifacts.get(workspace_id, action_id)
        if operation is ActionRunOperation.EXECUTE:
            if record.action.status not in {
                ActionStatus.POLICY_CHECKED,
                ActionStatus.APPROVED,
            }:
                raise ActionExecutionError(f"Action status {record.action.status.value} cannot start execution")
            if artifact is not None:
                raise ActionExecutionError("Action already has an execution artifact")
            goal = f"Execute policy-checked Action {action_id}"
        else:
            if record.action.status not in {
                ActionStatus.SUCCEEDED,
                ActionStatus.MONITORING,
            }:
                raise ActionExecutionError(f"Action status {record.action.status.value} cannot start rollback")
            if artifact is None:
                raise ActionExecutionError("Rollback requires a persisted Action artifact")
            goal = f"Rollback reversible Action {action_id}"

        occurred_at = self._clock()
        run = CommerceRun(
            id=_run_identity(
                workspace_id,
                action_id,
                operation,
                key_sha256,
            ),
            workspace_id=workspace_id,
            case_id=record.action.case_id,
            run_type=RunType.ACTION_EXECUTION,
            phase=RunPhase.EXECUTING,
            goal=goal,
            idempotency_key_sha256=key_sha256,
            subject_action_id=action_id,
            action_operation=operation,
            created_at=occurred_at,
            updated_at=occurred_at,
        )
        await self._uow.create_run(
            run,
            trace_id=TraceId.new(),
            correlation_id=CorrelationId.new(),
            actor=DomainEventActor.USER,
            actor_id=actor_id,
        )
        return ActionExecutionStartResult(run=run, created=True)

    async def execute(
        self,
        workspace_id: WorkspaceId,
        run_id: RunId,
        *,
        worker_id: str,
    ) -> ActionExecutionResult:
        run = await self._runs.get(workspace_id, run_id)
        if run is None or run.run_type is not RunType.ACTION_EXECUTION:
            raise ActionExecutionError("Action Execution Run was not found")
        assert run.subject_action_id is not None
        assert run.action_operation is not None
        if run.status in {RunStatus.COMPLETED, RunStatus.FAILED}:
            record = await self._require_action(workspace_id, run.subject_action_id)
            artifact = await self._artifacts.get(workspace_id, run.subject_action_id)
            return ActionExecutionResult(
                run=run,
                record=record,
                artifact=artifact,
                replayed=True,
                error_message=(run.stop_reason if run.status is RunStatus.FAILED else None),
            )
        if run.status not in {RunStatus.QUEUED, RunStatus.RUNNING}:
            raise ActionExecutionError(f"Action Execution Run status {run.status.value} is not executable")

        occurred_at = self._clock()
        trace_id = TraceId.new()
        correlation_id = CorrelationId.new()
        grant = await self._leases.acquire(
            workspace_id,
            run_id,
            worker_id=worker_id,
            ttl=self._lease_ttl,
            acquired_at=occurred_at,
            trace_id=trace_id,
            correlation_id=correlation_id,
        )
        record = await self._require_action(workspace_id, run.subject_action_id)
        case = await self._cases.get(workspace_id, record.action.case_id)
        if case is None:
            raise ActionExecutionError("Commerce Case was not found")
        prior_status = record.action.status
        artifact = await self._artifacts.get(workspace_id, record.action.id)
        operation = run.action_operation
        if operation is ActionRunOperation.EXECUTE:
            target_in_progress = ActionStatus.EXECUTING
        else:
            target_in_progress = ActionStatus.ROLLING_BACK

        if record.action.status is not target_in_progress:
            in_progress = _transition_action_record(
                record,
                target_in_progress,
                occurred_at=occurred_at,
            )
            await self._uow.begin_action_execution(
                in_progress,
                grant.run,
                operation=operation,
                prior_action_status=prior_status.value,
                expected_action_version=record.version,
                trace_id=trace_id,
                correlation_id=correlation_id,
                lease=grant.credentials,
                lease_checked_at=occurred_at,
            )
        else:
            in_progress = record

        try:
            if operation is ActionRunOperation.EXECUTE:
                connector_result = self._connectors.execute(
                    in_progress,
                    storage_root=self._storage_root,
                    occurred_at=occurred_at,
                    audit_rows=await self._audit_rows(in_progress),
                )
                artifact = connector_result.artifact
                target_status = ActionStatus.MONITORING if artifact.kind is ActionArtifactKind.METRIC_MONITOR else ActionStatus.SUCCEEDED
                expected_artifact_version = None
            else:
                if artifact is None:
                    raise ActionExecutionError("Rollback requires a persisted Action artifact")
                connector_result = self._connectors.rollback(
                    artifact,
                    storage_root=self._storage_root,
                    occurred_at=occurred_at,
                )
                artifact = connector_result.artifact
                target_status = ActionStatus.ROLLED_BACK
                expected_artifact_version = artifact.version - 1

            completed_record = _transition_action_record(
                in_progress,
                target_status,
                occurred_at=occurred_at,
            )
            completed_case = None
            if operation is ActionRunOperation.EXECUTE and case.status in {
                CaseStatus.INVESTIGATING,
                CaseStatus.ACTION_IN_PROGRESS,
            }:
                completed_case = case.transition_to(
                    CaseStatus.MONITORING,
                    occurred_at=occurred_at,
                )
            elif operation is ActionRunOperation.ROLLBACK and case.status in {
                CaseStatus.MONITORING,
                CaseStatus.RESOLVED,
            }:
                completed_case = case.transition_to(
                    CaseStatus.REOPENED,
                    occurred_at=occurred_at,
                )
            completed_run = grant.run.transition_to(
                RunStatus.COMPLETED,
                phase=RunPhase.EXECUTING,
                stop_reason=("action_execution_verified" if operation is ActionRunOperation.EXECUTE else "action_rollback_verified"),
                occurred_at=occurred_at,
            )
            await self._uow.finish_action_execution(
                completed_record,
                completed_run,
                artifact,
                case=completed_case,
                operation=operation,
                prior_action_status=in_progress.action.status.value,
                prior_case_status=(case.status if completed_case is not None else None),
                expected_action_version=in_progress.version,
                expected_case_version=(case.version if completed_case is not None else None),
                expected_run_version=grant.run.version,
                expected_artifact_version=expected_artifact_version,
                trace_id=trace_id,
                correlation_id=correlation_id,
                lease=grant.credentials,
                lease_checked_at=occurred_at,
            )
            await self._leases.release(
                workspace_id,
                run_id,
                grant.credentials,
                released_at=occurred_at,
                trace_id=trace_id,
                correlation_id=correlation_id,
            )
            return ActionExecutionResult(
                run=completed_run,
                record=completed_record,
                artifact=artifact,
            )
        except Exception as exc:
            failure_target = ActionStatus.FAILED if operation is ActionRunOperation.EXECUTE else prior_status
            failed_record = _transition_action_record(
                in_progress,
                failure_target,
                occurred_at=occurred_at,
            )
            failed_run = grant.run.transition_to(
                RunStatus.FAILED,
                phase=RunPhase.EXECUTING,
                stop_reason="connector_failed",
                occurred_at=occurred_at,
            )
            await self._uow.fail_action_execution(
                failed_record,
                failed_run,
                operation=operation,
                prior_action_status=in_progress.action.status.value,
                error_message=str(exc),
                expected_action_version=in_progress.version,
                expected_run_version=grant.run.version,
                trace_id=trace_id,
                correlation_id=correlation_id,
                lease=grant.credentials,
                lease_checked_at=occurred_at,
            )
            await self._leases.release(
                workspace_id,
                run_id,
                grant.credentials,
                released_at=occurred_at,
                trace_id=trace_id,
                correlation_id=correlation_id,
            )
            return ActionExecutionResult(
                run=failed_run,
                record=failed_record,
                artifact=artifact,
                error_message=str(exc),
            )

    async def _require_action(
        self,
        workspace_id: WorkspaceId,
        action_id: ActionId,
    ) -> ActionRecord:
        record = await self._actions.get(workspace_id, action_id)
        if record is None:
            raise ActionExecutionError("Commerce Action was not found")
        return record

    async def _audit_rows(
        self,
        record: ActionRecord,
    ) -> tuple[AuditCohortRow, ...]:
        if record.decision.validated.draft.kind is not ActionKind.EXPORT_AUDIT_COHORT:
            return ()
        rows: list[AuditCohortRow] = []
        for evidence_id in record.action.evidence_ids:
            evidence = await self._evidence.get(record.action.workspace_id, evidence_id)
            if evidence is None or evidence.case_id != record.action.case_id:
                raise ActionExecutionError("Audit export Evidence could not be reloaded from the Case")
            rows.append(
                AuditCohortRow(
                    evidence_id=evidence.id,
                    summary=evidence.summary,
                    confidence=evidence.confidence,
                    metric_observation_ids=evidence.metric_observation_ids,
                )
            )
        return tuple(rows)
