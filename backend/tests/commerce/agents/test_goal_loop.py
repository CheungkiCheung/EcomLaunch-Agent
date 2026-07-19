"""Deterministic GoalLoop stop, progress, budget, and checkpoint contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.commerce.agents.budget import (
    BudgetDelta,
    BudgetDimension,
    BudgetExceededError,
    BudgetManager,
)
from app.commerce.agents.contracts import AgentBudgetLimit
from app.commerce.agents.goal_loop import (
    GoalLoopAction,
    GoalLoopCheckpoint,
    GoalLoopController,
    GoalLoopOutcome,
    GoalLoopProgress,
    GoalLoopState,
    GoalStopReason,
    build_goal_loop_decision_event,
)
from app.commerce.domain.ids import (
    CaseId,
    CorrelationId,
    EvidenceId,
    HypothesisId,
    RunId,
    TraceId,
    WorkspaceId,
)


def _state() -> GoalLoopState:
    return GoalLoopState(
        workspace_id=WorkspaceId.new(),
        run_id=RunId.new(),
        case_id=CaseId.new(),
        goal="Find the strongest traceable explanation for the anomaly",
        context_sha256="a" * 64,
        resume_token_sha256="b" * 64,
    )


@pytest.mark.anyio
async def test_goal_achieved_stops_immediately_and_persists_safe_checkpoint():
    controller = GoalLoopController(BudgetManager(AgentBudgetLimit()))
    evidence_id = EvidenceId.new()
    hypothesis_id = HypothesisId.new()

    decision = await controller.advance(
        _state(),
        GoalLoopProgress(
            goal_achieved=True,
            new_evidence_ids=(evidence_id,),
            updated_hypothesis_ids=(hypothesis_id,),
        ),
    )

    assert decision.action is GoalLoopAction.STOP
    assert decision.outcome is GoalLoopOutcome.ACHIEVED
    assert decision.stop_reason is GoalStopReason.GOAL_ACHIEVED
    assert decision.state.loop_iteration == 1
    assert decision.checkpoint.evidence_ids == (evidence_id,)
    assert decision.checkpoint.hypothesis_ids == (hypothesis_id,)
    assert decision.checkpoint.budget_snapshot.usage.iterations == 1

    checkpoint_payload = decision.checkpoint.model_dump()
    with pytest.raises(ValidationError):
        GoalLoopCheckpoint(**checkpoint_payload, api_key="secret")
    with pytest.raises(ValidationError):
        GoalLoopCheckpoint(**checkpoint_payload, chain_of_thought="private reasoning")


@pytest.mark.anyio
async def test_iteration_budget_exceeded_returns_explicit_stop_without_overconsumption():
    manager = BudgetManager(AgentBudgetLimit(max_iterations=1))
    controller = GoalLoopController(manager)
    first = await controller.advance(
        _state(),
        GoalLoopProgress(
            new_evidence_ids=(EvidenceId.new(),),
            remaining_evidence_gaps=("Review experience path remains",),
        ),
    )

    assert first.action is GoalLoopAction.CONTINUE

    second = await controller.advance(
        first.state,
        GoalLoopProgress(
            new_evidence_ids=(EvidenceId.new(),),
            remaining_evidence_gaps=("Peer comparison remains",),
        ),
    )

    assert second.action is GoalLoopAction.STOP
    assert second.stop_reason is GoalStopReason.BUDGET_EXCEEDED
    assert second.budget_dimension is BudgetDimension.ITERATIONS
    assert second.state.loop_iteration == 1
    assert manager.snapshot.usage.iterations == 1

    event = build_goal_loop_decision_event(
        second,
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
    )
    assert event.event_type == "budget.exceeded"
    assert event.payload["budget_dimension"] == "iterations"
    assert event.payload["loop_iteration"] == 1


@pytest.mark.anyio
async def test_consecutive_no_new_evidence_stops_at_threshold():
    manager = BudgetManager(
        AgentBudgetLimit(
            max_iterations=5,
            max_consecutive_no_new_evidence=2,
        )
    )
    controller = GoalLoopController(manager)
    first = await controller.advance(
        _state(),
        GoalLoopProgress(remaining_evidence_gaps=("Need carrier facts",)),
    )
    second = await controller.advance(
        first.state,
        GoalLoopProgress(remaining_evidence_gaps=("Need carrier facts",)),
    )

    assert first.action is GoalLoopAction.CONTINUE
    assert second.action is GoalLoopAction.STOP
    assert second.stop_reason is GoalStopReason.NO_NEW_EVIDENCE
    assert second.checkpoint.budget_snapshot.usage.consecutive_no_new_evidence == 2


@pytest.mark.anyio
async def test_new_evidence_resets_no_progress_streak():
    manager = BudgetManager(
        AgentBudgetLimit(
            max_iterations=5,
            max_consecutive_no_new_evidence=2,
        )
    )
    controller = GoalLoopController(manager)
    first = await controller.advance(
        _state(),
        GoalLoopProgress(remaining_evidence_gaps=("Need facts",)),
    )
    second = await controller.advance(
        first.state,
        GoalLoopProgress(
            new_evidence_ids=(EvidenceId.new(),),
            remaining_evidence_gaps=("Need another fact",),
        ),
    )
    third = await controller.advance(
        second.state,
        GoalLoopProgress(remaining_evidence_gaps=("Need another fact",)),
    )

    assert second.checkpoint.budget_snapshot.usage.consecutive_no_new_evidence == 0
    assert third.action is GoalLoopAction.CONTINUE
    assert third.checkpoint.budget_snapshot.usage.consecutive_no_new_evidence == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("progress", "expected_reason", "expected_outcome"),
    [
        (
            GoalLoopProgress(awaiting_user_input=True),
            GoalStopReason.AWAITING_USER_INPUT,
            GoalLoopOutcome.WAITING,
        ),
        (
            GoalLoopProgress(awaiting_approval=True),
            GoalStopReason.AWAITING_APPROVAL,
            GoalLoopOutcome.WAITING,
        ),
        (
            GoalLoopProgress(policy_blocked=True),
            GoalStopReason.POLICY_BLOCKED,
            GoalLoopOutcome.BLOCKED,
        ),
        (
            GoalLoopProgress(tool_failure=True),
            GoalStopReason.TOOL_FAILURE,
            GoalLoopOutcome.FAILED,
        ),
        (
            GoalLoopProgress(cancelled=True),
            GoalStopReason.CANCELLED,
            GoalLoopOutcome.CANCELLED,
        ),
    ],
)
async def test_terminal_signals_do_not_retry(
    progress: GoalLoopProgress,
    expected_reason: GoalStopReason,
    expected_outcome: GoalLoopOutcome,
):
    decision = await GoalLoopController(
        BudgetManager(AgentBudgetLimit())
    ).advance(_state(), progress)

    assert decision.action is GoalLoopAction.STOP
    assert decision.stop_reason is expected_reason
    assert decision.outcome is expected_outcome


@pytest.mark.anyio
async def test_capability_missing_preserves_partial_result_or_reports_blocked():
    partial = await GoalLoopController(
        BudgetManager(AgentBudgetLimit())
    ).advance(
        _state(),
        GoalLoopProgress(
            partial_goal_achieved=True,
            capability_blocked=True,
        ),
    )
    blocked = await GoalLoopController(
        BudgetManager(AgentBudgetLimit())
    ).advance(
        _state(),
        GoalLoopProgress(capability_blocked=True),
    )

    assert partial.stop_reason is GoalStopReason.CAPABILITY_BLOCKED
    assert partial.outcome is GoalLoopOutcome.PARTIAL
    assert blocked.stop_reason is GoalStopReason.CAPABILITY_BLOCKED
    assert blocked.outcome is GoalLoopOutcome.BLOCKED


@pytest.mark.anyio
async def test_partial_goal_without_viable_next_step_has_explicit_stop_reason():
    decision = await GoalLoopController(
        BudgetManager(AgentBudgetLimit())
    ).advance(
        _state(),
        GoalLoopProgress(
            partial_goal_achieved=True,
            no_viable_next_step=True,
        ),
    )

    assert decision.action is GoalLoopAction.STOP
    assert decision.stop_reason is GoalStopReason.GOAL_PARTIALLY_ACHIEVED
    assert decision.outcome is GoalLoopOutcome.PARTIAL


@pytest.mark.anyio
async def test_verification_rejection_stops_partial_result_for_explicit_replan():
    decision = await GoalLoopController(
        BudgetManager(AgentBudgetLimit())
    ).advance(
        _state(),
        GoalLoopProgress(
            partial_goal_achieved=True,
            verification_replan_required=True,
            remaining_evidence_gaps=("Rejected claim requires a new evidence plan",),
        ),
    )

    assert decision.action is GoalLoopAction.STOP
    assert decision.stop_reason is GoalStopReason.VERIFICATION_REPLAN_REQUIRED
    assert decision.outcome is GoalLoopOutcome.PARTIAL


@pytest.mark.anyio
async def test_exhausted_verification_repair_budget_preserves_partial_result():
    manager = BudgetManager(AgentBudgetLimit(max_verification_repairs=0))
    controller = GoalLoopController(manager)
    with pytest.raises(BudgetExceededError) as raised:
        await manager.consume(BudgetDelta(verification_repairs=1))

    decision = controller.stop_for_budget(
        _state(),
        raised.value,
        partial_goal_achieved=True,
    )

    assert decision.action is GoalLoopAction.STOP
    assert decision.outcome is GoalLoopOutcome.PARTIAL
    assert decision.stop_reason is GoalStopReason.BUDGET_EXCEEDED
    assert decision.budget_dimension is BudgetDimension.VERIFICATION_REPAIRS
    assert decision.checkpoint.budget_snapshot.usage.verification_repairs == 0
