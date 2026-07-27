"""Evidence Barrier contracts for 0-3 persisted Commerce Path outcomes."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.commerce.agents.contracts import AgentBudgetLimit, ModelProfile, PathType
from app.commerce.agents.evidence_barrier import (
    EvidenceBarrier,
    EvidenceBarrierDisposition,
    EvidenceBarrierError,
    EvidenceBarrierReasonCode,
)
from app.commerce.agents.model_router import (
    ModelAssignment,
    ModelEffort,
    ModelRole,
    ModelRouteReasonCode,
)
from app.commerce.agents.path_result import (
    ModelExecutionTrace,
    PathCost,
    PathEvidenceItem,
    PathResult,
)
from app.commerce.agents.subagent_adapter import (
    CommerceAgentTask,
    CommerceSubagentErrorCode,
    CommerceSubagentOutcome,
    CommerceSubagentStatus,
)
from app.commerce.agents.subagent_committer import CommerceSubagentCommitReceipt
from app.commerce.domain.enums import SemanticStatus
from app.commerce.domain.ids import (
    AgentTaskId,
    CaseId,
    CheckpointId,
    CorrelationId,
    EventId,
    EvidenceId,
    MetricObservationId,
    RunId,
    TraceId,
    WorkspaceId,
)
from app.commerce.domain.models import Evidence, EvidenceRelation

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
    *,
    workspace_id: WorkspaceId,
    case_id: CaseId,
    run_id: RunId,
    path_type: PathType,
) -> CommerceAgentTask:
    return CommerceAgentTask(
        workspace_id=workspace_id,
        case_id=case_id,
        run_id=run_id,
        task_id=AgentTaskId.new(),
        path_type=path_type,
        subagent_name=f"commerce-{path_type.value}-path",
        context_sha256="a" * 64,
        budget=AgentBudgetLimit(max_path_agents=0),
        model_assignment=_assignment(),
        skill_id=f"commerce.{path_type.value}-investigation",
        skill_version="1.0.0",
        allowed_tools=frozenset({"metric_query"}),
        expected_result_schema="commerce.path_result@1.0.0",
        lease_worker_id="commerce-subagent-worker",
        fencing_token=1,
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
        issued_at=NOW,
    )


def _completed(
    task: CommerceAgentTask,
    *,
    evidence_id: EvidenceId | None = None,
    metric_id: MetricObservationId | None = None,
) -> tuple[CommerceSubagentOutcome, Evidence]:
    selected_evidence_id = evidence_id or EvidenceId.new()
    selected_metric_id = metric_id or MetricObservationId.new()
    evidence = Evidence(
        id=selected_evidence_id,
        workspace_id=task.workspace_id,
        case_id=task.case_id,
        summary=f"Persisted {task.path_type.value} evidence",
        relation=EvidenceRelation.CONTEXT,
        semantic_status=SemanticStatus.DERIVED,
        confidence=0.9,
        metric_observation_ids=(selected_metric_id,),
    )
    result = PathResult(
        path_type=task.path_type,
        evidence=(
            PathEvidenceItem(
                evidence_id=evidence.id,
                summary=evidence.summary,
                relation=evidence.relation,
                semantic_status=evidence.semantic_status,
                confidence=evidence.confidence,
                metric_observation_ids=evidence.metric_observation_ids,
            ),
        ),
        cost=PathCost(
            input_tokens=10,
            output_tokens=10,
            latency_ms=20,
            tool_call_count=0,
        ),
        trace_id=task.trace_id,
        model_assignment=task.model_assignment,
        model_execution=ModelExecutionTrace(
            provider_request_id="provider-request-1",
            actual_model_identity="deepseek-v4-flash",
            retry_count=0,
            stop_reason="stop",
            prompt_version="commerce-path@1.0.0",
            context_version="commerce-context@1.0.0",
        ),
        skill_version=f"{task.skill_id}@{task.skill_version}",
        context_sha256=task.context_sha256,
    )
    return (
        CommerceSubagentOutcome(
            task_id=task.task_id,
            path_type=task.path_type,
            status=CommerceSubagentStatus.COMPLETED,
            harness_trace_id=str(task.trace_id),
            result=result,
            result_sha256="b" * 64,
        ),
        evidence,
    )


def _unsuccessful(
    task: CommerceAgentTask,
    status: CommerceSubagentStatus,
) -> CommerceSubagentOutcome:
    code = {
        CommerceSubagentStatus.BLOCKED: CommerceSubagentErrorCode.INVALID_PATH_RESULT,
        CommerceSubagentStatus.FAILED: CommerceSubagentErrorCode.HARNESS_FAILED,
        CommerceSubagentStatus.CANCELLED: CommerceSubagentErrorCode.HARNESS_CANCELLED,
        CommerceSubagentStatus.TIMED_OUT: CommerceSubagentErrorCode.HARNESS_TIMED_OUT,
    }[status]
    return CommerceSubagentOutcome(
        task_id=task.task_id,
        path_type=task.path_type,
        status=status,
        harness_trace_id=str(task.trace_id),
        error_code=code,
        error_message="Terminal Path outcome",
    )


def _receipt(
    task: CommerceAgentTask,
    outcome: CommerceSubagentOutcome,
    *,
    evidence_ids: tuple[EvidenceId, ...] = (),
) -> CommerceSubagentCommitReceipt:
    return CommerceSubagentCommitReceipt(
        task_id=task.task_id,
        path_type=task.path_type,
        status=outcome.status,
        checkpoint_id=CheckpointId.new(),
        lifecycle_event_id=EventId.new(),
        evidence_ids=evidence_ids,
        case_version=2,
    )


class _EvidenceRepository:
    def __init__(self, records: tuple[Evidence, ...] = ()) -> None:
        self.records = {(item.workspace_id, item.id): item for item in records}

    async def get(self, workspace_id, evidence_id):
        return self.records.get((workspace_id, evidence_id))


def _identity():
    return WorkspaceId.new(), CaseId.new(), RunId.new()


@pytest.mark.anyio
async def test_zero_selected_paths_releases_empty_barrier_for_lead_unknowns():
    result = await EvidenceBarrier(_EvidenceRepository()).evaluate(
        tasks=(),
        outcomes=(),
        receipts=(),
    )

    assert result.disposition is EvidenceBarrierDisposition.READY
    assert result.may_synthesize is True
    assert result.evidence == ()
    assert EvidenceBarrierReasonCode.NO_PATHS_SELECTED in result.reason_codes


@pytest.mark.anyio
async def test_running_path_keeps_barrier_waiting():
    workspace_id, case_id, run_id = _identity()
    task = _task(
        workspace_id=workspace_id,
        case_id=case_id,
        run_id=run_id,
        path_type=PathType.FULFILLMENT,
    )
    outcome = CommerceSubagentOutcome(
        task_id=task.task_id,
        path_type=task.path_type,
        status=CommerceSubagentStatus.RUNNING,
        harness_trace_id=str(task.trace_id),
    )

    result = await EvidenceBarrier(_EvidenceRepository()).evaluate(
        tasks=(task,),
        outcomes=(outcome,),
        receipts=(),
    )

    assert result.disposition is EvidenceBarrierDisposition.WAITING
    assert result.may_synthesize is False
    assert result.running_task_ids == (task.task_id,)
    assert EvidenceBarrierReasonCode.PATHS_STILL_RUNNING in result.reason_codes


@pytest.mark.anyio
async def test_terminal_outcome_waits_until_committer_receipt_exists():
    workspace_id, case_id, run_id = _identity()
    task = _task(
        workspace_id=workspace_id,
        case_id=case_id,
        run_id=run_id,
        path_type=PathType.FULFILLMENT,
    )
    outcome, evidence = _completed(task)

    result = await EvidenceBarrier(_EvidenceRepository((evidence,))).evaluate(
        tasks=(task,),
        outcomes=(outcome,),
        receipts=(),
    )

    assert result.disposition is EvidenceBarrierDisposition.WAITING
    assert result.awaiting_persistence_task_ids == (task.task_id,)
    assert EvidenceBarrierReasonCode.AWAITING_PERSISTENCE in result.reason_codes


@pytest.mark.anyio
async def test_partial_path_success_releases_only_persisted_evidence():
    workspace_id, case_id, run_id = _identity()
    completed_task = _task(
        workspace_id=workspace_id,
        case_id=case_id,
        run_id=run_id,
        path_type=PathType.FULFILLMENT,
    )
    failed_task = _task(
        workspace_id=workspace_id,
        case_id=case_id,
        run_id=run_id,
        path_type=PathType.SELLER_PEER,
    )
    completed, evidence = _completed(completed_task)
    failed = _unsuccessful(failed_task, CommerceSubagentStatus.FAILED)

    result = await EvidenceBarrier(_EvidenceRepository((evidence,))).evaluate(
        tasks=(completed_task, failed_task),
        outcomes=(completed, failed),
        receipts=(
            _receipt(completed_task, completed, evidence_ids=(evidence.id,)),
            _receipt(failed_task, failed),
        ),
    )

    assert result.disposition is EvidenceBarrierDisposition.READY
    assert result.may_synthesize is True
    assert result.evidence == (evidence,)
    assert result.completed_task_ids == (completed_task.task_id,)
    assert result.failed_task_ids == (failed_task.task_id,)
    assert EvidenceBarrierReasonCode.PARTIAL_PATH_SUCCESS in result.reason_codes


@pytest.mark.anyio
async def test_all_unsuccessful_paths_block_claim_synthesis():
    workspace_id, case_id, run_id = _identity()
    first = _task(
        workspace_id=workspace_id,
        case_id=case_id,
        run_id=run_id,
        path_type=PathType.FULFILLMENT,
    )
    second = _task(
        workspace_id=workspace_id,
        case_id=case_id,
        run_id=run_id,
        path_type=PathType.REVIEW_EXPERIENCE,
    )
    blocked = _unsuccessful(first, CommerceSubagentStatus.BLOCKED)
    timed_out = _unsuccessful(second, CommerceSubagentStatus.TIMED_OUT)

    result = await EvidenceBarrier(_EvidenceRepository()).evaluate(
        tasks=(first, second),
        outcomes=(blocked, timed_out),
        receipts=(
            _receipt(first, blocked),
            _receipt(second, timed_out),
        ),
    )

    assert result.disposition is EvidenceBarrierDisposition.BLOCKED
    assert result.may_synthesize is False
    assert result.evidence == ()
    assert EvidenceBarrierReasonCode.NO_PATH_COMPLETED in result.reason_codes


@pytest.mark.anyio
async def test_receipt_status_mismatch_fails_closed():
    workspace_id, case_id, run_id = _identity()
    task = _task(
        workspace_id=workspace_id,
        case_id=case_id,
        run_id=run_id,
        path_type=PathType.FULFILLMENT,
    )
    outcome = _unsuccessful(task, CommerceSubagentStatus.BLOCKED)
    receipt = _receipt(task, outcome).model_copy(
        update={"status": CommerceSubagentStatus.FAILED}
    )

    with pytest.raises(EvidenceBarrierError, match="status"):
        await EvidenceBarrier(_EvidenceRepository()).evaluate(
            tasks=(task,),
            outcomes=(outcome,),
            receipts=(receipt,),
        )


@pytest.mark.anyio
async def test_missing_persisted_evidence_fails_closed():
    workspace_id, case_id, run_id = _identity()
    task = _task(
        workspace_id=workspace_id,
        case_id=case_id,
        run_id=run_id,
        path_type=PathType.FULFILLMENT,
    )
    outcome, evidence = _completed(task)

    with pytest.raises(EvidenceBarrierError, match="not persisted"):
        await EvidenceBarrier(_EvidenceRepository()).evaluate(
            tasks=(task,),
            outcomes=(outcome,),
            receipts=(
                _receipt(task, outcome, evidence_ids=(evidence.id,)),
            ),
        )


@pytest.mark.anyio
async def test_path_result_and_receipt_evidence_ids_must_match():
    workspace_id, case_id, run_id = _identity()
    task = _task(
        workspace_id=workspace_id,
        case_id=case_id,
        run_id=run_id,
        path_type=PathType.FULFILLMENT,
    )
    outcome, evidence = _completed(task)

    with pytest.raises(EvidenceBarrierError, match="Evidence IDs"):
        await EvidenceBarrier(_EvidenceRepository((evidence,))).evaluate(
            tasks=(task,),
            outcomes=(outcome,),
            receipts=(
                _receipt(task, outcome, evidence_ids=(EvidenceId.new(),)),
            ),
        )
