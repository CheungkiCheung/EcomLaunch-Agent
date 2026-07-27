"""Atomic Commerce mutations that keep Case rows and Domain Events aligned."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.commerce.actions.approval import (
    ApprovalDecisionCommand,
    ApprovalRequest,
)
from app.commerce.actions.artifacts import ActionExecutionArtifact
from app.commerce.actions.follow_up_contracts import FollowUpRecord
from app.commerce.agents.goal_loop import GoalLoopCheckpoint
from app.commerce.domain.enums import (
    ActionRunOperation,
    CaseStatus,
    RunPhase,
    RunStatus,
    RunType,
)
from app.commerce.domain.events import (
    DomainEventActor,
    DomainEventEnvelope,
    NewDomainEvent,
)
from app.commerce.domain.ids import (
    CheckpointId,
    CorrelationId,
    EventId,
    RunId,
    TraceId,
)
from app.commerce.domain.lineage import CaseLineage
from app.commerce.domain.models import Case, Evidence, Hypothesis
from app.commerce.domain.runs import CommerceRun
from app.commerce.persistence.action_artifacts import SqlActionArtifactRepository
from app.commerce.persistence.actions import (
    ActionRecord,
    SqlActionRepository,
    SqlApprovalRepository,
)
from app.commerce.persistence.events import (
    EventSequenceConflictError,
    SqlDomainEventStore,
)
from app.commerce.persistence.follow_ups import SqlFollowUpRepository
from app.commerce.persistence.lineage import SqlCaseLineageRepository
from app.commerce.persistence.repositories import (
    DuplicateEntityError,
    SqlCaseRepository,
)
from app.commerce.persistence.runs import (
    RunCheckpointRecord,
    RunLeaseCredentials,
    RunLeaseLostError,
    SqlRunCheckpointRepository,
    SqlRunLeaseRepository,
    SqlRunRepository,
)
from app.commerce.persistence.work_records import (
    SqlEvidenceRepository,
    SqlHypothesisRepository,
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

    async def create_case_with_lineage(
        self,
        case: Case,
        lineage: CaseLineage,
        *,
        trace_id: TraceId,
        correlation_id: CorrelationId,
        actor: DomainEventActor,
        causation_event_id: EventId | None = None,
        trigger_payload: dict[str, object] | None = None,
    ) -> DomainEventEnvelope:
        self._validate_lineage_membership(case, lineage)
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
                "dataset_id": str(lineage.dataset_id),
                "analysis_artifact_relative_path": (lineage.analysis_artifact_relative_path),
                "analysis_artifact_sha256": lineage.analysis_artifact_sha256,
                **({"trigger": trigger_payload} if trigger_payload is not None else {}),
            },
        )
        try:
            async with self._session_factory() as session, session.begin():
                await SqlCaseRepository.create_in_session(session, case)
                await SqlCaseLineageRepository.create_in_session(session, lineage)
                return await SqlDomainEventStore.append_in_session(session, event)
        except IntegrityError as exc:
            raise DuplicateEntityError(f"Case already exists: {case.id}") from exc

    async def attach_case_lineage(
        self,
        lineage: CaseLineage,
        *,
        trace_id: TraceId,
        correlation_id: CorrelationId,
        actor: DomainEventActor,
        causation_event_id: EventId | None = None,
    ) -> DomainEventEnvelope:
        event = NewDomainEvent(
            workspace_id=lineage.workspace_id,
            case_id=lineage.case_id,
            event_type="case.lineage_attached",
            occurred_at=lineage.created_at,
            trace_id=trace_id,
            correlation_id=correlation_id,
            causation_event_id=causation_event_id,
            actor=actor,
            payload={
                "dataset_id": str(lineage.dataset_id),
                "seller_entity_id": str(lineage.seller_entity_id),
                "analysis_artifact_relative_path": (lineage.analysis_artifact_relative_path),
                "analysis_artifact_sha256": lineage.analysis_artifact_sha256,
            },
        )
        try:
            async with self._session_factory() as session, session.begin():
                await SqlCaseLineageRepository.create_in_session(session, lineage)
                return await SqlDomainEventStore.append_in_session(session, event)
        except IntegrityError as exc:
            raise DuplicateEntityError(f"Case lineage already exists: {lineage.case_id}") from exc

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
        raise EventSequenceConflictError("Atomic Case/Event mutation exceeded sequence retry budget") from last_error

    @staticmethod
    def _case_event_type(previous: CaseStatus, current: CaseStatus) -> str:
        if current is CaseStatus.REOPENED and previous is CaseStatus.RESOLVED:
            return "case.reopened"
        if previous is not current:
            return "case.status_changed"
        return "case.updated"

    async def create_run(
        self,
        run: CommerceRun,
        *,
        trace_id: TraceId,
        correlation_id: CorrelationId,
        actor: DomainEventActor,
        actor_id: str | None = None,
        causation_event_id: EventId | None = None,
    ) -> DomainEventEnvelope:
        event = NewDomainEvent(
            workspace_id=run.workspace_id,
            case_id=run.case_id,
            run_id=run.id,
            event_type="run.created",
            occurred_at=run.created_at,
            trace_id=trace_id,
            correlation_id=correlation_id,
            causation_event_id=causation_event_id,
            actor=actor,
            payload={
                "run_type": run.run_type.value,
                "status": run.status.value,
                "phase": run.phase.value,
                "goal": run.goal,
                "parent_run_id": (str(run.parent_run_id) if run.parent_run_id is not None else None),
                "subject_action_id": (str(run.subject_action_id) if run.subject_action_id is not None else None),
                "action_operation": (run.action_operation.value if run.action_operation is not None else None),
                "actor_id": actor_id,
                "requested_paths": [value.value for value in run.requested_paths],
                "version": run.version,
            },
        )
        try:
            async with self._session_factory() as session, session.begin():
                await SqlRunRepository.create_in_session(session, run)
                return await SqlDomainEventStore.append_in_session(session, event)
        except IntegrityError as exc:
            raise DuplicateEntityError(f"Run or idempotency key already exists: {run.id}") from exc

    async def create_action(
        self,
        case: Case,
        record: ActionRecord,
        *,
        approval: ApprovalRequest | None,
        expected_case_version: int,
        trace_id: TraceId,
        correlation_id: CorrelationId,
        actor: DomainEventActor,
        actor_id: str | None = None,
        causation_event_id: EventId | None = None,
        run_id: RunId | None = None,
    ) -> tuple[DomainEventEnvelope, ...]:
        """Create an Action, optional Approval, Case membership, and events atomically."""

        if record.action.workspace_id != case.workspace_id or record.action.case_id != case.id or record.action.id not in case.action_ids or case.version != expected_case_version + 1:
            raise ValueError("Action membership must match the next Case version")
        if approval is not None and (approval.workspace_id != case.workspace_id or approval.case_id != case.id or approval.action_id != record.action.id or record.action.approval.approval_id != approval.id):
            raise ValueError("Approval request must match the persisted Action")

        try:
            async with self._session_factory() as session, session.begin():
                await SqlActionRepository.create_in_session(session, record)
                if approval is not None:
                    await SqlApprovalRepository.create_in_session(session, approval)
                await SqlCaseRepository.save_in_session(
                    session,
                    case,
                    expected_version=expected_case_version,
                )
                action_event = NewDomainEvent(
                    workspace_id=case.workspace_id,
                    case_id=case.id,
                    run_id=run_id,
                    event_type="action.created",
                    occurred_at=record.created_at,
                    trace_id=trace_id,
                    correlation_id=correlation_id,
                    causation_event_id=causation_event_id,
                    actor=actor,
                    payload={
                        "action_id": str(record.action.id),
                        "kind": record.decision.validated.draft.kind.value,
                        "status": record.action.status.value,
                        "policy_level": record.decision.level.value,
                        "policy_disposition": record.decision.disposition.value,
                        "risk_level": record.action.risk_level.value,
                        "evidence_ids": [str(value) for value in record.action.evidence_ids],
                        "validation_sha256": (record.decision.validated.validation_sha256),
                        "approval_id": (str(approval.id) if approval is not None else None),
                        "actor_id": actor_id,
                        "case_version": case.version,
                    },
                )
                envelopes = [
                    await SqlDomainEventStore.append_in_session(
                        session,
                        action_event,
                    )
                ]
                if approval is not None:
                    envelopes.append(
                        await SqlDomainEventStore.append_in_session(
                            session,
                            NewDomainEvent(
                                workspace_id=case.workspace_id,
                                case_id=case.id,
                                run_id=run_id,
                                event_type="approval.requested",
                                occurred_at=approval.created_at,
                                trace_id=trace_id,
                                correlation_id=correlation_id,
                                causation_event_id=envelopes[-1].id,
                                actor=DomainEventActor.POLICY,
                                payload={
                                    "approval_id": str(approval.id),
                                    "action_id": str(record.action.id),
                                    "required_approvals": (approval.required_approvals),
                                    "status": approval.status.value,
                                },
                            ),
                        )
                    )
                return tuple(envelopes)
        except IntegrityError as exc:
            raise DuplicateEntityError(f"Action or Approval already exists: {record.action.id}") from exc

    async def apply_approval_decision(
        self,
        record: ActionRecord,
        request: ApprovalRequest,
        command: ApprovalDecisionCommand,
        *,
        expected_action_version: int,
        expected_approval_version: int,
        prior_action_status: str,
        trace_id: TraceId,
        correlation_id: CorrelationId,
    ) -> tuple[DomainEventEnvelope, ...]:
        """Append one idempotent human decision and update projections atomically."""

        if (
            record.action.workspace_id != request.workspace_id
            or record.action.case_id != request.case_id
            or record.action.id != request.action_id
            or command.workspace_id != request.workspace_id
            or command.case_id != request.case_id
            or command.action_id != request.action_id
            or command.approval_id != request.id
        ):
            raise ValueError("Approval decision identities do not match")
        async with self._session_factory() as session, session.begin():
            await SqlApprovalRepository.append_decision_in_session(session, command)
            await SqlApprovalRepository.save_in_session(
                session,
                request,
                expected_version=expected_approval_version,
            )
            action_changed = record.version != expected_action_version
            if action_changed:
                await SqlActionRepository.save_in_session(
                    session,
                    record,
                    expected_version=expected_action_version,
                )
            approval_event = await SqlDomainEventStore.append_in_session(
                session,
                NewDomainEvent(
                    workspace_id=request.workspace_id,
                    case_id=request.case_id,
                    event_type=f"approval.{command.decision.value}",
                    occurred_at=command.created_at,
                    trace_id=trace_id,
                    correlation_id=correlation_id,
                    actor=DomainEventActor.USER,
                    payload={
                        "approval_id": str(request.id),
                        "action_id": str(request.action_id),
                        "decision_id": str(command.id),
                        "actor_id": command.actor_id,
                        "status": request.status.value,
                        "approved_count": len(request.approved_actor_ids),
                        "required_approvals": request.required_approvals,
                        "replacement_draft_sha256": (request.replacement_draft_sha256),
                    },
                ),
            )
            envelopes = [approval_event]
            if action_changed:
                envelopes.append(
                    await SqlDomainEventStore.append_in_session(
                        session,
                        NewDomainEvent(
                            workspace_id=request.workspace_id,
                            case_id=request.case_id,
                            event_type="action.status_changed",
                            occurred_at=record.updated_at,
                            trace_id=trace_id,
                            correlation_id=correlation_id,
                            causation_event_id=approval_event.id,
                            actor=DomainEventActor.POLICY,
                            payload={
                                "action_id": str(record.action.id),
                                "from_status": prior_action_status,
                                "to_status": record.action.status.value,
                                "approval_status": (record.action.approval.status.value),
                                "action_version": record.version,
                            },
                        ),
                    )
                )
            return tuple(envelopes)

    async def create_follow_up_run(
        self,
        follow_up: FollowUpRecord,
        run: CommerceRun,
        *,
        trace_id: TraceId,
        correlation_id: CorrelationId,
        actor_id: str,
    ) -> tuple[DomainEventEnvelope, ...]:
        """Atomically persist a pending Follow-up and its durable Run."""

        if run.run_type is not RunType.FOLLOW_UP or run.subject_action_id != follow_up.action_id or run.id != follow_up.run_id or run.workspace_id != follow_up.workspace_id or run.case_id != follow_up.case_id:
            raise ValueError("Follow-up and Run identities do not match")
        try:
            async with self._session_factory() as session, session.begin():
                await SqlRunRepository.create_in_session(session, run)
                await SqlFollowUpRepository.create_in_session(session, follow_up)
                run_event = await SqlDomainEventStore.append_in_session(
                    session,
                    NewDomainEvent(
                        workspace_id=run.workspace_id,
                        case_id=run.case_id,
                        run_id=run.id,
                        event_type="run.created",
                        occurred_at=run.created_at,
                        trace_id=trace_id,
                        correlation_id=correlation_id,
                        actor=DomainEventActor.USER,
                        payload={
                            "run_type": run.run_type.value,
                            "status": run.status.value,
                            "phase": run.phase.value,
                            "goal": run.goal,
                            "subject_action_id": str(follow_up.action_id),
                            "follow_up_id": str(follow_up.id),
                            "actor_id": actor_id,
                            "version": run.version,
                        },
                    ),
                )
                requested_event = await SqlDomainEventStore.append_in_session(
                    session,
                    NewDomainEvent(
                        workspace_id=run.workspace_id,
                        case_id=run.case_id,
                        run_id=run.id,
                        event_type="follow_up.requested",
                        occurred_at=follow_up.created_at,
                        trace_id=trace_id,
                        correlation_id=correlation_id,
                        causation_event_id=run_event.id,
                        actor=DomainEventActor.USER,
                        payload={
                            "follow_up_id": str(follow_up.id),
                            "action_id": str(follow_up.action_id),
                            "dataset_id": str(follow_up.dataset_id),
                            "evaluation_window": follow_up.evaluation_window.model_dump(mode="json"),
                            "minimum_sample_size": follow_up.minimum_sample_size,
                            "actor_id": actor_id,
                        },
                    ),
                )
                return run_event, requested_event
        except IntegrityError as exc:
            raise DuplicateEntityError(f"Follow-up or Run already exists: {follow_up.id}") from exc

    async def finish_follow_up(
        self,
        follow_up: FollowUpRecord,
        record: ActionRecord,
        case: Case,
        run: CommerceRun,
        *,
        prior_action_status: str,
        prior_case_status: CaseStatus,
        expected_follow_up_version: int,
        expected_action_version: int,
        expected_case_version: int,
        expected_run_version: int,
        trace_id: TraceId,
        correlation_id: CorrelationId,
        lease: RunLeaseCredentials,
        lease_checked_at: datetime,
    ) -> tuple[DomainEventEnvelope, ...]:
        """Commit Follow-up, Action, Case, and terminal Run in one transaction."""

        if (
            run.run_type is not RunType.FOLLOW_UP
            or run.status is not RunStatus.COMPLETED
            or run.subject_action_id != record.action.id
            or follow_up.run_id != run.id
            or follow_up.action_id != record.action.id
            or follow_up.case_id != case.id
            or follow_up.workspace_id != case.workspace_id
        ):
            raise ValueError("Finished Follow-up identities or state do not match")
        async with self._session_factory() as session, session.begin():
            await SqlRunLeaseRepository.require_valid_in_session(
                session,
                run.workspace_id,
                run.id,
                lease,
                checked_at=lease_checked_at,
            )
            await SqlFollowUpRepository.save_in_session(
                session,
                follow_up,
                expected_version=expected_follow_up_version,
            )
            await SqlActionRepository.save_in_session(
                session,
                record,
                expected_version=expected_action_version,
            )
            await SqlCaseRepository.save_in_session(
                session,
                case,
                expected_version=expected_case_version,
            )
            previous_run_status, previous_run_phase = await SqlRunRepository.save_in_session(
                session,
                run,
                expected_version=expected_run_version,
            )
            follow_up_event = await SqlDomainEventStore.append_in_session(
                session,
                NewDomainEvent(
                    workspace_id=run.workspace_id,
                    case_id=run.case_id,
                    run_id=run.id,
                    event_type="follow_up.evaluated",
                    occurred_at=follow_up.updated_at,
                    trace_id=trace_id,
                    correlation_id=correlation_id,
                    actor=DomainEventActor.SYSTEM,
                    payload={
                        "follow_up_id": str(follow_up.id),
                        "action_id": str(record.action.id),
                        "outcome": follow_up.outcome.value,
                        "signal_status": follow_up.signal_status.value,
                        "attribution_method": follow_up.attribution_method.value,
                        "metric_observation_id": (str(follow_up.metric_observation.id) if follow_up.metric_observation is not None else None),
                        "causal_claim": False,
                        "follow_up_version": follow_up.version,
                    },
                ),
            )
            action_event = await SqlDomainEventStore.append_in_session(
                session,
                NewDomainEvent(
                    workspace_id=run.workspace_id,
                    case_id=run.case_id,
                    run_id=run.id,
                    event_type="action.status_changed",
                    occurred_at=record.updated_at,
                    trace_id=trace_id,
                    correlation_id=correlation_id,
                    causation_event_id=follow_up_event.id,
                    actor=DomainEventActor.POLICY,
                    payload={
                        "action_id": str(record.action.id),
                        "from_status": prior_action_status,
                        "to_status": record.action.status.value,
                        "action_version": record.version,
                    },
                ),
            )
            case_event = await SqlDomainEventStore.append_in_session(
                session,
                NewDomainEvent(
                    workspace_id=run.workspace_id,
                    case_id=run.case_id,
                    run_id=run.id,
                    event_type=self._case_event_type(
                        prior_case_status,
                        case.status,
                    ),
                    occurred_at=case.updated_at,
                    trace_id=trace_id,
                    correlation_id=correlation_id,
                    causation_event_id=action_event.id,
                    actor=DomainEventActor.POLICY,
                    payload={
                        "from_status": prior_case_status.value,
                        "to_status": case.status.value,
                        "version": case.version,
                    },
                ),
            )
            run_event = await SqlDomainEventStore.append_in_session(
                session,
                NewDomainEvent(
                    workspace_id=run.workspace_id,
                    case_id=run.case_id,
                    run_id=run.id,
                    event_type="run.status_changed",
                    occurred_at=run.updated_at,
                    trace_id=trace_id,
                    correlation_id=correlation_id,
                    causation_event_id=case_event.id,
                    actor=DomainEventActor.SYSTEM,
                    payload={
                        "from_status": previous_run_status.value,
                        "to_status": run.status.value,
                        "from_phase": previous_run_phase.value,
                        "to_phase": run.phase.value,
                        "stop_reason": run.stop_reason,
                        "version": run.version,
                    },
                ),
            )
            return follow_up_event, action_event, case_event, run_event

    async def begin_action_execution(
        self,
        record: ActionRecord,
        run: CommerceRun,
        *,
        operation: ActionRunOperation,
        prior_action_status: str,
        expected_action_version: int,
        trace_id: TraceId,
        correlation_id: CorrelationId,
        lease: RunLeaseCredentials,
        lease_checked_at: datetime,
    ) -> DomainEventEnvelope:
        """Fence one Action transition into executing or rolling_back."""

        if run.run_type is not RunType.ACTION_EXECUTION or run.subject_action_id != record.action.id or run.action_operation is not operation or run.workspace_id != record.action.workspace_id or run.case_id != record.action.case_id:
            raise ValueError("Action Execution Run does not match the Action")
        async with self._session_factory() as session, session.begin():
            await SqlRunLeaseRepository.require_valid_in_session(
                session,
                run.workspace_id,
                run.id,
                lease,
                checked_at=lease_checked_at,
            )
            await SqlActionRepository.save_in_session(
                session,
                record,
                expected_version=expected_action_version,
            )
            return await SqlDomainEventStore.append_in_session(
                session,
                NewDomainEvent(
                    workspace_id=run.workspace_id,
                    case_id=run.case_id,
                    run_id=run.id,
                    event_type="action.status_changed",
                    occurred_at=record.updated_at,
                    trace_id=trace_id,
                    correlation_id=correlation_id,
                    actor=DomainEventActor.SYSTEM,
                    payload={
                        "action_id": str(record.action.id),
                        "operation": operation.value,
                        "from_status": prior_action_status,
                        "to_status": record.action.status.value,
                        "action_version": record.version,
                    },
                ),
            )

    async def finish_action_execution(
        self,
        record: ActionRecord,
        run: CommerceRun,
        artifact: ActionExecutionArtifact,
        *,
        case: Case | None,
        operation: ActionRunOperation,
        prior_action_status: str,
        prior_case_status: CaseStatus | None,
        expected_action_version: int,
        expected_case_version: int | None,
        expected_run_version: int,
        expected_artifact_version: int | None,
        trace_id: TraceId,
        correlation_id: CorrelationId,
        lease: RunLeaseCredentials,
        lease_checked_at: datetime,
    ) -> tuple[DomainEventEnvelope, ...]:
        """Atomically persist verified Artifact, Action result, and terminal Run."""

        if (
            run.run_type is not RunType.ACTION_EXECUTION
            or run.subject_action_id != record.action.id
            or run.action_operation is not operation
            or artifact.action_id != record.action.id
            or artifact.workspace_id != run.workspace_id
            or artifact.case_id != run.case_id
            or run.status is not RunStatus.COMPLETED
        ):
            raise ValueError("Finished Action Execution identities or state do not match")
        if case is not None and (case.workspace_id != run.workspace_id or case.id != run.case_id or prior_case_status is None or expected_case_version is None):
            raise ValueError("Action Execution Case update does not match the Run")
        async with self._session_factory() as session, session.begin():
            await SqlRunLeaseRepository.require_valid_in_session(
                session,
                run.workspace_id,
                run.id,
                lease,
                checked_at=lease_checked_at,
            )
            await SqlActionRepository.save_in_session(
                session,
                record,
                expected_version=expected_action_version,
            )
            if case is not None:
                await SqlCaseRepository.save_in_session(
                    session,
                    case,
                    expected_version=expected_case_version,
                )
            if expected_artifact_version is None:
                await SqlActionArtifactRepository.create_in_session(session, artifact)
                artifact_event_type = "action.artifact_created"
            else:
                await SqlActionArtifactRepository.save_in_session(
                    session,
                    artifact,
                    expected_version=expected_artifact_version,
                )
                artifact_event_type = "action.artifact_rolled_back"
            previous_run_status, previous_run_phase = await SqlRunRepository.save_in_session(
                session,
                run,
                expected_version=expected_run_version,
            )
            artifact_event = await SqlDomainEventStore.append_in_session(
                session,
                NewDomainEvent(
                    workspace_id=run.workspace_id,
                    case_id=run.case_id,
                    run_id=run.id,
                    event_type=artifact_event_type,
                    occurred_at=artifact.updated_at,
                    trace_id=trace_id,
                    correlation_id=correlation_id,
                    actor=DomainEventActor.SYSTEM,
                    payload={
                        "action_id": str(record.action.id),
                        "operation": operation.value,
                        "artifact_kind": artifact.kind.value,
                        "artifact_status": artifact.status.value,
                        "artifact_version": artifact.version,
                        "verification_sha256": artifact.verification_sha256,
                    },
                ),
            )
            action_event = await SqlDomainEventStore.append_in_session(
                session,
                NewDomainEvent(
                    workspace_id=run.workspace_id,
                    case_id=run.case_id,
                    run_id=run.id,
                    event_type="action.status_changed",
                    occurred_at=record.updated_at,
                    trace_id=trace_id,
                    correlation_id=correlation_id,
                    causation_event_id=artifact_event.id,
                    actor=DomainEventActor.POLICY,
                    payload={
                        "action_id": str(record.action.id),
                        "operation": operation.value,
                        "from_status": prior_action_status,
                        "to_status": record.action.status.value,
                        "action_version": record.version,
                    },
                ),
            )
            prior_event = action_event
            if case is not None:
                prior_event = await SqlDomainEventStore.append_in_session(
                    session,
                    NewDomainEvent(
                        workspace_id=run.workspace_id,
                        case_id=run.case_id,
                        run_id=run.id,
                        event_type=self._case_event_type(
                            prior_case_status,
                            case.status,
                        ),
                        occurred_at=case.updated_at,
                        trace_id=trace_id,
                        correlation_id=correlation_id,
                        causation_event_id=action_event.id,
                        actor=DomainEventActor.POLICY,
                        payload={
                            "from_status": prior_case_status.value,
                            "to_status": case.status.value,
                            "version": case.version,
                        },
                    ),
                )
            run_event = await SqlDomainEventStore.append_in_session(
                session,
                NewDomainEvent(
                    workspace_id=run.workspace_id,
                    case_id=run.case_id,
                    run_id=run.id,
                    event_type="run.status_changed",
                    occurred_at=run.updated_at,
                    trace_id=trace_id,
                    correlation_id=correlation_id,
                    causation_event_id=prior_event.id,
                    actor=DomainEventActor.SYSTEM,
                    payload={
                        "from_status": previous_run_status.value,
                        "to_status": run.status.value,
                        "from_phase": previous_run_phase.value,
                        "to_phase": run.phase.value,
                        "stop_reason": run.stop_reason,
                        "version": run.version,
                    },
                ),
            )
            if case is None:
                return artifact_event, action_event, run_event
            return artifact_event, action_event, prior_event, run_event

    async def fail_action_execution(
        self,
        record: ActionRecord,
        run: CommerceRun,
        *,
        operation: ActionRunOperation,
        prior_action_status: str,
        error_message: str,
        expected_action_version: int,
        expected_run_version: int,
        trace_id: TraceId,
        correlation_id: CorrelationId,
        lease: RunLeaseCredentials,
        lease_checked_at: datetime,
    ) -> tuple[DomainEventEnvelope, ...]:
        """Persist connector failure and a terminal failed Run under the lease."""

        if run.status is not RunStatus.FAILED:
            raise ValueError("Failed Action Execution requires a failed Run")
        async with self._session_factory() as session, session.begin():
            await SqlRunLeaseRepository.require_valid_in_session(
                session,
                run.workspace_id,
                run.id,
                lease,
                checked_at=lease_checked_at,
            )
            await SqlActionRepository.save_in_session(
                session,
                record,
                expected_version=expected_action_version,
            )
            previous_run_status, previous_run_phase = await SqlRunRepository.save_in_session(
                session,
                run,
                expected_version=expected_run_version,
            )
            failure_event = await SqlDomainEventStore.append_in_session(
                session,
                NewDomainEvent(
                    workspace_id=run.workspace_id,
                    case_id=run.case_id,
                    run_id=run.id,
                    event_type=("action.execution_failed" if operation is ActionRunOperation.EXECUTE else "action.rollback_failed"),
                    occurred_at=record.updated_at,
                    trace_id=trace_id,
                    correlation_id=correlation_id,
                    actor=DomainEventActor.SYSTEM,
                    payload={
                        "action_id": str(record.action.id),
                        "operation": operation.value,
                        "from_status": prior_action_status,
                        "to_status": record.action.status.value,
                        "action_version": record.version,
                        "error_message": error_message[:1_000],
                    },
                ),
            )
            run_event = await SqlDomainEventStore.append_in_session(
                session,
                NewDomainEvent(
                    workspace_id=run.workspace_id,
                    case_id=run.case_id,
                    run_id=run.id,
                    event_type="run.status_changed",
                    occurred_at=run.updated_at,
                    trace_id=trace_id,
                    correlation_id=correlation_id,
                    causation_event_id=failure_event.id,
                    actor=DomainEventActor.SYSTEM,
                    payload={
                        "from_status": previous_run_status.value,
                        "to_status": run.status.value,
                        "from_phase": previous_run_phase.value,
                        "to_phase": run.phase.value,
                        "stop_reason": run.stop_reason,
                        "version": run.version,
                    },
                ),
            )
            return failure_event, run_event

    async def save_run(
        self,
        run: CommerceRun,
        *,
        expected_version: int,
        trace_id: TraceId,
        correlation_id: CorrelationId,
        actor: DomainEventActor,
        causation_event_id: EventId | None = None,
        lease: RunLeaseCredentials | None = None,
        lease_checked_at: datetime | None = None,
    ) -> DomainEventEnvelope:
        last_error: IntegrityError | None = None
        for attempt in range(self.MAX_SEQUENCE_RETRIES):
            try:
                async with self._session_factory() as session, session.begin():
                    if lease is not None:
                        await SqlRunLeaseRepository.require_valid_in_session(
                            session,
                            run.workspace_id,
                            run.id,
                            lease,
                            checked_at=lease_checked_at or datetime.now(UTC),
                        )
                    previous_status, previous_phase = await SqlRunRepository.save_in_session(
                        session,
                        run,
                        expected_version=expected_version,
                    )
                    event_type = self._run_event_type(
                        previous_status,
                        run.status,
                        previous_phase,
                        run.phase,
                    )
                    event = NewDomainEvent(
                        workspace_id=run.workspace_id,
                        case_id=run.case_id,
                        run_id=run.id,
                        event_type=event_type,
                        occurred_at=run.updated_at,
                        trace_id=trace_id,
                        correlation_id=correlation_id,
                        causation_event_id=causation_event_id,
                        actor=actor,
                        payload={
                            "from_status": previous_status.value,
                            "to_status": run.status.value,
                            "from_phase": previous_phase.value,
                            "to_phase": run.phase.value,
                            "wait_reason": run.wait_reason,
                            "stop_reason": run.stop_reason,
                            "version": run.version,
                        },
                    )
                    return await SqlDomainEventStore.append_in_session(session, event)
            except IntegrityError as exc:
                last_error = exc
                await asyncio.sleep(0.001 * (attempt + 1))
        raise EventSequenceConflictError("Atomic Run/Event mutation exceeded sequence retry budget") from last_error

    @staticmethod
    def _run_event_type(
        previous_status: RunStatus,
        current_status: RunStatus,
        previous_phase: RunPhase,
        current_phase: RunPhase,
    ) -> str:
        if previous_status is not current_status:
            return "run.status_changed"
        if previous_phase is not current_phase:
            return "run.phase_changed"
        return "run.updated"

    async def append_run_checkpoint(
        self,
        checkpoint: GoalLoopCheckpoint,
        *,
        trace_id: TraceId,
        correlation_id: CorrelationId,
        actor: DomainEventActor,
        causation_event_id: EventId | None = None,
        checkpoint_id: CheckpointId | None = None,
        lease: RunLeaseCredentials | None = None,
        lease_checked_at: datetime | None = None,
    ) -> tuple[RunCheckpointRecord, DomainEventEnvelope]:
        selected_id = checkpoint_id or CheckpointId.new()
        last_error: IntegrityError | None = None
        for attempt in range(self.MAX_SEQUENCE_RETRIES):
            try:
                async with self._session_factory() as session, session.begin():
                    run = await SqlRunRepository.get_in_session(
                        session,
                        checkpoint.workspace_id,
                        checkpoint.run_id,
                    )
                    if run is None:
                        raise ValueError(f"Run not found: {checkpoint.run_id}")
                    if run.status is RunStatus.RUNNING:
                        if lease is None:
                            raise RunLeaseLostError("Running Run Checkpoint write requires a lease")
                        await SqlRunLeaseRepository.require_valid_in_session(
                            session,
                            checkpoint.workspace_id,
                            checkpoint.run_id,
                            lease,
                            checked_at=lease_checked_at or datetime.now(UTC),
                        )
                    elif lease is not None:
                        await SqlRunLeaseRepository.require_valid_in_session(
                            session,
                            checkpoint.workspace_id,
                            checkpoint.run_id,
                            lease,
                            checked_at=lease_checked_at or datetime.now(UTC),
                        )
                    record = await SqlRunCheckpointRepository.append_in_session(
                        session,
                        checkpoint,
                        checkpoint_id=selected_id,
                    )
                    event = NewDomainEvent(
                        workspace_id=checkpoint.workspace_id,
                        case_id=checkpoint.case_id,
                        run_id=checkpoint.run_id,
                        event_type="run.checkpoint_saved",
                        occurred_at=record.created_at,
                        trace_id=trace_id,
                        correlation_id=correlation_id,
                        causation_event_id=causation_event_id,
                        actor=actor,
                        payload={
                            "checkpoint_id": str(record.id),
                            "checkpoint_sequence": record.sequence,
                            "checkpoint_schema_version": checkpoint.schema_version,
                            "loop_iteration": checkpoint.loop_iteration,
                        },
                    )
                    envelope = await SqlDomainEventStore.append_in_session(
                        session,
                        event,
                    )
                    return record, envelope
            except IntegrityError as exc:
                last_error = exc
                await asyncio.sleep(0.001 * (attempt + 1))
        raise EventSequenceConflictError("Atomic Checkpoint/Event append exceeded sequence retry budget") from last_error

    async def append_run_checkpoint_with_events(
        self,
        checkpoint: GoalLoopCheckpoint,
        *,
        prior_events: tuple[NewDomainEvent, ...],
        trace_id: TraceId,
        correlation_id: CorrelationId,
        actor: DomainEventActor,
        causation_event_id: EventId | None = None,
        checkpoint_id: CheckpointId | None = None,
        checkpoint_event_id: EventId | None = None,
        lease: RunLeaseCredentials | None = None,
        lease_checked_at: datetime | None = None,
    ) -> tuple[RunCheckpointRecord, tuple[DomainEventEnvelope, ...]]:
        """Atomically append run events followed by one fenced Checkpoint."""

        for event in prior_events:
            if event.workspace_id != checkpoint.workspace_id or event.case_id != checkpoint.case_id or event.run_id != checkpoint.run_id:
                raise ValueError("Prior Checkpoint events must match Workspace, Case and Run")
        selected_id = checkpoint_id or CheckpointId.new()
        last_error: IntegrityError | None = None
        for attempt in range(self.MAX_SEQUENCE_RETRIES):
            try:
                async with self._session_factory() as session, session.begin():
                    run = await SqlRunRepository.get_in_session(
                        session,
                        checkpoint.workspace_id,
                        checkpoint.run_id,
                    )
                    if run is None:
                        raise ValueError(f"Run not found: {checkpoint.run_id}")
                    if run.status is RunStatus.RUNNING:
                        if lease is None:
                            raise RunLeaseLostError("Running Run Checkpoint write requires a lease")
                        await SqlRunLeaseRepository.require_valid_in_session(
                            session,
                            checkpoint.workspace_id,
                            checkpoint.run_id,
                            lease,
                            checked_at=lease_checked_at or datetime.now(UTC),
                        )
                    elif lease is not None:
                        await SqlRunLeaseRepository.require_valid_in_session(
                            session,
                            checkpoint.workspace_id,
                            checkpoint.run_id,
                            lease,
                            checked_at=lease_checked_at or datetime.now(UTC),
                        )

                    envelopes = [await SqlDomainEventStore.append_in_session(session, event) for event in prior_events]
                    record = await SqlRunCheckpointRepository.append_in_session(
                        session,
                        checkpoint,
                        checkpoint_id=selected_id,
                    )
                    checkpoint_event = NewDomainEvent(
                        id=checkpoint_event_id or EventId.new(),
                        workspace_id=checkpoint.workspace_id,
                        case_id=checkpoint.case_id,
                        run_id=checkpoint.run_id,
                        event_type="run.checkpoint_saved",
                        occurred_at=record.created_at,
                        trace_id=trace_id,
                        correlation_id=correlation_id,
                        causation_event_id=causation_event_id,
                        actor=actor,
                        payload={
                            "checkpoint_id": str(record.id),
                            "checkpoint_sequence": record.sequence,
                            "checkpoint_schema_version": checkpoint.schema_version,
                            "loop_iteration": checkpoint.loop_iteration,
                        },
                    )
                    envelopes.append(
                        await SqlDomainEventStore.append_in_session(
                            session,
                            checkpoint_event,
                        )
                    )
                    return record, tuple(envelopes)
            except IntegrityError as exc:
                last_error = exc
                await asyncio.sleep(0.001 * (attempt + 1))
        raise EventSequenceConflictError("Atomic prior Events/Checkpoint append exceeded sequence retry budget") from last_error

    async def append_evidence(
        self,
        case: Case,
        evidence: Evidence,
        *,
        expected_version: int,
        trace_id: TraceId,
        correlation_id: CorrelationId,
        actor: DomainEventActor,
        causation_event_id: EventId | None = None,
        run_id: RunId | None = None,
        lease: RunLeaseCredentials | None = None,
        lease_checked_at: datetime | None = None,
    ) -> DomainEventEnvelope:
        """Append Evidence and its Case membership/event atomically."""

        self._validate_evidence_membership(case, evidence)
        last_error: IntegrityError | None = None
        for attempt in range(self.MAX_SEQUENCE_RETRIES):
            try:
                async with self._session_factory() as session, session.begin():
                    if run_id is not None:
                        if lease is None:
                            raise RunLeaseLostError("Agent Evidence write for a running Run requires a lease")
                        lease_row = await SqlRunLeaseRepository.require_valid_in_session(
                            session,
                            case.workspace_id,
                            run_id,
                            lease,
                            checked_at=lease_checked_at or datetime.now(UTC),
                        )
                        if lease_row.case_id != str(case.id):
                            raise ValueError("Evidence Run lease must belong to the Case")
                    await SqlEvidenceRepository.append_in_session(session, evidence)
                    await SqlCaseRepository.save_in_session(
                        session,
                        case,
                        expected_version=expected_version,
                    )
                    event = NewDomainEvent(
                        workspace_id=case.workspace_id,
                        case_id=case.id,
                        run_id=run_id,
                        event_type="evidence.appended",
                        occurred_at=case.updated_at,
                        trace_id=trace_id,
                        correlation_id=correlation_id,
                        causation_event_id=causation_event_id,
                        actor=actor,
                        payload={
                            "evidence_id": str(evidence.id),
                            "relation": evidence.relation.value,
                            "semantic_status": evidence.semantic_status.value,
                            "confidence": evidence.confidence,
                            "fact_ids": [str(value) for value in evidence.fact_ids],
                            "metric_observation_ids": [str(value) for value in evidence.metric_observation_ids],
                            "case_version": case.version,
                        },
                    )
                    return await SqlDomainEventStore.append_in_session(session, event)
            except IntegrityError as exc:
                last_error = exc
                await asyncio.sleep(0.001 * (attempt + 1))
        raise EventSequenceConflictError("Atomic Evidence/Case/Event mutation exceeded sequence retry budget") from last_error

    async def append_evidence_batch(
        self,
        case: Case,
        evidences: tuple[Evidence, ...],
        *,
        expected_version: int,
        trace_id: TraceId,
        correlation_id: CorrelationId,
        actor: DomainEventActor,
        causation_event_id: EventId | None = None,
        run_id: RunId | None = None,
        lease: RunLeaseCredentials | None = None,
        lease_checked_at: datetime | None = None,
    ) -> tuple[DomainEventEnvelope, ...]:
        """Append one Path's Evidence set in a single Case transaction.

        The Case aggregate advances once for the Path submission while every
        immutable Evidence record receives its own authoritative event. This
        keeps audit granularity without exposing a partial Evidence set after a
        process failure.
        """

        if not evidences:
            raise ValueError("Evidence batch cannot be empty")
        if case.version != expected_version + 1:
            raise ValueError("Saved Case version must equal expected_version + 1")
        evidence_ids = tuple(evidence.id for evidence in evidences)
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("Evidence batch IDs must be unique")
        if len(set(case.evidence_ids)) != len(case.evidence_ids):
            raise ValueError("Case Evidence membership IDs must be unique")
        for evidence in evidences:
            self._validate_evidence_membership(case, evidence)

        last_error: IntegrityError | None = None
        for attempt in range(self.MAX_SEQUENCE_RETRIES):
            try:
                async with self._session_factory() as session, session.begin():
                    if run_id is not None:
                        if lease is None:
                            raise RunLeaseLostError("Agent Evidence write for a running Run requires a lease")
                        lease_row = await SqlRunLeaseRepository.require_valid_in_session(
                            session,
                            case.workspace_id,
                            run_id,
                            lease,
                            checked_at=lease_checked_at or datetime.now(UTC),
                        )
                        if lease_row.case_id != str(case.id):
                            raise ValueError("Evidence Run lease must belong to the Case")

                    for evidence in evidences:
                        await SqlEvidenceRepository.append_in_session(session, evidence)
                    await SqlCaseRepository.save_in_session(
                        session,
                        case,
                        expected_version=expected_version,
                    )

                    envelopes: list[DomainEventEnvelope] = []
                    prior_event_id = causation_event_id
                    for evidence in evidences:
                        event = NewDomainEvent(
                            workspace_id=case.workspace_id,
                            case_id=case.id,
                            run_id=run_id,
                            event_type="evidence.appended",
                            occurred_at=case.updated_at,
                            trace_id=trace_id,
                            correlation_id=correlation_id,
                            causation_event_id=prior_event_id,
                            actor=actor,
                            payload={
                                "evidence_id": str(evidence.id),
                                "relation": evidence.relation.value,
                                "semantic_status": evidence.semantic_status.value,
                                "confidence": evidence.confidence,
                                "fact_ids": [str(value) for value in evidence.fact_ids],
                                "metric_observation_ids": [str(value) for value in evidence.metric_observation_ids],
                                "case_version": case.version,
                            },
                        )
                        envelope = await SqlDomainEventStore.append_in_session(session, event)
                        envelopes.append(envelope)
                        prior_event_id = envelope.id
                    return tuple(envelopes)
            except IntegrityError as exc:
                last_error = exc
                await asyncio.sleep(0.001 * (attempt + 1))
        raise EventSequenceConflictError("Atomic Evidence batch/Case/Event mutation exceeded sequence retry budget") from last_error

    async def append_evidence_batch_with_checkpoint_events(
        self,
        case: Case,
        evidences: tuple[Evidence, ...],
        checkpoint: GoalLoopCheckpoint,
        *,
        expected_version: int,
        prior_events: tuple[NewDomainEvent, ...],
        trace_id: TraceId,
        correlation_id: CorrelationId,
        actor: DomainEventActor,
        lease: RunLeaseCredentials,
        lease_checked_at: datetime,
        causation_event_id: EventId | None = None,
        checkpoint_id: CheckpointId | None = None,
        checkpoint_event_id: EventId | None = None,
    ) -> tuple[RunCheckpointRecord, tuple[DomainEventEnvelope, ...]]:
        """Atomically commit Path Evidence, terminal events, and post-checkpoint."""

        if not evidences:
            raise ValueError("Evidence batch cannot be empty")
        if case.version != expected_version + 1:
            raise ValueError("Saved Case version must equal expected_version + 1")
        evidence_ids = tuple(evidence.id for evidence in evidences)
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("Evidence batch IDs must be unique")
        if len(set(case.evidence_ids)) != len(case.evidence_ids):
            raise ValueError("Case Evidence membership IDs must be unique")
        for evidence in evidences:
            self._validate_evidence_membership(case, evidence)
        if checkpoint.workspace_id != case.workspace_id or checkpoint.case_id != case.id:
            raise ValueError("Evidence checkpoint must match Workspace and Case")
        for event in prior_events:
            if event.workspace_id != checkpoint.workspace_id or event.case_id != checkpoint.case_id or event.run_id != checkpoint.run_id:
                raise ValueError("Terminal Path events must match Checkpoint Workspace, Case and Run")

        selected_id = checkpoint_id or CheckpointId.new()
        last_error: IntegrityError | None = None
        for attempt in range(self.MAX_SEQUENCE_RETRIES):
            try:
                async with self._session_factory() as session, session.begin():
                    lease_row = await SqlRunLeaseRepository.require_valid_in_session(
                        session,
                        checkpoint.workspace_id,
                        checkpoint.run_id,
                        lease,
                        checked_at=lease_checked_at,
                    )
                    if lease_row.case_id != str(case.id):
                        raise ValueError("Evidence Run lease must belong to the Case")

                    for evidence in evidences:
                        await SqlEvidenceRepository.append_in_session(session, evidence)
                    await SqlCaseRepository.save_in_session(
                        session,
                        case,
                        expected_version=expected_version,
                    )

                    envelopes: list[DomainEventEnvelope] = []
                    prior_event_id = causation_event_id
                    for evidence in evidences:
                        event = NewDomainEvent(
                            workspace_id=case.workspace_id,
                            case_id=case.id,
                            run_id=checkpoint.run_id,
                            event_type="evidence.appended",
                            occurred_at=case.updated_at,
                            trace_id=trace_id,
                            correlation_id=correlation_id,
                            causation_event_id=prior_event_id,
                            actor=actor,
                            payload={
                                "evidence_id": str(evidence.id),
                                "relation": evidence.relation.value,
                                "semantic_status": evidence.semantic_status.value,
                                "confidence": evidence.confidence,
                                "fact_ids": [str(value) for value in evidence.fact_ids],
                                "metric_observation_ids": [str(value) for value in evidence.metric_observation_ids],
                                "case_version": case.version,
                            },
                        )
                        envelope = await SqlDomainEventStore.append_in_session(session, event)
                        envelopes.append(envelope)
                        prior_event_id = envelope.id

                    for event in prior_events:
                        envelopes.append(await SqlDomainEventStore.append_in_session(session, event))
                    record = await SqlRunCheckpointRepository.append_in_session(
                        session,
                        checkpoint,
                        checkpoint_id=selected_id,
                    )
                    checkpoint_event = NewDomainEvent(
                        id=checkpoint_event_id or EventId.new(),
                        workspace_id=checkpoint.workspace_id,
                        case_id=checkpoint.case_id,
                        run_id=checkpoint.run_id,
                        event_type="run.checkpoint_saved",
                        occurred_at=record.created_at,
                        trace_id=trace_id,
                        correlation_id=correlation_id,
                        causation_event_id=(envelopes[-1].id if envelopes else causation_event_id),
                        actor=actor,
                        payload={
                            "checkpoint_id": str(record.id),
                            "checkpoint_sequence": record.sequence,
                            "checkpoint_schema_version": checkpoint.schema_version,
                            "loop_iteration": checkpoint.loop_iteration,
                        },
                    )
                    envelopes.append(await SqlDomainEventStore.append_in_session(session, checkpoint_event))
                    return record, tuple(envelopes)
            except IntegrityError as exc:
                last_error = exc
                await asyncio.sleep(0.001 * (attempt + 1))
        raise EventSequenceConflictError("Atomic Evidence/terminal Events/Checkpoint mutation exceeded sequence retry budget") from last_error

    async def append_hypothesis_version(
        self,
        case: Case,
        hypothesis: Hypothesis,
        *,
        expected_version: int,
        trace_id: TraceId,
        correlation_id: CorrelationId,
        actor: DomainEventActor,
        causation_event_id: EventId | None = None,
    ) -> DomainEventEnvelope:
        """Append a Hypothesis version and its Case membership/event atomically."""

        self._validate_hypothesis_membership(case, hypothesis)
        last_error: IntegrityError | None = None
        for attempt in range(self.MAX_SEQUENCE_RETRIES):
            try:
                async with self._session_factory() as session, session.begin():
                    await SqlHypothesisRepository.append_version_in_session(
                        session,
                        hypothesis,
                    )
                    await SqlCaseRepository.save_in_session(
                        session,
                        case,
                        expected_version=expected_version,
                    )
                    event = NewDomainEvent(
                        workspace_id=case.workspace_id,
                        case_id=case.id,
                        event_type="hypothesis.version_appended",
                        occurred_at=case.updated_at,
                        trace_id=trace_id,
                        correlation_id=correlation_id,
                        causation_event_id=causation_event_id,
                        actor=actor,
                        payload={
                            "hypothesis_id": str(hypothesis.id),
                            "hypothesis_version": hypothesis.version,
                            "status": hypothesis.status.value,
                            "confidence": hypothesis.confidence,
                            "supporting_evidence_ids": [str(value) for value in hypothesis.supporting_evidence_ids],
                            "contradicting_evidence_ids": [str(value) for value in hypothesis.contradicting_evidence_ids],
                            "case_version": case.version,
                        },
                    )
                    return await SqlDomainEventStore.append_in_session(session, event)
            except IntegrityError as exc:
                last_error = exc
                await asyncio.sleep(0.001 * (attempt + 1))
        raise EventSequenceConflictError("Atomic Hypothesis/Case/Event mutation exceeded sequence retry budget") from last_error

    async def append_hypothesis_versions_with_events(
        self,
        case: Case,
        hypotheses: tuple[Hypothesis, ...],
        *,
        expected_version: int,
        prior_events: tuple[NewDomainEvent, ...],
        trace_id: TraceId,
        correlation_id: CorrelationId,
        actor: DomainEventActor,
        causation_event_id: EventId | None = None,
        run_id: RunId | None = None,
        lease: RunLeaseCredentials | None = None,
        lease_checked_at: datetime | None = None,
    ) -> tuple[DomainEventEnvelope, ...]:
        """Atomically persist one Lead/Verification result as Hypothesis versions."""

        if not hypotheses:
            raise ValueError("Hypothesis batch cannot be empty")
        references = tuple((item.id, item.version) for item in hypotheses)
        if len(references) != len(set(references)):
            raise ValueError("Hypothesis batch references must be unique")
        for hypothesis in hypotheses:
            self._validate_hypothesis_membership(case, hypothesis)
        for event in prior_events:
            if event.workspace_id != case.workspace_id or event.case_id != case.id or event.run_id != run_id:
                raise ValueError("Prior Hypothesis events must match Workspace, Case and Run")

        last_error: IntegrityError | None = None
        for attempt in range(self.MAX_SEQUENCE_RETRIES):
            try:
                async with self._session_factory() as session, session.begin():
                    if run_id is not None:
                        if lease is None:
                            raise RunLeaseLostError("Agent Hypothesis write for a running Run requires a lease")
                        lease_row = await SqlRunLeaseRepository.require_valid_in_session(
                            session,
                            case.workspace_id,
                            run_id,
                            lease,
                            checked_at=lease_checked_at or datetime.now(UTC),
                        )
                        if lease_row.case_id != str(case.id):
                            raise ValueError("Hypothesis Run lease must belong to the Case")
                    elif lease is not None:
                        raise ValueError("Hypothesis lease requires a Run ID")

                    envelopes = [await SqlDomainEventStore.append_in_session(session, event) for event in prior_events]
                    for hypothesis in hypotheses:
                        await SqlHypothesisRepository.append_version_in_session(
                            session,
                            hypothesis,
                        )
                    await SqlCaseRepository.save_in_session(
                        session,
                        case,
                        expected_version=expected_version,
                    )
                    result_causation_id = envelopes[-1].id if envelopes else causation_event_id
                    for hypothesis in hypotheses:
                        event = NewDomainEvent(
                            workspace_id=case.workspace_id,
                            case_id=case.id,
                            run_id=run_id,
                            event_type="hypothesis.version_appended",
                            occurred_at=case.updated_at,
                            trace_id=trace_id,
                            correlation_id=correlation_id,
                            causation_event_id=result_causation_id,
                            actor=actor,
                            payload={
                                "hypothesis_id": str(hypothesis.id),
                                "hypothesis_version": hypothesis.version,
                                "status": hypothesis.status.value,
                                "confidence": hypothesis.confidence,
                                "supporting_evidence_ids": [str(value) for value in hypothesis.supporting_evidence_ids],
                                "contradicting_evidence_ids": [str(value) for value in hypothesis.contradicting_evidence_ids],
                                "case_version": case.version,
                            },
                        )
                        envelopes.append(await SqlDomainEventStore.append_in_session(session, event))
                    return tuple(envelopes)
            except IntegrityError as exc:
                last_error = exc
                await asyncio.sleep(0.001 * (attempt + 1))
        raise EventSequenceConflictError("Atomic Hypothesis batch/Case/Event mutation exceeded sequence retry budget") from last_error

    @staticmethod
    def _validate_evidence_membership(case: Case, evidence: Evidence) -> None:
        if evidence.workspace_id != case.workspace_id:
            raise ValueError("Evidence workspace must match Case workspace")
        if evidence.case_id != case.id:
            raise ValueError("Evidence Case must match the target Case")
        if evidence.id not in case.evidence_ids:
            raise ValueError("Case must include the appended Evidence ID")

    @staticmethod
    def _validate_hypothesis_membership(case: Case, hypothesis: Hypothesis) -> None:
        if hypothesis.workspace_id != case.workspace_id:
            raise ValueError("Hypothesis workspace must match Case workspace")
        if hypothesis.case_id != case.id:
            raise ValueError("Hypothesis Case must match the target Case")
        if hypothesis.id not in case.hypothesis_ids:
            raise ValueError("Case must include the appended Hypothesis ID")

    @staticmethod
    def _validate_lineage_membership(case: Case, lineage: CaseLineage) -> None:
        if lineage.workspace_id != case.workspace_id:
            raise ValueError("Case lineage workspace must match Case workspace")
        if lineage.case_id != case.id:
            raise ValueError("Case lineage Case must match target Case")
