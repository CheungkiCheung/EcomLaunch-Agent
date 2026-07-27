"""Durable deterministic Follow-up Runs over post-Action Commerce data."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.commerce.actions.artifacts import (
    ActionArtifactStatus,
    MetricMonitorArtifact,
)
from app.commerce.actions.contracts import (
    MetricComparison,
    MetricMonitorParameters,
)
from app.commerce.actions.follow_up_contracts import (
    FollowUpAttributionMethod,
    FollowUpComparisonBasis,
    FollowUpRecord,
    FollowUpSignalStatus,
    FollowUpStatus,
)
from app.commerce.api.data_service import CommerceDataService
from app.commerce.domain.enums import (
    ActionStatus,
    CaseStatus,
    FollowUpOutcome,
    RunPhase,
    RunStatus,
    RunType,
    SemanticStatus,
)
from app.commerce.domain.ids import (
    ActionId,
    CorrelationId,
    DatasetId,
    FollowUpId,
    RunId,
    TraceId,
    WorkspaceId,
)
from app.commerce.domain.models import (
    Action,
    Case,
    CommerceModel,
    MetricObservation,
)
from app.commerce.domain.runs import CommerceRun
from app.commerce.metrics.registry import MetricEngine, MetricName, MetricWindow
from app.commerce.persistence.action_artifacts import SqlActionArtifactRepository
from app.commerce.persistence.actions import ActionRecord, SqlActionRepository
from app.commerce.persistence.follow_ups import SqlFollowUpRepository
from app.commerce.persistence.lineage import SqlCaseLineageRepository
from app.commerce.persistence.repositories import SqlCaseRepository
from app.commerce.persistence.runs import SqlRunLeaseRepository, SqlRunRepository
from app.commerce.persistence.unit_of_work import SqlCommerceUnitOfWork


class FollowUpError(ValueError):
    pass


class FollowUpStartResult(CommerceModel):
    run: CommerceRun
    follow_up: FollowUpRecord
    created: bool


class FollowUpEvaluationResult(CommerceModel):
    run: CommerceRun
    follow_up: FollowUpRecord
    record: ActionRecord
    case: Case
    replayed: bool = False


def _stable_ids(
    workspace_id: WorkspaceId,
    action_id: ActionId,
    key_sha256: str,
) -> tuple[FollowUpId, RunId]:
    follow_value = uuid5(
        NAMESPACE_URL,
        f"commerce.follow-up@1:{workspace_id}:{action_id}:{key_sha256}",
    )
    run_value = uuid5(
        NAMESPACE_URL,
        f"commerce.follow-up-run@1:{workspace_id}:{action_id}:{key_sha256}",
    )
    return (
        FollowUpId(f"follow_{follow_value.hex}"),
        RunId(f"run_{run_value.hex}"),
    )


def _instant(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _action_with_status(
    record: ActionRecord,
    status: ActionStatus,
    *,
    occurred_at: datetime,
) -> ActionRecord:
    action = Action.model_validate(
        {
            **record.action.model_dump(mode="python"),
            "status": status,
        }
    )
    return record.with_action(action, occurred_at=occurred_at)


class FollowUpService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        data_service: CommerceDataService,
        clock: Callable[[], datetime] | None = None,
        minimum_sample_size: int = 20,
        lease_ttl: timedelta = timedelta(minutes=5),
    ) -> None:
        if minimum_sample_size < 1:
            raise ValueError("Follow-up minimum sample size must be positive")
        self._data = data_service
        self._clock = clock or (lambda: datetime.now(UTC))
        self._minimum_sample_size = minimum_sample_size
        self._lease_ttl = lease_ttl
        self._metric_engine = MetricEngine()
        self._actions = SqlActionRepository(session_factory)
        self._artifacts = SqlActionArtifactRepository(session_factory)
        self._cases = SqlCaseRepository(session_factory)
        self._lineage = SqlCaseLineageRepository(session_factory)
        self._follow_ups = SqlFollowUpRepository(session_factory)
        self._runs = SqlRunRepository(session_factory)
        self._leases = SqlRunLeaseRepository(session_factory)
        self._uow = SqlCommerceUnitOfWork(session_factory)

    async def start(
        self,
        workspace_id: WorkspaceId,
        action_id: ActionId,
        *,
        dataset_id: DatasetId,
        evaluation_window: MetricWindow,
        idempotency_key: str,
        actor_id: str,
    ) -> FollowUpStartResult:
        if len(idempotency_key) < 8 or len(idempotency_key) > 128:
            raise FollowUpError("Follow-up idempotency key must contain 8-128 characters")
        if not actor_id.strip():
            raise FollowUpError("Follow-up actor ID cannot be blank")
        record = await self._actions.get(workspace_id, action_id)
        if record is None:
            raise FollowUpError("Commerce Action was not found")
        key_sha256 = hashlib.sha256(f"follow_up:{idempotency_key}".encode()).hexdigest()
        existing_run = await self._runs.get_by_idempotency_key(
            workspace_id,
            record.action.case_id,
            key_sha256,
        )
        if existing_run is not None:
            existing = await self._follow_ups.get_by_run(
                workspace_id,
                existing_run.id,
            )
            if existing is None or existing.action_id != action_id or existing.dataset_id != dataset_id or existing.evaluation_window != evaluation_window:
                raise FollowUpError("Follow-up idempotency key was reused for another request")
            return FollowUpStartResult(
                run=existing_run,
                follow_up=existing,
                created=False,
            )
        if record.action.status not in {
            ActionStatus.MONITORING,
            ActionStatus.SUCCEEDED,
        }:
            raise FollowUpError(f"Action status {record.action.status.value} cannot start Follow-up")
        case = await self._cases.get(workspace_id, record.action.case_id)
        if case is None:
            raise FollowUpError("Commerce Case was not found")
        if case.status is not CaseStatus.MONITORING:
            raise FollowUpError("Follow-up requires the Case to be in monitoring state")
        artifact = await self._artifacts.get(workspace_id, action_id)
        if artifact is None or artifact.status is not ActionArtifactStatus.ACTIVE or not isinstance(artifact.payload, MetricMonitorArtifact):
            raise FollowUpError("Follow-up requires an active deterministic Metric Monitor artifact")
        self._data.get_view(workspace_id, dataset_id)
        occurred_at = self._clock()
        follow_up_id, run_id = _stable_ids(workspace_id, action_id, key_sha256)
        run = CommerceRun(
            id=run_id,
            workspace_id=workspace_id,
            case_id=record.action.case_id,
            run_type=RunType.FOLLOW_UP,
            phase=RunPhase.EVALUATING_FOLLOW_UP,
            goal=f"Evaluate post-Action signal for {action_id}",
            idempotency_key_sha256=key_sha256,
            subject_action_id=action_id,
            created_at=occurred_at,
            updated_at=occurred_at,
        )
        follow_up = FollowUpRecord(
            id=follow_up_id,
            workspace_id=workspace_id,
            case_id=record.action.case_id,
            action_id=action_id,
            run_id=run.id,
            dataset_id=dataset_id,
            evaluation_window=evaluation_window,
            minimum_sample_size=self._minimum_sample_size,
            created_at=occurred_at,
            updated_at=occurred_at,
        )
        await self._uow.create_follow_up_run(
            follow_up,
            run,
            trace_id=TraceId.new(),
            correlation_id=CorrelationId.new(),
            actor_id=actor_id,
        )
        return FollowUpStartResult(
            run=run,
            follow_up=follow_up,
            created=True,
        )

    async def evaluate(
        self,
        workspace_id: WorkspaceId,
        run_id: RunId,
        *,
        worker_id: str,
    ) -> FollowUpEvaluationResult:
        run = await self._runs.get(workspace_id, run_id)
        follow_up = await self._follow_ups.get_by_run(workspace_id, run_id)
        if run is None or run.run_type is not RunType.FOLLOW_UP or follow_up is None:
            raise FollowUpError("Follow-up Run was not found")
        record = await self._require_action(workspace_id, follow_up.action_id)
        case = await self._require_case(workspace_id, follow_up.case_id)
        if run.status is RunStatus.COMPLETED:
            return FollowUpEvaluationResult(
                run=run,
                follow_up=follow_up,
                record=record,
                case=case,
                replayed=True,
            )
        if run.status is not RunStatus.QUEUED:
            raise FollowUpError(f"Follow-up Run status {run.status.value} is not evaluable")
        occurred_at = self._clock()
        trace_id = TraceId.new()
        correlation_id = CorrelationId.new()
        grant = await self._leases.acquire(
            workspace_id,
            run_id,
            worker_id=worker_id,
            ttl=self._lease_ttl,
            acquired_at=occurred_at,
            trace_id=trace_id,
            correlation_id=correlation_id,
        )
        lineage = await self._lineage.get(workspace_id, follow_up.case_id)
        evaluation = self._evaluate_signal(follow_up, record, lineage)
        completed_follow_up = follow_up.complete(
            **evaluation,
            occurred_at=occurred_at,
        )
        action_status = ActionStatus.INCONCLUSIVE
        case_status = {
            FollowUpSignalStatus.TARGET_MET: CaseStatus.RESOLVED,
            FollowUpSignalStatus.TARGET_MISSED: CaseStatus.REOPENED,
            FollowUpSignalStatus.UNAVAILABLE: CaseStatus.INCONCLUSIVE,
        }[completed_follow_up.signal_status]
        completed_record = _action_with_status(
            record,
            action_status,
            occurred_at=occurred_at,
        )
        completed_case = case.transition_to(
            case_status,
            occurred_at=occurred_at,
        )
        completed_run = grant.run.transition_to(
            RunStatus.COMPLETED,
            phase=RunPhase.EVALUATING_FOLLOW_UP,
            stop_reason=f"follow_up_{completed_follow_up.outcome.value}",
            occurred_at=occurred_at,
        )
        await self._uow.finish_follow_up(
            completed_follow_up,
            completed_record,
            completed_case,
            completed_run,
            prior_action_status=record.action.status.value,
            prior_case_status=case.status,
            expected_follow_up_version=follow_up.version,
            expected_action_version=record.version,
            expected_case_version=case.version,
            expected_run_version=grant.run.version,
            trace_id=trace_id,
            correlation_id=correlation_id,
            lease=grant.credentials,
            lease_checked_at=occurred_at,
        )
        await self._leases.release(
            workspace_id,
            run_id,
            grant.credentials,
            released_at=occurred_at,
            trace_id=trace_id,
            correlation_id=correlation_id,
        )
        return FollowUpEvaluationResult(
            run=completed_run,
            follow_up=completed_follow_up,
            record=completed_record,
            case=completed_case,
        )

    async def list_action(
        self,
        workspace_id: WorkspaceId,
        action_id: ActionId,
    ) -> tuple[FollowUpRecord, ...] | None:
        if await self._actions.get(workspace_id, action_id) is None:
            return None
        return await self._follow_ups.list_action(workspace_id, action_id)

    def _evaluate_signal(
        self,
        follow_up: FollowUpRecord,
        record: ActionRecord,
        lineage,
    ) -> dict:
        causal_limit = "This observational Follow-up cannot establish causal impact from the Action."
        parameters = record.decision.validated.draft.parameters
        if not isinstance(parameters, MetricMonitorParameters):
            return self._inconclusive(
                assessment=("No deterministic target metric is attached to this Action; no causal effectiveness conclusion is permitted."),
                limitations=(causal_limit, "Action has no Metric Monitor target."),
            )
        common = {
            "comparison_basis": FollowUpComparisonBasis.METRIC_MONITOR_THRESHOLD,
            "metric_name": parameters.metric_name,
            "comparison": parameters.comparison,
            "threshold": parameters.threshold,
        }
        if lineage is None:
            return self._inconclusive(
                **common,
                assessment=("Case lineage is unavailable; no causal effectiveness conclusion is permitted."),
                limitations=(causal_limit, "Case lineage is unavailable."),
            )
        if _instant(follow_up.evaluation_window.start) < _instant(lineage.current_end):
            return self._inconclusive(
                **common,
                assessment=("The Follow-up window overlaps the original Case window; no causal effectiveness conclusion is permitted."),
                limitations=(causal_limit, "Evaluation window overlaps Case context."),
            )
        try:
            normalized = self._data.normalize(
                follow_up.workspace_id,
                follow_up.dataset_id,
            )
            snapshot = self._metric_engine.compute_seller_window(
                normalized,
                seller_id=lineage.seller_external_key,
                window=follow_up.evaluation_window,
            )
            observation = snapshot.metric(MetricName(parameters.metric_name))
        except (KeyError, ValueError) as exc:
            return self._inconclusive(
                **common,
                assessment=("The target signal could not be recomputed; no causal effectiveness conclusion is permitted."),
                limitations=(causal_limit, f"Metric recomputation failed: {exc}"),
            )
        if observation.semantic_status in {SemanticStatus.UNKNOWN, SemanticStatus.BLOCKED} or observation.value is None:
            return self._inconclusive(
                **common,
                metric_observation=observation,
                assessment=("The target signal is unavailable; no causal effectiveness conclusion is permitted."),
                limitations=(
                    causal_limit,
                    observation.unknown_reason or "Target metric is unavailable.",
                ),
            )
        sample_size = observation.sample_size or 0
        if sample_size < follow_up.minimum_sample_size:
            return self._inconclusive(
                **common,
                metric_observation=observation,
                assessment=("The target signal has insufficient sample size; no causal effectiveness conclusion is permitted."),
                limitations=(
                    causal_limit,
                    f"Sample size {sample_size} is below {follow_up.minimum_sample_size}.",
                ),
            )
        value = Decimal(str(observation.value))
        passed = value <= parameters.threshold if parameters.comparison is MetricComparison.LESS_THAN_OR_EQUAL else value >= parameters.threshold
        signal_status = FollowUpSignalStatus.TARGET_MET if passed else FollowUpSignalStatus.TARGET_MISSED
        result_language = "met" if passed else "did not meet"
        return {
            **common,
            "metric_observation": observation,
            "signal_status": signal_status,
            "attribution_method": FollowUpAttributionMethod.NONE,
            "outcome": FollowUpOutcome.INCONCLUSIVE,
            "assessment": (
                f"The observed {parameters.metric_name} signal {result_language} the "
                f"configured threshold. The Case may change state from this signal, "
                f"but the Action outcome remains inconclusive because this is "
                f"observational and does not establish causal impact."
            ),
            "limitations": (causal_limit,),
        }

    @staticmethod
    def _inconclusive(
        *,
        assessment: str,
        limitations: tuple[str, ...],
        comparison_basis: FollowUpComparisonBasis = (FollowUpComparisonBasis.NO_RELIABLE_TARGET),
        metric_name: str | None = None,
        comparison: MetricComparison | None = None,
        threshold: Decimal | None = None,
        metric_observation: MetricObservation | None = None,
    ) -> dict:
        return {
            "comparison_basis": comparison_basis,
            "metric_name": metric_name,
            "comparison": comparison,
            "threshold": threshold,
            "metric_observation": metric_observation,
            "signal_status": FollowUpSignalStatus.UNAVAILABLE,
            "attribution_method": FollowUpAttributionMethod.NONE,
            "outcome": FollowUpOutcome.INCONCLUSIVE,
            "assessment": assessment,
            "limitations": limitations,
        }

    async def _require_action(
        self,
        workspace_id: WorkspaceId,
        action_id: ActionId,
    ) -> ActionRecord:
        record = await self._actions.get(workspace_id, action_id)
        if record is None:
            raise FollowUpError("Commerce Action was not found")
        return record

    async def _require_case(
        self,
        workspace_id: WorkspaceId,
        case_id,
    ) -> Case:
        case = await self._cases.get(workspace_id, case_id)
        if case is None:
            raise FollowUpError("Commerce Case was not found")
        return case


__all__ = [
    "FollowUpError",
    "FollowUpEvaluationResult",
    "FollowUpService",
    "FollowUpStartResult",
    "FollowUpStatus",
]
