"""Unified persisted four-Gold investigation release gate."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal, Self
from uuid import uuid4

from pydantic import Field, model_validator
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.commerce.agents.contracts import AgentBudgetLimit, PathType
from app.commerce.agents.lead_execution import CommerceLeadTurnService
from app.commerce.agents.lead_loop import LeadTurnIntent, LeadTurnRequest
from app.commerce.agents.subagent_adapter import CommerceSubagentStatus
from app.commerce.agents.verification import ClaimVerdict
from app.commerce.agents.verification_execution import (
    CommerceVerificationTurnService,
)
from app.commerce.api.analysis_service import CommerceAnalysisService
from app.commerce.api.data_service import CommerceDataService
from app.commerce.api.run_service import CommerceRunService
from app.commerce.data.capabilities import CapabilityRegistry
from app.commerce.data.gold_cases import load_evaluation_case
from app.commerce.domain.enums import FollowUpOutcome, RunStatus
from app.commerce.domain.evaluation import EvaluationCase
from app.commerce.domain.ids import CorrelationId, TraceId, WorkspaceId
from app.commerce.domain.models import CommerceModel
from app.commerce.evaluation.run_experiment import GoldCaseExperimentInputBuilder
from app.commerce.evaluation.runner import (
    CommerceEvaluationRunner,
    EvaluationObservation,
    EvaluationScorecard,
    RealModelEvidence,
    TraceObservation,
)
from app.commerce.metrics.registry import MetricWindow, PeerCohortPolicy
from app.commerce.persistence.events import SqlDomainEventStore
from app.commerce.persistence.runs import (
    SqlRunCheckpointRepository,
    SqlRunLeaseRepository,
)
from app.commerce.persistence.schema import create_commerce_schema

_PATH_NAMES = {
    PathType.FULFILLMENT: "FulfillmentPathAgent",
    PathType.SELLER_PEER: "SellerPeerPathAgent",
    PathType.REVIEW_EXPERIENCE: "ReviewExperiencePathAgent",
}


class AgentReleaseModelEvidence(CommerceModel):
    role: Literal["path", "lead", "verifier"]
    actual_model_identity: str = Field(min_length=1)
    provider_request_ids: tuple[str, ...] = Field(min_length=1)
    input_tokens: int = Field(ge=1)
    output_tokens: int = Field(ge=0)
    latency_ms: float = Field(ge=0)
    retry_count: int = Field(ge=0)

    @model_validator(mode="after")
    def keep_request_ids_unique(self) -> Self:
        if len(self.provider_request_ids) != len(set(self.provider_request_ids)):
            raise ValueError("Agent release model Provider Request IDs must be unique")
        return self

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class GoldAgentReleaseCaseResult(CommerceModel):
    case_key: str = Field(pattern=r"^GC-[A-Z]+-\d{3}$")
    workspace_id: str
    case_id: str
    run_id: str
    expected_paths: tuple[str, ...]
    actual_paths: tuple[str, ...]
    scorecard: EvaluationScorecard
    verification_passed: bool
    run_status: str
    stop_reason: str | None = None
    lease_released: bool
    event_count: int = Field(ge=1)
    checkpoint_count: int = Field(ge=1)
    final_answer_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_evidence: tuple[AgentReleaseModelEvidence, ...] = Field(min_length=3)

    @model_validator(mode="after")
    def keep_request_ids_unique(self) -> Self:
        request_ids = tuple(
            request_id
            for item in self.model_evidence
            for request_id in item.provider_request_ids
        )
        if len(request_ids) != len(set(request_ids)):
            raise ValueError("Agent release Case model requests must be unique")
        return self


class GoldAgentReleaseReport(CommerceModel):
    schema_version: str = "commerce.gold-agent-release@1.0.0"
    created_at: datetime
    passed: bool
    cases: tuple[GoldAgentReleaseCaseResult, ...] = Field(min_length=1)
    provider_request_ids: tuple[str, ...] = Field(min_length=1)
    total_tokens: int = Field(ge=1)
    total_latency_ms: float = Field(ge=0)
    audit_path: str = Field(min_length=1)

    @model_validator(mode="after")
    def keep_report_consistent(self) -> Self:
        evidence = tuple(
            item
            for case_result in self.cases
            for item in case_result.model_evidence
        )
        request_ids = tuple(
            request_id
            for item in evidence
            for request_id in item.provider_request_ids
        )
        if self.provider_request_ids != request_ids:
            raise ValueError("Agent release report request IDs differ from Case evidence")
        if len(request_ids) != len(set(request_ids)):
            raise ValueError("Agent release report request IDs must be unique")
        if self.total_tokens != sum(item.total_tokens for item in evidence):
            raise ValueError("Agent release report Token total is inconsistent")
        if abs(
            self.total_latency_ms - sum(item.latency_ms for item in evidence)
        ) > 1e-6:
            raise ValueError("Agent release report Latency total is inconsistent")
        expected_passed = all(
            item.scorecard.release_gate_eligible
            and item.verification_passed
            and item.run_status == RunStatus.COMPLETED.value
            and item.lease_released
            and item.actual_paths == item.expected_paths
            for item in self.cases
        )
        if self.passed != expected_passed:
            raise ValueError("Agent release report pass state is inconsistent")
        return self


async def run_gold_agent_release_suite(
    *,
    case_roots: tuple[Path, ...],
    workspace_root: Path,
    budget: AgentBudgetLimit | None = None,
) -> GoldAgentReleaseReport:
    """Run four real persisted investigation Loops and persist a secret-free report."""

    if not case_roots or len(case_roots) != len(set(case_roots)):
        raise ValueError("Gold Agent release requires unique Case roots")
    workspace_root.mkdir(parents=True, exist_ok=False)
    data_service = CommerceDataService(storage_root=workspace_root / "data")
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{workspace_root / 'commerce.db'}"
    )
    await create_commerce_schema(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    limit = budget or AgentBudgetLimit(
        max_iterations=6,
        max_tokens=36_000,
        max_wall_time_seconds=900,
        max_model_escalations=3,
    )
    lease_ttl = timedelta(minutes=5)
    try:
        cases = tuple(
            [
                await _run_gold_case(
                    case_root=case_root,
                    workspace_root=workspace_root,
                    data_service=data_service,
                    session_factory=factory,
                    lease_ttl=lease_ttl,
                    budget=limit,
                )
                for case_root in case_roots
            ]
        )
    finally:
        await engine.dispose()

    evidence = tuple(
        item for case_result in cases for item in case_result.model_evidence
    )
    audit_path = workspace_root / f"report-{uuid4().hex}.json"
    report = GoldAgentReleaseReport(
        created_at=datetime.now(UTC),
        passed=all(
            item.scorecard.release_gate_eligible
            and item.verification_passed
            and item.run_status == RunStatus.COMPLETED.value
            and item.lease_released
            and item.actual_paths == item.expected_paths
            for item in cases
        ),
        cases=cases,
        provider_request_ids=tuple(
            request_id
            for item in evidence
            for request_id in item.provider_request_ids
        ),
        total_tokens=sum(item.total_tokens for item in evidence),
        total_latency_ms=sum(item.latency_ms for item in evidence),
        audit_path=str(audit_path),
    )
    with audit_path.open("x", encoding="utf-8") as handle:
        json.dump(
            report.model_dump(mode="json"),
            handle,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        handle.write("\n")
    return report


async def _run_gold_case(
    *,
    case_root: Path,
    workspace_root: Path,
    data_service: CommerceDataService,
    session_factory,
    lease_ttl: timedelta,
    budget: AgentBudgetLimit,
) -> GoldAgentReleaseCaseResult:
    evaluation_case = load_evaluation_case(case_root)
    workspace_id = WorkspaceId.new()
    view = data_service.ingest_uploads(
        workspace_id,
        tuple(
            (
                Path(item.relative_path).name,
                (case_root / item.relative_path).read_bytes(),
            )
            for item in evaluation_case.input_bundle.files
        ),
    )
    case = await _open_case(
        evaluation_case,
        workspace_id=workspace_id,
        dataset_id=view.manifest.dataset_id,
        data_service=data_service,
        session_factory=session_factory,
    )
    started = await CommerceRunService(session_factory).start_investigation(
        workspace_id,
        case.id,
        goal=evaluation_case.input_bundle.user_prompt,
        idempotency_key=f"gold-agent-release-{evaluation_case.case_key.lower()}",
    )
    acquired_at = max(datetime.now(UTC), started.run.updated_at)
    grant = await SqlRunLeaseRepository(session_factory).acquire(
        workspace_id,
        started.run.id,
        worker_id=f"gold-agent-release-{evaluation_case.case_key.lower()}",
        ttl=lease_ttl,
        acquired_at=acquired_at,
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
    )
    turn = await CommerceLeadTurnService(
        data_service=data_service,
        session_factory=session_factory,
        lease_ttl=lease_ttl,
    ).execute(
        workspace_id,
        started.run.id,
        request=LeadTurnRequest(intent=LeadTurnIntent.START),
        budget=budget,
        lease=grant.credentials,
        correlation_id=CorrelationId.new(),
    )
    if turn.fanout is None or turn.lead_run is None:
        raise RuntimeError("Gold Agent release requires Path fan-out and Lead synthesis")
    outcome_by_task = {
        outcome.task_id: outcome for outcome in turn.fanout.outcomes
    }
    failed_paths = tuple(
        path
        for path in turn.fanout.paths
        if (
            (outcome := outcome_by_task.get(path.task_id)) is None
            or outcome.status is not CommerceSubagentStatus.COMPLETED
        )
    )
    if failed_paths:
        diagnostics = []
        for path in failed_paths:
            outcome = outcome_by_task.get(path.task_id)
            diagnostics.append(
                "/".join(
                    (
                        path.path_type.value,
                        (
                            outcome.status.value
                            if outcome is not None
                            else "missing_outcome"
                        ),
                        (
                            outcome.error_code.value
                            if outcome is not None
                            and outcome.error_code is not None
                            else path.error_type or "unknown_error"
                        ),
                    )
                )
            )
        raise RuntimeError(
            "Gold Agent release requires every selected Path to complete: "
            + "; ".join(diagnostics)
        )
    if not turn.proposed_hypothesis_ids:
        raise RuntimeError("Gold Agent release requires proposed Hypotheses")

    verified = await CommerceVerificationTurnService(
        data_service=data_service,
        session_factory=session_factory,
        lease_ttl=lease_ttl,
    ).verify(
        workspace_id,
        started.run.id,
        hypothesis_ids=turn.proposed_hypothesis_ids,
        budget=budget,
        lease=grant.credentials,
        correlation_id=CorrelationId.new(),
    )
    verification_passed = (
        verified.verification.result.overall_verdict is ClaimVerdict.PASS
    )
    events = await SqlDomainEventStore(session_factory).list_run(
        workspace_id,
        started.run.id,
    )
    checkpoints = await SqlRunCheckpointRepository(session_factory).list_run(
        workspace_id,
        started.run.id,
    )
    event_types = tuple(item.event_type for item in events)
    lease_released = bool(events and events[-1].event_type == "run.lease_released")
    tool_keys = tuple(
        (
            str(event.payload.get("task_id", "")),
            str(event.payload.get("tool_call_id", "")),
        )
        for event in events
        if event.event_type in {"tool.completed", "tool.failed"}
    )
    duplicate_tool_calls = len(tool_keys) - len(set(tool_keys))
    actual_paths = tuple(
        sorted(_PATH_NAMES[outcome.path_type] for outcome in turn.fanout.outcomes)
    )
    expected_paths = tuple(
        sorted(evaluation_case.expected_behavior.expected_path_agents)
    )
    final_answer = _render_lead_answer(turn.lead_run.result)
    packet = GoldCaseExperimentInputBuilder().build(
        evaluation_case,
        case_root=case_root,
        storage_root=workspace_root / "evaluation-input" / evaluation_case.case_key,
    )
    follow_up_outcome = _visible_follow_up_outcome(evaluation_case)
    lead_real_model_evidence = tuple(
        _runner_evidence(item)
        for item in turn.lead_run.attempt_telemetry
    )
    observation = EvaluationObservation(
        case_key=evaluation_case.case_key,
        repetition=1,
        facts=packet.facts,
        capabilities=packet.capabilities,
        executed_path_agents=frozenset(actual_paths),
        skipped_path_agents=(
            frozenset(
                definition.path_agent
                for definition in CapabilityRegistry.DEFINITIONS
            )
            - frozenset(actual_paths)
        ),
        final_answer=final_answer,
        follow_up_outcome=follow_up_outcome,
        schema_valid=True,
        budget_within_limit=True,
        policy_valid=True,
        trace=TraceObservation(
            model_assignment_count=event_types.count("model.assigned"),
            checkpoint_count=len(checkpoints),
            verification_count=event_types.count("verification.completed"),
            duplicate_side_effect_tool_calls=duplicate_tool_calls,
            lease_required=True,
            lease_released=lease_released,
        ),
        real_model_evidence=lead_real_model_evidence,
    )
    scorecard = CommerceEvaluationRunner().evaluate(
        evaluation_case,
        observation,
        requires_real_model=True,
        requires_agent_trace=True,
    )
    model_evidence = (
        *(
            _path_evidence(outcome.result)
            for outcome in turn.fanout.outcomes
            if outcome.result is not None
        ),
        *(
            _lead_evidence(item)
            for item in turn.lead_run.attempt_telemetry
        ),
        _verification_evidence(verified.verification),
    )
    return GoldAgentReleaseCaseResult(
        case_key=evaluation_case.case_key,
        workspace_id=str(workspace_id),
        case_id=str(case.id),
        run_id=str(started.run.id),
        expected_paths=expected_paths,
        actual_paths=actual_paths,
        scorecard=scorecard,
        verification_passed=verification_passed,
        run_status=verified.run.status.value,
        stop_reason=verified.run.stop_reason,
        lease_released=lease_released,
        event_count=len(events),
        checkpoint_count=len(checkpoints),
        final_answer_sha256=hashlib.sha256(final_answer.encode()).hexdigest(),
        model_evidence=model_evidence,
    )


async def _open_case(
    evaluation_case: EvaluationCase,
    *,
    workspace_id,
    dataset_id,
    data_service,
    session_factory,
):
    request = evaluation_case.input_bundle.analysis_request
    peer_request = evaluation_case.input_bundle.peer_analysis_request
    service = CommerceAnalysisService(
        data_service=data_service,
        session_factory=session_factory,
    )
    if request is not None:
        outcome = await service.analyze(
            workspace_id,
            dataset_id,
            baseline_window=MetricWindow(
                start=request.baseline_window.start,
                end=request.baseline_window.end,
            ),
            current_window=MetricWindow(
                start=request.anomaly_window.start,
                end=request.anomaly_window.end,
            ),
            seller_id=request.seller_id,
        )
    elif peer_request is not None:
        outcome = await service.open_explicit_case(
            workspace_id,
            dataset_id,
            seller_id=peer_request.seller_id,
            baseline_window=MetricWindow(
                start=peer_request.baseline_window.start,
                end=peer_request.baseline_window.end,
            ),
            current_window=MetricWindow(
                start=peer_request.window.start,
                end=peer_request.window.end,
            ),
            requested_paths=peer_request.requested_paths,
            peer_policy=PeerCohortPolicy(
                product_category=peer_request.product_category,
                min_orders_per_seller=peer_request.min_orders_per_seller,
                match_seller_state=peer_request.match_seller_state,
            ),
        )
    else:
        raise ValueError("Gold Agent release Case has no visible analysis request")
    if len(outcome.cases) != 1:
        raise RuntimeError("Gold Agent release requires exactly one Case")
    return outcome.cases[0]


def _visible_follow_up_outcome(
    evaluation_case: EvaluationCase,
) -> FollowUpOutcome | None:
    request = evaluation_case.input_bundle.analysis_request
    if (
        request is not None
        and request.follow_up_window is not None
        and (
            not request.controlled_intervention_observed
            or not request.comparison_group_observed
        )
    ):
        return FollowUpOutcome.INCONCLUSIVE
    return None


def _render_lead_answer(result) -> str:
    claims = [item.statement for item in result.claims]
    unknowns = [
        f"Unknown: {item.question}. {item.reason}"
        for item in result.unknowns
    ]
    return " ".join((*claims, *unknowns))


def _runner_evidence(telemetry) -> RealModelEvidence:
    usage = telemetry.token_usage
    if (
        telemetry.actual_model_identity is None
        or telemetry.provider_request_id is None
        or usage is None
    ):
        raise RuntimeError("Lead telemetry is incomplete")
    return RealModelEvidence(
        actual_model_identity=telemetry.actual_model_identity,
        provider_request_id=telemetry.provider_request_id,
        configured_model_alias=telemetry.configured_alias,
        endpoint=telemetry.endpoint,
        fresh_request=True,
        retry_count=telemetry.retry_count,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        latency_ms=telemetry.latency_ms,
    )


def _path_evidence(result) -> AgentReleaseModelEvidence:
    return AgentReleaseModelEvidence(
        role="path",
        actual_model_identity=result.model_execution.actual_model_identity,
        provider_request_ids=(
            result.model_execution.provider_request_ids
            or (result.model_execution.provider_request_id,)
        ),
        input_tokens=result.cost.input_tokens,
        output_tokens=result.cost.output_tokens,
        latency_ms=result.cost.latency_ms,
        retry_count=result.model_execution.retry_count,
    )


def _lead_evidence(telemetry) -> AgentReleaseModelEvidence:
    usage = telemetry.token_usage
    if (
        telemetry.actual_model_identity is None
        or telemetry.provider_request_id is None
        or usage is None
    ):
        raise RuntimeError("Lead telemetry is incomplete")
    return AgentReleaseModelEvidence(
        role="lead",
        actual_model_identity=telemetry.actual_model_identity,
        provider_request_ids=(telemetry.provider_request_id,),
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        latency_ms=telemetry.latency_ms,
        retry_count=telemetry.retry_count,
    )


def _verification_evidence(run) -> AgentReleaseModelEvidence:
    return AgentReleaseModelEvidence(
        role="verifier",
        actual_model_identity=run.actual_model_identity,
        provider_request_ids=(run.provider_request_id,),
        input_tokens=run.token_usage.input_tokens,
        output_tokens=run.token_usage.output_tokens,
        latency_ms=run.latency_ms,
        retry_count=run.retry_count,
    )
