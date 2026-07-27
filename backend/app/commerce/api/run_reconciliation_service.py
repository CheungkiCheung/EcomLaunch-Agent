"""Fenced reconciliation for Path calls whose external outcome is unknowable."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.commerce.agents.budget import BudgetUsage
from app.commerce.agents.contracts import PathType
from app.commerce.agents.resume import (
    ResumeDisposition,
    ResumeExecutionDisposition,
    RunResumeClassifier,
)
from app.commerce.domain.enums import RunStatus
from app.commerce.domain.events import DomainEventActor, DomainEventEnvelope, NewDomainEvent
from app.commerce.domain.ids import (
    AgentTaskId,
    CheckpointId,
    CorrelationId,
    EventId,
    RunId,
    TraceId,
    WorkspaceId,
)
from app.commerce.domain.models import CommerceModel
from app.commerce.domain.runs import CommerceRun
from app.commerce.persistence.events import SqlDomainEventStore
from app.commerce.persistence.runs import (
    RunCheckpointRecord,
    RunLeaseConflictError,
    SqlRunCheckpointRepository,
    SqlRunLeaseRepository,
    SqlRunRepository,
)
from app.commerce.persistence.unit_of_work import SqlCommerceUnitOfWork
from app.commerce.persistence.work_records import SqlEvidenceRepository


class RunReconciliationNotFoundError(LookupError):
    pass


class RunReconciliationConflictError(ValueError):
    pass


class RunReconciliationResult(CommerceModel):
    run: CommerceRun
    latest_checkpoint: RunCheckpointRecord
    disposition: ResumeExecutionDisposition
    replayed: bool = False


class CommerceRunReconciliationService:
    """Resolve unknown remote outcomes without silently repeating a model call."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        clock: Callable[[], datetime] | None = None,
        lease_ttl: timedelta = timedelta(minutes=5),
    ) -> None:
        if lease_ttl.total_seconds() <= 0:
            raise ValueError("Reconciliation lease TTL must be positive")
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lease_ttl = lease_ttl
        self._runs = SqlRunRepository(session_factory)
        self._checkpoints = SqlRunCheckpointRepository(session_factory)
        self._events = SqlDomainEventStore(session_factory)
        self._evidence = SqlEvidenceRepository(session_factory)
        self._leases = SqlRunLeaseRepository(session_factory)
        self._uow = SqlCommerceUnitOfWork(session_factory)

    async def reconcile_unknown_outcome(
        self,
        workspace_id: WorkspaceId,
        run_id: RunId,
        *,
        actor_id: str,
        reason: str,
        idempotency_key: str,
    ) -> RunReconciliationResult:
        actor_id = actor_id.strip()
        reason = reason.strip()
        if not actor_id:
            raise RunReconciliationConflictError("Reconciliation requires a human actor")
        if not reason:
            raise RunReconciliationConflictError("Reconciliation requires a reason")
        if not 8 <= len(idempotency_key) <= 128:
            raise RunReconciliationConflictError(
                "Reconciliation idempotency key must contain 8-128 characters"
            )
        key_sha256 = hashlib.sha256(idempotency_key.encode()).hexdigest()
        request_sha256 = self._request_sha256(
            run_id=run_id,
            actor_id=actor_id,
            reason=reason,
            key_sha256=key_sha256,
        )
        run = await self._runs.get(workspace_id, run_id)
        if run is None:
            raise RunReconciliationNotFoundError("Commerce Run was not found")
        events = await self._events.list_run(workspace_id, run_id)
        replay = await self._replay_if_completed(
            run,
            events,
            key_sha256=key_sha256,
            request_sha256=request_sha256,
        )
        if replay is not None:
            return replay
        latest = await self._checkpoints.get_latest(workspace_id, run_id)
        plan = RunResumeClassifier().classify(
            latest_checkpoint=latest,
            run_events=events,
        )
        if latest is None or plan.disposition not in {
            ResumeDisposition.AWAIT_RETRY_DECISION,
            ResumeDisposition.RECONCILE_PARTIAL_EVIDENCE,
        }:
            raise RunReconciliationConflictError(
                f"Run is not awaiting unknown-outcome reconciliation: {plan.disposition.value}"
            )
        if run.status is not RunStatus.RUNNING:
            raise RunReconciliationConflictError(
                f"Run status {run.status.value} cannot reconcile an unknown external outcome"
            )

        reconciled_at = self._clock()
        worker_id = f"reconcile-{hashlib.sha256(actor_id.encode()).hexdigest()[:16]}"
        try:
            grant = await self._leases.acquire(
                workspace_id,
                run_id,
                worker_id=worker_id,
                ttl=self._lease_ttl,
                acquired_at=reconciled_at,
                trace_id=TraceId.new(),
                correlation_id=CorrelationId.new(),
            )
        except RunLeaseConflictError as exc:
            raise RunReconciliationConflictError(
                "Run is still owned by another Worker and cannot be reconciled"
            ) from exc

        try:
            partial_ids = await self._validate_partial_evidence(
                run,
                plan.partial_evidence_ids,
            )
            checkpoint = self._reconciled_checkpoint(
                latest,
                partial_evidence_ids=partial_ids,
            )
            blocked_events = self._blocked_events(
                run,
                events,
                task_ids=plan.active_task_ids,
                actor_id=actor_id,
                reason=reason,
                occurred_at=reconciled_at,
            )
            trace_id = TraceId.new()
            correlation_id = CorrelationId.new()
            reconciliation_event = NewDomainEvent(
                id=self._event_id(run.id, "run.reconciled"),
                workspace_id=workspace_id,
                case_id=run.case_id,
                run_id=run.id,
                event_type="run.reconciled",
                occurred_at=reconciled_at,
                trace_id=trace_id,
                correlation_id=correlation_id,
                actor=DomainEventActor.USER,
                payload={
                    "decision": "abandon_unknown_outcome",
                    "actor_id": actor_id,
                    "reason": reason,
                    "idempotency_key_sha256": key_sha256,
                    "request_sha256": request_sha256,
                    "retry_requires_new_run": True,
                    "partial_evidence_ids": [str(value) for value in partial_ids],
                },
            )
            record, envelopes = await self._uow.append_run_checkpoint_with_events(
                checkpoint,
                prior_events=(*blocked_events, reconciliation_event),
                trace_id=trace_id,
                correlation_id=correlation_id,
                actor=DomainEventActor.SYSTEM,
                checkpoint_id=self._checkpoint_id(run.id),
                checkpoint_event_id=self._event_id(run.id, "checkpoint.reconciled"),
                lease=grant.credentials,
                lease_checked_at=reconciled_at,
            )
            reconciliation_envelope = next(
                event for event in envelopes if event.event_type == "run.reconciled"
            )
            blocked_at = max(reconciled_at, grant.run.updated_at)
            blocked = grant.run.transition_to(
                RunStatus.BLOCKED,
                stop_reason="external_outcome_unknown",
                occurred_at=blocked_at,
            )
            await self._uow.save_run(
                blocked,
                expected_version=grant.run.version,
                trace_id=trace_id,
                correlation_id=correlation_id,
                actor=DomainEventActor.SYSTEM,
                causation_event_id=reconciliation_envelope.id,
                lease=grant.credentials,
                lease_checked_at=blocked_at,
            )
            await self._leases.release(
                workspace_id,
                run.id,
                grant.credentials,
                released_at=blocked_at,
                trace_id=trace_id,
                correlation_id=correlation_id,
            )
            return RunReconciliationResult(
                run=blocked,
                latest_checkpoint=record,
                disposition=ResumeExecutionDisposition.BLOCKED_FOR_REPLAN,
            )
        except Exception:
            # A running Run cannot release its lease. Let the fenced lease
            # expire so the same durable command can finish on the next retry.
            raise

    async def _replay_if_completed(
        self,
        run: CommerceRun,
        events: tuple[DomainEventEnvelope, ...],
        *,
        key_sha256: str,
        request_sha256: str,
    ) -> RunReconciliationResult | None:
        reconciliations = tuple(event for event in events if event.event_type == "run.reconciled")
        if not reconciliations:
            return None
        if len(reconciliations) != 1:
            raise RunReconciliationConflictError("Run has conflicting reconciliation records")
        payload = reconciliations[0].payload
        if (
            payload.get("idempotency_key_sha256") != key_sha256
            or payload.get("request_sha256") != request_sha256
        ):
            raise RunReconciliationConflictError(
                "Reconciliation idempotency key conflicts with the completed command"
            )
        latest = await self._checkpoints.get_latest(run.workspace_id, run.id)
        if latest is None:
            raise RunReconciliationConflictError("Reconciled Run is missing its post-checkpoint")
        if latest.checkpoint.active_path_task_ids or latest.checkpoint.loop_iteration < 1:
            raise RunReconciliationConflictError("Reconciled post-checkpoint is inconsistent")
        if run.status is RunStatus.RUNNING:
            recovered_at = self._clock()
            worker_id = (
                "reconcile-recovery-"
                + hashlib.sha256(request_sha256.encode()).hexdigest()[:16]
            )
            try:
                grant = await self._leases.acquire(
                    run.workspace_id,
                    run.id,
                    worker_id=worker_id,
                    ttl=self._lease_ttl,
                    acquired_at=recovered_at,
                    trace_id=TraceId.new(),
                    correlation_id=CorrelationId.new(),
                )
            except RunLeaseConflictError as exc:
                raise RunReconciliationConflictError(
                    "Partially reconciled Run is still owned by another Worker"
                ) from exc
            trace_id = TraceId.new()
            correlation_id = CorrelationId.new()
            blocked = grant.run.transition_to(
                RunStatus.BLOCKED,
                stop_reason="external_outcome_unknown",
                occurred_at=max(recovered_at, grant.run.updated_at),
            )
            await self._uow.save_run(
                blocked,
                expected_version=grant.run.version,
                trace_id=trace_id,
                correlation_id=correlation_id,
                actor=DomainEventActor.SYSTEM,
                causation_event_id=reconciliations[0].id,
                lease=grant.credentials,
                lease_checked_at=recovered_at,
            )
            await self._leases.release(
                run.workspace_id,
                run.id,
                grant.credentials,
                released_at=max(recovered_at, blocked.updated_at),
                trace_id=trace_id,
                correlation_id=correlation_id,
            )
            run = blocked
        elif run.status is not RunStatus.BLOCKED or run.stop_reason != "external_outcome_unknown":
            raise RunReconciliationConflictError("Reconciled Run projection is inconsistent")
        return RunReconciliationResult(
            run=run,
            latest_checkpoint=latest,
            disposition=ResumeExecutionDisposition.BLOCKED_FOR_REPLAN,
            replayed=True,
        )

    async def _validate_partial_evidence(
        self,
        run: CommerceRun,
        evidence_ids,
    ):
        for evidence_id in evidence_ids:
            evidence = await self._evidence.get(run.workspace_id, evidence_id)
            if evidence is None or evidence.case_id != run.case_id:
                raise RunReconciliationConflictError(
                    "Partial Evidence cannot be verified against the reconciled Case"
                )
        return evidence_ids

    @staticmethod
    def _reconciled_checkpoint(
        latest: RunCheckpointRecord,
        *,
        partial_evidence_ids,
    ):
        checkpoint = latest.checkpoint
        next_iteration = checkpoint.loop_iteration + 1
        if next_iteration > checkpoint.budget_snapshot.limit.max_iterations:
            raise RunReconciliationConflictError(
                "Unknown external attempt exceeds the persisted iteration budget"
            )
        usage = checkpoint.budget_snapshot.usage
        next_usage = BudgetUsage.model_validate(
            {
                **usage.model_dump(),
                "iterations": next_iteration,
                "consecutive_no_new_evidence": (
                    0
                    if partial_evidence_ids
                    else usage.consecutive_no_new_evidence + 1
                ),
            }
        )
        return checkpoint.model_copy(
            update={
                "loop_iteration": next_iteration,
                "budget_snapshot": checkpoint.budget_snapshot.model_copy(
                    update={"usage": next_usage}
                ),
                "active_path_task_ids": (),
                "evidence_ids": tuple(
                    dict.fromkeys((*checkpoint.evidence_ids, *partial_evidence_ids))
                ),
                "wait_reason": None,
            }
        )

    @staticmethod
    def _blocked_events(
        run: CommerceRun,
        events: tuple[DomainEventEnvelope, ...],
        *,
        task_ids: tuple[AgentTaskId, ...],
        actor_id: str,
        reason: str,
        occurred_at: datetime,
    ) -> tuple[NewDomainEvent, ...]:
        started_by_task = {}
        for event in events:
            if event.event_type != "path.started":
                continue
            try:
                task_id = AgentTaskId(str(event.payload["task_id"]))
                path_type = PathType(str(event.payload["path_type"]))
            except (KeyError, TypeError, ValueError) as exc:
                raise RunReconciliationConflictError("Path start event is invalid") from exc
            started_by_task[task_id] = (event, path_type)
        blocked = []
        for task_id in task_ids:
            if task_id not in started_by_task:
                raise RunReconciliationConflictError("Active Path is missing its start event")
            started, path_type = started_by_task[task_id]
            blocked.append(
                NewDomainEvent(
                    id=CommerceRunReconciliationService._event_id(
                        run.id,
                        f"path.blocked:{task_id}",
                    ),
                    workspace_id=run.workspace_id,
                    case_id=run.case_id,
                    run_id=run.id,
                    event_type="path.blocked",
                    occurred_at=occurred_at,
                    trace_id=started.trace_id,
                    correlation_id=started.correlation_id,
                    causation_event_id=started.id,
                    actor=DomainEventActor.SYSTEM,
                    payload={
                        "task_id": str(task_id),
                        "path_type": path_type.value,
                        "status": "blocked",
                        "error_code": "external_outcome_unknown",
                        "error_message": reason,
                        "actor_id": actor_id,
                        "retry_requires_new_run": True,
                    },
                )
            )
        return tuple(blocked)

    @staticmethod
    def _request_sha256(
        *,
        run_id: RunId,
        actor_id: str,
        reason: str,
        key_sha256: str,
    ) -> str:
        payload = {
            "actor_id": actor_id,
            "decision": "abandon_unknown_outcome",
            "idempotency_key_sha256": key_sha256,
            "reason": reason,
            "run_id": str(run_id),
        }
        return hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
        ).hexdigest()

    @staticmethod
    def _checkpoint_id(run_id: RunId) -> CheckpointId:
        return CheckpointId(
            f"chkpt_{uuid5(NAMESPACE_URL, f'{run_id}:external-outcome-reconciliation').hex}"
        )

    @staticmethod
    def _event_id(run_id: RunId, kind: str) -> EventId:
        return EventId(f"evt_{uuid5(NAMESPACE_URL, f'{run_id}:{kind}').hex}")
