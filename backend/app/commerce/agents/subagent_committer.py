"""Fenced persistence boundary for validated Commerce Subagent outcomes."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from uuid import NAMESPACE_URL, uuid5

from app.commerce.agents.contracts import (
    ContextManifest,
    PathEvidenceScope,
    PathType,
)
from app.commerce.agents.goal_loop import GoalLoopCheckpoint, SkillVersionRef
from app.commerce.agents.path_result import PathResult
from app.commerce.agents.subagent_adapter import (
    CommerceAgentTask,
    CommerceSubagentOutcome,
    CommerceSubagentStatus,
    CommerceSubagentToolStatus,
)
from app.commerce.domain.events import DomainEventActor, NewDomainEvent
from app.commerce.domain.ids import AgentTaskId, CheckpointId, EventId, EvidenceId
from app.commerce.domain.models import Case, CommerceModel, Evidence
from app.commerce.persistence.repositories import (
    CaseRepository,
    OptimisticConcurrencyError,
)
from app.commerce.persistence.runs import RunLeaseCredentials
from app.commerce.persistence.unit_of_work import SqlCommerceUnitOfWork
from app.commerce.persistence.work_records import EvidenceRepository


class CommerceSubagentCommitError(ValueError):
    """Raised when a validated Subagent result cannot enter Commerce state."""


class CommerceSubagentCommitReceipt(CommerceModel):
    task_id: AgentTaskId
    path_type: PathType
    status: CommerceSubagentStatus
    checkpoint_id: CheckpointId | None = None
    lifecycle_event_id: EventId | None = None
    event_ids: tuple[EventId, ...] = ()
    evidence_ids: tuple[EvidenceId, ...] = ()
    case_version: int | None = None
    idempotent: bool = False


class CommerceSubagentCommitter:
    """Commit only structured Subagent state, never model-authored prose."""

    MAX_CONCURRENCY_RETRIES = 3

    def __init__(
        self,
        *,
        uow: SqlCommerceUnitOfWork,
        cases: CaseRepository,
        evidence: EvidenceRepository,
    ) -> None:
        self._uow = uow
        self._cases = cases
        self._evidence = evidence

    async def commit_started(
        self,
        task: CommerceAgentTask,
        checkpoint: GoalLoopCheckpoint,
        *,
        lease: RunLeaseCredentials,
        checked_at: datetime,
    ) -> CommerceSubagentCommitReceipt:
        self._validate_lease_identity(task, lease)
        self._validate_checkpoint(task, checkpoint, active=True)
        event = NewDomainEvent(
            id=self._event_id(task, "path.started"),
            workspace_id=task.workspace_id,
            case_id=task.case_id,
            run_id=task.run_id,
            event_type="path.started",
            trace_id=task.trace_id,
            correlation_id=task.correlation_id,
            occurred_at=task.issued_at,
            actor=DomainEventActor.AGENT,
            payload={
                "task_id": str(task.task_id),
                "path_type": task.path_type.value,
                "context_sha256": task.context_sha256,
                "skill_id": task.skill_id,
                "skill_version": task.skill_version,
                "allowed_tools": sorted(task.allowed_tools),
            },
        )
        record, envelopes = await self._uow.append_run_checkpoint_with_events(
            checkpoint,
            prior_events=(event,),
            trace_id=task.trace_id,
            correlation_id=task.correlation_id,
            actor=DomainEventActor.AGENT,
            checkpoint_id=self._checkpoint_id(task, "pre"),
            checkpoint_event_id=self._event_id(task, "checkpoint.pre"),
            lease=lease,
            lease_checked_at=checked_at,
        )
        lifecycle = next(item for item in envelopes if item.event_type == "path.started")
        return CommerceSubagentCommitReceipt(
            task_id=task.task_id,
            path_type=task.path_type,
            status=CommerceSubagentStatus.RUNNING,
            checkpoint_id=record.id,
            lifecycle_event_id=lifecycle.id,
            event_ids=tuple(item.id for item in envelopes),
        )

    async def commit_outcome(
        self,
        task: CommerceAgentTask,
        outcome: CommerceSubagentOutcome,
        manifest: ContextManifest,
        checkpoint: GoalLoopCheckpoint,
        *,
        lease: RunLeaseCredentials,
        checked_at: datetime,
        causation_event_id: EventId | None = None,
    ) -> CommerceSubagentCommitReceipt:
        self._validate_lease_identity(task, lease)
        self._validate_outcome(task, outcome)
        self._validate_manifest(task, manifest)
        self._validate_checkpoint(task, checkpoint, active=False)
        if outcome.status in {
            CommerceSubagentStatus.PENDING,
            CommerceSubagentStatus.RUNNING,
        }:
            raise CommerceSubagentCommitError(
                "Only terminal Subagent outcomes may be committed"
            )

        if outcome.status is CommerceSubagentStatus.COMPLETED:
            assert outcome.result is not None
            return await self._commit_completed(
                task,
                outcome,
                manifest,
                checkpoint,
                lease=lease,
                checked_at=checked_at,
                causation_event_id=causation_event_id,
            )

        event_type = (
            "path.blocked"
            if outcome.status is CommerceSubagentStatus.BLOCKED
            else "path.failed"
        )
        event = NewDomainEvent(
            id=self._event_id(task, event_type),
            workspace_id=task.workspace_id,
            case_id=task.case_id,
            run_id=task.run_id,
            event_type=event_type,
            trace_id=task.trace_id,
            correlation_id=task.correlation_id,
            occurred_at=task.issued_at,
            causation_event_id=causation_event_id,
            actor=DomainEventActor.AGENT,
            payload={
                "task_id": str(task.task_id),
                "path_type": task.path_type.value,
                "status": outcome.status.value,
                "harness_trace_id": outcome.harness_trace_id,
                "error_code": outcome.error_code.value if outcome.error_code else None,
                "error_message": outcome.error_message,
                "evidence_scope": self._evidence_scope(
                    task,
                    manifest,
                    evidence_ids=(),
                ).model_dump(mode="json"),
            },
        )
        tool_events = self._tool_domain_events(
            task,
            outcome,
            causation_event_id=causation_event_id,
        )
        record, envelopes = await self._uow.append_run_checkpoint_with_events(
            checkpoint,
            prior_events=(*tool_events, event),
            trace_id=task.trace_id,
            correlation_id=task.correlation_id,
            actor=DomainEventActor.AGENT,
            checkpoint_id=self._checkpoint_id(task, "post"),
            checkpoint_event_id=self._event_id(task, "checkpoint.post"),
            lease=lease,
            lease_checked_at=checked_at,
        )
        lifecycle = next(item for item in envelopes if item.event_type == event_type)
        case = await self._require_case(task)
        return CommerceSubagentCommitReceipt(
            task_id=task.task_id,
            path_type=task.path_type,
            status=outcome.status,
            checkpoint_id=record.id,
            lifecycle_event_id=lifecycle.id,
            event_ids=tuple(item.id for item in envelopes),
            case_version=case.version,
        )

    async def _commit_completed(
        self,
        task: CommerceAgentTask,
        outcome: CommerceSubagentOutcome,
        manifest: ContextManifest,
        checkpoint: GoalLoopCheckpoint,
        *,
        lease: RunLeaseCredentials,
        checked_at: datetime,
        causation_event_id: EventId | None,
    ) -> CommerceSubagentCommitReceipt:
        assert outcome.result is not None
        evidences = self._evidence_records(task, outcome.result, manifest)
        evidence_ids = tuple(item.id for item in evidences)
        for attempt in range(self.MAX_CONCURRENCY_RETRIES):
            case = await self._require_case(task)
            existing_ids = set(case.evidence_ids) & set(evidence_ids)
            if existing_ids:
                if existing_ids != set(evidence_ids):
                    raise CommerceSubagentCommitError(
                        "Some Path Evidence IDs already exist while others are new"
                    )
                for evidence in evidences:
                    stored = await self._evidence.get(task.workspace_id, evidence.id)
                    if stored != evidence:
                        raise CommerceSubagentCommitError(
                            "Existing Evidence ID has different immutable content"
                        )
                return CommerceSubagentCommitReceipt(
                    task_id=task.task_id,
                    path_type=task.path_type,
                    status=CommerceSubagentStatus.COMPLETED,
                    evidence_ids=evidence_ids,
                    case_version=case.version,
                    idempotent=True,
                )

            if not evidences:
                return await self._commit_completed_without_evidence(
                    task,
                    outcome,
                    manifest,
                    checkpoint,
                    case,
                    lease=lease,
                    checked_at=checked_at,
                    causation_event_id=causation_event_id,
                )

            updated_case = case.model_copy(
                update={
                    "evidence_ids": (*case.evidence_ids, *evidence_ids),
                    "updated_at": max(checked_at, case.updated_at),
                    "version": case.version + 1,
                }
            )
            completed_event = self._completed_event(
                task,
                outcome,
                evidence_ids,
                manifest,
                causation_event_id,
            )
            post_checkpoint = checkpoint.model_copy(
                update={"evidence_ids": updated_case.evidence_ids}
            )
            tool_events = self._tool_domain_events(
                task,
                outcome,
                causation_event_id=causation_event_id,
            )
            try:
                record, envelopes = (
                    await self._uow.append_evidence_batch_with_checkpoint_events(
                        updated_case,
                        evidences,
                        post_checkpoint,
                        expected_version=case.version,
                        prior_events=(*tool_events, completed_event),
                        trace_id=task.trace_id,
                        correlation_id=task.correlation_id,
                        actor=DomainEventActor.AGENT,
                        causation_event_id=causation_event_id,
                        checkpoint_id=self._checkpoint_id(task, "post"),
                        checkpoint_event_id=self._event_id(
                            task, "checkpoint.post"
                        ),
                        lease=lease,
                        lease_checked_at=checked_at,
                    )
                )
            except OptimisticConcurrencyError:
                if attempt + 1 >= self.MAX_CONCURRENCY_RETRIES:
                    raise
                continue

            lifecycle = next(item for item in envelopes if item.event_type == "path.completed")
            return CommerceSubagentCommitReceipt(
                task_id=task.task_id,
                path_type=task.path_type,
                status=CommerceSubagentStatus.COMPLETED,
                checkpoint_id=record.id,
                lifecycle_event_id=lifecycle.id,
                event_ids=tuple(item.id for item in envelopes),
                evidence_ids=evidence_ids,
                case_version=updated_case.version,
            )
        raise AssertionError("unreachable concurrency retry state")

    async def _commit_completed_without_evidence(
        self,
        task: CommerceAgentTask,
        outcome: CommerceSubagentOutcome,
        manifest: ContextManifest,
        checkpoint: GoalLoopCheckpoint,
        case: Case,
        *,
        lease: RunLeaseCredentials,
        checked_at: datetime,
        causation_event_id: EventId | None,
    ) -> CommerceSubagentCommitReceipt:
        event = self._completed_event(
            task,
            outcome,
            (),
            manifest,
            causation_event_id,
        )
        tool_events = self._tool_domain_events(
            task,
            outcome,
            causation_event_id=causation_event_id,
        )
        record, envelopes = await self._uow.append_run_checkpoint_with_events(
            checkpoint,
            prior_events=(*tool_events, event),
            trace_id=task.trace_id,
            correlation_id=task.correlation_id,
            actor=DomainEventActor.AGENT,
            checkpoint_id=self._checkpoint_id(task, "post"),
            checkpoint_event_id=self._event_id(task, "checkpoint.post"),
            lease=lease,
            lease_checked_at=checked_at,
        )
        lifecycle = next(item for item in envelopes if item.event_type == "path.completed")
        return CommerceSubagentCommitReceipt(
            task_id=task.task_id,
            path_type=task.path_type,
            status=CommerceSubagentStatus.COMPLETED,
            checkpoint_id=record.id,
            lifecycle_event_id=lifecycle.id,
            event_ids=tuple(item.id for item in envelopes),
            case_version=case.version,
        )

    @staticmethod
    def _completed_event(
        task: CommerceAgentTask,
        outcome: CommerceSubagentOutcome,
        evidence_ids: tuple[EvidenceId, ...],
        manifest: ContextManifest,
        causation_event_id: EventId | None,
    ) -> NewDomainEvent:
        assert outcome.result is not None
        result = outcome.result
        return NewDomainEvent(
            id=CommerceSubagentCommitter._event_id(task, "path.completed"),
            workspace_id=task.workspace_id,
            case_id=task.case_id,
            run_id=task.run_id,
            event_type="path.completed",
            trace_id=task.trace_id,
            correlation_id=task.correlation_id,
            occurred_at=task.issued_at,
            causation_event_id=causation_event_id,
            actor=DomainEventActor.AGENT,
            payload={
                "task_id": str(task.task_id),
                "path_type": task.path_type.value,
                "path_result_sha256": outcome.result_sha256,
                "evidence_ids": [str(item) for item in evidence_ids],
                "provider_request_id": result.model_execution.provider_request_id,
                "provider_request_ids": list(
                    result.model_execution.provider_request_ids
                    or (result.model_execution.provider_request_id,)
                ),
                "actual_model_identity": result.model_execution.actual_model_identity,
                "input_tokens": result.cost.input_tokens,
                "output_tokens": result.cost.output_tokens,
                "total_tokens": result.cost.input_tokens + result.cost.output_tokens,
                "latency_ms": result.cost.latency_ms,
                "tool_call_count": (
                    len(outcome.tool_events)
                    if outcome.tool_events
                    else result.cost.tool_call_count
                ),
                "evidence_scope": CommerceSubagentCommitter._evidence_scope(
                    task,
                    manifest,
                    evidence_ids=evidence_ids,
                ).model_dump(mode="json"),
            },
        )

    @staticmethod
    def _evidence_scope(
        task: CommerceAgentTask,
        manifest: ContextManifest,
        *,
        evidence_ids: tuple[EvidenceId, ...],
    ) -> PathEvidenceScope:
        return PathEvidenceScope.from_manifest(
            manifest,
            run_id=task.run_id,
            task_id=task.task_id,
            path_type=task.path_type,
            evidence_ids=evidence_ids,
        )

    @staticmethod
    def _tool_domain_events(
        task: CommerceAgentTask,
        outcome: CommerceSubagentOutcome,
        *,
        causation_event_id: EventId | None,
    ) -> tuple[NewDomainEvent, ...]:
        return tuple(
            NewDomainEvent(
                id=CommerceSubagentCommitter._event_id(
                    task,
                    f"tool.{event.tool_call_id}.{event.status.value}",
                ),
                workspace_id=task.workspace_id,
                case_id=task.case_id,
                run_id=task.run_id,
                event_type=(
                    "tool.completed"
                    if event.status is CommerceSubagentToolStatus.SUCCEEDED
                    else "tool.failed"
                ),
            trace_id=task.trace_id,
            correlation_id=task.correlation_id,
            occurred_at=task.issued_at,
            causation_event_id=causation_event_id,
                actor=DomainEventActor.AGENT,
                payload={
                    "task_id": str(task.task_id),
                    "path_type": task.path_type.value,
                    "tool_call_id": event.tool_call_id,
                    "tool_name": event.tool_name,
                    "status": event.status.value,
                    "request_sha256": event.request_sha256,
                    "response_sha256": event.response_sha256,
                    "latency_ms": event.latency_ms,
                    "error_code": event.error_code,
                },
            )
            for event in outcome.tool_events
        )

    @staticmethod
    def _evidence_records(
        task: CommerceAgentTask,
        result: PathResult,
        manifest: ContextManifest,
    ) -> tuple[Evidence, ...]:
        allowed_facts = set(manifest.included_fact_ids)
        allowed_metrics = set(manifest.included_metric_observation_ids)
        records: list[Evidence] = []
        for item in result.evidence:
            if not set(item.fact_ids).issubset(allowed_facts) or not set(
                item.metric_observation_ids
            ).issubset(allowed_metrics):
                raise CommerceSubagentCommitError(
                    "Path Evidence references IDs outside ContextManifest"
                )
            records.append(
                Evidence(
                    id=item.evidence_id,
                    workspace_id=task.workspace_id,
                    case_id=task.case_id,
                    summary=item.summary,
                    relation=item.relation,
                    semantic_status=item.semantic_status,
                    confidence=item.confidence,
                    fact_ids=item.fact_ids,
                    metric_observation_ids=item.metric_observation_ids,
                )
            )
        return tuple(records)

    async def _require_case(self, task: CommerceAgentTask) -> Case:
        case = await self._cases.get(task.workspace_id, task.case_id)
        if case is None:
            raise CommerceSubagentCommitError(f"Case not found: {task.case_id}")
        return case

    @staticmethod
    def _validate_lease_identity(
        task: CommerceAgentTask,
        lease: RunLeaseCredentials,
    ) -> None:
        if lease.worker_id != task.lease_worker_id:
            raise CommerceSubagentCommitError(
                "Lease worker does not match Commerce AgentTask"
            )
        if lease.fencing_token != task.fencing_token:
            raise CommerceSubagentCommitError(
                "Lease fencing token does not match Commerce AgentTask"
            )

    @staticmethod
    def _validate_outcome(
        task: CommerceAgentTask,
        outcome: CommerceSubagentOutcome,
    ) -> None:
        if outcome.task_id != task.task_id:
            raise CommerceSubagentCommitError(
                "Outcome task does not match Commerce AgentTask"
            )
        if outcome.path_type is not task.path_type:
            raise CommerceSubagentCommitError(
                "Outcome PathType does not match Commerce AgentTask"
            )
        tool_call_ids = tuple(event.tool_call_id for event in outcome.tool_events)
        if len(set(tool_call_ids)) != len(tool_call_ids):
            raise CommerceSubagentCommitError(
                "Outcome Tool event IDs must be unique"
            )
        if any(event.tool_name not in task.allowed_tools for event in outcome.tool_events):
            raise CommerceSubagentCommitError(
                "Outcome Tool event is outside the task allowlist"
            )
        if outcome.status is CommerceSubagentStatus.COMPLETED:
            if outcome.result is None:
                raise CommerceSubagentCommitError(
                    "Completed outcome is missing PathResult"
                )
            result = outcome.result
            if result.trace_id != task.trace_id:
                raise CommerceSubagentCommitError(
                    "Completed outcome trace does not match Commerce AgentTask"
                )
            if result.path_type is not task.path_type:
                raise CommerceSubagentCommitError(
                    "PathResult PathType does not match Commerce AgentTask"
                )
            if result.context_sha256 != task.context_sha256:
                raise CommerceSubagentCommitError(
                    "PathResult context does not match Commerce AgentTask"
                )
            if result.model_assignment != task.model_assignment:
                raise CommerceSubagentCommitError(
                    "PathResult ModelAssignment does not match Commerce AgentTask"
                )
            if result.skill_version != f"{task.skill_id}@{task.skill_version}":
                raise CommerceSubagentCommitError(
                    "PathResult SkillVersion does not match Commerce AgentTask"
                )
            if result.schema_version != task.expected_result_schema:
                raise CommerceSubagentCommitError(
                    "PathResult schema does not match Commerce AgentTask"
                )
            unauthorized = {
                call.tool_name
                for call in result.tool_calls
                if call.tool_name not in task.allowed_tools
            }
            if unauthorized:
                raise CommerceSubagentCommitError(
                    "PathResult contains Tool calls outside the task allowlist"
                )
            canonical_result = json.dumps(
                result.model_dump(mode="json"),
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            actual_sha256 = hashlib.sha256(canonical_result).hexdigest()
            if actual_sha256 != outcome.result_sha256:
                raise CommerceSubagentCommitError(
                    "PathResult hash does not match CommerceSubagentOutcome"
                )

    @staticmethod
    def _validate_manifest(
        task: CommerceAgentTask,
        manifest: ContextManifest,
    ) -> None:
        if (
            manifest.workspace_id != task.workspace_id
            or manifest.case_id != task.case_id
            or manifest.context_sha256 != task.context_sha256
        ):
            raise CommerceSubagentCommitError(
                "ContextManifest does not match Commerce AgentTask"
            )

    @staticmethod
    def _validate_checkpoint(
        task: CommerceAgentTask,
        checkpoint: GoalLoopCheckpoint,
        *,
        active: bool,
    ) -> None:
        if (
            checkpoint.workspace_id != task.workspace_id
            or checkpoint.case_id != task.case_id
            or checkpoint.run_id != task.run_id
            or checkpoint.context_sha256 != task.context_sha256
        ):
            raise CommerceSubagentCommitError(
                "Checkpoint does not match Commerce AgentTask"
            )
        if (task.task_id in checkpoint.active_path_task_ids) is not active:
            raise CommerceSubagentCommitError(
                "Checkpoint active Path task membership is inconsistent"
            )
        if task.model_assignment not in checkpoint.model_assignments:
            raise CommerceSubagentCommitError(
                "Checkpoint is missing the Path ModelAssignment"
            )
        skill = SkillVersionRef(skill_id=task.skill_id, version=task.skill_version)
        if skill not in checkpoint.skill_versions:
            raise CommerceSubagentCommitError(
                "Checkpoint is missing the Path SkillVersion"
            )

    @staticmethod
    def _checkpoint_id(task: CommerceAgentTask, phase: str) -> CheckpointId:
        # The identifier is stable across retries for one Task and phase.
        return CheckpointId(
            f"chkpt_{uuid5(NAMESPACE_URL, f'{task.task_id}:{phase}').hex}"
        )

    @staticmethod
    def _event_id(task: CommerceAgentTask, kind: str) -> EventId:
        return EventId(
            f"evt_{uuid5(NAMESPACE_URL, f'{task.task_id}:{kind}').hex}"
        )
