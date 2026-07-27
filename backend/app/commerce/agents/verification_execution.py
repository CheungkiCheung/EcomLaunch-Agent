"""Fenced Fresh Verification turn for the continuous Commerce Goal Loop."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.commerce.agents.budget import (
    BudgetDelta,
    BudgetExceededError,
    BudgetManager,
    BudgetSnapshot,
)
from app.commerce.agents.contracts import AgentBudgetLimit
from app.commerce.agents.goal_loop import (
    GoalLoopCheckpoint,
    GoalLoopController,
    GoalLoopDecision,
    GoalLoopOutcome,
    GoalLoopState,
    SkillVersionRef,
    build_goal_loop_decision_event,
)
from app.commerce.agents.lead import build_persisted_lead_context
from app.commerce.agents.lead_loop import CommerceLeadObserver
from app.commerce.agents.model_router import build_model_assignment_event
from app.commerce.agents.synthesis import (
    project_verified_hypotheses,
    verification_goal_progress,
)
from app.commerce.agents.verification_subagent import (
    FRESH_VERIFICATION_SKILL_ID,
    FRESH_VERIFICATION_SKILL_VERSION,
    FreshVerificationSubagent,
    FreshVerificationSubagentRun,
    build_fresh_verification_packet,
)
from app.commerce.api.data_service import CommerceDataService
from app.commerce.domain.enums import RunPhase, RunStatus
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
from app.commerce.persistence.work_records import SqlHypothesisRepository


class CommerceVerificationTurnError(RuntimeError):
    """Raised when Fresh Verification cannot safely mutate the Goal Loop."""


class CommerceVerificationTurnResult(CommerceModel):
    verification: FreshVerificationSubagentRun
    verified_hypothesis_ids: tuple[HypothesisId, ...]
    goal_decision: GoalLoopDecision
    final_checkpoint: RunCheckpointRecord
    run: CommerceRun


class CommerceVerificationTurnService:
    """Reload, verify, version Hypotheses, decide Goal progress, and stop."""

    def __init__(
        self,
        *,
        data_service: CommerceDataService,
        session_factory: async_sessionmaker[AsyncSession],
        lease_ttl: timedelta,
    ) -> None:
        if lease_ttl.total_seconds() <= 0:
            raise ValueError("Verification lease TTL must be positive")
        self._lease_ttl = lease_ttl
        self._clock = lambda: datetime.now(UTC)
        self._observer = CommerceLeadObserver(
            data_service=data_service,
            session_factory=session_factory,
        )
        self._verification = FreshVerificationSubagent()
        self._uow = SqlCommerceUnitOfWork(session_factory)
        self._cases = SqlCaseRepository(session_factory)
        self._hypotheses = SqlHypothesisRepository(session_factory)
        self._leases = SqlRunLeaseRepository(session_factory)

    async def verify(
        self,
        workspace_id: WorkspaceId,
        run_id: RunId,
        *,
        hypothesis_ids: tuple[HypothesisId, ...],
        budget: AgentBudgetLimit,
        lease: RunLeaseCredentials,
        correlation_id: CorrelationId,
    ) -> CommerceVerificationTurnResult:
        if not hypothesis_ids or len(hypothesis_ids) != len(set(hypothesis_ids)):
            raise CommerceVerificationTurnError(
                "Fresh Verification requires unique proposed Hypothesis IDs"
            )
        trace_id = TraceId.new()
        observation = await self._observer.observe(
            workspace_id,
            run_id,
            budget=budget,
        )
        if observation.run.status is not RunStatus.RUNNING:
            raise CommerceVerificationTurnError(
                "Fresh Verification requires a running fenced Run"
            )
        if observation.latest_checkpoint is None:
            raise CommerceVerificationTurnError(
                "Fresh Verification requires the persisted post-Lead Checkpoint"
            )
        base_checkpoint = observation.latest_checkpoint.checkpoint
        if base_checkpoint.budget_snapshot.limit != budget:
            raise CommerceVerificationTurnError(
                "Verification budget must match the persisted Run budget"
            )

        proposed = await self._load_proposed_hypotheses(
            workspace_id,
            observation.run.case_id,
            hypothesis_ids,
        )
        current_scopes = tuple(
            scope for scope in observation.path_scopes if scope.run_id == run_id
        )
        persisted = build_persisted_lead_context(
            observation.context,
            path_scopes=current_scopes,
        )
        packet = build_fresh_verification_packet(
            base=observation.context,
            persisted=persisted,
            claims=tuple(item.statement for item in proposed),
            claim_evidence_ids=tuple(
                item.supporting_evidence_ids for item in proposed
            ),
        )
        manager = BudgetManager(
            budget,
            initial_usage=base_checkpoint.budget_snapshot.usage,
        )
        plan = await self._verification.prepare(packet, budget=manager)

        run = observation.run
        if run.phase is not RunPhase.VERIFYING:
            run = await self._advance_to_verifying(
                run,
                lease=lease,
                trace_id=trace_id,
                correlation_id=correlation_id,
            )
        task_id = self._task_id(run.id, packet.manifest.context_sha256)
        skill = SkillVersionRef(
            skill_id=FRESH_VERIFICATION_SKILL_ID,
            version=FRESH_VERIFICATION_SKILL_VERSION,
        )
        state = self._state_from_checkpoint(base_checkpoint).model_copy(
            update={
                "active_path_task_ids": (task_id,),
                "model_assignments": (
                    *base_checkpoint.model_assignments,
                    plan.assignment,
                ),
                "skill_versions": (*base_checkpoint.skill_versions, skill),
                "context_sha256": packet.manifest.context_sha256,
            }
        )
        checked_at = self._checked_time(run.updated_at)
        _, pre_events = await self._uow.append_run_checkpoint_with_events(
            self._checkpoint(state, manager.snapshot),
            prior_events=(
                build_model_assignment_event(
                    plan.assignment,
                    workspace_id=workspace_id,
                    case_id=run.case_id,
                    run_id=run.id,
                    trace_id=trace_id,
                    correlation_id=correlation_id,
                ).model_copy(
                    update={
                        "id": self._event_id(
                            run.id,
                            "model.assigned.verification",
                            packet.manifest.context_sha256,
                        )
                    }
                ),
                NewDomainEvent(
                    id=self._event_id(
                        run.id,
                        "verification.started",
                        packet.manifest.context_sha256,
                    ),
                    workspace_id=workspace_id,
                    case_id=run.case_id,
                    run_id=run.id,
                    event_type="verification.started",
                    trace_id=trace_id,
                    correlation_id=correlation_id,
                    actor=DomainEventActor.AGENT,
                    payload={
                        "task_id": str(task_id),
                        "context_sha256": packet.manifest.context_sha256,
                        "hypothesis_ids": [str(value) for value in hypothesis_ids],
                        "claim_count": len(hypothesis_ids),
                        "lead_reasoning_included": False,
                        "skill_id": skill.skill_id,
                        "skill_version": skill.version,
                    },
                ),
            ),
            trace_id=trace_id,
            correlation_id=correlation_id,
            actor=DomainEventActor.AGENT,
            checkpoint_id=self._checkpoint_id(
                run.id,
                "pre-verification",
                packet.manifest.context_sha256,
            ),
            checkpoint_event_id=self._event_id(
                run.id,
                "checkpoint.pre-verification",
                packet.manifest.context_sha256,
            ),
            lease=lease,
            lease_checked_at=checked_at,
        )
        await self._leases.heartbeat(
            workspace_id,
            run.id,
            lease,
            ttl=self._lease_ttl,
            heartbeat_at=self._checked_time(checked_at),
        )
        verification = await self._verification.run(
            plan,
            run_id=run.id,
            task_id=task_id,
            trace_id=trace_id,
        )
        completed_at = self._clock()
        await self._leases.heartbeat(
            workspace_id,
            run.id,
            lease,
            ttl=self._lease_ttl,
            heartbeat_at=completed_at,
        )
        await manager.consume(
            BudgetDelta(
                tokens=verification.token_usage.total_tokens,
                wall_time_seconds=verification.latency_ms / 1000,
            )
        )

        verified = project_verified_hypotheses(proposed, verification.result)
        current_case = await self._require_case(workspace_id, run.case_id)
        verified_case = current_case.model_copy(
            update={
                "updated_at": max(completed_at, current_case.updated_at),
                "version": current_case.version + 1,
            }
        )
        result_events = await self._uow.append_hypothesis_versions_with_events(
            verified_case,
            verified,
            expected_version=current_case.version,
            prior_events=(
                NewDomainEvent(
                    id=self._event_id(
                        run.id,
                        "verification.completed",
                        packet.manifest.context_sha256,
                    ),
                    workspace_id=workspace_id,
                    case_id=run.case_id,
                    run_id=run.id,
                    event_type="verification.completed",
                    trace_id=trace_id,
                    correlation_id=correlation_id,
                    causation_event_id=pre_events[1].id,
                    actor=DomainEventActor.AGENT,
                    payload={
                        "task_id": str(task_id),
                        "result_sha256": verification.result_sha256,
                        "context_sha256": packet.manifest.context_sha256,
                        "overall_verdict": (
                            verification.result.overall_verdict.value
                        ),
                        "provider_request_id": verification.provider_request_id,
                        "actual_model_identity": (
                            verification.actual_model_identity
                        ),
                        "input_tokens": verification.token_usage.input_tokens,
                        "output_tokens": verification.token_usage.output_tokens,
                        "total_tokens": verification.token_usage.total_tokens,
                        "latency_ms": verification.latency_ms,
                        "retry_count": verification.retry_count,
                        "stop_reason": verification.stop_reason,
                        "claim_verdicts": [
                            {
                                "hypothesis_id": str(proposed[item.claim_index].id),
                                "claim_index": item.claim_index,
                                "verdict": item.verdict.value,
                                "issue_codes": sorted(
                                    code.value for code in item.issue_codes
                                ),
                                "evidence_ids": [
                                    str(value) for value in item.evidence_ids
                                ],
                                "fact_ids": [
                                    str(value) for value in item.fact_ids
                                ],
                                "metric_observation_ids": [
                                    str(value)
                                    for value in item.metric_observation_ids
                                ],
                            }
                            for item in verification.result.claims
                        ],
                    },
                ),
            ),
            trace_id=trace_id,
            correlation_id=correlation_id,
            actor=DomainEventActor.AGENT,
            run_id=run.id,
            lease=lease,
            lease_checked_at=completed_at,
        )

        decision_state = state.model_copy(
            update={
                "active_path_task_ids": (),
                "evidence_ids": verified_case.evidence_ids,
                "hypothesis_ids": verified_case.hypothesis_ids,
            }
        )
        controller = GoalLoopController(manager)
        try:
            if verification.result.overall_verdict.value != "pass":
                await manager.consume(BudgetDelta(verification_repairs=1))
            decision = await controller.advance(
                decision_state,
                verification_goal_progress(verification.result),
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
            update={
                "id": self._event_id(
                    run.id,
                    "goal-loop-decision",
                    packet.manifest.context_sha256,
                ),
                "causation_event_id": result_events[-1].id,
            }
        )
        final_record, final_events = await self._uow.append_run_checkpoint_with_events(
            decision.checkpoint,
            prior_events=(goal_event,),
            trace_id=trace_id,
            correlation_id=correlation_id,
            actor=DomainEventActor.AGENT,
            checkpoint_id=self._checkpoint_id(
                run.id,
                "post-verification",
                packet.manifest.context_sha256,
            ),
            checkpoint_event_id=self._event_id(
                run.id,
                "checkpoint.post-verification",
                packet.manifest.context_sha256,
            ),
            lease=lease,
            lease_checked_at=completed_at,
        )
        terminal_status = (
            RunStatus.COMPLETED
            if decision.outcome is GoalLoopOutcome.ACHIEVED
            else RunStatus.BLOCKED
        )
        if decision.stop_reason is None:
            raise CommerceVerificationTurnError(
                "Terminal Verification decision is missing stop_reason"
            )
        terminal_at = self._checked_time(completed_at)
        terminal = run.transition_to(
            terminal_status,
            stop_reason=decision.stop_reason.value,
            occurred_at=terminal_at,
        )
        await self._uow.save_run(
            terminal,
            expected_version=run.version,
            trace_id=trace_id,
            correlation_id=correlation_id,
            actor=DomainEventActor.AGENT,
            causation_event_id=final_events[-1].id,
            lease=lease,
            lease_checked_at=terminal_at,
        )
        await self._leases.release(
            workspace_id,
            run.id,
            lease,
            released_at=self._checked_time(terminal_at),
            trace_id=trace_id,
            correlation_id=correlation_id,
        )
        return CommerceVerificationTurnResult(
            verification=verification,
            verified_hypothesis_ids=tuple(item.id for item in verified),
            goal_decision=decision,
            final_checkpoint=final_record,
            run=terminal,
        )

    async def _load_proposed_hypotheses(
        self,
        workspace_id: WorkspaceId,
        case_id,
        hypothesis_ids: tuple[HypothesisId, ...],
    ) -> tuple[Hypothesis, ...]:
        loaded: list[Hypothesis] = []
        for hypothesis_id in hypothesis_ids:
            item = await self._hypotheses.get_latest(workspace_id, hypothesis_id)
            if (
                item is None
                or item.case_id != case_id
                or item.workspace_id != workspace_id
                or item.version != 1
            ):
                raise CommerceVerificationTurnError(
                    "Fresh Verification requires current proposed Hypothesis v1"
                )
            loaded.append(item)
        return tuple(loaded)

    async def _advance_to_verifying(
        self,
        run: CommerceRun,
        *,
        lease: RunLeaseCredentials,
        trace_id: TraceId,
        correlation_id: CorrelationId,
    ) -> CommerceRun:
        checked_at = self._checked_time(run.updated_at)
        verifying = run.advance_phase(
            RunPhase.VERIFYING,
            occurred_at=checked_at,
        )
        await self._uow.save_run(
            verifying,
            expected_version=run.version,
            trace_id=trace_id,
            correlation_id=correlation_id,
            actor=DomainEventActor.AGENT,
            lease=lease,
            lease_checked_at=checked_at,
        )
        return verifying

    async def _require_case(
        self,
        workspace_id: WorkspaceId,
        case_id,
    ) -> Case:
        case = await self._cases.get(workspace_id, case_id)
        if case is None:
            raise CommerceVerificationTurnError(
                f"Case disappeared during Verification: {case_id}"
            )
        return case

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

    @staticmethod
    def _task_id(run_id: RunId, discriminator: str) -> AgentTaskId:
        return AgentTaskId(
            f"task_{uuid5(NAMESPACE_URL, f'{run_id}:verification:{discriminator}').hex}"
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
