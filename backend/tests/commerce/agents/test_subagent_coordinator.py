"""Deterministic Case-level assembly for prepared Commerce Subagents."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from app.commerce.agents.budget import BudgetSnapshot, BudgetUsage
from app.commerce.agents.contracts import AgentBudgetLimit, ModelProfile, PathType
from app.commerce.agents.goal_loop import GoalLoopCheckpoint
from app.commerce.agents.model_router import (
    ModelAssignment,
    ModelEffort,
    ModelRole,
    ModelRouteReasonCode,
)
from app.commerce.agents.subagent_adapter import CommerceAgentTask
from app.commerce.agents.subagent_coordinator import (
    CommerceSubagentCoordinator,
    PreparedCommercePath,
)
from app.commerce.domain.ids import (
    CaseId,
    CorrelationId,
    RunId,
    WorkspaceId,
)
from app.commerce.persistence.runs import RunLeaseCredentials


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


def _base(identity):
    workspace_id, case_id, run_id = identity
    limit = AgentBudgetLimit(max_iterations=4, max_tokens=16_000)
    return GoalLoopCheckpoint(
        workspace_id=workspace_id,
        case_id=case_id,
        run_id=run_id,
        goal="Investigate selected paths",
        loop_iteration=0,
        budget_snapshot=BudgetSnapshot(limit=limit, usage=BudgetUsage()),
        context_sha256="f" * 64,
    )


class _Spec:
    def __init__(self, identity, path_type, context_sha256):
        self.identity = identity
        self.plan = SimpleNamespace(
            assignment=_assignment(),
            context=SimpleNamespace(
                path_type=path_type,
                manifest=SimpleNamespace(context_sha256=context_sha256),
            ),
        )
        self.adapters = []

    def build_task(self, **kwargs):
        workspace_id, case_id, _run_id = self.identity
        context = self.plan.context
        return CommerceAgentTask(
            workspace_id=workspace_id,
            case_id=case_id,
            run_id=kwargs["run_id"],
            task_id=kwargs["task_id"],
            path_type=context.path_type,
            subagent_name=f"commerce-{context.path_type.value}-path",
            context_sha256=context.manifest.context_sha256,
            budget=AgentBudgetLimit(max_path_agents=0),
            model_assignment=self.plan.assignment,
            skill_id=f"commerce.{context.path_type.value}-investigation",
            skill_version="1.0.0",
            allowed_tools=frozenset({"metric_query"}),
            expected_result_schema="commerce.path_result@1.0.0",
            lease_worker_id=kwargs["lease_worker_id"],
            fencing_token=kwargs["fencing_token"],
            trace_id=kwargs["trace_id"],
            correlation_id=kwargs["correlation_id"],
        )

    def build_adapter(self, *, tools):
        adapter = SimpleNamespace(tools=tools, path_type=self.plan.context.path_type)
        self.adapters.append(adapter)
        return adapter


class _Fanout:
    def __init__(self):
        self.calls = []
        self.result = SimpleNamespace(kind="fanout-result")

    async def run(self, entries):
        self.calls.append(entries)
        return self.result


def _lease():
    return RunLeaseCredentials(
        worker_id="coordinator-worker",
        lease_token=SecretStr("lease-token"),
        fencing_token=4,
    )


@pytest.mark.anyio
async def test_coordinator_gates_builds_stable_tasks_and_shared_checkpoint_ledger():
    identity = (WorkspaceId.new(), CaseId.new(), RunId.new())
    fulfillment = _Spec(identity, PathType.FULFILLMENT, "a" * 64)
    peer = _Spec(identity, PathType.SELLER_PEER, "b" * 64)
    built_tools = []

    def tool_builder(context):
        built_tools.append(context.path_type)
        return (SimpleNamespace(name="metric_query"),)

    preflights = []

    async def preflight(alias):
        preflights.append(alias)

    supervisors = []

    def supervisor_factory(**kwargs):
        supervisor = SimpleNamespace(kwargs=kwargs)
        supervisors.append(supervisor)
        return supervisor

    fanout = _Fanout()
    coordinator = CommerceSubagentCoordinator(
        committer=object(),
        leases=object(),
        barrier=object(),
        lease_ttl=timedelta(minutes=5),
        preflight_gate=preflight,
        supervisor_factory=supervisor_factory,
        fanout=fanout,
        poll_interval_seconds=0.1,
        max_polls=40,
    )

    result = await coordinator.run(
        prepared_paths=(
            PreparedCommercePath(fulfillment, tool_builder),
            PreparedCommercePath(peer, tool_builder),
        ),
        run_id=identity[2],
        base_checkpoint=_base(identity),
        lease=_lease(),
        correlation_id=CorrelationId.new(),
    )

    assert result is fanout.result
    assert preflights == ["deepseek-reasoner", "deepseek-reasoner"]
    assert built_tools == [PathType.FULFILLMENT, PathType.SELLER_PEER]
    assert len(supervisors) == 2
    entries = fanout.calls[0]
    assert len(entries) == 2
    expected_ids = {
        CommerceSubagentCoordinator._task_id(identity[2], path_type.value)
        for path_type in (PathType.FULFILLMENT, PathType.SELLER_PEER)
    }
    assert {entry.task.task_id for entry in entries} == expected_ids
    assert all(
        set(entry.pre_checkpoint.active_path_task_ids) == expected_ids
        for entry in entries
    )
    assert {entry.pre_checkpoint.context_sha256 for entry in entries} == {
        "a" * 64,
        "b" * 64,
    }
    assert all(entry.lease.fencing_token == 4 for entry in entries)
    assert all(item.kwargs["max_polls"] == 40 for item in supervisors)


@pytest.mark.anyio
async def test_coordinator_zero_paths_releases_fanout_without_preflight():
    identity = (WorkspaceId.new(), CaseId.new(), RunId.new())
    preflights = []

    async def preflight(alias):
        preflights.append(alias)

    fanout = _Fanout()
    coordinator = CommerceSubagentCoordinator(
        committer=object(),
        leases=object(),
        barrier=object(),
        lease_ttl=timedelta(minutes=5),
        preflight_gate=preflight,
        fanout=fanout,
    )

    result = await coordinator.run(
        prepared_paths=(),
        run_id=identity[2],
        base_checkpoint=_base(identity),
        lease=_lease(),
        correlation_id=CorrelationId.new(),
    )

    assert result is fanout.result
    assert fanout.calls == [()]
    assert preflights == []


@pytest.mark.anyio
async def test_coordinator_stops_before_task_start_when_preflight_blocks():
    identity = (WorkspaceId.new(), CaseId.new(), RunId.new())
    spec = _Spec(identity, PathType.FULFILLMENT, "a" * 64)
    fanout = _Fanout()

    async def blocked(_alias):
        raise RuntimeError("blocked preflight")

    coordinator = CommerceSubagentCoordinator(
        committer=object(),
        leases=object(),
        barrier=object(),
        lease_ttl=timedelta(minutes=5),
        preflight_gate=blocked,
        fanout=fanout,
    )

    with pytest.raises(RuntimeError, match="blocked preflight"):
        await coordinator.run(
            prepared_paths=(
                PreparedCommercePath(
                    spec,
                    lambda _context: (SimpleNamespace(name="metric_query"),),
                ),
            ),
            run_id=identity[2],
            base_checkpoint=_base(identity),
            lease=_lease(),
            correlation_id=CorrelationId.new(),
        )

    assert fanout.calls == []
