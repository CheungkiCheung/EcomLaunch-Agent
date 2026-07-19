"""Fenced Commerce Worker step that durably executes the first Path Agent."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.commerce.agents.budget import BudgetDelta, BudgetManager, BudgetSnapshot
from app.commerce.agents.context_loader import ContextPacketLoader
from app.commerce.agents.contracts import AgentBudgetLimit, PathType
from app.commerce.agents.fulfillment import (
    FulfillmentPathAgent,
    FulfillmentPathRun,
)
from app.commerce.agents.goal_loop import (
    GoalLoopCheckpoint,
    GoalLoopState,
    SkillVersionRef,
)
from app.commerce.agents.model_router import build_model_assignment_event
from app.commerce.api.data_service import CommerceDataService
from app.commerce.domain.enums import RunPhase, RunStatus
from app.commerce.domain.events import (
    DomainEventActor,
    DomainEventEnvelope,
    NewDomainEvent,
)
from app.commerce.domain.ids import (
    AgentTaskId,
    CheckpointId,
    CorrelationId,
    EventId,
    RunId,
    TraceId,
    WorkspaceId,
)
from app.commerce.domain.models import Case, CommerceModel, Evidence
from app.commerce.domain.runs import CommerceRun
from app.commerce.persistence.repositories import SqlCaseRepository
from app.commerce.persistence.runs import (
    RunCheckpointRecord,
    RunLeaseCredentials,
    SqlRunLeaseRepository,
    SqlRunRepository,
)
from app.commerce.persistence.unit_of_work import SqlCommerceUnitOfWork


class FulfillmentWorkerStepResult(CommerceModel):
    run: CommerceRun
    lease: RunLeaseCredentials
    task_id: AgentTaskId
    pre_call_checkpoint: RunCheckpointRecord
    post_call_checkpoint: RunCheckpointRecord
    evidence: tuple[Evidence, ...]
    path_run: FulfillmentPathRun
    events: tuple[DomainEventEnvelope, ...]


class CommerceInvestigationWorker:
    """Execute one durable Fulfillment Path step under a current fencing token."""

    def __init__(
        self,
        *,
        data_service: CommerceDataService,
        session_factory: async_sessionmaker[AsyncSession],
        fulfillment_agent: FulfillmentPathAgent | None = None,
        lease_ttl: timedelta = timedelta(minutes=5),
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if lease_ttl.total_seconds() <= 0:
            raise ValueError("Worker lease TTL must be positive")
        self._data = data_service
        self._session_factory = session_factory
        self._agent = fulfillment_agent or FulfillmentPathAgent()
        self._leases = SqlRunLeaseRepository(session_factory)
        self._runs = SqlRunRepository(session_factory)
        self._cases = SqlCaseRepository(session_factory)
        self._uow = SqlCommerceUnitOfWork(session_factory)
        self._lease_ttl = lease_ttl
        self._clock = clock or (lambda: datetime.now(UTC))

    async def execute_fulfillment_step(
        self,
        workspace_id: WorkspaceId,
        run_id: RunId,
        *,
        worker_id: str,
        budget: AgentBudgetLimit,
    ) -> FulfillmentWorkerStepResult:
        trace_id = TraceId.new()
        correlation_id = CorrelationId.new()
        acquired_at = self._clock()
        grant = await self._leases.acquire(
            workspace_id,
            run_id,
            worker_id=worker_id,
            ttl=self._lease_ttl,
            acquired_at=acquired_at,
            trace_id=trace_id,
            correlation_id=correlation_id,
        )
        if grant.latest_checkpoint is not None:
            raise RuntimeError(
                "Fulfillment Worker resume is not implemented for an existing Checkpoint"
            )

        investigating = grant.run.advance_phase(
            RunPhase.INVESTIGATING,
            occurred_at=self._checked_time(grant.run.updated_at),
        )
        phase_event = await self._uow.save_run(
            investigating,
            expected_version=grant.run.version,
            trace_id=trace_id,
            correlation_id=correlation_id,
            actor=DomainEventActor.AGENT,
            lease=grant.credentials,
            lease_checked_at=self._checked_time(acquired_at),
        )
        initial = await ContextPacketLoader(
            data_service=self._data,
            session_factory=self._session_factory,
        ).load_initial(
            workspace_id,
            run_id,
            budget=budget,
        )
        plan = await self._agent.prepare(initial.packet)
        task_id = AgentTaskId(
            f"task_{uuid5(NAMESPACE_URL, f'{run_id}:fulfillment').hex}"
        )
        skill_ref = SkillVersionRef(
            skill_id="commerce.fulfillment-investigation",
            version="1.0.0",
        )
        planned_state = initial.state.model_copy(
            update={
                "active_path_task_ids": (task_id,),
                "model_assignments": (plan.assignment,),
                "skill_versions": (skill_ref,),
                "context_sha256": plan.context.manifest.context_sha256,
            }
        )
        planned_checkpoint = self._checkpoint(
            planned_state,
            initial.checkpoint.budget_snapshot,
        )
        assigned_event = build_model_assignment_event(
            plan.assignment,
            workspace_id=workspace_id,
            case_id=investigating.case_id,
            run_id=run_id,
            trace_id=trace_id,
            correlation_id=correlation_id,
        )
        started_event = NewDomainEvent(
            workspace_id=workspace_id,
            case_id=investigating.case_id,
            run_id=run_id,
            event_type="path.started",
            trace_id=trace_id,
            correlation_id=correlation_id,
            actor=DomainEventActor.AGENT,
            payload={
                "task_id": str(task_id),
                "path_type": PathType.FULFILLMENT.value,
                "context_sha256": plan.context.manifest.context_sha256,
                "skill_id": skill_ref.skill_id,
                "skill_version": skill_ref.version,
                "allowed_tools": sorted(plan.context.allowed_tools),
                "expected_tool_calls": 0,
            },
        )
        pre_record, pre_events = await self._uow.append_run_checkpoint_with_events(
            planned_checkpoint,
            prior_events=(assigned_event, started_event),
            trace_id=trace_id,
            correlation_id=correlation_id,
            actor=DomainEventActor.AGENT,
            checkpoint_id=self._checkpoint_id(run_id, "pre-fulfillment"),
            lease=grant.credentials,
            lease_checked_at=self._checked_time(acquired_at),
        )

        await self._leases.heartbeat(
            workspace_id,
            run_id,
            grant.credentials,
            ttl=self._lease_ttl,
            heartbeat_at=self._checked_time(acquired_at),
        )
        path_run = await self._agent.run_prepared(plan)
        post_model_time = self._clock()
        await self._leases.heartbeat(
            workspace_id,
            run_id,
            grant.credentials,
            ttl=self._lease_ttl,
            heartbeat_at=post_model_time,
        )

        manager = BudgetManager(budget)
        token_usage = path_run.telemetry.token_usage
        assert token_usage is not None
        await manager.consume(
            BudgetDelta(
                path_agents=1,
                tokens=token_usage.total_tokens,
                wall_time_seconds=path_run.telemetry.latency_ms / 1000,
            )
        )
        await manager.record_iteration(has_new_evidence=bool(path_run.result.evidence))

        case = await self._cases.get(workspace_id, investigating.case_id)
        if case is None:
            raise RuntimeError(f"Case disappeared during Worker execution: {investigating.case_id}")
        evidence, evidence_events, current_case = await self._persist_evidence(
            case,
            path_run,
            run_id=run_id,
            trace_id=trace_id,
            correlation_id=correlation_id,
            lease=grant.credentials,
            checked_at=post_model_time,
            causation_event_id=pre_events[1].id,
        )

        completed_state = GoalLoopState(
            workspace_id=workspace_id,
            run_id=run_id,
            case_id=investigating.case_id,
            goal=investigating.goal,
            loop_iteration=manager.snapshot.usage.iterations,
            evidence_ids=current_case.evidence_ids,
            hypothesis_ids=planned_state.hypothesis_ids,
            active_path_task_ids=(),
            model_assignments=planned_state.model_assignments,
            skill_versions=planned_state.skill_versions,
            context_sha256=planned_state.context_sha256,
            tool_state=(),
            resume_token_sha256=planned_state.resume_token_sha256,
        )
        completed_checkpoint = self._checkpoint(
            completed_state,
            manager.snapshot,
        )
        completed_event = NewDomainEvent(
            workspace_id=workspace_id,
            case_id=investigating.case_id,
            run_id=run_id,
            event_type="path.completed",
            trace_id=trace_id,
            correlation_id=correlation_id,
            causation_event_id=pre_events[1].id,
            actor=DomainEventActor.AGENT,
            payload={
                "task_id": str(task_id),
                "path_type": PathType.FULFILLMENT.value,
                "path_result_sha256": path_run.telemetry.path_result_sha256,
                "evidence_ids": [str(item.id) for item in evidence],
                "provider_request_id": path_run.telemetry.provider_request_id,
                "actual_model_identity": path_run.telemetry.actual_model_identity,
                "input_tokens": token_usage.input_tokens,
                "output_tokens": token_usage.output_tokens,
                "total_tokens": token_usage.total_tokens,
                "latency_ms": path_run.telemetry.latency_ms,
                "tool_call_count": path_run.result.cost.tool_call_count,
            },
        )
        post_record, post_events = (
            await self._uow.append_run_checkpoint_with_events(
                completed_checkpoint,
                prior_events=(completed_event,),
                trace_id=trace_id,
                correlation_id=correlation_id,
                actor=DomainEventActor.AGENT,
                checkpoint_id=self._checkpoint_id(run_id, "post-fulfillment"),
                lease=grant.credentials,
                lease_checked_at=self._checked_time(post_model_time),
            )
        )
        persisted_run = await self._runs.get(workspace_id, run_id)
        if persisted_run is None or persisted_run.status is not RunStatus.RUNNING:
            raise RuntimeError("Fulfillment Worker lost its running Run projection")
        return FulfillmentWorkerStepResult(
            run=persisted_run,
            lease=grant.credentials,
            task_id=task_id,
            pre_call_checkpoint=pre_record,
            post_call_checkpoint=post_record,
            evidence=evidence,
            path_run=path_run,
            events=(
                phase_event,
                *pre_events,
                *evidence_events,
                *post_events,
            ),
        )

    async def _persist_evidence(
        self,
        case: Case,
        path_run: FulfillmentPathRun,
        *,
        run_id: RunId,
        trace_id: TraceId,
        correlation_id: CorrelationId,
        lease: RunLeaseCredentials,
        checked_at: datetime,
        causation_event_id: EventId,
    ) -> tuple[tuple[Evidence, ...], tuple[DomainEventEnvelope, ...], Case]:
        current = case
        evidence_records: list[Evidence] = []
        events: list[DomainEventEnvelope] = []
        for candidate in path_run.result.evidence:
            evidence = Evidence(
                id=candidate.evidence_id,
                workspace_id=case.workspace_id,
                case_id=case.id,
                summary=candidate.summary,
                relation=candidate.relation,
                semantic_status=candidate.semantic_status,
                confidence=candidate.confidence,
                fact_ids=candidate.fact_ids,
                metric_observation_ids=candidate.metric_observation_ids,
            )
            updated = current.model_copy(
                update={
                    "evidence_ids": (*current.evidence_ids, evidence.id),
                    "updated_at": max(checked_at, current.updated_at),
                    "version": current.version + 1,
                }
            )
            event = await self._uow.append_evidence(
                updated,
                evidence,
                expected_version=current.version,
                trace_id=trace_id,
                correlation_id=correlation_id,
                actor=DomainEventActor.AGENT,
                causation_event_id=causation_event_id,
                run_id=run_id,
                lease=lease,
                lease_checked_at=self._checked_time(checked_at),
            )
            evidence_records.append(evidence)
            events.append(event)
            current = updated
        return tuple(evidence_records), tuple(events), current

    @staticmethod
    def _checkpoint(
        state: GoalLoopState,
        budget_snapshot: BudgetSnapshot,
    ) -> GoalLoopCheckpoint:
        return GoalLoopCheckpoint(
            workspace_id=state.workspace_id,
            run_id=state.run_id,
            case_id=state.case_id,
            goal=state.goal,
            loop_iteration=state.loop_iteration,
            budget_snapshot=budget_snapshot,
            evidence_ids=state.evidence_ids,
            hypothesis_ids=state.hypothesis_ids,
            active_path_task_ids=state.active_path_task_ids,
            model_assignments=state.model_assignments,
            skill_versions=state.skill_versions,
            context_sha256=state.context_sha256,
            tool_state=state.tool_state,
            resume_token_sha256=state.resume_token_sha256,
        )

    @staticmethod
    def _checkpoint_id(run_id: RunId, stage: str) -> CheckpointId:
        return CheckpointId(
            f"chkpt_{uuid5(NAMESPACE_URL, f'{run_id}:{stage}').hex}"
        )

    def _checked_time(self, lower_bound: datetime) -> datetime:
        return max(self._clock(), lower_bound)
