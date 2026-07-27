"""Deterministic restart/resume classification for Commerce Path execution."""

from __future__ import annotations

from datetime import UTC, datetime

from app.commerce.agents.budget import BudgetSnapshot, BudgetUsage
from app.commerce.agents.contracts import AgentBudgetLimit
from app.commerce.agents.goal_loop import GoalLoopCheckpoint, GoalStopReason
from app.commerce.agents.resume import (
    ResumeDisposition,
    ResumeReasonCode,
    RunResumeClassifier,
)
from app.commerce.domain.events import DomainEventActor, DomainEventEnvelope
from app.commerce.domain.ids import (
    AgentTaskId,
    CaseId,
    CheckpointId,
    CorrelationId,
    EventId,
    EvidenceId,
    RunId,
    TraceId,
    WorkspaceId,
)
from app.commerce.persistence.runs import RunCheckpointRecord


def _checkpoint(
    *,
    workspace_id: WorkspaceId,
    case_id: CaseId,
    run_id: RunId,
    sequence: int,
    iteration: int,
    task_ids: tuple[AgentTaskId, ...],
    evidence_ids: tuple[EvidenceId, ...] = (),
    wait_reason: GoalStopReason | None = None,
) -> RunCheckpointRecord:
    now = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)
    return RunCheckpointRecord(
        id=CheckpointId.new(),
        workspace_id=workspace_id,
        case_id=case_id,
        run_id=run_id,
        sequence=sequence,
        checkpoint=GoalLoopCheckpoint(
            workspace_id=workspace_id,
            case_id=case_id,
            run_id=run_id,
            goal="Explain the fulfillment anomaly",
            loop_iteration=iteration,
            budget_snapshot=BudgetSnapshot(
                limit=AgentBudgetLimit(),
                usage=BudgetUsage(iterations=iteration),
            ),
            evidence_ids=evidence_ids,
            active_path_task_ids=task_ids,
            context_sha256="a" * 64,
            wait_reason=wait_reason,
        ),
        created_at=now,
    )


def _event(
    event_type: str,
    *,
    workspace_id: WorkspaceId,
    case_id: CaseId,
    run_id: RunId,
    run_sequence: int,
    payload: dict,
    event_id: EventId | None = None,
    causation_event_id: EventId | None = None,
) -> DomainEventEnvelope:
    now = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)
    return DomainEventEnvelope(
        id=event_id or EventId.new(),
        workspace_id=workspace_id,
        case_id=case_id,
        run_id=run_id,
        event_type=event_type,
        occurred_at=now,
        recorded_at=now,
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
        causation_event_id=causation_event_id,
        actor=DomainEventActor.AGENT,
        payload=payload,
        case_sequence=run_sequence,
        run_sequence=run_sequence,
    )


def _identity():
    return WorkspaceId.new(), CaseId.new(), RunId.new(), AgentTaskId.new()


def test_no_checkpoint_is_the_only_automatic_first_call_state():
    workspace_id, case_id, run_id, _ = _identity()

    plan = RunResumeClassifier().classify(
        latest_checkpoint=None,
        run_events=(
            _event(
                "run.created",
                workspace_id=workspace_id,
                case_id=case_id,
                run_id=run_id,
                run_sequence=1,
                payload={"status": "queued"},
            ),
        ),
    )

    assert plan.disposition is ResumeDisposition.INITIAL_CALL_ALLOWED
    assert plan.may_invoke_external_model is True
    assert ResumeReasonCode.NO_CHECKPOINT in plan.reason_codes


def test_pre_call_checkpoint_blocks_blind_external_retry():
    workspace_id, case_id, run_id, task_id = _identity()
    started_id = EventId.new()
    latest = _checkpoint(
        workspace_id=workspace_id,
        case_id=case_id,
        run_id=run_id,
        sequence=1,
        iteration=0,
        task_ids=(task_id,),
    )

    plan = RunResumeClassifier().classify(
        latest_checkpoint=latest,
        run_events=(
            _event(
                "path.started",
                workspace_id=workspace_id,
                case_id=case_id,
                run_id=run_id,
                run_sequence=1,
                event_id=started_id,
                payload={"task_id": str(task_id), "path_type": "fulfillment"},
            ),
        ),
    )

    assert plan.disposition is ResumeDisposition.AWAIT_RETRY_DECISION
    assert plan.may_invoke_external_model is False
    assert plan.active_task_ids == (task_id,)
    assert ResumeReasonCode.EXTERNAL_OUTCOME_UNKNOWN in plan.reason_codes


