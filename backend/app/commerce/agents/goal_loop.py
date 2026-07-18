"""Deterministic Goal Loop state, stop conditions, and safe checkpoints."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from app.commerce.agents.budget import (
    BudgetDimension,
    BudgetExceededError,
    BudgetManager,
    BudgetSnapshot,
)
from app.commerce.agents.model_router import ModelAssignment
from app.commerce.domain.events import DomainEventActor, NewDomainEvent
from app.commerce.domain.ids import (
    AgentTaskId,
    CaseId,
    CorrelationId,
    EvidenceId,
    HypothesisId,
    RunId,
    TraceId,
    WorkspaceId,
)
from app.commerce.domain.models import CommerceModel


class GoalLoopAction(StrEnum):
    CONTINUE = "continue"
    STOP = "stop"


class GoalLoopOutcome(StrEnum):
    IN_PROGRESS = "in_progress"
    ACHIEVED = "achieved"
    PARTIAL = "partial"
    WAITING = "waiting"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"


class GoalStopReason(StrEnum):
    GOAL_ACHIEVED = "goal_achieved"
    GOAL_PARTIALLY_ACHIEVED = "goal_partially_achieved"
    AWAITING_USER_INPUT = "awaiting_user_input"
    AWAITING_APPROVAL = "awaiting_approval"
    CAPABILITY_BLOCKED = "capability_blocked"
    BUDGET_EXCEEDED = "budget_exceeded"
    NO_NEW_EVIDENCE = "no_new_evidence"
    POLICY_BLOCKED = "policy_blocked"
    TOOL_FAILURE = "tool_failure"
    CANCELLED = "cancelled"


class GoalLoopReasonCode(StrEnum):
    PROGRESS_RECORDED = "progress_recorded"
    EVIDENCE_GAP_REMAINS = "evidence_gap_remains"
    GOAL_COMPLETE = "goal_complete"
    PARTIAL_RESULT_PRESERVED = "partial_result_preserved"
    WAIT_REQUIRED = "wait_required"
    TERMINAL_BLOCK = "terminal_block"
    BUDGET_LIMIT_REACHED = "budget_limit_reached"
    NO_PROGRESS_THRESHOLD_REACHED = "no_progress_threshold_reached"
    TERMINAL_TOOL_FAILURE = "terminal_tool_failure"
    USER_CANCELLED = "user_cancelled"


class ToolStateStatus(StrEnum):
    PLANNED = "planned"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DENIED = "denied"


class ToolStateDigest(CommerceModel):
    tool_name: str = Field(min_length=1)
    status: ToolStateStatus
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    error_code: str | None = Field(default=None, min_length=1)


class SkillVersionRef(CommerceModel):
    skill_id: str = Field(min_length=1)
    version: str = Field(min_length=1)


class GoalLoopState(CommerceModel):
    schema_version: str = "1.0"
    workspace_id: WorkspaceId
    run_id: RunId
    case_id: CaseId
    goal: str = Field(min_length=1)
    loop_iteration: int = Field(default=0, ge=0)
    evidence_ids: tuple[EvidenceId, ...] = ()
    hypothesis_ids: tuple[HypothesisId, ...] = ()
    active_path_task_ids: tuple[AgentTaskId, ...] = ()
    model_assignments: tuple[ModelAssignment, ...] = ()
    skill_versions: tuple[SkillVersionRef, ...] = ()
    context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    tool_state: tuple[ToolStateDigest, ...] = ()
    resume_token_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )

    @model_validator(mode="after")
    def keep_references_unique(self) -> Self:
        _require_unique("Evidence", self.evidence_ids)
        _require_unique("Hypothesis", self.hypothesis_ids)
        _require_unique("active Path Task", self.active_path_task_ids)
        return self


class GoalLoopProgress(CommerceModel):
    new_evidence_ids: tuple[EvidenceId, ...] = ()
    updated_hypothesis_ids: tuple[HypothesisId, ...] = ()
    remaining_evidence_gaps: tuple[str, ...] = ()
    goal_achieved: bool = False
    partial_goal_achieved: bool = False
    no_viable_next_step: bool = False
    awaiting_user_input: bool = False
    awaiting_approval: bool = False
    capability_blocked: bool = False
    policy_blocked: bool = False
    tool_failure: bool = False
    cancelled: bool = False

    @model_validator(mode="after")
    def reject_conflicting_terminal_signals(self) -> Self:
        terminal_flags = (
            self.goal_achieved,
            self.awaiting_user_input,
            self.awaiting_approval,
            self.capability_blocked,
            self.policy_blocked,
            self.tool_failure,
            self.cancelled,
        )
        if sum(terminal_flags) > 1:
            raise ValueError("GoalLoopProgress has conflicting terminal signals")
        if self.goal_achieved and self.remaining_evidence_gaps:
            raise ValueError("Achieved Goal cannot retain evidence gaps")
        if self.no_viable_next_step and not self.partial_goal_achieved:
            raise ValueError("No viable next step requires a partial Goal result")
        _require_unique("new Evidence", self.new_evidence_ids)
        _require_unique("updated Hypothesis", self.updated_hypothesis_ids)
        return self


class GoalLoopCheckpoint(CommerceModel):
    schema_version: str = "commerce.goal-loop-checkpoint@1.0.0"
    workspace_id: WorkspaceId
    run_id: RunId
    case_id: CaseId
    goal: str = Field(min_length=1)
    loop_iteration: int = Field(ge=0)
    budget_snapshot: BudgetSnapshot
    evidence_ids: tuple[EvidenceId, ...] = ()
    hypothesis_ids: tuple[HypothesisId, ...] = ()
    active_path_task_ids: tuple[AgentTaskId, ...] = ()
    model_assignments: tuple[ModelAssignment, ...] = ()
    skill_versions: tuple[SkillVersionRef, ...] = ()
    context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    tool_state: tuple[ToolStateDigest, ...] = ()
    wait_reason: GoalStopReason | None = None
    resume_token_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )

    @model_validator(mode="after")
    def match_budget_iteration(self) -> Self:
        if self.loop_iteration != self.budget_snapshot.usage.iterations:
            raise ValueError("Checkpoint iteration must match Budget usage")
        if self.wait_reason not in {
            None,
            GoalStopReason.AWAITING_USER_INPUT,
            GoalStopReason.AWAITING_APPROVAL,
        }:
            raise ValueError("Checkpoint wait_reason must describe a resumable wait")
        return self


class GoalLoopDecision(CommerceModel):
    action: GoalLoopAction
    outcome: GoalLoopOutcome
    stop_reason: GoalStopReason | None = None
    reason_codes: frozenset[GoalLoopReasonCode] = Field(min_length=1)
    budget_dimension: BudgetDimension | None = None
    state: GoalLoopState
    checkpoint: GoalLoopCheckpoint

    @model_validator(mode="after")
    def keep_action_and_stop_reason_consistent(self) -> Self:
        if self.action is GoalLoopAction.CONTINUE:
            if self.stop_reason is not None:
                raise ValueError("Continue decision cannot carry stop_reason")
            if self.outcome is not GoalLoopOutcome.IN_PROGRESS:
                raise ValueError("Continue decision must remain in_progress")
        elif self.stop_reason is None:
            raise ValueError("Stop decision requires stop_reason")
        if self.state.loop_iteration != self.checkpoint.loop_iteration:
            raise ValueError("Decision State and Checkpoint iterations must match")
        if self.state.run_id != self.checkpoint.run_id:
            raise ValueError("Decision State and Checkpoint Runs must match")
        return self


class GoalLoopController:
    """Consume one iteration, normalize progress, and decide Continue or Stop."""

    def __init__(self, budget: BudgetManager) -> None:
        self._budget = budget

    async def advance(
        self,
        state: GoalLoopState,
        progress: GoalLoopProgress,
    ) -> GoalLoopDecision:
        if state.loop_iteration != self._budget.snapshot.usage.iterations:
            raise ValueError("GoalLoop State iteration does not match Budget usage")

        known_evidence = set(state.evidence_ids)
        effective_new_evidence = tuple(
            evidence_id
            for evidence_id in progress.new_evidence_ids
            if evidence_id not in known_evidence
        )
        try:
            snapshot = await self._budget.record_iteration(
                has_new_evidence=bool(effective_new_evidence)
            )
        except BudgetExceededError as error:
            reason = (
                GoalStopReason.NO_NEW_EVIDENCE
                if error.dimension
                is BudgetDimension.CONSECUTIVE_NO_NEW_EVIDENCE
                else GoalStopReason.BUDGET_EXCEEDED
            )
            reason_code = (
                GoalLoopReasonCode.NO_PROGRESS_THRESHOLD_REACHED
                if reason is GoalStopReason.NO_NEW_EVIDENCE
                else GoalLoopReasonCode.BUDGET_LIMIT_REACHED
            )
            return self._stop(
                state,
                self._budget.snapshot,
                reason=reason,
                outcome=GoalLoopOutcome.BLOCKED,
                reason_codes=frozenset({reason_code}),
                budget_dimension=error.dimension,
            )

        updated_state = state.model_copy(
            update={
                "loop_iteration": snapshot.usage.iterations,
                "evidence_ids": _merge_unique(
                    state.evidence_ids,
                    effective_new_evidence,
                ),
                "hypothesis_ids": _merge_unique(
                    state.hypothesis_ids,
                    progress.updated_hypothesis_ids,
                ),
            }
        )

        terminal = self._terminal_decision(updated_state, progress, snapshot)
        if terminal is not None:
            return terminal

        if (
            snapshot.usage.consecutive_no_new_evidence
            >= snapshot.limit.max_consecutive_no_new_evidence
        ):
            return self._stop(
                updated_state,
                snapshot,
                reason=GoalStopReason.NO_NEW_EVIDENCE,
                outcome=GoalLoopOutcome.PARTIAL,
                reason_codes=frozenset(
                    {GoalLoopReasonCode.NO_PROGRESS_THRESHOLD_REACHED}
                ),
            )

        reasons = {GoalLoopReasonCode.PROGRESS_RECORDED}
        if progress.remaining_evidence_gaps:
            reasons.add(GoalLoopReasonCode.EVIDENCE_GAP_REMAINS)
        return GoalLoopDecision(
            action=GoalLoopAction.CONTINUE,
            outcome=GoalLoopOutcome.IN_PROGRESS,
            reason_codes=frozenset(reasons),
            state=updated_state,
            checkpoint=self._checkpoint(updated_state, snapshot),
        )

    def _terminal_decision(
        self,
        state: GoalLoopState,
        progress: GoalLoopProgress,
        snapshot: BudgetSnapshot,
    ) -> GoalLoopDecision | None:
        if progress.goal_achieved:
            return self._stop(
                state,
                snapshot,
                reason=GoalStopReason.GOAL_ACHIEVED,
                outcome=GoalLoopOutcome.ACHIEVED,
                reason_codes=frozenset({GoalLoopReasonCode.GOAL_COMPLETE}),
            )
        if progress.awaiting_user_input:
            return self._stop(
                state,
                snapshot,
                reason=GoalStopReason.AWAITING_USER_INPUT,
                outcome=GoalLoopOutcome.WAITING,
                reason_codes=frozenset({GoalLoopReasonCode.WAIT_REQUIRED}),
            )
        if progress.awaiting_approval:
            return self._stop(
                state,
                snapshot,
                reason=GoalStopReason.AWAITING_APPROVAL,
                outcome=GoalLoopOutcome.WAITING,
                reason_codes=frozenset({GoalLoopReasonCode.WAIT_REQUIRED}),
            )
        if progress.capability_blocked:
            return self._stop(
                state,
                snapshot,
                reason=GoalStopReason.CAPABILITY_BLOCKED,
                outcome=(
                    GoalLoopOutcome.PARTIAL
                    if progress.partial_goal_achieved
                    else GoalLoopOutcome.BLOCKED
                ),
                reason_codes=frozenset(
                    {
                        GoalLoopReasonCode.TERMINAL_BLOCK,
                        *(
                            {GoalLoopReasonCode.PARTIAL_RESULT_PRESERVED}
                            if progress.partial_goal_achieved
                            else set()
                        ),
                    }
                ),
            )
        if progress.policy_blocked:
            return self._stop(
                state,
                snapshot,
                reason=GoalStopReason.POLICY_BLOCKED,
                outcome=GoalLoopOutcome.BLOCKED,
                reason_codes=frozenset({GoalLoopReasonCode.TERMINAL_BLOCK}),
            )
        if progress.tool_failure:
            return self._stop(
                state,
                snapshot,
                reason=GoalStopReason.TOOL_FAILURE,
                outcome=GoalLoopOutcome.FAILED,
                reason_codes=frozenset(
                    {GoalLoopReasonCode.TERMINAL_TOOL_FAILURE}
                ),
            )
        if progress.cancelled:
            return self._stop(
                state,
                snapshot,
                reason=GoalStopReason.CANCELLED,
                outcome=GoalLoopOutcome.CANCELLED,
                reason_codes=frozenset({GoalLoopReasonCode.USER_CANCELLED}),
            )
        if progress.partial_goal_achieved and progress.no_viable_next_step:
            return self._stop(
                state,
                snapshot,
                reason=GoalStopReason.GOAL_PARTIALLY_ACHIEVED,
                outcome=GoalLoopOutcome.PARTIAL,
                reason_codes=frozenset(
                    {GoalLoopReasonCode.PARTIAL_RESULT_PRESERVED}
                ),
            )
        return None

    def _stop(
        self,
        state: GoalLoopState,
        snapshot: BudgetSnapshot,
        *,
        reason: GoalStopReason,
        outcome: GoalLoopOutcome,
        reason_codes: frozenset[GoalLoopReasonCode],
        budget_dimension: BudgetDimension | None = None,
    ) -> GoalLoopDecision:
        wait_reason = (
            reason
            if reason
            in {
                GoalStopReason.AWAITING_USER_INPUT,
                GoalStopReason.AWAITING_APPROVAL,
            }
            else None
        )
        return GoalLoopDecision(
            action=GoalLoopAction.STOP,
            outcome=outcome,
            stop_reason=reason,
            reason_codes=reason_codes,
            budget_dimension=budget_dimension,
            state=state,
            checkpoint=self._checkpoint(
                state,
                snapshot,
                wait_reason=wait_reason,
            ),
        )

    @staticmethod
    def _checkpoint(
        state: GoalLoopState,
        snapshot: BudgetSnapshot,
        *,
        wait_reason: GoalStopReason | None = None,
    ) -> GoalLoopCheckpoint:
        return GoalLoopCheckpoint(
            workspace_id=state.workspace_id,
            run_id=state.run_id,
            case_id=state.case_id,
            goal=state.goal,
            loop_iteration=state.loop_iteration,
            budget_snapshot=snapshot,
            evidence_ids=state.evidence_ids,
            hypothesis_ids=state.hypothesis_ids,
            active_path_task_ids=state.active_path_task_ids,
            model_assignments=state.model_assignments,
            skill_versions=state.skill_versions,
            context_sha256=state.context_sha256,
            tool_state=state.tool_state,
            wait_reason=wait_reason,
            resume_token_sha256=state.resume_token_sha256,
        )


def _merge_unique(existing: tuple, additions: tuple) -> tuple:
    return tuple(dict.fromkeys((*existing, *additions)))


def _require_unique(label: str, values: tuple) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"{label} references must be unique")


def build_goal_loop_decision_event(
    decision: GoalLoopDecision,
    *,
    trace_id: TraceId,
    correlation_id: CorrelationId,
) -> NewDomainEvent:
    """Expose real Loop decisions to the authoritative Domain Event stream."""

    if decision.stop_reason is GoalStopReason.BUDGET_EXCEEDED:
        event_type = "budget.exceeded"
    elif decision.action is GoalLoopAction.CONTINUE:
        event_type = "goal_loop.continued"
    else:
        event_type = "goal_loop.stopped"
    return NewDomainEvent(
        workspace_id=decision.state.workspace_id,
        case_id=decision.state.case_id,
        run_id=decision.state.run_id,
        event_type=event_type,
        trace_id=trace_id,
        correlation_id=correlation_id,
        actor=DomainEventActor.AGENT,
        payload={
            "action": decision.action.value,
            "outcome": decision.outcome.value,
            "stop_reason": (
                decision.stop_reason.value if decision.stop_reason else None
            ),
            "reason_codes": sorted(reason.value for reason in decision.reason_codes),
            "budget_dimension": (
                decision.budget_dimension.value
                if decision.budget_dimension
                else None
            ),
            "loop_iteration": decision.state.loop_iteration,
            "budget_usage": decision.checkpoint.budget_snapshot.usage.model_dump(
                mode="json"
            ),
            "checkpoint_schema_version": decision.checkpoint.schema_version,
        },
    )
