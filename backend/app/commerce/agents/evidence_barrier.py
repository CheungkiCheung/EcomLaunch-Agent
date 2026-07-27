"""Release only persisted Evidence after every selected Path reaches a terminal state."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from app.commerce.agents.subagent_adapter import (
    CommerceAgentTask,
    CommerceSubagentOutcome,
    CommerceSubagentStatus,
)
from app.commerce.agents.subagent_committer import CommerceSubagentCommitReceipt
from app.commerce.domain.ids import AgentTaskId
from app.commerce.domain.models import CommerceModel, Evidence
from app.commerce.persistence.work_records import EvidenceRepository


class EvidenceBarrierError(ValueError):
    """Raised when Path outcomes cannot prove a coherent persisted state."""


class EvidenceBarrierDisposition(StrEnum):
    WAITING = "waiting"
    READY = "ready"
    BLOCKED = "blocked"


class EvidenceBarrierReasonCode(StrEnum):
    NO_PATHS_SELECTED = "no_paths_selected"
    PATHS_STILL_RUNNING = "paths_still_running"
    AWAITING_PERSISTENCE = "awaiting_persistence"
    ALL_PATHS_COMPLETED = "all_paths_completed"
    PARTIAL_PATH_SUCCESS = "partial_path_success"
    NO_PATH_COMPLETED = "no_path_completed"


class EvidenceBarrierResult(CommerceModel):
    disposition: EvidenceBarrierDisposition
    reason_codes: frozenset[EvidenceBarrierReasonCode] = Field(min_length=1)
    may_synthesize: bool
    selected_task_ids: tuple[AgentTaskId, ...] = ()
    pending_task_ids: tuple[AgentTaskId, ...] = ()
    running_task_ids: tuple[AgentTaskId, ...] = ()
    awaiting_persistence_task_ids: tuple[AgentTaskId, ...] = ()
    completed_task_ids: tuple[AgentTaskId, ...] = ()
    blocked_task_ids: tuple[AgentTaskId, ...] = ()
    failed_task_ids: tuple[AgentTaskId, ...] = ()
    cancelled_task_ids: tuple[AgentTaskId, ...] = ()
    timed_out_task_ids: tuple[AgentTaskId, ...] = ()
    evidence: tuple[Evidence, ...] = ()

    @model_validator(mode="after")
    def keep_disposition_and_membership_consistent(self) -> Self:
        groups = (
            self.pending_task_ids,
            self.running_task_ids,
            self.awaiting_persistence_task_ids,
            self.completed_task_ids,
            self.blocked_task_ids,
            self.failed_task_ids,
            self.cancelled_task_ids,
            self.timed_out_task_ids,
        )
        for values in (self.selected_task_ids, *groups):
            if len(values) != len(set(values)):
                raise ValueError("Evidence Barrier task IDs must be unique")
        selected = set(self.selected_task_ids)
        if any(not set(values).issubset(selected) for values in groups):
            raise ValueError("Evidence Barrier state contains an unselected task")
        if self.disposition is EvidenceBarrierDisposition.READY:
            if not self.may_synthesize:
                raise ValueError("Ready Evidence Barrier must allow synthesis")
        elif self.may_synthesize:
            raise ValueError("Only a ready Evidence Barrier may allow synthesis")
        if self.disposition is EvidenceBarrierDisposition.WAITING and self.evidence:
            raise ValueError("Waiting Evidence Barrier cannot release Evidence")
        return self


class EvidenceBarrier:
    """Join 0-3 Path tasks only after their terminal commits are durable."""

    TERMINAL_STATUSES = frozenset(
        {
            CommerceSubagentStatus.COMPLETED,
            CommerceSubagentStatus.BLOCKED,
            CommerceSubagentStatus.FAILED,
            CommerceSubagentStatus.CANCELLED,
            CommerceSubagentStatus.TIMED_OUT,
        }
    )

    def __init__(self, evidence: EvidenceRepository) -> None:
        self._evidence = evidence

    async def evaluate(
        self,
        *,
        tasks: tuple[CommerceAgentTask, ...],
        outcomes: tuple[CommerceSubagentOutcome, ...],
        receipts: tuple[CommerceSubagentCommitReceipt, ...],
    ) -> EvidenceBarrierResult:
        self._validate_tasks(tasks)
        selected_ids = tuple(task.task_id for task in tasks)
        if not tasks:
            if outcomes or receipts:
                raise EvidenceBarrierError(
                    "Evidence Barrier received outcomes without selected tasks"
                )
            return EvidenceBarrierResult(
                disposition=EvidenceBarrierDisposition.READY,
                reason_codes=frozenset(
                    {EvidenceBarrierReasonCode.NO_PATHS_SELECTED}
                ),
                may_synthesize=True,
            )

        outcomes_by_task = self._index_outcomes(tasks, outcomes)
        receipts_by_task = self._index_receipts(tasks, receipts)
        pending: list[AgentTaskId] = []
        running: list[AgentTaskId] = []
        awaiting_persistence: list[AgentTaskId] = []
        completed: list[AgentTaskId] = []
        blocked: list[AgentTaskId] = []
        failed: list[AgentTaskId] = []
        cancelled: list[AgentTaskId] = []
        timed_out: list[AgentTaskId] = []
        persisted_evidence: list[Evidence] = []

        status_groups = {
            CommerceSubagentStatus.COMPLETED: completed,
            CommerceSubagentStatus.BLOCKED: blocked,
            CommerceSubagentStatus.FAILED: failed,
            CommerceSubagentStatus.CANCELLED: cancelled,
            CommerceSubagentStatus.TIMED_OUT: timed_out,
        }
        for task in tasks:
            outcome = outcomes_by_task.get(task.task_id)
            receipt = receipts_by_task.get(task.task_id)
            if outcome is None:
                if receipt is not None:
                    raise EvidenceBarrierError(
                        "Commit receipt exists without a Subagent outcome"
                    )
                pending.append(task.task_id)
                continue
            if outcome.status is CommerceSubagentStatus.PENDING:
                if receipt is not None:
                    raise EvidenceBarrierError(
                        "Pending Path cannot have a terminal commit receipt"
                    )
                pending.append(task.task_id)
                continue
            if outcome.status is CommerceSubagentStatus.RUNNING:
                if receipt is not None:
                    raise EvidenceBarrierError(
                        "Running Path cannot have a terminal commit receipt"
                    )
                running.append(task.task_id)
                continue
            if outcome.status not in self.TERMINAL_STATUSES:
                raise EvidenceBarrierError(
                    f"Unsupported Path status: {outcome.status.value}"
                )
            if receipt is None:
                awaiting_persistence.append(task.task_id)
                continue
            self._validate_receipt(task, outcome, receipt)
            status_groups[outcome.status].append(task.task_id)
            if outcome.status is CommerceSubagentStatus.COMPLETED:
                persisted_evidence.extend(
                    await self._load_completed_evidence(task, outcome, receipt)
                )
            elif receipt.evidence_ids:
                raise EvidenceBarrierError(
                    "Unsuccessful Path receipt cannot release Evidence"
                )

        waiting = bool(pending or running or awaiting_persistence)
        if waiting:
            reasons = set()
            if pending or running:
                reasons.add(EvidenceBarrierReasonCode.PATHS_STILL_RUNNING)
            if awaiting_persistence:
                reasons.add(EvidenceBarrierReasonCode.AWAITING_PERSISTENCE)
            return EvidenceBarrierResult(
                disposition=EvidenceBarrierDisposition.WAITING,
                reason_codes=frozenset(reasons),
                may_synthesize=False,
                selected_task_ids=selected_ids,
                pending_task_ids=tuple(pending),
                running_task_ids=tuple(running),
                awaiting_persistence_task_ids=tuple(awaiting_persistence),
            )

        common = {
            "selected_task_ids": selected_ids,
            "completed_task_ids": tuple(completed),
            "blocked_task_ids": tuple(blocked),
            "failed_task_ids": tuple(failed),
            "cancelled_task_ids": tuple(cancelled),
            "timed_out_task_ids": tuple(timed_out),
            "evidence": tuple(persisted_evidence),
        }
        if not completed:
            return EvidenceBarrierResult(
                disposition=EvidenceBarrierDisposition.BLOCKED,
                reason_codes=frozenset(
                    {EvidenceBarrierReasonCode.NO_PATH_COMPLETED}
                ),
                may_synthesize=False,
                **common,
            )
        unsuccessful = blocked or failed or cancelled or timed_out
        reason = (
            EvidenceBarrierReasonCode.PARTIAL_PATH_SUCCESS
            if unsuccessful
            else EvidenceBarrierReasonCode.ALL_PATHS_COMPLETED
        )
        return EvidenceBarrierResult(
            disposition=EvidenceBarrierDisposition.READY,
            reason_codes=frozenset({reason}),
            may_synthesize=True,
            **common,
        )

    @staticmethod
    def _validate_tasks(tasks: tuple[CommerceAgentTask, ...]) -> None:
        if len(tasks) > 3:
            raise EvidenceBarrierError("Evidence Barrier supports at most three Paths")
        task_ids = tuple(task.task_id for task in tasks)
        if len(task_ids) != len(set(task_ids)):
            raise EvidenceBarrierError("Selected Path task IDs must be unique")
        path_types = tuple(task.path_type for task in tasks)
        if len(path_types) != len(set(path_types)):
            raise EvidenceBarrierError("Selected Path types must be unique")
        if tasks:
            identity = (tasks[0].workspace_id, tasks[0].case_id, tasks[0].run_id)
            if any(
                (task.workspace_id, task.case_id, task.run_id) != identity
                for task in tasks[1:]
            ):
                raise EvidenceBarrierError(
                    "Selected Paths must belong to one Workspace, Case and Run"
                )

    @staticmethod
    def _index_outcomes(
        tasks: tuple[CommerceAgentTask, ...],
        outcomes: tuple[CommerceSubagentOutcome, ...],
    ) -> dict[AgentTaskId, CommerceSubagentOutcome]:
        selected = {task.task_id: task for task in tasks}
        indexed: dict[AgentTaskId, CommerceSubagentOutcome] = {}
        for outcome in outcomes:
            task = selected.get(outcome.task_id)
            if task is None:
                raise EvidenceBarrierError("Outcome belongs to an unselected Path")
            if outcome.task_id in indexed:
                raise EvidenceBarrierError("Path outcome task IDs must be unique")
            if outcome.path_type is not task.path_type:
                raise EvidenceBarrierError("Outcome PathType does not match selected task")
            indexed[outcome.task_id] = outcome
        return indexed

    @staticmethod
    def _index_receipts(
        tasks: tuple[CommerceAgentTask, ...],
        receipts: tuple[CommerceSubagentCommitReceipt, ...],
    ) -> dict[AgentTaskId, CommerceSubagentCommitReceipt]:
        selected = {task.task_id for task in tasks}
        indexed: dict[AgentTaskId, CommerceSubagentCommitReceipt] = {}
        for receipt in receipts:
            if receipt.task_id not in selected:
                raise EvidenceBarrierError("Receipt belongs to an unselected Path")
            if receipt.task_id in indexed:
                raise EvidenceBarrierError("Path receipt task IDs must be unique")
            indexed[receipt.task_id] = receipt
        return indexed

    @staticmethod
    def _validate_receipt(
        task: CommerceAgentTask,
        outcome: CommerceSubagentOutcome,
        receipt: CommerceSubagentCommitReceipt,
    ) -> None:
        if receipt.task_id != task.task_id or receipt.path_type is not task.path_type:
            raise EvidenceBarrierError("Receipt identity does not match selected task")
        if receipt.status is not outcome.status:
            raise EvidenceBarrierError("Receipt status does not match Path outcome")
        if not receipt.idempotent and (
            receipt.checkpoint_id is None or receipt.lifecycle_event_id is None
        ):
            raise EvidenceBarrierError(
                "Terminal Path receipt is missing persistence event identity"
            )

    async def _load_completed_evidence(
        self,
        task: CommerceAgentTask,
        outcome: CommerceSubagentOutcome,
        receipt: CommerceSubagentCommitReceipt,
    ) -> tuple[Evidence, ...]:
        if outcome.result is None:
            raise EvidenceBarrierError("Completed Path is missing PathResult")
        result_ids = tuple(item.evidence_id for item in outcome.result.evidence)
        if result_ids != receipt.evidence_ids:
            raise EvidenceBarrierError(
                "PathResult and commit receipt Evidence IDs do not match"
            )
        records: list[Evidence] = []
        for evidence_id in receipt.evidence_ids:
            evidence = await self._evidence.get(task.workspace_id, evidence_id)
            if evidence is None:
                raise EvidenceBarrierError(
                    f"Committed Evidence is not persisted: {evidence_id}"
                )
            if evidence.workspace_id != task.workspace_id or evidence.case_id != task.case_id:
                raise EvidenceBarrierError(
                    "Persisted Evidence identity does not match selected Path"
                )
            records.append(evidence)
        return tuple(records)