def test_partial_evidence_requires_reconciliation_instead_of_model_retry():
    workspace_id, case_id, run_id, task_id = _identity()
    started_id = EventId.new()
    evidence_id = EvidenceId.new()
    latest = _checkpoint(
        workspace_id=workspace_id,
        case_id=case_id,
        run_id=run_id,
        sequence=1,
        iteration=0,
        task_ids=(task_id,),
    )

    plan = RunResumeClassifier().classify(
        latest_checkpoint=latest,
        run_events=(
            _event(
                "path.started",
                workspace_id=workspace_id,
                case_id=case_id,
                run_id=run_id,
                run_sequence=1,
                event_id=started_id,
                payload={"task_id": str(task_id), "path_type": "fulfillment"},
            ),
            _event(
                "evidence.appended",
                workspace_id=workspace_id,
                case_id=case_id,
                run_id=run_id,
                run_sequence=2,
                causation_event_id=started_id,
                payload={"evidence_id": str(evidence_id)},
            ),
        ),
    )

    assert plan.disposition is ResumeDisposition.RECONCILE_PARTIAL_EVIDENCE
    assert plan.may_invoke_external_model is False
    assert plan.partial_evidence_ids == (evidence_id,)
    assert ResumeReasonCode.PARTIAL_EVIDENCE_PRESENT in plan.reason_codes


def test_post_call_checkpoint_skips_completed_path_and_continues_loop():
    workspace_id, case_id, run_id, task_id = _identity()
    evidence_id = EvidenceId.new()
    latest = _checkpoint(
        workspace_id=workspace_id,
        case_id=case_id,
        run_id=run_id,
        sequence=2,
        iteration=1,
        task_ids=(),
        evidence_ids=(evidence_id,),
    )

    plan = RunResumeClassifier().classify(
        latest_checkpoint=latest,
        run_events=(
            _event(
                "path.completed",
                workspace_id=workspace_id,
                case_id=case_id,
                run_id=run_id,
                run_sequence=1,
                payload={
                    "task_id": str(task_id),
                    "path_type": "fulfillment",
                    "evidence_ids": [str(evidence_id)],
                },
            ),
        ),
    )

    assert plan.disposition is ResumeDisposition.CONTINUE_AFTER_COMPLETED_PATH
    assert plan.may_invoke_external_model is False
    assert plan.completed_task_ids == (task_id,)
    assert ResumeReasonCode.POST_CALL_CHECKPOINT_VERIFIED in plan.reason_codes


def test_post_call_checkpoint_reconciles_blocked_path_without_model_retry():
    workspace_id, case_id, run_id, task_id = _identity()
    latest = _checkpoint(
        workspace_id=workspace_id,
        case_id=case_id,
        run_id=run_id,
        sequence=2,
        iteration=1,
        task_ids=(),
    )

    plan = RunResumeClassifier().classify(
        latest_checkpoint=latest,
        run_events=(
            _event(
                "path.blocked",
                workspace_id=workspace_id,
                case_id=case_id,
                run_id=run_id,
                run_sequence=1,
                payload={
                    "task_id": str(task_id),
                    "path_type": "fulfillment",
                    "status": "blocked",
                    "error_code": "invalid_path_result",
                },
            ),
        ),
    )

    assert plan.disposition is ResumeDisposition.CONTINUE_AFTER_TERMINAL_PATH
    assert plan.may_invoke_external_model is False
    assert plan.blocked_task_ids == (task_id,)
    assert ResumeReasonCode.TERMINAL_PATH_CHECKPOINT_VERIFIED in plan.reason_codes


