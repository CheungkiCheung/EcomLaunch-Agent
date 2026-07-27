"""Deterministic continuous Lead action planning contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.commerce.agents.contracts import PathType, default_path_agent_specs
from app.commerce.agents.goal_loop import GoalStopReason
from app.commerce.agents.lead_loop import (
    LeadAction,
    LeadActionDecision,
    LeadActionReasonCode,
    LeadLoopPlanner,
    LeadPlanningState,
    LeadTurnIntent,
    LeadTurnRequest,
)
from app.commerce.agents.router import DynamicPathPlan, PathAssignment


def _route_plan(*path_types: PathType) -> DynamicPathPlan:
    specs = {item.path_type: item for item in default_path_agent_specs()}
    return DynamicPathPlan(
        assignments=tuple(
            PathAssignment(path_type=path_type, spec=specs[path_type])
            for path_type in path_types
        ),
        decisions=(),
    )


def test_initial_turn_investigates_only_routable_missing_paths():
    decision = LeadLoopPlanner().decide(
        request=LeadTurnRequest(intent=LeadTurnIntent.START),
        state=LeadPlanningState(
            completed_path_types=(PathType.FULFILLMENT,),
            persisted_evidence_count=2,
        ),
        route_plan=_route_plan(
            PathType.FULFILLMENT,
            PathType.SELLER_PEER,
            PathType.REVIEW_EXPERIENCE,
        ),
    )

    assert decision.action is LeadAction.INVESTIGATE
    assert decision.selected_paths == (
        PathType.SELLER_PEER,
        PathType.REVIEW_EXPERIENCE,
    )
    assert decision.reason_codes == frozenset(
        {LeadActionReasonCode.MISSING_PATH_EVIDENCE}
    )


def test_follow_up_over_existing_conclusions_is_read_only_answer():
    decision = LeadLoopPlanner().decide(
        request=LeadTurnRequest(
            intent=LeadTurnIntent.READ_ONLY_QUESTION,
            question="为什么判断问题集中在运输而不是商家处理？",
        ),
        state=LeadPlanningState(
            completed_path_types=(PathType.FULFILLMENT,),
            persisted_evidence_count=3,
            latest_hypothesis_count=1,
        ),
        route_plan=_route_plan(
            PathType.FULFILLMENT,
            PathType.SELLER_PEER,
        ),
    )

    assert decision.action is LeadAction.ANSWER
    assert decision.read_only is True
    assert decision.selected_paths == ()
    assert LeadActionReasonCode.EXISTING_CONCLUSION_SUFFICIENT in (
        decision.reason_codes
    )


def test_new_angle_replans_only_explicit_missing_paths():
    decision = LeadLoopPlanner().decide(
        request=LeadTurnRequest(
            intent=LeadTurnIntent.NEW_INVESTIGATION_ANGLE,
            question="再看一下同类卖家和评价体验",
            requested_paths=(
                PathType.SELLER_PEER,
                PathType.REVIEW_EXPERIENCE,
            ),
        ),
        state=LeadPlanningState(
            completed_path_types=(
                PathType.FULFILLMENT,
                PathType.REVIEW_EXPERIENCE,
            ),
            persisted_evidence_count=4,
            latest_hypothesis_count=1,
        ),
        route_plan=_route_plan(
            PathType.FULFILLMENT,
            PathType.SELLER_PEER,
            PathType.REVIEW_EXPERIENCE,
        ),
    )

    assert decision.action is LeadAction.REPLAN
    assert decision.selected_paths == (PathType.SELLER_PEER,)
    assert decision.read_only is False


def test_completed_or_unavailable_new_angle_answers_without_duplicate_path_run():
    completed = LeadLoopPlanner().decide(
        request=LeadTurnRequest(
            intent=LeadTurnIntent.NEW_INVESTIGATION_ANGLE,
            question="再看一次履约",
            requested_paths=(PathType.FULFILLMENT,),
        ),
        state=LeadPlanningState(
            completed_path_types=(PathType.FULFILLMENT,),
            persisted_evidence_count=2,
        ),
        route_plan=_route_plan(PathType.FULFILLMENT),
    )
    unavailable = LeadLoopPlanner().decide(
        request=LeadTurnRequest(
            intent=LeadTurnIntent.NEW_INVESTIGATION_ANGLE,
            question="检查评价体验",
            requested_paths=(PathType.REVIEW_EXPERIENCE,),
        ),
        state=LeadPlanningState(),
        route_plan=_route_plan(PathType.FULFILLMENT),
    )

    assert completed.action is LeadAction.ANSWER
    assert completed.selected_paths == ()
    assert LeadActionReasonCode.PATH_ALREADY_COMPLETED in completed.reason_codes
    assert unavailable.action is LeadAction.ANSWER
    assert unavailable.selected_paths == ()
    assert LeadActionReasonCode.CAPABILITY_GAP_REQUIRES_UNKNOWN in (
        unavailable.reason_codes
    )


def test_zero_path_start_returns_unknown_answer_instead_of_fake_activity():
    decision = LeadLoopPlanner().decide(
        request=LeadTurnRequest(intent=LeadTurnIntent.START),
        state=LeadPlanningState(),
        route_plan=_route_plan(),
    )

    assert decision.action is LeadAction.ANSWER
    assert decision.read_only is True
    assert decision.selected_paths == ()
    assert decision.reason_codes == frozenset(
        {LeadActionReasonCode.NO_ROUTABLE_PATH_REQUIRES_UNKNOWN}
    )


def test_wait_resume_and_cancel_have_explicit_stop_semantics():
    planner = LeadLoopPlanner()
    waiting = planner.decide(
        request=LeadTurnRequest(
            intent=LeadTurnIntent.WAIT,
            wait_reason=GoalStopReason.AWAITING_USER_INPUT,
        ),
        state=LeadPlanningState(),
        route_plan=_route_plan(PathType.FULFILLMENT),
    )
    resumed = planner.decide(
        request=LeadTurnRequest(intent=LeadTurnIntent.RESUME),
        state=LeadPlanningState(
            wait_reason=GoalStopReason.AWAITING_USER_INPUT,
        ),
        route_plan=_route_plan(PathType.FULFILLMENT),
    )
    cancelled = planner.decide(
        request=LeadTurnRequest(intent=LeadTurnIntent.CANCEL),
        state=LeadPlanningState(),
        route_plan=_route_plan(PathType.FULFILLMENT),
    )

    assert waiting.action is LeadAction.WAIT
    assert waiting.stop_reason is GoalStopReason.AWAITING_USER_INPUT
    assert resumed.action is LeadAction.INVESTIGATE
    assert LeadActionReasonCode.RESUMED_FROM_WAIT in resumed.reason_codes
    assert cancelled.action is LeadAction.STOP
    assert cancelled.stop_reason is GoalStopReason.CANCELLED


def test_action_contract_rejects_paths_on_read_only_answer():
    with pytest.raises(ValidationError, match="Answer cannot schedule Paths"):
        LeadActionDecision(
            action=LeadAction.ANSWER,
            selected_paths=(PathType.FULFILLMENT,),
            read_only=True,
            reason_codes=frozenset(
                {LeadActionReasonCode.EXISTING_CONCLUSION_SUFFICIENT}
            ),
        )
