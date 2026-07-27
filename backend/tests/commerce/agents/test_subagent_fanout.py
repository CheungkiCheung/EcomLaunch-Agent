"""Deterministic parallel Path fan-out and Barrier join contracts."""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from app.commerce.agents.contracts import AgentBudgetLimit, ModelProfile, PathType
from app.commerce.agents.evidence_barrier import (
    EvidenceBarrierDisposition,
    EvidenceBarrierReasonCode,
    EvidenceBarrierResult,
)
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
from app.commerce.agents.subagent_fanout import (
    CommerceSubagentFanout,
    CommerceSubagentFanoutEntry,
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
from app.commerce.persistence.runs import RunLeaseCredentials


def _task(path_type: PathType) -> CommerceAgentTask:
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
        path_type=path_type,
        subagent_name=f"commerce-{path_type.value}-path",
        context_sha256="a" * 64,
        budget=AgentBudgetLimit(max_path_agents=0),
        model_assignment=assignment,
        skill_id=f"commerce.{path_type.value}-investigation",
        skill_version="1.0.0",
        allowed_tools=frozenset({"metric_query"}),
        expected_result_schema="commerce.path_result@1.0.0",
        lease_worker_id="fanout-worker",
        fencing_token=1,
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
    )


def _same_identity_tasks() -> tuple[CommerceAgentTask, ...]:
    first = _task(PathType.FULFILLMENT)
    return (
        first,
        first.model_copy(
            update={
                "task_id": AgentTaskId.new(),
                "path_type": PathType.SELLER_PEER,
                "subagent_name": "commerce-seller-peer-path",
            }
        ),
    )


def _blocked(task: CommerceAgentTask) -> CommerceSubagentOutcome:
    return CommerceSubagentOutcome(
        task_id=task.task_id,
        path_type=task.path_type,
        status=CommerceSubagentStatus.BLOCKED,
        harness_trace_id=str(task.trace_id),
        error_code=CommerceSubagentErrorCode.INVALID_PATH_RESULT,
        error_message="bounded test failure",
    )


def _receipt(
    task: CommerceAgentTask,
    outcome: CommerceSubagentOutcome,
) -> CommerceSubagentCommitReceipt:
    return CommerceSubagentCommitReceipt(
        task_id=task.task_id,
        path_type=task.path_type,
        status=outcome.status,
        checkpoint_id=CheckpointId.new(),
        lifecycle_event_id=EventId.new(),
    )


def _lease() -> RunLeaseCredentials:
    return RunLeaseCredentials(
        worker_id="fanout-worker",
        lease_token=SecretStr("lease-token"),
        fencing_token=1,
    )


class _Barrier:
    def __init__(self, disposition=EvidenceBarrierDisposition.BLOCKED):
        self.calls = []
        self.disposition = disposition

    async def evaluate(self, *, tasks, outcomes, receipts):
        self.calls.append((tasks, outcomes, receipts))
        return EvidenceBarrierResult(
            disposition=self.disposition,
            reason_codes=frozenset(
                {
                    EvidenceBarrierReasonCode.NO_PATH_COMPLETED
                    if self.disposition is EvidenceBarrierDisposition.BLOCKED
                    else EvidenceBarrierReasonCode.PATHS_STILL_RUNNING
                }
            ),
            may_synthesize=self.disposition is EvidenceBarrierDisposition.READY,
            selected_task_ids=tuple(task.task_id for task in tasks),
        )


class _Supervisor:
    def __init__(self, outcome, receipt, delay, starts, *, error=None):
        self.outcome = outcome
        self.receipt = receipt
        self.delay = delay
        self.starts = starts
        self.error = error

    async def run(self, task, **kwargs):
        self.starts.append((task.task_id, "start", time.perf_counter()))
        if self.error is not None:
            raise self.error
        await asyncio.sleep(self.delay)
        self.starts.append((task.task_id, "end", time.perf_counter()))
        return SimpleNamespace(outcome=self.outcome, terminal_commit=self.receipt)


def _entry(task, supervisor):
    return CommerceSubagentFanoutEntry(
        task=task,
        context=object(),
        manifest=object(),
        pre_checkpoint=object(),
        post_checkpoint_builder=lambda _outcome: object(),
        lease=_lease(),
        supervisor=supervisor,
    )


@pytest.mark.anyio
async def test_fanout_runs_selected_paths_in_parallel_and_joins_terminal_states():
    tasks = _same_identity_tasks()
    starts = []
    supervisors = [
        _Supervisor(_blocked(task), _receipt(task, _blocked(task)), delay, starts)
        for task, delay in zip(tasks, (0.08, 0.12), strict=True)
    ]
    barrier = _Barrier()
    started = time.perf_counter()
    result = await CommerceSubagentFanout(barrier=barrier).run(
        tuple(_entry(task, supervisor) for task, supervisor in zip(tasks, supervisors, strict=True))
    )
    elapsed = time.perf_counter() - started

    assert elapsed < 0.18
    assert len(result.paths) == 2
    assert result.critical_path_ms >= 100
    assert result.wall_time_ms >= result.critical_path_ms
    assert result.barrier.disposition is EvidenceBarrierDisposition.BLOCKED
    assert len(barrier.calls) == 1
    assert len(barrier.calls[0][0]) == 2
    assert len(barrier.calls[0][1]) == 2
    assert len(barrier.calls[0][2]) == 2
    starts_by_task = {
        task_id: started_at for task_id, phase, started_at in starts if phase == "start"
    }
    ends_by_task = {
        task_id: ended_at for task_id, phase, ended_at in starts if phase == "end"
    }
    assert starts_by_task[tasks[1].task_id] < ends_by_task[tasks[0].task_id]


@pytest.mark.anyio
async def test_fanout_preserves_unknown_external_outcome_without_fabricating_failure():
    tasks = _same_identity_tasks()
    starts = []
    successful_outcome = _blocked(tasks[1])
    successful_receipt = _receipt(tasks[1], successful_outcome)
    barrier = _Barrier(EvidenceBarrierDisposition.WAITING)
    result = await CommerceSubagentFanout(barrier=barrier).run(
        (
            _entry(
                tasks[0],
                _Supervisor(
                    _blocked(tasks[0]),
                    _receipt(tasks[0], _blocked(tasks[0])),
                    0,
                    starts,
                    error=RuntimeError("lease outcome unknown"),
                ),
            ),
            _entry(
                tasks[1],
                _Supervisor(
                    successful_outcome,
                    successful_receipt,
                    0,
                    starts,
                ),
            ),
        )
    )

    assert result.paths[0].error_type == "RuntimeError"
    assert result.paths[0].outcome_status is None
    assert result.outcomes == (successful_outcome,)
    assert result.receipts == (successful_receipt,)
    assert result.barrier.disposition is EvidenceBarrierDisposition.WAITING


def test_fanout_rejects_duplicate_path_or_more_than_three_entries():
    first = _task(PathType.FULFILLMENT)
    duplicate = first.model_copy(update={"task_id": AgentTaskId.new()})
    with pytest.raises(ValueError, match="Path types"):
        CommerceSubagentFanout._validate_entries(
            ( _entry(first, object()), _entry(duplicate, object()) )
        )


@pytest.mark.anyio
async def test_fanout_rejects_more_than_three_entries_before_execution():
    first = _task(PathType.FULFILLMENT)
    entries = tuple(
        _entry(
            first.model_copy(update={"task_id": AgentTaskId.new()}),
            object(),
        )
        for _ in range(4)
    )

    with pytest.raises(ValueError, match="at most three"):
        await CommerceSubagentFanout(barrier=_Barrier()).run(entries)
