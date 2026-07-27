"""Deterministic shared Checkpoint ledger for parallel Path outcomes."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.commerce.agents.budget import BudgetSnapshot, BudgetUsage
from app.commerce.agents.contracts import AgentBudgetLimit, ModelProfile, PathType
from app.commerce.agents.fanout_checkpoint import (
    FanoutCheckpointError,
    FanoutCheckpointLedger,
)
from app.commerce.agents.goal_loop import GoalLoopCheckpoint
from app.commerce.agents.model_router import (
    ModelAssignment,
    ModelEffort,
    ModelRole,
    ModelRouteReasonCode,
)
from app.commerce.agents.path_result import (
    ModelExecutionTrace,
    PathCost,
    PathResult,
    PathUnknown,
    ToolCallStatus,
    ToolCallTrace,
)
from app.commerce.agents.subagent_adapter import (
    CommerceAgentTask,
    CommerceSubagentErrorCode,
    CommerceSubagentOutcome,
    CommerceSubagentStatus,
    CommerceSubagentToolEvent,
    CommerceSubagentToolStatus,
)
from app.commerce.domain.ids import (
    AgentTaskId,
    CaseId,
    CorrelationId,
    RunId,
    TraceId,
    WorkspaceId,
)

NOW = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)


def _assignment() -> ModelAssignment:
    return ModelAssignment(
        role=ModelRole.PATH,
        base_profile=ModelProfile.BALANCED_TOOL_USER,
        profile=ModelProfile.BALANCED_TOOL_USER,
        model_alias="deepseek-reasoner",
        effort=ModelEffort.MEDIUM,
        max_output_tokens=1_600,
        timeout_seconds=120,
        reason_codes=frozenset({ModelRouteReasonCode.PROFILE_BINDING}),
        escalation_count=0,
    )


def _task(
    identity,
    path_type: PathType,
    *,
    context_sha256: str,
) -> CommerceAgentTask:
    workspace_id, case_id, run_id = identity
    return CommerceAgentTask(
        workspace_id=workspace_id,
        case_id=case_id,
        run_id=run_id,
        task_id=AgentTaskId.new(),
        path_type=path_type,
        subagent_name=f"commerce-{path_type.value}-path",
        context_sha256=context_sha256,
        budget=AgentBudgetLimit(max_path_agents=0),
        model_assignment=_assignment(),
        skill_id=f"commerce.{path_type.value}-investigation",
        skill_version="1.0.0",
        allowed_tools=frozenset({"metric_query"}),
        expected_result_schema="commerce.path_result@1.0.0",
        lease_worker_id="fanout-worker",
        fencing_token=1,
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
        issued_at=NOW,
    )


def _base(identity, *, max_path_agents=3, max_tokens=1_000):
    workspace_id, case_id, run_id = identity
    limit = AgentBudgetLimit(
        max_iterations=4,
        max_path_agents=max_path_agents,
        max_tokens=max_tokens,
        max_tool_calls=20,
    )
    return GoalLoopCheckpoint(
        workspace_id=workspace_id,
        case_id=case_id,
        run_id=run_id,
        goal="Investigate selected paths",
        loop_iteration=0,
        budget_snapshot=BudgetSnapshot(limit=limit, usage=BudgetUsage()),
        context_sha256="f" * 64,
    )


def _completed(task):
    result = PathResult(
        path_type=task.path_type,
        unknowns=(
            PathUnknown(
                question="What remains unknown?",
                reason="Bounded test result",
            ),
        ),
        tool_calls=(
            ToolCallTrace(
                tool_name="metric_query",
                status=ToolCallStatus.SUCCEEDED,
                request_sha256="a" * 64,
                response_sha256="b" * 64,
                latency_ms=5,
            ),
        ),
        cost=PathCost(
            input_tokens=20,
            output_tokens=10,
            latency_ms=100,
            tool_call_count=1,
        ),
        trace_id=task.trace_id,
        model_assignment=task.model_assignment,
        model_execution=ModelExecutionTrace(
            provider_request_id="provider-request",
            actual_model_identity="deepseek-v4-flash",
            retry_count=0,
            stop_reason="stop",
            prompt_version="commerce-path@1.0.0",
            context_version="commerce-context@1.0.0",
        ),
        skill_version=f"{task.skill_id}@{task.skill_version}",
        context_sha256=task.context_sha256,
    )
    return CommerceSubagentOutcome(
        task_id=task.task_id,
        path_type=task.path_type,
        status=CommerceSubagentStatus.COMPLETED,
        harness_trace_id=str(task.trace_id),
        result=result,
        result_sha256="c" * 64,
        tool_events=(
            CommerceSubagentToolEvent(
                tool_call_id="runtime-call-1",
                tool_name="metric_query",
                status=CommerceSubagentToolStatus.SUCCEEDED,
                request_sha256="d" * 64,
                response_sha256="e" * 64,
                latency_ms=6,
            ),
            CommerceSubagentToolEvent(
                tool_call_id="runtime-call-2",
                tool_name="metric_query",
                status=CommerceSubagentToolStatus.SUCCEEDED,
                request_sha256="1" * 64,
                response_sha256="2" * 64,
                latency_ms=7,
            ),
        ),
    )


def _blocked(task):
    return CommerceSubagentOutcome(
        task_id=task.task_id,
        path_type=task.path_type,
        status=CommerceSubagentStatus.BLOCKED,
        harness_trace_id=str(task.trace_id),
        error_code=CommerceSubagentErrorCode.INVALID_PATH_RESULT,
        error_message="bounded failure",
        tool_events=(
            CommerceSubagentToolEvent(
                tool_call_id="failed-runtime-call",
                tool_name="metric_query",
                status=CommerceSubagentToolStatus.FAILED,
                request_sha256="3" * 64,
                response_sha256="4" * 64,
                latency_ms=8,
                error_code="tool_execution_failed",
            ),
        ),
    )


def test_checkpoint_ledger_accumulates_parallel_usage_and_never_reactivates_tasks():
    identity = (WorkspaceId.new(), CaseId.new(), RunId.new())
    fulfillment = _task(
        identity,
        PathType.FULFILLMENT,
        context_sha256="a" * 64,
    )
    peer = _task(identity, PathType.SELLER_PEER, context_sha256="b" * 64)
    ledger = FanoutCheckpointLedger(
        base=_base(identity),
        tasks=(fulfillment, peer),
    )

    fulfillment_pre = ledger.pre_checkpoint(fulfillment)
    peer_pre = ledger.pre_checkpoint(peer)
    fulfillment_post = ledger.complete(fulfillment, _completed(fulfillment))
    peer_post = ledger.complete(peer, _blocked(peer))

    assert fulfillment_pre.active_path_task_ids == (fulfillment.task_id, peer.task_id)
    assert peer_pre.active_path_task_ids == (fulfillment.task_id, peer.task_id)
    assert fulfillment_pre.context_sha256 == fulfillment.context_sha256
    assert peer_pre.context_sha256 == peer.context_sha256
    assert fulfillment_post.active_path_task_ids == (peer.task_id,)
    assert fulfillment_post.budget_snapshot.usage.path_agents == 1
    assert fulfillment_post.budget_snapshot.usage.tokens == 30
    assert fulfillment_post.budget_snapshot.usage.tool_calls == 3
    assert fulfillment_post.budget_snapshot.usage.wall_time_seconds == 0.1
    assert peer_post.active_path_task_ids == ()
    assert peer_post.budget_snapshot.usage.path_agents == 2
    assert peer_post.budget_snapshot.usage.tokens == 30
    assert peer_post.budget_snapshot.usage.tool_calls == 4
    assert peer_post.context_sha256 == peer.context_sha256


def test_checkpoint_ledger_completion_is_idempotent_per_task():
    identity = (WorkspaceId.new(), CaseId.new(), RunId.new())
    task = _task(identity, PathType.FULFILLMENT, context_sha256="a" * 64)
    ledger = FanoutCheckpointLedger(base=_base(identity), tasks=(task,))
    outcome = _completed(task)

    first = ledger.complete(task, outcome)
    repeated = ledger.complete(task, outcome)

    assert repeated == first
    assert repeated.budget_snapshot.usage.path_agents == 1
    assert repeated.budget_snapshot.usage.tokens == 30


def test_checkpoint_ledger_rejects_path_count_beyond_run_budget():
    identity = (WorkspaceId.new(), CaseId.new(), RunId.new())
    tasks = (
        _task(identity, PathType.FULFILLMENT, context_sha256="a" * 64),
        _task(identity, PathType.SELLER_PEER, context_sha256="b" * 64),
    )

    with pytest.raises(FanoutCheckpointError, match="path-agent budget"):
        FanoutCheckpointLedger(
            base=_base(identity, max_path_agents=1),
            tasks=tasks,
        )
