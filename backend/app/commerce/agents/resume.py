"""Deterministic restart classification for fenced Commerce Agent execution."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from app.commerce.agents.goal_loop import GoalStopReason
from app.commerce.domain.events import DomainEventEnvelope
from app.commerce.domain.ids import AgentTaskId, EvidenceId
from app.commerce.domain.models import CommerceModel
from app.commerce.persistence.runs import RunCheckpointRecord


class ResumeDisposition(StrEnum):
    INITIAL_CALL_ALLOWED = "initial_call_allowed"
    AWAIT_RETRY_DECISION = "await_retry_decision"
    RECONCILE_PARTIAL_EVIDENCE = "reconcile_partial_evidence"
    CONTINUE_AFTER_COMPLETED_PATH = "continue_after_completed_path"
    CONTINUE_AFTER_TERMINAL_PATH = "continue_after_terminal_path"
    WAITING_FOR_USER_INPUT = "waiting_for_user_input"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    CONTINUE_AFTER_WAIT = "continue_after_wait"
    INVALID_STATE = "invalid_state"


class ResumeReasonCode(StrEnum):
    NO_CHECKPOINT = "no_checkpoint"
    PRE_CALL_CHECKPOINT_PRESENT = "pre_call_checkpoint_present"
    EXTERNAL_OUTCOME_UNKNOWN = "external_outcome_unknown"
    PARTIAL_EVIDENCE_PRESENT = "partial_evidence_present"
    POST_CALL_CHECKPOINT_VERIFIED = "post_call_checkpoint_verified"
    TERMINAL_PATH_CHECKPOINT_VERIFIED = "terminal_path_checkpoint_verified"
    COMPLETION_WITHOUT_POST_CHECKPOINT = "completion_without_post_checkpoint"
    CHECKPOINT_EVENT_IDENTITY_MISMATCH = "checkpoint_event_identity_mismatch"
    ACTIVE_TASK_MISSING_START_EVENT = "active_task_missing_start_event"
    UNRECOGNIZED_CHECKPOINT_SHAPE = "unrecognized_checkpoint_shape"
    USER_INPUT_WAIT_CHECKPOINT_VERIFIED = "user_input_wait_checkpoint_verified"
    APPROVAL_WAIT_CHECKPOINT_VERIFIED = "approval_wait_checkpoint_verified"
    WAIT_RESUME_FENCING_VERIFIED = "wait_resume_fencing_verified"


class ResumeResolutionDecision(StrEnum):
    ABANDON_UNKNOWN_OUTCOME = "abandon_unknown_outcome"


class ResumeExecutionDisposition(StrEnum):
    BLOCKED_FOR_REPLAN = "blocked_for_replan"


class ResumePlan(CommerceModel):
    disposition: ResumeDisposition
    reason_codes: frozenset[ResumeReasonCode] = Field(min_length=1)
    may_invoke_external_model: bool
    checkpoint_sequence: int | None = Field(default=None, ge=1)
    active_task_ids: tuple[AgentTaskId, ...] = ()
    completed_task_ids: tuple[AgentTaskId, ...] = ()
    blocked_task_ids: tuple[AgentTaskId, ...] = ()
    failed_task_ids: tuple[AgentTaskId, ...] = ()
    partial_evidence_ids: tuple[EvidenceId, ...] = ()

    @model_validator(mode="after")
    def keep_retry_authority_fail_closed(self) -> Self:
        if self.may_invoke_external_model != (
            self.disposition is ResumeDisposition.INITIAL_CALL_ALLOWED
        ):
            raise ValueError(
                "Only the no-Checkpoint initial state may invoke an external model"
            )
        for label, values in (
            ("active task", self.active_task_ids),
            ("completed task", self.completed_task_ids),
            ("blocked task", self.blocked_task_ids),
            ("failed task", self.failed_task_ids),
            ("partial Evidence", self.partial_evidence_ids),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"Resume {label} IDs must be unique")
        terminal_sets = (
            set(self.completed_task_ids),
            set(self.blocked_task_ids),
            set(self.failed_task_ids),
        )
        if any(
            terminal_sets[index] & terminal_sets[other]
            for index in range(len(terminal_sets))
            for other in range(index + 1, len(terminal_sets))
        ):
            raise ValueError("Resume task cannot have multiple terminal outcomes")
        return self


class RunResumeClassifier:
    """Classify persisted Checkpoint/Event state without calling a model."""

    def classify(
        self,
        *,
        latest_checkpoint: RunCheckpointRecord | None,
        run_events: tuple[DomainEventEnvelope, ...],
    ) -> ResumePlan:
        if latest_checkpoint is None:
            if any(
                event.event_type
                in {
                    "path.started",
                    "path.completed",
                    "path.blocked",
                    "path.failed",
                    "evidence.appended",
                }
                for event in run_events
            ):
                return self._invalid(
                    ResumeReasonCode.CHECKPOINT_EVENT_IDENTITY_MISMATCH
                )
            return ResumePlan(
                disposition=ResumeDisposition.INITIAL_CALL_ALLOWED,
                reason_codes=frozenset({ResumeReasonCode.NO_CHECKPOINT}),
                may_invoke_external_model=True,
            )

        checkpoint = latest_checkpoint.checkpoint
        if any(
            event.workspace_id != latest_checkpoint.workspace_id
            or event.run_id != latest_checkpoint.run_id
            or event.case_id != latest_checkpoint.case_id
            for event in run_events
        ):
            return self._invalid(
                ResumeReasonCode.CHECKPOINT_EVENT_IDENTITY_MISMATCH,
                sequence=latest_checkpoint.sequence,
            )

        if checkpoint.wait_reason is not None:
            return self._classify_wait_checkpoint(
                latest_checkpoint,
                run_events,
            )

        started_events = tuple(
            event for event in run_events if event.event_type == "path.started"
        )
        completed_events = tuple(
            event for event in run_events if event.event_type == "path.completed"
        )
        blocked_events = tuple(
            event for event in run_events if event.event_type == "path.blocked"
        )
        failed_events = tuple(
            event for event in run_events if event.event_type == "path.failed"
        )
        try:
            started_by_task = {
                AgentTaskId(str(event.payload["task_id"])): event
                for event in started_events
            }
            completed_by_task = {
                AgentTaskId(str(event.payload["task_id"])): event
                for event in completed_events
            }
            blocked_by_task = {
                AgentTaskId(str(event.payload["task_id"])): event
                for event in blocked_events
            }
            failed_by_task = {
                AgentTaskId(str(event.payload["task_id"])): event
                for event in failed_events
            }
        except (KeyError, TypeError, ValueError):
            return self._invalid(
                ResumeReasonCode.CHECKPOINT_EVENT_IDENTITY_MISMATCH,
                sequence=latest_checkpoint.sequence,
            )

        terminal_task_ids = (
            set(completed_by_task) | set(blocked_by_task) | set(failed_by_task)
        )
        if (
            set(completed_by_task) & set(blocked_by_task)
            or set(completed_by_task) & set(failed_by_task)
            or set(blocked_by_task) & set(failed_by_task)
        ):
            return self._invalid(
                ResumeReasonCode.CHECKPOINT_EVENT_IDENTITY_MISMATCH,
                sequence=latest_checkpoint.sequence,
            )

        if terminal_task_ids:
            if checkpoint.loop_iteration < 1 or terminal_task_ids & set(
                checkpoint.active_path_task_ids
            ):
                return self._invalid(
                    ResumeReasonCode.COMPLETION_WITHOUT_POST_CHECKPOINT,
                    sequence=latest_checkpoint.sequence,
                    active_task_ids=checkpoint.active_path_task_ids,
                )
            try:
                completed_evidence_ids = frozenset(
                    EvidenceId(str(evidence_id))
                    for event in completed_by_task.values()
                    for evidence_id in event.payload.get("evidence_ids", ())
                )
            except (TypeError, ValueError):
                return self._invalid(
                    ResumeReasonCode.CHECKPOINT_EVENT_IDENTITY_MISMATCH,
                    sequence=latest_checkpoint.sequence,
                )
            if not completed_evidence_ids.issubset(checkpoint.evidence_ids):
                return self._invalid(
                    ResumeReasonCode.CHECKPOINT_EVENT_IDENTITY_MISMATCH,
                    sequence=latest_checkpoint.sequence,
                )
            if blocked_by_task or failed_by_task:
                return ResumePlan(
                    disposition=ResumeDisposition.CONTINUE_AFTER_TERMINAL_PATH,
                    reason_codes=frozenset(
                        {ResumeReasonCode.TERMINAL_PATH_CHECKPOINT_VERIFIED}
                    ),
                    may_invoke_external_model=False,
                    checkpoint_sequence=latest_checkpoint.sequence,
                    active_task_ids=checkpoint.active_path_task_ids,
                    completed_task_ids=tuple(completed_by_task),
                    blocked_task_ids=tuple(blocked_by_task),
                    failed_task_ids=tuple(failed_by_task),
                )
            return ResumePlan(
                disposition=ResumeDisposition.CONTINUE_AFTER_COMPLETED_PATH,
                reason_codes=frozenset(
                    {ResumeReasonCode.POST_CALL_CHECKPOINT_VERIFIED}
                ),
                may_invoke_external_model=False,
                checkpoint_sequence=latest_checkpoint.sequence,
                active_task_ids=checkpoint.active_path_task_ids,
                completed_task_ids=tuple(completed_by_task),
            )

        active_task_ids = checkpoint.active_path_task_ids
        if checkpoint.loop_iteration == 0 and active_task_ids:
            if not set(active_task_ids).issubset(started_by_task):
                return self._invalid(
                    ResumeReasonCode.ACTIVE_TASK_MISSING_START_EVENT,
                    sequence=latest_checkpoint.sequence,
                    active_task_ids=active_task_ids,
                )
            started_event_ids = frozenset(
                started_by_task[task_id].id for task_id in active_task_ids
            )
            partial_evidence_ids: list[EvidenceId] = []
            try:
                for event in run_events:
                    if (
                        event.event_type == "evidence.appended"
                        and event.causation_event_id in started_event_ids
                    ):
                        partial_evidence_ids.append(
                            EvidenceId(str(event.payload["evidence_id"]))
                        )
            except (KeyError, TypeError, ValueError):
                return self._invalid(
                    ResumeReasonCode.CHECKPOINT_EVENT_IDENTITY_MISMATCH,
                    sequence=latest_checkpoint.sequence,
                    active_task_ids=active_task_ids,
                )
            if partial_evidence_ids:
                return ResumePlan(
                    disposition=ResumeDisposition.RECONCILE_PARTIAL_EVIDENCE,
                    reason_codes=frozenset(
                        {
                            ResumeReasonCode.PRE_CALL_CHECKPOINT_PRESENT,
                            ResumeReasonCode.PARTIAL_EVIDENCE_PRESENT,
                        }
                    ),
                    may_invoke_external_model=False,
                    checkpoint_sequence=latest_checkpoint.sequence,
                    active_task_ids=active_task_ids,
                    partial_evidence_ids=tuple(dict.fromkeys(partial_evidence_ids)),
                )
            return ResumePlan(
                disposition=ResumeDisposition.AWAIT_RETRY_DECISION,
                reason_codes=frozenset(
                    {
                        ResumeReasonCode.PRE_CALL_CHECKPOINT_PRESENT,
                        ResumeReasonCode.EXTERNAL_OUTCOME_UNKNOWN,
                    }
                ),
                may_invoke_external_model=False,
                checkpoint_sequence=latest_checkpoint.sequence,
                active_task_ids=active_task_ids,
            )

        return self._invalid(
            ResumeReasonCode.UNRECOGNIZED_CHECKPOINT_SHAPE,
            sequence=latest_checkpoint.sequence,
            active_task_ids=active_task_ids,
        )

    def _classify_wait_checkpoint(
        self,
        latest_checkpoint: RunCheckpointRecord,
        run_events: tuple[DomainEventEnvelope, ...],
    ) -> ResumePlan:
        checkpoint = latest_checkpoint.checkpoint
        if checkpoint.active_path_task_ids:
            return self._invalid(
                ResumeReasonCode.UNRECOGNIZED_CHECKPOINT_SHAPE,
                sequence=latest_checkpoint.sequence,
                active_task_ids=checkpoint.active_path_task_ids,
            )
        waiting_events = tuple(
            event for event in run_events if event.event_type == "lead.waiting"
        )
        try:
            matching_waits = tuple(
                event
                for event in waiting_events
                if GoalStopReason(str(event.payload["wait_reason"]))
                is checkpoint.wait_reason
            )
        except (KeyError, TypeError, ValueError):
            return self._invalid(
                ResumeReasonCode.CHECKPOINT_EVENT_IDENTITY_MISMATCH,
                sequence=latest_checkpoint.sequence,
            )
        if len(matching_waits) != 1:
            return self._invalid(
                ResumeReasonCode.CHECKPOINT_EVENT_IDENTITY_MISMATCH,
                sequence=latest_checkpoint.sequence,
            )
        wait_event = matching_waits[0]
        resume_candidates = tuple(
            event
            for event in run_events
            if event.event_type == "run.status_changed"
            and event.payload.get("resumed_from_wait") is True
        )
        if resume_candidates:
            try:
                valid_resumes = tuple(
                    event
                    for event in resume_candidates
                    if event.run_sequence > wait_event.run_sequence
                    and event.payload["from_status"] == "waiting"
                    and event.payload["to_status"] == "running"
                    and int(event.payload["fencing_token"]) >= 2
                )
            except (KeyError, TypeError, ValueError):
                return self._invalid(
                    ResumeReasonCode.CHECKPOINT_EVENT_IDENTITY_MISMATCH,
                    sequence=latest_checkpoint.sequence,
                )
            if len(valid_resumes) != 1:
                return self._invalid(
                    ResumeReasonCode.CHECKPOINT_EVENT_IDENTITY_MISMATCH,
                    sequence=latest_checkpoint.sequence,
                )
            return ResumePlan(
                disposition=ResumeDisposition.CONTINUE_AFTER_WAIT,
                reason_codes=frozenset(
                    {ResumeReasonCode.WAIT_RESUME_FENCING_VERIFIED}
                ),
                may_invoke_external_model=False,
                checkpoint_sequence=latest_checkpoint.sequence,
            )
        if checkpoint.wait_reason is GoalStopReason.AWAITING_APPROVAL:
            return ResumePlan(
                disposition=ResumeDisposition.WAITING_FOR_APPROVAL,
                reason_codes=frozenset(
                    {ResumeReasonCode.APPROVAL_WAIT_CHECKPOINT_VERIFIED}
                ),
                may_invoke_external_model=False,
                checkpoint_sequence=latest_checkpoint.sequence,
            )
        return ResumePlan(
            disposition=ResumeDisposition.WAITING_FOR_USER_INPUT,
            reason_codes=frozenset(
                {ResumeReasonCode.USER_INPUT_WAIT_CHECKPOINT_VERIFIED}
            ),
            may_invoke_external_model=False,
            checkpoint_sequence=latest_checkpoint.sequence,
        )

    @staticmethod
    def _invalid(
        reason: ResumeReasonCode,
        *,
        sequence: int | None = None,
        active_task_ids: tuple[AgentTaskId, ...] = (),
    ) -> ResumePlan:
        return ResumePlan(
            disposition=ResumeDisposition.INVALID_STATE,
            reason_codes=frozenset({reason}),
            may_invoke_external_model=False,
            checkpoint_sequence=sequence,
            active_task_ids=active_task_ids,
        )
