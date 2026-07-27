"""Deterministic action planning for the continuous Commerce Lead Loop."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.commerce.agents.context_loader import ContextPacketLoader
from app.commerce.agents.contracts import (
    AgentBudgetLimit,
    LeadContextPacket,
    PathEvidenceScope,
    PathType,
)
from app.commerce.agents.goal_loop import GoalStopReason
from app.commerce.agents.lead import path_evidence_scopes_from_events
from app.commerce.agents.router import DynamicPathPlan
from app.commerce.api.data_service import CommerceDataService
from app.commerce.domain.enums import RunStatus, RunType
from app.commerce.domain.events import DomainEventEnvelope
from app.commerce.domain.ids import RunId, WorkspaceId
from app.commerce.domain.models import CommerceModel
from app.commerce.domain.runs import CommerceRun
from app.commerce.persistence.events import SqlDomainEventStore
from app.commerce.persistence.runs import (
    RunCheckpointRecord,
    SqlRunCheckpointRepository,
    SqlRunRepository,
)


class LeadAction(StrEnum):
    INVESTIGATE = "investigate"
    REPLAN = "replan"
    WAIT = "wait"
    ANSWER = "answer"
    STOP = "stop"


class LeadTurnIntent(StrEnum):
    START = "start"
    READ_ONLY_QUESTION = "read_only_question"
    NEW_INVESTIGATION_ANGLE = "new_investigation_angle"
    WAIT = "wait"
    RESUME = "resume"
    CANCEL = "cancel"


class LeadActionReasonCode(StrEnum):
    MISSING_PATH_EVIDENCE = "missing_path_evidence"
    EXISTING_CONCLUSION_SUFFICIENT = "existing_conclusion_sufficient"
    EXPLICIT_NEW_ANGLE = "explicit_new_angle"
    PATH_ALREADY_COMPLETED = "path_already_completed"
    CAPABILITY_GAP_REQUIRES_UNKNOWN = "capability_gap_requires_unknown"
    NO_ROUTABLE_PATH_REQUIRES_UNKNOWN = "no_routable_path_requires_unknown"
    WAIT_REQUESTED = "wait_requested"
    RESUMED_FROM_WAIT = "resumed_from_wait"
    USER_CANCELLED = "user_cancelled"


class LeadTurnRequest(CommerceModel):
    intent: LeadTurnIntent
    question: str | None = Field(default=None, min_length=1)
    requested_paths: tuple[PathType, ...] = ()
    wait_reason: GoalStopReason | None = None

    @model_validator(mode="after")
    def keep_intent_payload_consistent(self) -> Self:
        if len(self.requested_paths) != len(set(self.requested_paths)):
            raise ValueError("Lead requested Paths must be unique")
        if self.intent is LeadTurnIntent.NEW_INVESTIGATION_ANGLE:
            if self.question is None or not self.requested_paths:
                raise ValueError("New investigation angle requires question and Paths")
        elif self.requested_paths:
            raise ValueError("Only a new investigation angle may request Paths")
        if self.intent is LeadTurnIntent.READ_ONLY_QUESTION and self.question is None:
            raise ValueError("Read-only question requires question text")
        if self.intent is LeadTurnIntent.WAIT:
            if self.wait_reason not in {
                GoalStopReason.AWAITING_USER_INPUT,
                GoalStopReason.AWAITING_APPROVAL,
            }:
                raise ValueError("Lead wait requires a resumable wait reason")
        elif self.wait_reason is not None:
            raise ValueError("Only a wait request may carry wait_reason")
        return self


class LeadPlanningState(CommerceModel):
    completed_path_types: tuple[PathType, ...] = ()
    persisted_evidence_count: int = Field(default=0, ge=0)
    latest_hypothesis_count: int = Field(default=0, ge=0)
    wait_reason: GoalStopReason | None = None

    @model_validator(mode="after")
    def keep_persisted_state_coherent(self) -> Self:
        if len(self.completed_path_types) != len(set(self.completed_path_types)):
            raise ValueError("Completed Lead Path types must be unique")
        if self.wait_reason not in {
            None,
            GoalStopReason.AWAITING_USER_INPUT,
            GoalStopReason.AWAITING_APPROVAL,
        }:
            raise ValueError("Lead planning wait_reason must be resumable")
        return self

    @property
    def has_existing_conclusion(self) -> bool:
        return bool(self.persisted_evidence_count or self.latest_hypothesis_count)


class PersistedLeadObservation(CommerceModel):
    """Lead-visible state reconstructed without Path memory or chat history."""

    run: CommerceRun
    context: LeadContextPacket
    case_events: tuple[DomainEventEnvelope, ...]
    run_events: tuple[DomainEventEnvelope, ...]
    latest_checkpoint: RunCheckpointRecord | None = None
    path_scopes: tuple[PathEvidenceScope, ...] = ()
    scope_run_ids: tuple[RunId, ...] = ()
    planning_state: LeadPlanningState

    @model_validator(mode="after")
    def keep_observation_persisted_and_case_scoped(self) -> Self:
        identity = (self.run.workspace_id, self.run.case_id)
        if (
            self.context.case.workspace_id,
            self.context.case.case_id,
        ) != identity:
            raise ValueError("Lead observation Context must match Run Case")
        if any(
            (event.workspace_id, event.case_id) != identity
            for event in self.case_events
        ):
            raise ValueError("Lead Case events must belong to the observed Case")
        if any(
            event.workspace_id != self.run.workspace_id
            or event.run_id != self.run.id
            for event in self.run_events
        ):
            raise ValueError("Lead Run events must belong to the observed Run")
        if self.latest_checkpoint is not None and (
            self.latest_checkpoint.workspace_id != self.run.workspace_id
            or self.latest_checkpoint.case_id != self.run.case_id
            or self.latest_checkpoint.run_id != self.run.id
        ):
            raise ValueError("Lead Checkpoint must belong to the observed Run")
        if (
            not self.scope_run_ids
            or self.scope_run_ids[-1] != self.run.id
            or len(self.scope_run_ids) != len(set(self.scope_run_ids))
        ):
            raise ValueError("Lead scope Run lineage must end at the observed Run")
        allowed_run_ids = set(self.scope_run_ids)
        current_scopes = tuple(
            scope for scope in self.path_scopes if scope.run_id in allowed_run_ids
        )
        completed_paths = tuple(
            dict.fromkeys(scope.path_type for scope in current_scopes)
        )
        if self.planning_state.completed_path_types != completed_paths:
            raise ValueError("Lead planning Paths must derive from persisted scopes")
        if self.planning_state.persisted_evidence_count != len(
            self.context.evidence
        ):
            raise ValueError("Lead planning Evidence count must match reloaded Case")
        if self.planning_state.latest_hypothesis_count != len(
            self.context.hypotheses
        ):
            raise ValueError("Lead planning Hypothesis count must match reloaded Case")
        return self


class LeadObservationError(LookupError):
    """Raised when a requested persisted Run cannot be observed."""


class CommerceLeadObserver:
    """Reload all Lead-visible state from repositories on every turn."""

    def __init__(
        self,
        *,
        data_service: CommerceDataService,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._contexts = ContextPacketLoader(
            data_service=data_service,
            session_factory=session_factory,
        )
        self._runs = SqlRunRepository(session_factory)
        self._checkpoints = SqlRunCheckpointRepository(session_factory)
        self._events = SqlDomainEventStore(session_factory)

    async def observe(
        self,
        workspace_id: WorkspaceId,
        run_id: RunId,
        *,
        budget: AgentBudgetLimit,
    ) -> PersistedLeadObservation:
        run = await self._runs.get(workspace_id, run_id)
        if run is None:
            raise LeadObservationError(f"Investigation Run not found: {run_id}")
        context = await self._contexts.load_case_packet(
            workspace_id,
            run.case_id,
            goal=run.goal,
            budget=budget,
        )
        case_events = await self._events.list_case(workspace_id, run.case_id)
        run_events = await self._events.list_run(workspace_id, run.id)
        latest_checkpoint = await self._checkpoints.get_latest(workspace_id, run.id)
        path_scopes = path_evidence_scopes_from_events(case_events)
        scope_run_ids = await self._scope_run_lineage(run)
        allowed_run_ids = set(scope_run_ids)
        current_scopes = tuple(
            scope for scope in path_scopes if scope.run_id in allowed_run_ids
        )
        wait_reason = None
        if latest_checkpoint is not None:
            wait_reason = latest_checkpoint.checkpoint.wait_reason
        elif run.status is RunStatus.WAITING and run.wait_reason is not None:
            try:
                wait_reason = GoalStopReason(run.wait_reason)
            except ValueError as exc:
                raise ValueError("Persisted Run wait_reason is not a GoalStopReason") from exc
        planning_state = LeadPlanningState(
            completed_path_types=tuple(
                dict.fromkeys(scope.path_type for scope in current_scopes)
            ),
            persisted_evidence_count=len(context.evidence),
            latest_hypothesis_count=len(context.hypotheses),
            wait_reason=wait_reason,
        )
        return PersistedLeadObservation(
            run=run,
            context=context,
            case_events=case_events,
            run_events=run_events,
            latest_checkpoint=latest_checkpoint,
            path_scopes=path_scopes,
            scope_run_ids=scope_run_ids,
            planning_state=planning_state,
        )

    async def _scope_run_lineage(self, run: CommerceRun) -> tuple[RunId, ...]:
        lineage = [run.id]
        current = run
        while current.parent_run_id is not None:
            if current.run_type is not RunType.REPLAN:
                raise ValueError("Only Replan Runs may inherit parent Path scopes")
            parent = await self._runs.get(current.workspace_id, current.parent_run_id)
            if parent is None:
                raise LeadObservationError(
                    f"Parent Run not found: {current.parent_run_id}"
                )
            if (
                parent.workspace_id != run.workspace_id
                or parent.case_id != run.case_id
            ):
                raise ValueError("Replan parent Run must belong to the same Case")
            if parent.id in lineage:
                raise ValueError("Replan Run lineage contains a cycle")
            lineage.append(parent.id)
            current = parent
        return tuple(reversed(lineage))


class LeadActionDecision(CommerceModel):
    schema_version: str = "commerce.lead-action-decision@1.0.0"
    action: LeadAction
    selected_paths: tuple[PathType, ...] = ()
    read_only: bool = False
    stop_reason: GoalStopReason | None = None
    reason_codes: frozenset[LeadActionReasonCode] = Field(min_length=1)

    @model_validator(mode="after")
    def keep_action_contract_consistent(self) -> Self:
        if len(self.selected_paths) != len(set(self.selected_paths)):
            raise ValueError("Lead selected Paths must be unique")
        if self.action in {LeadAction.INVESTIGATE, LeadAction.REPLAN}:
            if not self.selected_paths:
                raise ValueError("Investigate or replan requires selected Paths")
            if self.read_only or self.stop_reason is not None:
                raise ValueError("Investigate or replan cannot be read-only or stopped")
            return self
        if self.selected_paths:
            if self.action is LeadAction.ANSWER:
                raise ValueError("Answer cannot schedule Paths")
            raise ValueError("Only investigate or replan may schedule Paths")
        if self.action is LeadAction.ANSWER:
            if not self.read_only:
                raise ValueError("Answer must be read-only")
            if self.stop_reason is not None:
                raise ValueError("Answer cannot carry a stop reason")
        elif self.action is LeadAction.WAIT:
            if self.stop_reason not in {
                GoalStopReason.AWAITING_USER_INPUT,
                GoalStopReason.AWAITING_APPROVAL,
            }:
                raise ValueError("Wait requires a resumable stop reason")
            if self.read_only:
                raise ValueError("Wait is not a read-only answer")
        elif self.action is LeadAction.STOP:
            if self.stop_reason is None:
                raise ValueError("Stop requires stop_reason")
            if self.read_only:
                raise ValueError("Stop is not a read-only answer")
        return self


class LeadLoopPlanner:
    """Choose one bounded Lead action without invoking a model or Path runtime."""

    def decide(
        self,
        *,
        request: LeadTurnRequest,
        state: LeadPlanningState,
        route_plan: DynamicPathPlan,
    ) -> LeadActionDecision:
        routable = tuple(item.path_type for item in route_plan.assignments)
        completed = set(state.completed_path_types)

        if request.intent is LeadTurnIntent.CANCEL:
            return LeadActionDecision(
                action=LeadAction.STOP,
                stop_reason=GoalStopReason.CANCELLED,
                reason_codes=frozenset({LeadActionReasonCode.USER_CANCELLED}),
            )
        if request.intent is LeadTurnIntent.WAIT:
            assert request.wait_reason is not None
            return LeadActionDecision(
                action=LeadAction.WAIT,
                stop_reason=request.wait_reason,
                reason_codes=frozenset({LeadActionReasonCode.WAIT_REQUESTED}),
            )
        if request.intent is LeadTurnIntent.NEW_INVESTIGATION_ANGLE:
            requested = set(request.requested_paths)
            selected = tuple(
                path
                for path in routable
                if path in requested and path not in completed
            )
            if selected:
                return LeadActionDecision(
                    action=LeadAction.REPLAN,
                    selected_paths=selected,
                    reason_codes=frozenset(
                        {
                            LeadActionReasonCode.EXPLICIT_NEW_ANGLE,
                            LeadActionReasonCode.MISSING_PATH_EVIDENCE,
                        }
                    ),
                )
            if requested & completed:
                return self._answer(LeadActionReasonCode.PATH_ALREADY_COMPLETED)
            return self._answer(
                LeadActionReasonCode.CAPABILITY_GAP_REQUIRES_UNKNOWN
            )

        if (
            request.intent is LeadTurnIntent.READ_ONLY_QUESTION
            and state.has_existing_conclusion
        ):
            return self._answer(
                LeadActionReasonCode.EXISTING_CONCLUSION_SUFFICIENT
            )

        selected = tuple(path for path in routable if path not in completed)
        if selected:
            reasons = {LeadActionReasonCode.MISSING_PATH_EVIDENCE}
            if request.intent is LeadTurnIntent.RESUME:
                reasons.add(LeadActionReasonCode.RESUMED_FROM_WAIT)
            return LeadActionDecision(
                action=LeadAction.INVESTIGATE,
                selected_paths=selected,
                reason_codes=frozenset(reasons),
            )
        if state.has_existing_conclusion:
            return self._answer(
                LeadActionReasonCode.EXISTING_CONCLUSION_SUFFICIENT
            )
        return self._answer(
            LeadActionReasonCode.NO_ROUTABLE_PATH_REQUIRES_UNKNOWN
        )

    @staticmethod
    def _answer(reason: LeadActionReasonCode) -> LeadActionDecision:
        return LeadActionDecision(
            action=LeadAction.ANSWER,
            read_only=True,
            reason_codes=frozenset({reason}),
        )
