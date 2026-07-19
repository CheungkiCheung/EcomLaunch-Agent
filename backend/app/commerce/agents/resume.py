"""Deterministic restart classification for fenced Commerce Agent execution."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from app.commerce.domain.events import DomainEventEnvelope
from app.commerce.domain.ids import AgentTaskId, EvidenceId
from app.commerce.domain.models import CommerceModel
from app.commerce.persistence.runs import RunCheckpointRecord


class ResumeDisposition(StrEnum):
    INITIAL_CALL_ALLOWED = "initial_call_allowed"
    AWAIT_RETRY_DECISION = "await_retry_decision"
    RECONCILE_PARTIAL_EVIDENCE = "reconcile_partial_evidence"
    CONTINUE_AFTER_COMPLETED_PATH = "continue_after_completed_path"
    INVALID_STATE = "invalid_state"


class ResumeReasonCode(StrEnum):
    NO_CHECKPOINT = "no_checkpoint"
    PRE_CALL_CHECKPOINT_PRESENT = "pre_call_checkpoint_present"
    EXTERNAL_OUTCOME_UNKNOWN = "external_outcome_unknown"
    PARTIAL_EVIDENCE_PRESENT = "partial_evidence_present"
    POST_CALL_CHECKPOINT_VERIFIED = "post_call_checkpoint_verified"
    COMPLETION_WITHOUT_POST_CHECKPOINT = "completion_without_post_checkpoint"
    CHECKPOINT_EVENT_IDENTITY_MISMATCH = "checkpoint_event_identity_mismatch"
    ACTIVE_TASK_MISSING_START_EVENT = "active_task_missing_start_event"
    UNRECOGNIZED_CHECKPOINT_SHAPE = "unrecognized_checkpoint_shape"


class ResumePlan(CommerceModel):
    disposition: ResumeDisposition
    reason_codes: frozenset[ResumeReasonCode] = Field(min_length=1)
    may_invoke_external_model: bool
    checkpoint_sequence: int | None = Field(default=None, ge=1)
    active_task_ids: tuple[AgentTaskId, ...] = ()
    completed_task_ids: tuple[AgentTaskId, ...] = ()
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
            ("partial Evidence", self.partial_evidence_ids),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"Resume {label} IDs must be unique")
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
                in {"path.started", "path.completed", "evidence.appended"}
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

        started_events = tuple(
            event for event in run_events if event.event_type == "path.started"
        )
        completed_events = tuple(
            event for event in run_events if event.event_type == "path.completed"
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
        except (KeyError, TypeError, ValueError):
            return self._invalid(
                ResumeReasonCode.CHECKPOINT_EVENT_IDENTITY_MISMATCH,
                sequence=latest_checkpoint.sequence,
            )

        if completed_by_task:
            if checkpoint.loop_iteration < 1 or checkpoint.active_path_task_ids:
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
            return ResumePlan(
                disposition=ResumeDisposition.CONTINUE_AFTER_COMPLETED_PATH,
                reason_codes=frozenset(
                    {ResumeReasonCode.POST_CALL_CHECKPOINT_VERIFIED}
                ),
                may_invoke_external_model=False,
                checkpoint_sequence=latest_checkpoint.sequence,
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
