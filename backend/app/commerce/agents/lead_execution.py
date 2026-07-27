"""Translate deterministic Lead decisions into case-bound Subagent work."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.commerce.agents.budget import BudgetDelta, BudgetManager, BudgetSnapshot, BudgetUsage
from app.commerce.agents.contracts import AgentBudgetLimit, PathType
from app.commerce.agents.evidence_barrier import (
    EvidenceBarrier,
    EvidenceBarrierDisposition,
)
from app.commerce.agents.fulfillment import FulfillmentPathAgent
from app.commerce.agents.fulfillment_subagent import (
    FulfillmentSubagentSpec,
    build_fulfillment_read_tools,
)
from app.commerce.agents.goal_loop import (
    GoalLoopCheckpoint,
    GoalLoopState,
    SkillVersionRef,
)
from app.commerce.agents.lead import (
    LeadSynthesisAgent,
    LeadSynthesisRun,
    build_persisted_lead_context,
)
from app.commerce.agents.lead_loop import (
    CommerceLeadObserver,
    LeadAction,
    LeadActionDecision,
    LeadLoopPlanner,
    LeadTurnIntent,
    LeadTurnRequest,
    PersistedLeadObservation,
)
from app.commerce.agents.model_router import build_model_assignment_event
from app.commerce.agents.review_experience import ReviewExperiencePathAgent
from app.commerce.agents.review_experience_subagent import (
    ReviewExperienceSubagentSpec,
    build_review_experience_read_tools,
)
from app.commerce.agents.router import (
    DynamicPathPlan,
    DynamicPathRouter,
    summarize_case_signals,
)
from app.commerce.agents.seller_peer import SellerPeerPathAgent
from app.commerce.agents.seller_peer_subagent import (
    SellerPeerSubagentSpec,
    build_seller_peer_read_tools,
)
from app.commerce.agents.subagent_committer import CommerceSubagentCommitter
from app.commerce.agents.subagent_coordinator import (
    CommerceSubagentCoordinator,
    PreparedCommercePath,
)
from app.commerce.agents.subagent_fanout import CommerceSubagentFanoutResult
from app.commerce.agents.synthesis import project_proposed_hypotheses
from app.commerce.api.data_service import CommerceDataService
from app.commerce.domain.enums import RunPhase, RunStatus, RunType
from app.commerce.domain.events import DomainEventActor, NewDomainEvent
from app.commerce.domain.ids import (
    AgentTaskId,
    CheckpointId,
    CorrelationId,
    EventId,
    HypothesisId,
    RunId,
    TraceId,
    WorkspaceId,
)
from app.commerce.domain.models import Case, CommerceModel, Hypothesis
from app.commerce.domain.runs import CommerceRun
from app.commerce.persistence.repositories import SqlCaseRepository
from app.commerce.persistence.runs import (
    RunCheckpointRecord,
    RunLeaseCredentials,
    SqlRunLeaseRepository,
)
from app.commerce.persistence.unit_of_work import SqlCommerceUnitOfWork
from app.commerce.persistence.work_records import SqlEvidenceRepository


class CommercePathPreparationError(ValueError):
    """Raised when a Lead decision cannot become a valid bounded Path plan."""


class CommercePathPreparationService:
    """Prepare only the Paths selected by the deterministic Lead planner."""

    def __init__(self, *, data_service: CommerceDataService) -> None:
        self._fulfillment = FulfillmentPathAgent()
        self._seller_peer = SellerPeerPathAgent(data_service=data_service)
        self._review_experience = ReviewExperiencePathAgent(
            data_service=data_service
        )

    async def prepare(
        self,
        *,
        observation: PersistedLeadObservation,
        decision: LeadActionDecision,
    ) -> tuple[PreparedCommercePath, ...]:
        if decision.action not in {LeadAction.INVESTIGATE, LeadAction.REPLAN}:
            raise CommercePathPreparationError(
                "Only investigate or replan decisions may prepare Subagent Paths"
            )

        context = observation.context
        prepared: list[PreparedCommercePath] = []
        for path_type in decision.selected_paths:
            if path_type is PathType.FULFILLMENT:
                plan = await self._fulfillment.prepare(context)
                prepared.append(
                    PreparedCommercePath(
                        spec=FulfillmentSubagentSpec(plan),
                        tool_builder=build_fulfillment_read_tools,
                    )
                )
                continue
            if path_type is PathType.SELLER_PEER:
                policy = context.analysis.trigger.peer_policy
                if policy is None:
                    raise CommercePathPreparationError(
                        "SellerPeer Path requires a persisted peer cohort policy"
                    )
                plan = await self._seller_peer.prepare(
                    context.case.workspace_id,
                    context.manifest.dataset_id,
                    seller_id=context.analysis.seller_external_key,
                    window=context.analysis.current_window,
                    policy=policy,
                )
                spec = SellerPeerSubagentSpec(plan).bind_to_case(
                    context.case,
                    source_artifact_sha256=(
                        context.manifest.source_artifact_sha256
                    ),
                )
                prepared.append(
                    PreparedCommercePath(
                        spec=spec,
                        tool_builder=build_seller_peer_read_tools,
                    )
                )
                continue
            if path_type is PathType.REVIEW_EXPERIENCE:
                plan = await self._review_experience.prepare(
                    context.case.workspace_id,
                    context.manifest.dataset_id,
                    seller_id=context.analysis.seller_external_key,
                    baseline_window=context.analysis.baseline_window,
                    current_window=context.analysis.current_window,
                )
                spec = ReviewExperienceSubagentSpec(plan).bind_to_case(
                    context.case,
                    source_artifact_sha256=(
                        context.manifest.source_artifact_sha256
                    ),
                )
                prepared.append(
                    PreparedCommercePath(
                        spec=spec,
                        tool_builder=build_review_experience_read_tools,
                    )
                )
                continue
            raise CommercePathPreparationError(
                f"Unsupported Commerce Path: {path_type.value}"
            )

        for item in prepared:
            path_context = item.spec.plan.context
            if path_context.case != context.case:
                raise CommercePathPreparationError(
                    "Prepared Path is not bound to the persisted Case identity"
                )
            if path_context.path_type not in decision.selected_paths:
                raise CommercePathPreparationError(
                    "Prepared Path is outside the Lead decision allowlist"
                )
        return tuple(prepared)


class CommerceLeadTurnExecutionError(RuntimeError):
    """Raised when one persisted Lead turn cannot safely continue."""


class CommerceLeadTurnResult(CommerceModel):
    decision: LeadActionDecision
    route_plan: DynamicPathPlan
    fanout: CommerceSubagentFanoutResult | None = None
    lead_run: LeadSynthesisRun | None = None
    proposed_hypothesis_ids: tuple[HypothesisId, ...] = ()
    final_checkpoint: RunCheckpointRecord | None = None
    run: CommerceRun


class CommerceLeadTurnService:
    """Execute one persisted Lead turn through bounded DeerFlow Subagents."""

    def __init__(
        self,
        *,
        data_service: CommerceDataService,
        session_factory: async_sessionmaker[AsyncSession],
        lease_ttl: timedelta,
    ) -> None:
        if lease_ttl.total_seconds() <= 0:
            raise ValueError("Lead turn lease TTL must be positive")
        self._lease_ttl = lease_ttl
        self._clock = lambda: datetime.now(UTC)
        self._observer = CommerceLeadObserver(
            data_service=data_service,
            session_factory=session_factory,
        )
        self._planner = LeadLoopPlanner()
        self._router = DynamicPathRouter()
        self._preparer = CommercePathPreparationService(data_service=data_service)
        self._lead = LeadSynthesisAgent()
        self._uow = SqlCommerceUnitOfWork(session_factory)
        self._cases = SqlCaseRepository(session_factory)
        self._leases = SqlRunLeaseRepository(session_factory)
        evidence = SqlEvidenceRepository(session_factory)
        self._coordinator = CommerceSubagentCoordinator(
            committer=CommerceSubagentCommitter(
                uow=self._uow,
                cases=self._cases,
                evidence=evidence,
            ),
            leases=self._leases,
            barrier=EvidenceBarrier(evidence),
            lease_ttl=lease_ttl,
        )

    async def execute(
        self,
        workspace_id: WorkspaceId,
        run_id: RunId,
        *,
        request: LeadTurnRequest,
        budget: AgentBudgetLimit,
        lease: RunLeaseCredentials,
        correlation_id: CorrelationId,
    ) -> CommerceLeadTurnResult:
        trace_id = TraceId.new()
        observation = await self._observer.observe(
            workspace_id,
            run_id,
            budget=budget,
        )
        if observation.run.status is not RunStatus.RUNNING:
            raise CommerceLeadTurnExecutionError(
                "Lead turn requires a running fenced Commerce Run"
            )
        self._validate_request_matches_run(observation, request)

        signals = summarize_case_signals(observation.context.analysis)
        if request.intent is LeadTurnIntent.NEW_INVESTIGATION_ANGLE:
            signals = signals.model_copy(
                update={"requested_paths": frozenset(request.requested_paths)}
            )
        route_plan = self._router.route(
            observation.context.capability_profile,
            signals,
        )
        decision = self._planner.decide(
            request=request,
            state=observation.planning_state,
            route_plan=route_plan,
        )
        if decision.action is LeadAction.WAIT:
            return await self._persist_wait(
                observation=observation,
                decision=decision,
                route_plan=route_plan,
                budget=budget,
                lease=lease,
                trace_id=trace_id,
                correlation_id=correlation_id,
            )
        if decision.action is LeadAction.STOP:
            return await self._persist_stop(
                observation=observation,
                decision=decision,
                route_plan=route_plan,
                budget=budget,
                lease=lease,
                trace_id=trace_id,
                correlation_id=correlation_id,
            )

        fanout = None
        run = observation.run
        if decision.action in {LeadAction.INVESTIGATE, LeadAction.REPLAN}:
            run = await self._advance_phase(
                run,
                RunPhase.INVESTIGATING,
                lease=lease,
                trace_id=trace_id,
                correlation_id=correlation_id,
            )
            observation = observation.model_copy(update={"run": run})
            prepared = await self._preparer.prepare(
                observation=observation,
                decision=decision,
            )
            base_checkpoint = self._base_checkpoint(observation, budget)
            fanout = await self._coordinator.run(
                prepared_paths=prepared,
                run_id=run_id,
                base_checkpoint=base_checkpoint,
                lease=lease,
                correlation_id=correlation_id,
            )
            if fanout.barrier.disposition is not EvidenceBarrierDisposition.READY:
                raise CommerceLeadTurnExecutionError(
                    "Evidence Barrier did not release a synthesizable persisted state"
                )
            observation = await self._observer.observe(
                workspace_id,
                run_id,
                budget=budget,
            )
            run = observation.run

        if run.phase is not RunPhase.SYNTHESIZING:
            run = await self._advance_phase(
                run,
                RunPhase.SYNTHESIZING,
                lease=lease,
                trace_id=trace_id,
                correlation_id=correlation_id,
            )
            observation = observation.model_copy(update={"run": run})

        allowed_scope_run_ids = set(observation.scope_run_ids)
        selected_scopes = tuple(
            scope
            for scope in observation.path_scopes
            if scope.run_id in allowed_scope_run_ids
        )
        lead_context = build_persisted_lead_context(
            observation.context,
            path_scopes=selected_scopes,
            goal=request.question or run.goal,
        )
        lead_run, hypothesis_ids, final_checkpoint = (
            await self._synthesize_and_persist(
                observation=observation,
                decision=decision,
                context=lead_context,
                lease=lease,
                trace_id=trace_id,
                correlation_id=correlation_id,
                budget=budget,
            )
        )
        return CommerceLeadTurnResult(
            decision=decision,
            route_plan=route_plan,
            fanout=fanout,
            lead_run=lead_run,
            proposed_hypothesis_ids=hypothesis_ids,
            final_checkpoint=final_checkpoint,
            run=run,
        )

    @staticmethod
    def _validate_request_matches_run(
        observation: PersistedLeadObservation,
        request: LeadTurnRequest,
    ) -> None:
        run = observation.run
        if run.run_type is RunType.REPLAN and observation.latest_checkpoint is None:
            if (
                request.intent is not LeadTurnIntent.NEW_INVESTIGATION_ANGLE
                or request.question != run.goal
                or request.requested_paths != run.requested_paths
            ):
                raise CommerceLeadTurnExecutionError(
                    "Initial Replan turn must match its persisted Run request"
                )
            return
        if (
            run.run_type is not RunType.REPLAN
            and request.intent is LeadTurnIntent.NEW_INVESTIGATION_ANGLE
        ):
            raise CommerceLeadTurnExecutionError(
                "A new investigation angle requires an independent Replan Run"
            )

    async def _persist_wait(
        self,
        *,
        observation: PersistedLeadObservation,
        decision: LeadActionDecision,
        route_plan: DynamicPathPlan,
        budget: AgentBudgetLimit,
        lease: RunLeaseCredentials,
        trace_id: TraceId,
        correlation_id: CorrelationId,
    ) -> CommerceLeadTurnResult:
        if decision.stop_reason is None:
            raise CommerceLeadTurnExecutionError("Wait decision is missing stop_reason")
        base = self._base_checkpoint(observation, budget)
        checkpoint = base.model_copy(
            update={
                "active_path_task_ids": (),
                "wait_reason": decision.stop_reason,
            }
        )
        checked_at = self._checked_time(observation.run.updated_at)
        record, checkpoint_events = await self._uow.append_run_checkpoint_with_events(
            checkpoint,
            prior_events=(
                NewDomainEvent(
                    id=self._event_id(
                        observation.run.id,
                        "lead.waiting",
                        decision.stop_reason.value,
                    ),
                    workspace_id=observation.run.workspace_id,
                    case_id=observation.run.case_id,
                    run_id=observation.run.id,
                    event_type="lead.waiting",
                    trace_id=trace_id,
                    correlation_id=correlation_id,
                    actor=DomainEventActor.AGENT,
                    payload={
                        "wait_reason": decision.stop_reason.value,
                        "reason_codes": sorted(
                            item.value for item in decision.reason_codes
                        ),
                    },
                ),
            ),
            trace_id=trace_id,
            correlation_id=correlation_id,
            actor=DomainEventActor.AGENT,
            checkpoint_id=self._checkpoint_id(
                observation.run.id,
                "lead-wait",
                decision.stop_reason.value,
            ),
            checkpoint_event_id=self._event_id(
                observation.run.id,
                "checkpoint.lead-wait",
                decision.stop_reason.value,
            ),
            lease=lease,
            lease_checked_at=checked_at,
        )
        waiting_at = self._checked_time(checked_at)
        waiting = observation.run.transition_to(
            RunStatus.WAITING,
            wait_reason=decision.stop_reason.value,
            occurred_at=waiting_at,
        )
        await self._uow.save_run(
            waiting,
            expected_version=observation.run.version,
            trace_id=trace_id,
            correlation_id=correlation_id,
            actor=DomainEventActor.AGENT,
            causation_event_id=checkpoint_events[-1].id,
            lease=lease,
            lease_checked_at=waiting_at,
        )
        await self._leases.release(
            observation.run.workspace_id,
            observation.run.id,
            lease,
            released_at=self._checked_time(waiting_at),
            trace_id=trace_id,
            correlation_id=correlation_id,
        )
        return CommerceLeadTurnResult(
            decision=decision,
            route_plan=route_plan,
            final_checkpoint=record,
            run=waiting,
        )

    async def _persist_stop(
        self,
        *,
        observation: PersistedLeadObservation,
        decision: LeadActionDecision,
        route_plan: DynamicPathPlan,
        budget: AgentBudgetLimit,
        lease: RunLeaseCredentials,
        trace_id: TraceId,
        correlation_id: CorrelationId,
    ) -> CommerceLeadTurnResult:
        if decision.stop_reason is None:
            raise CommerceLeadTurnExecutionError("Stop decision is missing stop_reason")
        base = self._base_checkpoint(observation, budget).model_copy(
            update={"active_path_task_ids": (), "wait_reason": None}
        )
        checked_at = self._checked_time(observation.run.updated_at)
        record, checkpoint_events = await self._uow.append_run_checkpoint_with_events(
            base,
            prior_events=(
                NewDomainEvent(
                    id=self._event_id(
                        observation.run.id,
                        "lead.stopped",
                        decision.stop_reason.value,
                    ),
                    workspace_id=observation.run.workspace_id,
                    case_id=observation.run.case_id,
                    run_id=observation.run.id,
                    event_type="lead.stopped",
                    trace_id=trace_id,
                    correlation_id=correlation_id,
                    actor=DomainEventActor.AGENT,
                    payload={
                        "stop_reason": decision.stop_reason.value,
                        "reason_codes": sorted(
                            item.value for item in decision.reason_codes
                        ),
                    },
                ),
            ),
            trace_id=trace_id,
            correlation_id=correlation_id,
            actor=DomainEventActor.AGENT,
            checkpoint_id=self._checkpoint_id(
                observation.run.id,
                "lead-stop",
                decision.stop_reason.value,
            ),
            checkpoint_event_id=self._event_id(
                observation.run.id,
                "checkpoint.lead-stop",
                decision.stop_reason.value,
            ),
            lease=lease,
            lease_checked_at=checked_at,
        )
        stopped_at = self._checked_time(checked_at)
        stopped = observation.run.transition_to(
            RunStatus.CANCELLED,
            stop_reason=decision.stop_reason.value,
            occurred_at=stopped_at,
        )
        await self._uow.save_run(
            stopped,
            expected_version=observation.run.version,
            trace_id=trace_id,
            correlation_id=correlation_id,
            actor=DomainEventActor.AGENT,
            causation_event_id=checkpoint_events[-1].id,
            lease=lease,
            lease_checked_at=stopped_at,
        )
        await self._leases.release(
            observation.run.workspace_id,
            observation.run.id,
            lease,
            released_at=self._checked_time(stopped_at),
            trace_id=trace_id,
            correlation_id=correlation_id,
        )
        return CommerceLeadTurnResult(
            decision=decision,
            route_plan=route_plan,
            final_checkpoint=record,
            run=stopped,
        )

    async def _synthesize_and_persist(
        self,
        *,
        observation: PersistedLeadObservation,
        decision: LeadActionDecision,
        context,
        lease: RunLeaseCredentials,
        trace_id: TraceId,
        correlation_id: CorrelationId,
        budget: AgentBudgetLimit,
    ) -> tuple[LeadSynthesisRun, tuple[HypothesisId, ...], RunCheckpointRecord]:
        base = self._base_checkpoint(observation, budget)
        manager = BudgetManager(
            base.budget_snapshot.limit,
            initial_usage=base.budget_snapshot.usage,
        )
        plan = await self._lead.prepare(
            context,
            budget=manager,
            read_only=decision.read_only,
        )
        task_id = self._task_id(
            observation.run.id,
            "lead-answer" if decision.read_only else "lead-synthesis",
            context.manifest.context_sha256,
        )
        skill = SkillVersionRef(
            skill_id="commerce.lead-synthesis",
            version="1.0.0",
        )
        state = self._state_from_checkpoint(base).model_copy(
            update={
                "active_path_task_ids": (task_id,),
                "model_assignments": (*base.model_assignments, plan.assignment),
                "skill_versions": (*base.skill_versions, skill),
                "context_sha256": context.manifest.context_sha256,
            }
        )
        started_type = "lead.answer_started" if decision.read_only else "lead.started"
        started = NewDomainEvent(
            id=self._event_id(
                observation.run.id,
                started_type,
                context.manifest.context_sha256,
            ),
            workspace_id=observation.run.workspace_id,
            case_id=observation.run.case_id,
            run_id=observation.run.id,
            event_type=started_type,
            trace_id=trace_id,
            correlation_id=correlation_id,
            actor=DomainEventActor.AGENT,
            payload={
                "task_id": str(task_id),
                "context_sha256": context.manifest.context_sha256,
                "skill_id": skill.skill_id,
                "skill_version": skill.version,
                "read_only": decision.read_only,
                "claim_source": "persisted_case_evidence",
            },
        )
        assignment_event = build_model_assignment_event(
            plan.assignment,
            workspace_id=observation.run.workspace_id,
            case_id=observation.run.case_id,
            run_id=observation.run.id,
            trace_id=trace_id,
            correlation_id=correlation_id,
        ).model_copy(
            update={
                "id": self._event_id(
                    observation.run.id,
                    "model.assigned.lead",
                    context.manifest.context_sha256,
                )
            }
        )
        checked_at = self._checked_time(observation.run.updated_at)
        _, pre_events = await self._uow.append_run_checkpoint_with_events(
            self._checkpoint(state, manager.snapshot),
            prior_events=(assignment_event, started),
            trace_id=trace_id,
            correlation_id=correlation_id,
            actor=DomainEventActor.AGENT,
            checkpoint_id=self._checkpoint_id(
                observation.run.id,
                "pre-lead",
                context.manifest.context_sha256,
            ),
            checkpoint_event_id=self._event_id(
                observation.run.id,
                "checkpoint.pre-lead",
                context.manifest.context_sha256,
            ),
            lease=lease,
            lease_checked_at=checked_at,
        )
        await self._leases.heartbeat(
            observation.run.workspace_id,
            observation.run.id,
            lease,
            ttl=self._lease_ttl,
            heartbeat_at=self._checked_time(checked_at),
        )
        lead_run = await self._lead.run_prepared(plan)
        completed_at = self._clock()
        await self._leases.heartbeat(
            observation.run.workspace_id,
            observation.run.id,
            lease,
            ttl=self._lease_ttl,
            heartbeat_at=completed_at,
        )
        if any(
            item.token_usage is None for item in lead_run.attempt_telemetry
        ):
            raise CommerceLeadTurnExecutionError(
                "Passed Lead call is missing token telemetry"
            )
        await manager.consume(
            BudgetDelta(
                tokens=lead_run.total_tokens,
                wall_time_seconds=lead_run.total_latency_ms / 1000,
                repeated_actions=len(lead_run.attempt_telemetry) - 1,
            )
        )

        proposed = (
            ()
            if decision.read_only
            else project_proposed_hypotheses(
                workspace_id=observation.run.workspace_id,
                case_id=observation.run.case_id,
                lead=lead_run.result,
            )
        )
        current_case = await self._require_case(
            observation.run.workspace_id,
            observation.run.case_id,
        )
        completed_type = (
            "lead.answer_completed" if decision.read_only else "lead.completed"
        )
        completed = NewDomainEvent(
            id=self._event_id(
                observation.run.id,
                completed_type,
                context.manifest.context_sha256,
            ),
            workspace_id=observation.run.workspace_id,
            case_id=observation.run.case_id,
            run_id=observation.run.id,
            event_type=completed_type,
            trace_id=trace_id,
            correlation_id=correlation_id,
            causation_event_id=pre_events[1].id,
            actor=DomainEventActor.AGENT,
            payload={
                "task_id": str(task_id),
                "result_sha256": lead_run.result_sha256,
                "context_sha256": lead_run.result.context_sha256,
                "claim_count": len(lead_run.result.claims),
                "unknown_count": len(lead_run.result.unknowns),
                "suggested_next_paths": [
                    item.value for item in lead_run.result.suggested_next_paths
                ],
                "read_only": decision.read_only,
                **self._model_completion_payload(lead_run),
            },
        )

        hypothesis_ids: tuple[HypothesisId, ...] = ()
        causation_event_id = completed.id
        if proposed:
            proposed_case = self._case_with_hypotheses(
                current_case,
                proposed,
                occurred_at=completed_at,
            )
            result_events = await self._uow.append_hypothesis_versions_with_events(
                proposed_case,
                proposed,
                expected_version=current_case.version,
                prior_events=(completed,),
                trace_id=trace_id,
                correlation_id=correlation_id,
                actor=DomainEventActor.AGENT,
                run_id=observation.run.id,
                lease=lease,
                lease_checked_at=completed_at,
            )
            current_case = proposed_case
            hypothesis_ids = tuple(item.id for item in proposed)
            causation_event_id = result_events[-1].id
        final_state = state.model_copy(
            update={
                "active_path_task_ids": (),
                "evidence_ids": current_case.evidence_ids,
                "hypothesis_ids": current_case.hypothesis_ids,
                "context_sha256": context.manifest.context_sha256,
            }
        )
        final_checkpoint = self._checkpoint(final_state, manager.snapshot)
        if proposed:
            record, _ = await self._uow.append_run_checkpoint(
                final_checkpoint,
                trace_id=trace_id,
                correlation_id=correlation_id,
                actor=DomainEventActor.AGENT,
                causation_event_id=causation_event_id,
                checkpoint_id=self._checkpoint_id(
                    observation.run.id,
                    "post-lead",
                    context.manifest.context_sha256,
                ),
                lease=lease,
                lease_checked_at=completed_at,
            )
        else:
            record, _ = await self._uow.append_run_checkpoint_with_events(
                final_checkpoint,
                prior_events=(completed,),
                trace_id=trace_id,
                correlation_id=correlation_id,
                actor=DomainEventActor.AGENT,
                checkpoint_id=self._checkpoint_id(
                    observation.run.id,
                    "post-lead",
                    context.manifest.context_sha256,
                ),
                checkpoint_event_id=self._event_id(
                    observation.run.id,
                    "checkpoint.post-lead",
                    context.manifest.context_sha256,
                ),
                lease=lease,
                lease_checked_at=completed_at,
            )
        return lead_run, hypothesis_ids, record

    async def _advance_phase(
        self,
        run: CommerceRun,
        target: RunPhase,
        *,
        lease: RunLeaseCredentials,
        trace_id: TraceId,
        correlation_id: CorrelationId,
    ) -> CommerceRun:
        if run.phase is target:
            return run
        checked_at = self._checked_time(run.updated_at)
        advanced = run.advance_phase(target, occurred_at=checked_at)
        await self._uow.save_run(
            advanced,
            expected_version=run.version,
            trace_id=trace_id,
            correlation_id=correlation_id,
            actor=DomainEventActor.AGENT,
            lease=lease,
            lease_checked_at=checked_at,
        )
        return advanced

    @staticmethod
    def _base_checkpoint(
        observation: PersistedLeadObservation,
        budget: AgentBudgetLimit,
    ) -> GoalLoopCheckpoint:
        if observation.latest_checkpoint is not None:
            checkpoint = observation.latest_checkpoint.checkpoint
            if checkpoint.budget_snapshot.limit != budget:
                raise CommerceLeadTurnExecutionError(
                    "Lead turn budget must match the persisted Run budget"
                )
            if (
                observation.run.status is RunStatus.RUNNING
                and checkpoint.wait_reason is not None
            ):
                checkpoint = checkpoint.model_copy(update={"wait_reason": None})
            return checkpoint
        return GoalLoopCheckpoint(
            workspace_id=observation.run.workspace_id,
            run_id=observation.run.id,
            case_id=observation.run.case_id,
            goal=observation.run.goal,
            loop_iteration=0,
            budget_snapshot=BudgetSnapshot(
                limit=budget,
                usage=BudgetUsage(),
            ),
            evidence_ids=observation.context.manifest.included_evidence_ids,
            hypothesis_ids=tuple(
                item.hypothesis_id for item in observation.context.hypotheses
            ),
            context_sha256=observation.context.manifest.context_sha256,
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

    async def _require_case(
        self,
        workspace_id: WorkspaceId,
        case_id,
    ) -> Case:
        case = await self._cases.get(workspace_id, case_id)
        if case is None:
            raise CommerceLeadTurnExecutionError(
                f"Case disappeared during Lead turn: {case_id}"
            )
        return case

    @staticmethod
    def _case_with_hypotheses(
        case: Case,
        hypotheses: tuple[Hypothesis, ...],
        *,
        occurred_at: datetime,
    ) -> Case:
        hypothesis_ids = tuple(item.id for item in hypotheses)
        if set(hypothesis_ids) & set(case.hypothesis_ids):
            raise CommerceLeadTurnExecutionError(
                "Lead Hypothesis IDs already belong to the Case"
            )
        return case.model_copy(
            update={
                "hypothesis_ids": (*case.hypothesis_ids, *hypothesis_ids),
                "updated_at": max(occurred_at, case.updated_at),
                "version": case.version + 1,
            }
        )

    @staticmethod
    def _model_completion_payload(lead_run: LeadSynthesisRun) -> dict[str, object]:
        telemetry = lead_run.telemetry
        token_usages = tuple(
            item.token_usage
            for item in lead_run.attempt_telemetry
            if item.token_usage is not None
        )
        assert len(token_usages) == len(lead_run.attempt_telemetry)
        return {
            "provider_request_id": telemetry.provider_request_id,
            "provider_request_ids": [
                item.provider_request_id for item in lead_run.attempt_telemetry
            ],
            "actual_model_identity": telemetry.actual_model_identity,
            "input_tokens": sum(item.input_tokens for item in token_usages),
            "output_tokens": sum(item.output_tokens for item in token_usages),
            "total_tokens": lead_run.total_tokens,
            "latency_ms": lead_run.total_latency_ms,
            "model_call_count": len(lead_run.attempt_telemetry),
            "request_attempt_count": sum(
                item.request_attempt_count for item in lead_run.attempt_telemetry
            ),
            "retry_count": sum(
                item.retry_count for item in lead_run.attempt_telemetry
            ),
            "stop_reason": telemetry.stop_reason,
        }

    @staticmethod
    def _task_id(run_id: RunId, stage: str, discriminator: str) -> AgentTaskId:
        return AgentTaskId(
            f"task_{uuid5(NAMESPACE_URL, f'{run_id}:{stage}:{discriminator}').hex}"
        )

    @staticmethod
    def _checkpoint_id(
        run_id: RunId,
        stage: str,
        discriminator: str,
    ) -> CheckpointId:
        return CheckpointId(
            f"chkpt_{uuid5(NAMESPACE_URL, f'{run_id}:{stage}:{discriminator}').hex}"
        )

    @staticmethod
    def _event_id(run_id: RunId, stage: str, discriminator: str) -> EventId:
        return EventId(
            f"evt_{uuid5(NAMESPACE_URL, f'{run_id}:{stage}:{discriminator}').hex}"
        )

    def _checked_time(self, lower_bound: datetime) -> datetime:
        return max(self._clock(), lower_bound)
