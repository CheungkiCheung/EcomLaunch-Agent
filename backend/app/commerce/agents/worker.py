"""Fenced Commerce Worker steps for the first durable diagnosis Loop."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.commerce.agents.budget import (
    BudgetDelta,
    BudgetExceededError,
    BudgetManager,
    BudgetSnapshot,
)
from app.commerce.agents.context_loader import ContextPacketLoader
from app.commerce.agents.contracts import (
    AgentBudgetLimit,
    PathType,
)
from app.commerce.agents.fulfillment import (
    FulfillmentPathAgent,
    FulfillmentPathRun,
)
from app.commerce.agents.goal_loop import (
    GoalLoopCheckpoint,
    GoalLoopController,
    GoalLoopDecision,
    GoalLoopOutcome,
    GoalLoopState,
    SkillVersionRef,
    build_goal_loop_decision_event,
)
from app.commerce.agents.lead import (
    LeadSynthesisAgent,
    LeadSynthesisRun,
    build_path_scoped_lead_context,
)
from app.commerce.agents.model_router import build_model_assignment_event
from app.commerce.agents.resume import ResumePlan, RunResumeClassifier
from app.commerce.agents.synthesis import (
    project_proposed_hypotheses,
    project_verified_hypotheses,
    verification_goal_progress,
)
from app.commerce.agents.verification import (
    ClaimVerdict,
    VerificationEngine,
    VerificationRun,
)
from app.commerce.agents.verified_call import VerifiedCallTelemetry
from app.commerce.api.data_service import CommerceDataService
from app.commerce.domain.enums import RunPhase, RunStatus
from app.commerce.domain.events import (
    DomainEventActor,
    DomainEventEnvelope,
    NewDomainEvent,
)
from app.commerce.domain.ids import (
    AgentTaskId,
    CaseId,
    CheckpointId,
    CorrelationId,
    EventId,
    RunId,
    TraceId,
    WorkspaceId,
)
from app.commerce.domain.models import Case, CommerceModel, Evidence, Hypothesis
from app.commerce.domain.runs import CommerceRun
from app.commerce.persistence.events import SqlDomainEventStore
from app.commerce.persistence.repositories import SqlCaseRepository
from app.commerce.persistence.runs import (
    RunCheckpointRecord,
    RunLeaseCredentials,
    SqlRunCheckpointRepository,
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


class FulfillmentCaseLoopResult(CommerceModel):
    run: CommerceRun
    path_step: FulfillmentWorkerStepResult
    lead_pre_call_checkpoint: RunCheckpointRecord
    verification_pre_call_checkpoint: RunCheckpointRecord
    final_checkpoint: RunCheckpointRecord
    lead_run: LeadSynthesisRun
    verification_run: VerificationRun
    proposed_hypotheses: tuple[Hypothesis, ...]
    verified_hypotheses: tuple[Hypothesis, ...]
    decision: GoalLoopDecision
    events: tuple[DomainEventEnvelope, ...]


class CommerceInvestigationWorker:
    """Execute one durable Fulfillment Path step under a current fencing token."""

    def __init__(
        self,
        *,
        data_service: CommerceDataService,
        session_factory: async_sessionmaker[AsyncSession],
        fulfillment_agent: FulfillmentPathAgent | None = None,
        lead_agent: LeadSynthesisAgent | None = None,
        verification_engine: VerificationEngine | None = None,
        lease_ttl: timedelta = timedelta(minutes=5),
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if lease_ttl.total_seconds() <= 0:
            raise ValueError("Worker lease TTL must be positive")
        self._data = data_service
        self._session_factory = session_factory
        self._agent = fulfillment_agent or FulfillmentPathAgent()
        self._lead = lead_agent or LeadSynthesisAgent()
        self._verification = verification_engine or VerificationEngine()
        self._leases = SqlRunLeaseRepository(session_factory)
        self._checkpoints = SqlRunCheckpointRepository(session_factory)
        self._events = SqlDomainEventStore(session_factory)
        self._runs = SqlRunRepository(session_factory)
        self._cases = SqlCaseRepository(session_factory)
        self._uow = SqlCommerceUnitOfWork(session_factory)
        self._lease_ttl = lease_ttl
        self._clock = clock or (lambda: datetime.now(UTC))

    async def execute_fulfillment_case_loop(
        self,
        workspace_id: WorkspaceId,
        run_id: RunId,
        *,
        worker_id: str,
        budget: AgentBudgetLimit,
    ) -> FulfillmentCaseLoopResult:
        """Execute Path → Lead → fresh Verification under one fenced owner."""

        path_step = await self.execute_fulfillment_step(
            workspace_id,
            run_id,
            worker_id=worker_id,
            budget=budget,
        )
        return await self._execute_lead_verification(
            workspace_id,
            path_step,
        )

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
            resume = await self.plan_resume(workspace_id, run_id)
            raise RuntimeError(
                "Fulfillment Worker automatic retry is blocked for existing "
                f"Checkpoint: {resume.disposition.value}"
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

    async def plan_resume(
        self,
        workspace_id: WorkspaceId,
        run_id: RunId,
    ) -> ResumePlan:
        latest = await self._checkpoints.get_latest(workspace_id, run_id)
        events = await self._events.list_run(workspace_id, run_id)
        return RunResumeClassifier().classify(
            latest_checkpoint=latest,
            run_events=events,
        )

    async def _execute_lead_verification(
        self,
        workspace_id: WorkspaceId,
        path_step: FulfillmentWorkerStepResult,
    ) -> FulfillmentCaseLoopResult:
        run_id = path_step.run.id
        trace_id = TraceId.new()
        correlation_id = CorrelationId.new()
        lease = path_step.lease
        path_checkpoint = path_step.post_call_checkpoint.checkpoint
        manager = BudgetManager(
            path_checkpoint.budget_snapshot.limit,
            initial_usage=path_checkpoint.budget_snapshot.usage,
        )
        state = self._state_from_checkpoint(path_checkpoint)

        synthesis_time = self._checked_time(path_step.run.updated_at)
        synthesizing = path_step.run.advance_phase(
            RunPhase.SYNTHESIZING,
            occurred_at=synthesis_time,
        )
        synthesizing_event = await self._uow.save_run(
            synthesizing,
            expected_version=path_step.run.version,
            trace_id=trace_id,
            correlation_id=correlation_id,
            actor=DomainEventActor.AGENT,
            lease=lease,
            lease_checked_at=synthesis_time,
        )

        lead_context = await ContextPacketLoader(
            data_service=self._data,
            session_factory=self._session_factory,
        ).load_case_packet(
            workspace_id,
            synthesizing.case_id,
            goal=synthesizing.goal,
            budget=path_checkpoint.budget_snapshot.limit,
        )
        lead_context = build_path_scoped_lead_context(
            lead_context,
            path_step.path_run.context,
            evidence_ids=frozenset(item.id for item in path_step.evidence),
        )
        lead_plan = await self._lead.prepare(lead_context, budget=manager)
        lead_task_id = self._task_id(run_id, "lead-synthesis")
        lead_skill = SkillVersionRef(
            skill_id="commerce.lead-synthesis",
            version="1.0.0",
        )
        lead_state = state.model_copy(
            update={
                "active_path_task_ids": (lead_task_id,),
                "model_assignments": (
                    *state.model_assignments,
                    lead_plan.assignment,
                ),
                "skill_versions": (*state.skill_versions, lead_skill),
                "context_sha256": lead_context.manifest.context_sha256,
            }
        )
        lead_started = NewDomainEvent(
            workspace_id=workspace_id,
            case_id=synthesizing.case_id,
            run_id=run_id,
            event_type="lead.started",
            trace_id=trace_id,
            correlation_id=correlation_id,
            actor=DomainEventActor.AGENT,
            payload={
                "task_id": str(lead_task_id),
                "context_sha256": lead_context.manifest.context_sha256,
                "skill_id": lead_skill.skill_id,
                "skill_version": lead_skill.version,
                "claim_source": "persisted_case_evidence",
            },
        )
        lead_pre_record, lead_pre_events = (
            await self._uow.append_run_checkpoint_with_events(
                self._checkpoint(lead_state, manager.snapshot),
                prior_events=(
                    build_model_assignment_event(
                        lead_plan.assignment,
                        workspace_id=workspace_id,
                        case_id=synthesizing.case_id,
                        run_id=run_id,
                        trace_id=trace_id,
                        correlation_id=correlation_id,
                    ),
                    lead_started,
                ),
                trace_id=trace_id,
                correlation_id=correlation_id,
                actor=DomainEventActor.AGENT,
                checkpoint_id=self._checkpoint_id(run_id, "pre-lead"),
                lease=lease,
                lease_checked_at=synthesis_time,
            )
        )
        await self._leases.heartbeat(
            workspace_id,
            run_id,
            lease,
            ttl=self._lease_ttl,
            heartbeat_at=self._checked_time(synthesis_time),
        )
        lead_run = await self._lead.run_prepared(lead_plan)
        post_lead_time = self._clock()
        await self._leases.heartbeat(
            workspace_id,
            run_id,
            lease,
            ttl=self._lease_ttl,
            heartbeat_at=post_lead_time,
        )
        lead_tokens = lead_run.telemetry.token_usage
        assert lead_tokens is not None
        await manager.consume(
            BudgetDelta(
                tokens=lead_tokens.total_tokens,
                wall_time_seconds=lead_run.telemetry.latency_ms / 1000,
            )
        )

        proposed = project_proposed_hypotheses(
            workspace_id=workspace_id,
            case_id=synthesizing.case_id,
            lead=lead_run.result,
        )
        current_case = await self._require_case(workspace_id, synthesizing.case_id)
        proposed_case = self._case_with_hypotheses(
            current_case,
            proposed,
            occurred_at=post_lead_time,
            add_membership=True,
        )
        lead_completed = NewDomainEvent(
            workspace_id=workspace_id,
            case_id=synthesizing.case_id,
            run_id=run_id,
            event_type="lead.completed",
            trace_id=trace_id,
            correlation_id=correlation_id,
            causation_event_id=lead_pre_events[1].id,
            actor=DomainEventActor.AGENT,
            payload={
                "task_id": str(lead_task_id),
                "result_sha256": lead_run.result_sha256,
                "context_sha256": lead_run.result.context_sha256,
                "claim_count": len(lead_run.result.claims),
                "unknown_count": len(lead_run.result.unknowns),
                "suggested_next_paths": [
                    item.value for item in lead_run.result.suggested_next_paths
                ],
                **self._model_completion_payload(lead_run.telemetry),
            },
        )
        lead_result_events = await self._uow.append_hypothesis_versions_with_events(
            proposed_case,
            proposed,
            expected_version=current_case.version,
            prior_events=(lead_completed,),
            trace_id=trace_id,
            correlation_id=correlation_id,
            actor=DomainEventActor.AGENT,
            run_id=run_id,
            lease=lease,
            lease_checked_at=post_lead_time,
        )

        verifying_time = self._checked_time(post_lead_time)
        verifying = synthesizing.advance_phase(
            RunPhase.VERIFYING,
            occurred_at=verifying_time,
        )
        verifying_event = await self._uow.save_run(
            verifying,
            expected_version=synthesizing.version,
            trace_id=trace_id,
            correlation_id=correlation_id,
            actor=DomainEventActor.AGENT,
            causation_event_id=lead_result_events[0].id,
            lease=lease,
            lease_checked_at=verifying_time,
        )
        claims = tuple(claim.statement for claim in lead_run.result.claims)
        verification_plan = await self._verification.prepare(
            lead_context,
            claims=claims,
            budget=manager,
        )
        verification_task_id = self._task_id(run_id, "verification")
        verification_skill = SkillVersionRef(
            skill_id="commerce.claim-verification",
            version="1.0.0",
        )
        verification_state = lead_state.model_copy(
            update={
                "evidence_ids": proposed_case.evidence_ids,
                "hypothesis_ids": proposed_case.hypothesis_ids,
                "active_path_task_ids": (verification_task_id,),
                "model_assignments": (
                    *lead_state.model_assignments,
                    verification_plan.assignment,
                ),
                "skill_versions": (
                    *lead_state.skill_versions,
                    verification_skill,
                ),
                "context_sha256": (
                    verification_plan.context.manifest.context_sha256
                ),
            }
        )
        verification_started = NewDomainEvent(
            workspace_id=workspace_id,
            case_id=verifying.case_id,
            run_id=run_id,
            event_type="verification.started",
            trace_id=trace_id,
            correlation_id=correlation_id,
            causation_event_id=lead_result_events[0].id,
            actor=DomainEventActor.AGENT,
            payload={
                "task_id": str(verification_task_id),
                "context_sha256": (
                    verification_plan.context.manifest.context_sha256
                ),
                "claim_count": len(claims),
                "claims_sha256": self._claims_sha256(claims),
                "lead_reasoning_included": False,
                "skill_id": verification_skill.skill_id,
                "skill_version": verification_skill.version,
            },
        )
        verification_pre_record, verification_pre_events = (
            await self._uow.append_run_checkpoint_with_events(
                self._checkpoint(verification_state, manager.snapshot),
                prior_events=(
                    build_model_assignment_event(
                        verification_plan.assignment,
                        workspace_id=workspace_id,
                        case_id=verifying.case_id,
                        run_id=run_id,
                        trace_id=trace_id,
                        correlation_id=correlation_id,
                    ),
                    verification_started,
                ),
                trace_id=trace_id,
                correlation_id=correlation_id,
                actor=DomainEventActor.AGENT,
                checkpoint_id=self._checkpoint_id(run_id, "pre-verification"),
                lease=lease,
                lease_checked_at=verifying_time,
            )
        )
        await self._leases.heartbeat(
            workspace_id,
            run_id,
            lease,
            ttl=self._lease_ttl,
            heartbeat_at=self._checked_time(verifying_time),
        )
        verification_run = await self._verification.run_prepared(verification_plan)
        post_verification_time = self._clock()
        await self._leases.heartbeat(
            workspace_id,
            run_id,
            lease,
            ttl=self._lease_ttl,
            heartbeat_at=post_verification_time,
        )
        verification_tokens = verification_run.telemetry.token_usage
        assert verification_tokens is not None
        await manager.consume(
            BudgetDelta(
                tokens=verification_tokens.total_tokens,
                wall_time_seconds=verification_run.telemetry.latency_ms / 1000,
            )
        )

        verified = project_verified_hypotheses(
            proposed,
            verification_run.result,
        )
        verified_case = self._case_with_hypotheses(
            proposed_case,
            verified,
            occurred_at=post_verification_time,
            add_membership=False,
        )
        verification_completed = NewDomainEvent(
            workspace_id=workspace_id,
            case_id=verifying.case_id,
            run_id=run_id,
            event_type="verification.completed",
            trace_id=trace_id,
            correlation_id=correlation_id,
            causation_event_id=verification_pre_events[1].id,
            actor=DomainEventActor.AGENT,
            payload={
                "task_id": str(verification_task_id),
                "result_sha256": verification_run.result_sha256,
                "context_sha256": verification_run.result.context_sha256,
                "overall_verdict": (
                    verification_run.result.overall_verdict.value
                ),
                "claim_verdicts": [
                    {
                        "hypothesis_id": str(proposed[item.claim_index].id),
                        "claim_index": item.claim_index,
                        "verdict": item.verdict.value,
                        "issue_codes": sorted(
                            code.value for code in item.issue_codes
                        ),
                        "metric_observation_ids": [
                            str(value) for value in item.metric_observation_ids
                        ],
                    }
                    for item in verification_run.result.claims
                ],
                **self._model_completion_payload(verification_run.telemetry),
            },
        )
        verification_result_events = (
            await self._uow.append_hypothesis_versions_with_events(
                verified_case,
                verified,
                expected_version=proposed_case.version,
                prior_events=(verification_completed,),
                trace_id=trace_id,
                correlation_id=correlation_id,
                actor=DomainEventActor.AGENT,
                run_id=run_id,
                lease=lease,
                lease_checked_at=post_verification_time,
            )
        )

        decision_state = verification_state.model_copy(
            update={
                "active_path_task_ids": (),
                "hypothesis_ids": verified_case.hypothesis_ids,
            }
        )
        controller = GoalLoopController(manager)
        try:
            if verification_run.result.overall_verdict is not ClaimVerdict.PASS:
                await manager.consume(BudgetDelta(verification_repairs=1))
            decision = await controller.advance(
                decision_state,
                verification_goal_progress(verification_run.result),
            )
        except BudgetExceededError as error:
            decision = controller.stop_for_budget(
                decision_state,
                error,
                partial_goal_achieved=True,
            )
        goal_event = build_goal_loop_decision_event(
            decision,
            trace_id=trace_id,
            correlation_id=correlation_id,
        ).model_copy(
            update={"causation_event_id": verification_result_events[0].id}
        )
        final_record, final_events = await self._uow.append_run_checkpoint_with_events(
            decision.checkpoint,
            prior_events=(goal_event,),
            trace_id=trace_id,
            correlation_id=correlation_id,
            actor=DomainEventActor.AGENT,
            checkpoint_id=self._checkpoint_id(run_id, "post-verification"),
            lease=lease,
            lease_checked_at=post_verification_time,
        )
        terminal_status = (
            RunStatus.COMPLETED
            if decision.outcome is GoalLoopOutcome.ACHIEVED
            else RunStatus.BLOCKED
        )
        assert decision.stop_reason is not None
        terminal_time = self._checked_time(post_verification_time)
        terminal_run = verifying.transition_to(
            terminal_status,
            stop_reason=decision.stop_reason.value,
            occurred_at=terminal_time,
        )
        terminal_event = await self._uow.save_run(
            terminal_run,
            expected_version=verifying.version,
            trace_id=trace_id,
            correlation_id=correlation_id,
            actor=DomainEventActor.AGENT,
            causation_event_id=final_events[0].id,
            lease=lease,
            lease_checked_at=terminal_time,
        )
        return FulfillmentCaseLoopResult(
            run=terminal_run,
            path_step=path_step,
            lead_pre_call_checkpoint=lead_pre_record,
            verification_pre_call_checkpoint=verification_pre_record,
            final_checkpoint=final_record,
            lead_run=lead_run,
            verification_run=verification_run,
            proposed_hypotheses=proposed,
            verified_hypotheses=verified,
            decision=decision,
            events=(
                *path_step.events,
                synthesizing_event,
                *lead_pre_events,
                *lead_result_events,
                verifying_event,
                *verification_pre_events,
                *verification_result_events,
                *final_events,
                terminal_event,
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

    async def _require_case(
        self,
        workspace_id: WorkspaceId,
        case_id: CaseId,
    ) -> Case:
        case = await self._cases.get(workspace_id, case_id)
        if case is None:
            raise RuntimeError(f"Case disappeared during Worker execution: {case_id}")
        return case

    @staticmethod
    def _case_with_hypotheses(
        case: Case,
        hypotheses: tuple[Hypothesis, ...],
        *,
        occurred_at: datetime,
        add_membership: bool,
    ) -> Case:
        hypothesis_ids = tuple(item.id for item in hypotheses)
        if add_membership:
            if set(hypothesis_ids) & set(case.hypothesis_ids):
                raise ValueError("Lead Hypothesis IDs already belong to the Case")
            next_ids = (*case.hypothesis_ids, *hypothesis_ids)
        else:
            if not set(hypothesis_ids).issubset(set(case.hypothesis_ids)):
                raise ValueError("Verified Hypotheses must already belong to the Case")
            next_ids = case.hypothesis_ids
        return case.model_copy(
            update={
                "hypothesis_ids": next_ids,
                "updated_at": max(occurred_at, case.updated_at),
                "version": case.version + 1,
            }
        )

    @staticmethod
    def _state_from_checkpoint(checkpoint: GoalLoopCheckpoint) -> GoalLoopState:
        return GoalLoopState(
            workspace_id=checkpoint.workspace_id,
            run_id=checkpoint.run_id,
            case_id=checkpoint.case_id,
            goal=checkpoint.goal,
            loop_iteration=checkpoint.loop_iteration,
            evidence_ids=checkpoint.evidence_ids,
            hypothesis_ids=checkpoint.hypothesis_ids,
            active_path_task_ids=checkpoint.active_path_task_ids,
            model_assignments=checkpoint.model_assignments,
            skill_versions=checkpoint.skill_versions,
            context_sha256=checkpoint.context_sha256,
            tool_state=checkpoint.tool_state,
            resume_token_sha256=checkpoint.resume_token_sha256,
        )

    @staticmethod
    def _model_completion_payload(
        telemetry: VerifiedCallTelemetry,
    ) -> dict[str, object]:
        token_usage = telemetry.token_usage
        assert token_usage is not None
        return {
            "provider_request_id": telemetry.provider_request_id,
            "actual_model_identity": telemetry.actual_model_identity,
            "input_tokens": token_usage.input_tokens,
            "output_tokens": token_usage.output_tokens,
            "total_tokens": token_usage.total_tokens,
            "latency_ms": telemetry.latency_ms,
            "request_attempt_count": telemetry.request_attempt_count,
            "retry_count": telemetry.retry_count,
            "stop_reason": telemetry.stop_reason,
        }

    @staticmethod
    def _claims_sha256(claims: tuple[str, ...]) -> str:
        return hashlib.sha256(
            json.dumps(
                claims,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

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

    @staticmethod
    def _task_id(run_id: RunId, stage: str) -> AgentTaskId:
        return AgentTaskId(
            f"task_{uuid5(NAMESPACE_URL, f'{run_id}:{stage}').hex}"
        )

    def _checked_time(self, lower_bound: datetime) -> datetime:
        return max(self._clock(), lower_bound)
