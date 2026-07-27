"""Application services for Action proposal and human Approval decisions."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.commerce.actions.approval import (
    ApprovalDecisionCommand,
    ApprovalDecisionType,
    ApprovalRequest,
)
from app.commerce.actions.contracts import ActionDraft
from app.commerce.actions.policy import (
    ActionPolicyDisposition,
    ActionPolicyGate,
)
from app.commerce.actions.validator import ActionValidator
from app.commerce.agents.contracts import LeadContextPacket
from app.commerce.domain.enums import ActionStatus, ApprovalStatus
from app.commerce.domain.events import DomainEventActor, DomainEventEnvelope
from app.commerce.domain.ids import (
    ActionId,
    CorrelationId,
    TraceId,
    WorkspaceId,
)
from app.commerce.domain.models import Action, ApprovalRequirement, CommerceModel
from app.commerce.persistence.actions import (
    ActionRecord,
    SqlActionRepository,
    SqlApprovalRepository,
)
from app.commerce.persistence.repositories import SqlCaseRepository
from app.commerce.persistence.unit_of_work import SqlCommerceUnitOfWork


class ActionProposalError(ValueError):
    pass


class ApprovalDecisionError(ValueError):
    pass


class ActionProposalResult(CommerceModel):
    record: ActionRecord
    approval: ApprovalRequest | None = None
    events: tuple[DomainEventEnvelope, ...]
    created: bool


class ApprovalDecisionResult(CommerceModel):
    record: ActionRecord
    approval: ApprovalRequest
    command: ApprovalDecisionCommand
    events: tuple[DomainEventEnvelope, ...] = ()
    replayed: bool = False


class ActionProposalService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        policy_gate: ActionPolicyGate | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._validator = ActionValidator()
        self._policy = policy_gate or ActionPolicyGate()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._actions = SqlActionRepository(session_factory)
        self._approvals = SqlApprovalRepository(session_factory)
        self._cases = SqlCaseRepository(session_factory)
        self._uow = SqlCommerceUnitOfWork(session_factory)

    async def propose(
        self,
        draft: ActionDraft,
        context: LeadContextPacket,
        *,
        actor: DomainEventActor,
        actor_id: str | None = None,
        correlation_id: CorrelationId,
    ) -> ActionProposalResult:
        existing = await self._actions.get(draft.workspace_id, draft.id)
        if existing is not None:
            if existing.decision.validated.draft != draft:
                raise ActionProposalError("Action ID was reused with another Draft")
            approval = await self._approvals.get_by_action(
                draft.workspace_id,
                draft.id,
            )
            return ActionProposalResult(
                record=existing,
                approval=approval,
                events=(),
                created=False,
            )

        validated = self._validator.validate(draft, context)
        decision = self._policy.evaluate(validated)
        occurred_at = self._clock()
        approval = None
        if decision.disposition is ActionPolicyDisposition.APPROVAL_REQUIRED:
            approval = ApprovalRequest.from_policy(
                decision,
                occurred_at=occurred_at,
            )
            requirement = decision.action.approval.model_copy(update={"approval_id": approval.id})
            action = Action.model_validate(
                {
                    **decision.action.model_dump(mode="python"),
                    "approval": requirement,
                }
            )
            decision = decision.model_copy(update={"action": action})

        case = await self._cases.get(draft.workspace_id, draft.case_id)
        if case is None:
            raise ActionProposalError("Action Case does not exist")
        if case.version != context.case.version:
            raise ActionProposalError("Action context is stale for the current Case")
        updated_case = case.model_copy(
            update={
                "action_ids": (*case.action_ids, draft.id),
                "updated_at": max(occurred_at, case.updated_at),
                "version": case.version + 1,
            }
        )
        record = ActionRecord.from_policy(decision, occurred_at=occurred_at)
        events = await self._uow.create_action(
            updated_case,
            record,
            approval=approval,
            expected_case_version=case.version,
            trace_id=TraceId.new(),
            correlation_id=correlation_id,
            actor=actor,
            actor_id=actor_id,
        )
        return ActionProposalResult(
            record=record,
            approval=approval,
            events=events,
            created=True,
        )


class ApprovalDecisionService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._actions = SqlActionRepository(session_factory)
        self._approvals = SqlApprovalRepository(session_factory)
        self._uow = SqlCommerceUnitOfWork(session_factory)

    async def decide(
        self,
        workspace_id: WorkspaceId,
        action_id: ActionId,
        *,
        decision: ApprovalDecisionType,
        actor_id: str,
        idempotency_key: str,
        reason: str | None = None,
        replacement_draft: ActionDraft | None = None,
        correlation_id: CorrelationId,
    ) -> ApprovalDecisionResult:
        record = await self._actions.get(workspace_id, action_id)
        approval = await self._approvals.get_by_action(workspace_id, action_id)
        if record is None or approval is None:
            raise ApprovalDecisionError("Approval-gated Action was not found")
        key_sha256 = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
        existing = await self._approvals.get_decision_by_idempotency(
            workspace_id,
            action_id,
            key_sha256,
        )
        if existing is not None:
            if existing.decision is not decision or existing.actor_id != actor_id or existing.reason != reason or existing.replacement_draft != replacement_draft:
                raise ApprovalDecisionError("Approval idempotency key was reused with another decision")
            current_record = await self._actions.get(workspace_id, action_id)
            current_approval = await self._approvals.get_by_action(
                workspace_id,
                action_id,
            )
            assert current_record is not None and current_approval is not None
            return ApprovalDecisionResult(
                record=current_record,
                approval=current_approval,
                command=existing,
                replayed=True,
            )

        occurred_at = self._clock()
        command = ApprovalDecisionCommand(
            workspace_id=workspace_id,
            case_id=approval.case_id,
            action_id=action_id,
            approval_id=approval.id,
            decision=decision,
            actor_id=actor_id,
            idempotency_key_sha256=key_sha256,
            reason=reason,
            replacement_draft=replacement_draft,
            created_at=occurred_at,
        )
        if decision is ApprovalDecisionType.APPROVE:
            updated_approval = approval.approve(
                actor_id,
                occurred_at=occurred_at,
            )
        elif decision is ApprovalDecisionType.REJECT:
            updated_approval = approval.reject(
                actor_id,
                occurred_at=occurred_at,
            )
        else:
            assert replacement_draft is not None
            replacement_sha256 = hashlib.sha256(replacement_draft.model_dump_json().encode("utf-8")).hexdigest()
            updated_approval = approval.modify(
                actor_id,
                replacement_draft_sha256=replacement_sha256,
                occurred_at=occurred_at,
            )

        updated_record = record
        target_status = None
        if updated_approval.status is ApprovalStatus.APPROVED:
            target_status = ActionStatus.APPROVED
        elif updated_approval.status in {
            ApprovalStatus.REJECTED,
            ApprovalStatus.REVOKED,
        }:
            target_status = ActionStatus.REJECTED
        if target_status is not None:
            requirement = ApprovalRequirement(
                required=True,
                status=updated_approval.status,
                approval_id=updated_approval.id,
                reason=record.action.approval.reason,
            )
            action = Action.model_validate(
                {
                    **record.action.model_dump(mode="python"),
                    "status": target_status,
                    "approval": requirement,
                }
            )
            updated_record = record.with_action(action, occurred_at=occurred_at)

        events = await self._uow.apply_approval_decision(
            updated_record,
            updated_approval,
            command,
            expected_action_version=record.version,
            expected_approval_version=approval.version,
            prior_action_status=record.action.status.value,
            trace_id=TraceId.new(),
            correlation_id=correlation_id,
        )
        return ApprovalDecisionResult(
            record=updated_record,
            approval=updated_approval,
            command=command,
            events=events,
        )
