"""Deterministic heartbeat and terminal supervision for Commerce Subagents."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from app.commerce.agents.contracts import AgentBudgetLimit, ModelProfile, PathType
from app.commerce.agents.model_router import (
    ModelAssignment,
    ModelEffort,
    ModelRole,
    ModelRouteReasonCode,
)
from app.commerce.agents.subagent_adapter import (
    CommerceAgentTask,
    CommerceSubagentErrorCode,
    CommerceSubagentOutcome,
    CommerceSubagentStatus,
)
from app.commerce.agents.subagent_committer import CommerceSubagentCommitReceipt
from app.commerce.agents.subagent_supervisor import (
    CommerceSubagentSupervisionError,
    CommerceSubagentSupervisor,
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
from app.commerce.persistence.runs import RunLeaseCredentials, RunLeaseLostError


def _task() -> CommerceAgentTask:
    assignment = ModelAssignment(
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
    return CommerceAgentTask(
        workspace_id=WorkspaceId.new(),
        case_id=CaseId.new(),
        run_id=RunId.new(),
        task_id=AgentTaskId.new(),
        path_type=PathType.FULFILLMENT,
        subagent_name="commerce-fulfillment-path",
        context_sha256="a" * 64,
        budget=AgentBudgetLimit(max_path_agents=0),
        model_assignment=assignment,
        skill_id="commerce.fulfillment-investigation",
        skill_version="1.0.0",
        allowed_tools=frozenset({"metric_query"}),
        expected_result_schema="commerce.path_result@1.0.0",
        lease_worker_id="commerce-subagent-worker",
        fencing_token=1,
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
    )


def _outcome(
    task: CommerceAgentTask,
    status: CommerceSubagentStatus,
) -> CommerceSubagentOutcome:
    if status in {CommerceSubagentStatus.PENDING, CommerceSubagentStatus.RUNNING}:
        return CommerceSubagentOutcome(
            task_id=task.task_id,
            path_type=task.path_type,
            status=status,
            harness_trace_id=str(task.trace_id),
        )
    error_code = {
        CommerceSubagentStatus.CANCELLED: CommerceSubagentErrorCode.HARNESS_CANCELLED,
        CommerceSubagentStatus.TIMED_OUT: CommerceSubagentErrorCode.HARNESS_TIMED_OUT,
        CommerceSubagentStatus.FAILED: CommerceSubagentErrorCode.HARNESS_FAILED,
    }[status]
    return CommerceSubagentOutcome(
        task_id=task.task_id,
        path_type=task.path_type,
        status=status,
        harness_trace_id=str(task.trace_id),
        error_code=error_code,
        error_message="Harness terminal state",
    )


class _Adapter:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.started = []
        self.cancelled = []
        self.cleaned = []

    def start(self, task, context):
        self.started.append((task, context))
        return task.task_id

    def poll(self, task):
        return self.outcomes.pop(0)

    def cancel(self, task):
        self.cancelled.append(task.task_id)

    def cleanup(self, task):
        self.cleaned.append(task.task_id)


class _Committer:
    def __init__(self):
        self.started = []
        self.outcomes = []

    async def commit_started(self, task, checkpoint, *, lease, checked_at):
        self.started.append((task, checkpoint, lease, checked_at))
        return CommerceSubagentCommitReceipt(
            task_id=task.task_id,
            path_type=task.path_type,
            status=CommerceSubagentStatus.RUNNING,
            checkpoint_id=CheckpointId.new(),
            lifecycle_event_id=EventId.new(),
        )

    async def commit_outcome(
        self,
        task,
        outcome,
        manifest,
        checkpoint,
        *,
        lease,
        checked_at,
        causation_event_id=None,
    ):
        self.outcomes.append(
            (
                task,
                outcome,
                manifest,
                checkpoint,
                lease,
                checked_at,
                causation_event_id,
            )
        )
        return CommerceSubagentCommitReceipt(
            task_id=task.task_id,
            path_type=task.path_type,
            status=outcome.status,
            checkpoint_id=CheckpointId.new(),
            lifecycle_event_id=EventId.new(),
        )


class _Leases:
    def __init__(self, *, fail_on_heartbeat: int | None = None):
        self.calls = []
        self.fail_on_heartbeat = fail_on_heartbeat

    async def heartbeat(
        self,
        workspace_id,
        run_id,
        credentials,
        *,
        ttl,
        heartbeat_at,
    ):
        self.calls.append((workspace_id, run_id, credentials, ttl, heartbeat_at))
        if self.fail_on_heartbeat == len(self.calls):
            raise RunLeaseLostError("stale lease")
        return SimpleNamespace(expires_at=heartbeat_at + ttl)


def _clock():
    values = iter(
        datetime(2026, 7, 19, 12, 0, second, tzinfo=UTC)
        for second in range(20)
    )
    return lambda: next(values)


async def _no_sleep(_seconds):
    return None


def _lease() -> RunLeaseCredentials:
    return RunLeaseCredentials(
        worker_id="commerce-subagent-worker",
        lease_token=SecretStr("secret-lease-token"),
        fencing_token=1,
    )


@pytest.mark.anyio
async def test_supervisor_heartbeats_until_terminal_commit_and_cleanup():
    task = _task()
    adapter = _Adapter(
        [
            _outcome(task, CommerceSubagentStatus.PENDING),
            _outcome(task, CommerceSubagentStatus.RUNNING),
            _outcome(task, CommerceSubagentStatus.CANCELLED),
        ]
    )
    committer = _Committer()
    leases = _Leases()
    post_checkpoint_outcomes = []

    def build_post_checkpoint(outcome):
        post_checkpoint_outcomes.append(outcome)
        return object()

    supervisor = CommerceSubagentSupervisor(
        adapter=adapter,
        committer=committer,
        leases=leases,
        lease_ttl=timedelta(seconds=30),
        poll_interval_seconds=0,
        max_polls=4,
        clock=_clock(),
        sleeper=_no_sleep,
    )

    result = await supervisor.run(
        task,
        context=object(),
        manifest=object(),
        pre_checkpoint=object(),
        post_checkpoint_builder=build_post_checkpoint,
        lease=_lease(),
    )

    assert result.outcome.status is CommerceSubagentStatus.CANCELLED
    assert result.heartbeat_count == 3
    assert len(committer.started) == 1
    assert len(committer.outcomes) == 1
    assert committer.outcomes[0][-1] == result.started_commit.lifecycle_event_id
    assert post_checkpoint_outcomes == [result.outcome]
    assert adapter.cancelled == []
    assert adapter.cleaned == [task.task_id]


@pytest.mark.anyio
async def test_supervisor_requests_cancel_but_does_not_fabricate_terminal_outcome():
    task = _task()
    adapter = _Adapter(
        [
            _outcome(task, CommerceSubagentStatus.RUNNING),
            _outcome(task, CommerceSubagentStatus.RUNNING),
        ]
    )
    committer = _Committer()
    supervisor = CommerceSubagentSupervisor(
        adapter=adapter,
        committer=committer,
        leases=_Leases(),
        lease_ttl=timedelta(seconds=30),
        poll_interval_seconds=0,
        max_polls=1,
        clock=_clock(),
        sleeper=_no_sleep,
    )

    with pytest.raises(CommerceSubagentSupervisionError, match="unresolved"):
        await supervisor.run(
            task,
            context=object(),
            manifest=object(),
            pre_checkpoint=object(),
            post_checkpoint_builder=lambda _outcome: object(),
            lease=_lease(),
        )

    assert adapter.cancelled == [task.task_id]
    assert adapter.cleaned == []
    assert committer.outcomes == []


@pytest.mark.anyio
async def test_supervisor_stops_before_poll_or_commit_when_heartbeat_loses_lease():
    task = _task()
    adapter = _Adapter([_outcome(task, CommerceSubagentStatus.CANCELLED)])
    committer = _Committer()
    supervisor = CommerceSubagentSupervisor(
        adapter=adapter,
        committer=committer,
        leases=_Leases(fail_on_heartbeat=1),
        lease_ttl=timedelta(seconds=30),
        poll_interval_seconds=0,
        max_polls=1,
        clock=_clock(),
        sleeper=_no_sleep,
    )

    with pytest.raises(RunLeaseLostError):
        await supervisor.run(
            task,
            context=object(),
            manifest=object(),
            pre_checkpoint=object(),
            post_checkpoint_builder=lambda _outcome: object(),
            lease=_lease(),
        )

    assert len(committer.started) == 1
    assert committer.outcomes == []
    assert adapter.cleaned == []