def test_post_call_checkpoint_reconciles_cancelled_path_as_failed_terminal():
    workspace_id, case_id, run_id, task_id = _identity()
    latest = _checkpoint(
        workspace_id=workspace_id,
        case_id=case_id,
        run_id=run_id,
        sequence=2,
        iteration=1,
        task_ids=(),
    )

    plan = RunResumeClassifier().classify(
        latest_checkpoint=latest,
        run_events=(
            _event(
                "path.failed",
                workspace_id=workspace_id,
                case_id=case_id,
                run_id=run_id,
                run_sequence=1,
                payload={
                    "task_id": str(task_id),
                    "path_type": "fulfillment",
                    "status": "cancelled",
                    "error_code": "harness_cancelled",
                },
            ),
        ),
    )

    assert plan.disposition is ResumeDisposition.CONTINUE_AFTER_TERMINAL_PATH
    assert plan.may_invoke_external_model is False
    assert plan.failed_task_ids == (task_id,)
    assert ResumeReasonCode.TERMINAL_PATH_CHECKPOINT_VERIFIED in plan.reason_codes


def test_completed_event_without_post_call_checkpoint_is_invalid_state():
    workspace_id, case_id, run_id, task_id = _identity()
    latest = _checkpoint(
        workspace_id=workspace_id,
        case_id=case_id,
        run_id=run_id,
        sequence=1,
        iteration=0,
        task_ids=(task_id,),
    )

    plan = RunResumeClassifier().classify(
        latest_checkpoint=latest,
        run_events=(
            _event(
                "path.completed",
                workspace_id=workspace_id,
                case_id=case_id,
                run_id=run_id,
                run_sequence=1,
                payload={
                    "task_id": str(task_id),
                    "path_type": "fulfillment",
                    "evidence_ids": [],
                },
            ),
        ),
    )

    assert plan.disposition is ResumeDisposition.INVALID_STATE
    assert plan.may_invoke_external_model is False
    assert ResumeReasonCode.COMPLETION_WITHOUT_POST_CHECKPOINT in plan.reason_codes


def test_approval_wait_checkpoint_remains_waiting_without_a_fenced_resume_event():
    workspace_id, case_id, run_id, _task_id = _identity()
    latest = _checkpoint(
        workspace_id=workspace_id,
        case_id=case_id,
        run_id=run_id,
        sequence=1,
        iteration=0,
        task_ids=(),
        wait_reason=GoalStopReason.AWAITING_APPROVAL,
    )

    plan = RunResumeClassifier().classify(
        latest_checkpoint=latest,
        run_events=(
            _event(
                "lead.waiting",
                workspace_id=workspace_id,
                case_id=case_id,
                run_id=run_id,
                run_sequence=1,
                payload={"wait_reason": "awaiting_approval"},
            ),
        ),
    )

    assert plan.disposition is ResumeDisposition.WAITING_FOR_APPROVAL
    assert plan.may_invoke_external_model is False
    assert ResumeReasonCode.APPROVAL_WAIT_CHECKPOINT_VERIFIED in plan.reason_codes


def test_user_input_wait_continues_only_after_a_fenced_resume_event():
    workspace_id, case_id, run_id, _task_id = _identity()
    latest = _checkpoint(
        workspace_id=workspace_id,
        case_id=case_id,
        run_id=run_id,
        sequence=1,
        iteration=0,
        task_ids=(),
        wait_reason=GoalStopReason.AWAITING_USER_INPUT,
    )

    waiting = RunResumeClassifier().classify(
        latest_checkpoint=latest,
        run_events=(
            _event(
                "lead.waiting",
                workspace_id=workspace_id,
                case_id=case_id,
                run_id=run_id,
                run_sequence=1,
                payload={"wait_reason": "awaiting_user_input"},
            ),
        ),
    )
    resumed = RunResumeClassifier().classify(
        latest_checkpoint=latest,
        run_events=(
            _event(
                "lead.waiting",
                workspace_id=workspace_id,
                case_id=case_id,
                run_id=run_id,
                run_sequence=1,
                payload={"wait_reason": "awaiting_user_input"},
            ),
            _event(
                "run.status_changed",
                workspace_id=workspace_id,
                case_id=case_id,
                run_id=run_id,
                run_sequence=2,
                payload={
                    "from_status": "waiting",
                    "to_status": "running",
                    "resumed_from_wait": True,
                    "fencing_token": 2,
                },
            ),
        ),
    )

    assert waiting.disposition is ResumeDisposition.WAITING_FOR_USER_INPUT
    assert resumed.disposition is ResumeDisposition.CONTINUE_AFTER_WAIT
    assert resumed.may_invoke_external_model is False
    assert ResumeReasonCode.WAIT_RESUME_FENCING_VERIFIED in resumed.reason_codes
