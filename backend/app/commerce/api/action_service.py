"""HTTP-facing orchestration for deterministic Commerce Actions and Approvals."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.commerce.actions.approval import (
    ApprovalDecisionType,
    ApprovalRequest,
)
from app.commerce.actions.artifacts import ActionExecutionArtifact
from app.commerce.actions.contracts import ActionDraft, ActionParameters
from app.commerce.actions.follow_up_contracts import FollowUpRecord
from app.commerce.actions.planner import (
    ActionPlanningResult,
    FreshActionPlanner,
)
from app.commerce.actions.policy import ActionPolicyGate
from app.commerce.actions.service import (
    ActionProposalResult,
    ActionProposalService,
    ApprovalDecisionResult,
    ApprovalDecisionService,
)
from app.commerce.agents.context_loader import ContextPacketLoader
from app.commerce.agents.contracts import AgentBudgetLimit, LeadContextPacket
from app.commerce.api.data_service import CommerceDataService
from app.commerce.domain.events import DomainEventActor
from app.commerce.domain.ids import (
    ActionId,
    CaseId,
    CorrelationId,
    EvidenceId,
    HypothesisId,
    MetricObservationId,
    WorkspaceId,
)
from app.commerce.domain.models import CommerceModel, RollbackPlan
from app.commerce.persistence.action_artifacts import SqlActionArtifactRepository
from app.commerce.persistence.actions import (
    ActionRecord,
    SqlActionRepository,
    SqlApprovalRepository,
)
from app.commerce.persistence.follow_ups import SqlFollowUpRepository
from app.commerce.persistence.repositories import SqlCaseRepository


class CaseContextLoader(Protocol):
    async def load_case_packet(
        self,
        workspace_id: WorkspaceId,
        case_id: CaseId,
        *,
        goal: str,
        budget: AgentBudgetLimit,
    ) -> LeadContextPacket: ...


class ActionPlanner(Protocol):
    async def plan(
        self,
        context: LeadContextPacket,
        *,
        action_id: ActionId,
    ) -> ActionPlanningResult: ...


class PlannedActionProposalResult(CommerceModel):
    planning: ActionPlanningResult | None = None
    proposal: ActionProposalResult


def action_id_from_idempotency(
    workspace_id: WorkspaceId,
    case_id: CaseId,
    idempotency_key: str,
) -> ActionId:
    """Derive a stable opaque Action ID without persisting the raw key."""

    key_sha256 = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
    value = uuid5(
        NAMESPACE_URL,
        f"commerce.action@1:{workspace_id}:{case_id}:{key_sha256}",
    )
    return ActionId(f"act_{value.hex}")


class CommerceActionService:
    """Keep client identity fields outside the trusted Action Draft boundary."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        data_service: CommerceDataService | None = None,
        context_loader: CaseContextLoader | None = None,
        policy_gate: ActionPolicyGate | None = None,
        planner: ActionPlanner | None = None,
    ) -> None:
        if context_loader is None:
            if data_service is None:
                raise ValueError("CommerceActionService requires data_service or context_loader")
            context_loader = ContextPacketLoader(
                data_service=data_service,
                session_factory=session_factory,
            )
        self._context_loader = context_loader
        self._planner = planner or FreshActionPlanner()
        self._proposals = ActionProposalService(
            session_factory,
            policy_gate=policy_gate,
        )
        self._decisions = ApprovalDecisionService(session_factory)
        self._actions = SqlActionRepository(session_factory)
        self._artifacts = SqlActionArtifactRepository(session_factory)
        self._follow_ups = SqlFollowUpRepository(session_factory)
        self._approvals = SqlApprovalRepository(session_factory)
        self._cases = SqlCaseRepository(session_factory)

    @staticmethod
    def build_draft(
        workspace_id: WorkspaceId,
        case_id: CaseId,
        *,
        idempotency_key: str,
        title: str,
        description: str,
        evidence_ids: Sequence[EvidenceId],
        hypothesis_ids: Sequence[HypothesisId],
        expected_signal_metric_ids: Sequence[MetricObservationId],
        parameters: ActionParameters,
        rollback_plan: RollbackPlan,
    ) -> ActionDraft:
        return ActionDraft(
            id=action_id_from_idempotency(
                workspace_id,
                case_id,
                idempotency_key,
            ),
            workspace_id=workspace_id,
            case_id=case_id,
            title=title,
            description=description,
            evidence_ids=tuple(evidence_ids),
            hypothesis_ids=tuple(hypothesis_ids),
            expected_signal_metric_ids=tuple(expected_signal_metric_ids),
            parameters=parameters,
            rollback_plan=rollback_plan,
        )

    async def propose(
        self,
        workspace_id: WorkspaceId,
        case_id: CaseId,
        *,
        idempotency_key: str,
        title: str,
        description: str,
        evidence_ids: Sequence[EvidenceId],
        hypothesis_ids: Sequence[HypothesisId],
        expected_signal_metric_ids: Sequence[MetricObservationId],
        parameters: ActionParameters,
        rollback_plan: RollbackPlan,
        actor_id: str,
    ) -> ActionProposalResult:
        draft = self.build_draft(
            workspace_id,
            case_id,
            idempotency_key=idempotency_key,
            title=title,
            description=description,
            evidence_ids=evidence_ids,
            hypothesis_ids=hypothesis_ids,
            expected_signal_metric_ids=expected_signal_metric_ids,
            parameters=parameters,
            rollback_plan=rollback_plan,
        )
        context = await self._context_loader.load_case_packet(
            workspace_id,
            case_id,
            goal="Validate and policy-check a bounded Action proposal",
            budget=AgentBudgetLimit(),
        )
        return await self._proposals.propose(
            draft,
            context,
            actor=DomainEventActor.USER,
            actor_id=actor_id,
            correlation_id=CorrelationId.new(),
        )

    async def plan_and_propose(
        self,
        workspace_id: WorkspaceId,
        case_id: CaseId,
        *,
        idempotency_key: str,
        actor_id: str,
    ) -> PlannedActionProposalResult:
        action_id = action_id_from_idempotency(
            workspace_id,
            case_id,
            idempotency_key,
        )
        existing = await self._actions.get(workspace_id, action_id)
        if existing is not None:
            approval = await self._approvals.get_by_action(
                workspace_id,
                action_id,
            )
            return PlannedActionProposalResult(
                planning=None,
                proposal=ActionProposalResult(
                    record=existing,
                    approval=approval,
                    events=(),
                    created=False,
                ),
            )
        context = await self._context_loader.load_case_packet(
            workspace_id,
            case_id,
            goal="Choose one bounded internal Action from fresh persisted context",
            budget=AgentBudgetLimit(max_tokens=8_000),
        )
        planning = await self._planner.plan(
            context,
            action_id=action_id,
        )
        proposal = await self._proposals.propose(
            planning.validated.draft,
            context,
            actor=DomainEventActor.AGENT,
            actor_id=f"action-planner:{actor_id}",
            correlation_id=CorrelationId.new(),
        )
        return PlannedActionProposalResult(
            planning=planning,
            proposal=proposal,
        )

    async def get_action(
        self,
        workspace_id: WorkspaceId,
        action_id: ActionId,
    ) -> ActionRecord | None:
        return await self._actions.get(workspace_id, action_id)

    async def get_artifact(
        self,
        workspace_id: WorkspaceId,
        action_id: ActionId,
    ) -> ActionExecutionArtifact | None:
        return await self._artifacts.get(workspace_id, action_id)

    async def list_follow_ups(
        self,
        workspace_id: WorkspaceId,
        action_id: ActionId,
    ) -> tuple[FollowUpRecord, ...]:
        return await self._follow_ups.list_action(workspace_id, action_id)

    async def list_case_actions(
        self,
        workspace_id: WorkspaceId,
        case_id: CaseId,
    ) -> tuple[ActionRecord, ...] | None:
        case = await self._cases.get(workspace_id, case_id)
        if case is None:
            return None
        return await self._actions.list_case(workspace_id, case_id)

    async def get_approval(
        self,
        workspace_id: WorkspaceId,
        action_id: ActionId,
    ) -> ApprovalRequest | None:
        return await self._approvals.get_by_action(workspace_id, action_id)

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
    ) -> ApprovalDecisionResult:
        return await self._decisions.decide(
            workspace_id,
            action_id,
            decision=decision,
            actor_id=actor_id,
            idempotency_key=idempotency_key,
            reason=reason,
            replacement_draft=replacement_draft,
            correlation_id=CorrelationId.new(),
        )
