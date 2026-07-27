"""Fresh V4 E2E for persisted Observe -> Subagent -> Lead synthesis."""

from __future__ import annotations

import importlib
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.commerce.agents.contracts import AgentBudgetLimit, PathType
from app.commerce.agents.lead import PersistedLeadContextPacket
from app.commerce.agents.lead_execution import CommerceLeadTurnService
from app.commerce.agents.lead_loop import LeadAction, LeadTurnIntent, LeadTurnRequest
from app.commerce.agents.subagent_adapter import CommerceSubagentStatus
from app.commerce.agents.verification import ClaimVerdict
from app.commerce.agents.verification_execution import (
    CommerceVerificationTurnService,
)
from app.commerce.api.analysis_service import CommerceAnalysisService
from app.commerce.api.data_service import CommerceDataService
from app.commerce.api.run_service import CommerceRunService
from app.commerce.data.gold_cases import load_evaluation_case
from app.commerce.domain.enums import HypothesisStatus, RunPhase, RunStatus
from app.commerce.domain.ids import CorrelationId, TraceId, WorkspaceId
from app.commerce.metrics.registry import MetricWindow
from app.commerce.persistence.events import SqlDomainEventStore
from app.commerce.persistence.repositories import SqlCaseRepository
from app.commerce.persistence.runs import (
    SqlRunCheckpointRepository,
    SqlRunLeaseRepository,
)
from app.commerce.persistence.schema import create_commerce_schema
from app.commerce.persistence.work_records import SqlHypothesisRepository

REPO_ROOT = Path(__file__).parents[4]
CASE_ROOT = REPO_ROOT / "evals" / "commerce" / "cases" / "GC-FULFILLMENT-001"
SELLER_ID = "4869f7a5dfa277a7dca6462dcf3b52b2"


@pytest.fixture
def real_deerflow_subagent_executor():
    """Replace the suite-wide circular-import mock with the real executor."""

    __import__("deerflow.agents")
    module_name = "deerflow.subagents.executor"
    package = sys.modules["deerflow.subagents"]
    original_module = sys.modules.get(module_name)
    original_attribute = getattr(package, "executor", None)
    sys.modules.pop(module_name, None)
    if hasattr(package, "executor"):
        delattr(package, "executor")
    module = importlib.import_module(module_name)
    try:
        yield module
    finally:
        sys.modules.pop(module_name, None)
        if original_module is not None:
            sys.modules[module_name] = original_module
        if original_attribute is not None:
            setattr(package, "executor", original_attribute)


@pytest.mark.real_model
@pytest.mark.anyio
async def test_continuous_lead_turn_persists_real_path_and_multi_path_context(
    tmp_path,
    real_deerflow_subagent_executor,
):
    evaluation_case = load_evaluation_case(CASE_ROOT)
    workspace_id = WorkspaceId.new()
    data_service = CommerceDataService(storage_root=tmp_path / "commerce-storage")
    view = data_service.ingest_uploads(
        workspace_id,
        tuple(
            (
                Path(file.relative_path).name,
                (CASE_ROOT / file.relative_path).read_bytes(),
            )
            for file in evaluation_case.input_bundle.files
        ),
    )
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'lead-turn.db'}")
    await create_commerce_schema(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        analysis = await CommerceAnalysisService(
            data_service=data_service,
            session_factory=factory,
        ).analyze(
            workspace_id,
            view.manifest.dataset_id,
            baseline_window=MetricWindow(
                start=datetime(2017, 12, 2),
                end=datetime(2018, 1, 31),
            ),
            current_window=MetricWindow(
                start=datetime(2018, 1, 31),
                end=datetime(2018, 4, 1),
            ),
            seller_id=SELLER_ID,
        )
        started = await CommerceRunService(factory).start_investigation(
            workspace_id,
            analysis.cases[0].id,
            goal=evaluation_case.input_bundle.user_prompt,
            idempotency_key="continuous-lead-turn-live",
        )
        lease_ttl = timedelta(minutes=5)
        grant = await SqlRunLeaseRepository(factory).acquire(
            workspace_id,
            started.run.id,
            worker_id="continuous-lead-turn-live-worker",
            ttl=lease_ttl,
            acquired_at=datetime.now(UTC),
            trace_id=TraceId.new(),
            correlation_id=CorrelationId.new(),
        )
        budget = AgentBudgetLimit(
            max_iterations=5,
            max_tokens=24_000,
            max_wall_time_seconds=600,
            max_model_escalations=2,
        )

        service = CommerceLeadTurnService(
            data_service=data_service,
            session_factory=factory,
            lease_ttl=lease_ttl,
        )
        turn = await service.execute(
            workspace_id,
            started.run.id,
            request=LeadTurnRequest(intent=LeadTurnIntent.START),
            budget=budget,
            lease=grant.credentials,
            correlation_id=CorrelationId.new(),
        )

        assert turn.decision.action is LeadAction.INVESTIGATE
        assert turn.decision.selected_paths == (
            PathType.FULFILLMENT,
            PathType.REVIEW_EXPERIENCE,
        )
        assert turn.fanout is not None
        assert turn.fanout.barrier.may_synthesize is True
        assert len(turn.fanout.outcomes) == 2
        terminal_statuses = {
            CommerceSubagentStatus.COMPLETED,
            CommerceSubagentStatus.BLOCKED,
            CommerceSubagentStatus.FAILED,
            CommerceSubagentStatus.CANCELLED,
            CommerceSubagentStatus.TIMED_OUT,
        }
        assert all(
            outcome.status in terminal_statuses
            for outcome in turn.fanout.outcomes
        )
        completed_outcomes = tuple(
            outcome
            for outcome in turn.fanout.outcomes
            if outcome.status is CommerceSubagentStatus.COMPLETED
        )
        assert completed_outcomes
        path_results = tuple(
            outcome.result for outcome in completed_outcomes if outcome.result
        )
        assert len(path_results) == len(completed_outcomes)
        assert {item.path_type for item in path_results}.issubset(
            {PathType.FULFILLMENT, PathType.REVIEW_EXPERIENCE}
        )
        assert all(
            item.model_execution.actual_model_identity.startswith("deepseek-v4")
            and item.model_execution.provider_request_id
            for item in path_results
        )
        assert turn.fanout.wall_time_ms < sum(
            item.wall_time_ms for item in turn.fanout.paths
        )

        assert turn.lead_run is not None
        assert isinstance(turn.lead_run.context, PersistedLeadContextPacket)
        assert len(turn.lead_run.context.path_scopes) == len(completed_outcomes)
        assert turn.lead_run.result.claims
        assert turn.lead_run.telemetry.actual_model_identity is not None
        assert turn.lead_run.telemetry.actual_model_identity.startswith(
            "deepseek-v4"
        )
        assert turn.lead_run.telemetry.provider_request_id
        assert turn.lead_run.telemetry.request_attempt_count == 1
        assert turn.lead_run.telemetry.retry_count == 0
        assert 1 <= len(turn.lead_run.attempt_telemetry) <= 2
        assert all(
            item.actual_model_identity is not None
            and item.actual_model_identity.startswith("deepseek-v4")
            and item.provider_request_id
            and item.request_attempt_count == 1
            and item.retry_count == 0
            for item in turn.lead_run.attempt_telemetry
        )
        released_ids = {
            item.evidence_id for item in turn.lead_run.context.evidence
        }
        assert all(
            set(claim.evidence_ids).issubset(released_ids)
            for claim in turn.lead_run.result.claims
        )

        persisted_case = await SqlCaseRepository(factory).get(
            workspace_id,
            started.run.case_id,
        )
        assert persisted_case is not None
        assert set(turn.proposed_hypothesis_ids).issubset(
            persisted_case.hypothesis_ids
        )
        repository = SqlHypothesisRepository(factory)
        persisted_hypotheses = tuple(
            [
                await repository.get_latest(workspace_id, hypothesis_id)
                for hypothesis_id in turn.proposed_hypothesis_ids
            ]
        )
        assert all(item is not None for item in persisted_hypotheses)

        events = await SqlDomainEventStore(factory).list_run(
            workspace_id,
            started.run.id,
        )
        event_types = [event.event_type for event in events]
        assert event_types.count("path.started") == 2
        assert sum(
            event_types.count(event_type)
            for event_type in ("path.completed", "path.blocked", "path.failed")
        ) == 2
        assert event_types.count("path.completed") == len(completed_outcomes)
        assert event_types.count("lead.started") == 1
        assert event_types.count("lead.completed") == 1
        completed_paths = tuple(
            event for event in events if event.event_type == "path.completed"
        )
        assert all(
            event.payload["evidence_scope"]["evidence_ids"]
            for event in completed_paths
        )

        checkpoints = await SqlRunCheckpointRepository(factory).list_run(
            workspace_id,
            started.run.id,
        )
        assert len(checkpoints) >= 4
        final = checkpoints[-1].checkpoint
        assert final.active_path_task_ids == ()
        expected_tokens = sum(
            item.cost.input_tokens + item.cost.output_tokens
            for item in path_results
        ) + turn.lead_run.total_tokens
        assert final.budget_snapshot.usage.tokens == expected_tokens
        assert final.budget_snapshot.usage.path_agents == 2
        assert final.budget_snapshot.usage.repeated_actions == (
            len(turn.lead_run.attempt_telemetry) - 1
        )
        assert turn.run.status is RunStatus.RUNNING
        assert turn.run.phase is RunPhase.SYNTHESIZING

        hypotheses_before_answer = persisted_case.hypothesis_ids
        answer = await service.execute(
            workspace_id,
            started.run.id,
            request=LeadTurnRequest(
                intent=LeadTurnIntent.READ_ONLY_QUESTION,
                question="为什么问题更接近履约或评价体验，而不是未观察到的广告指标？",
            ),
            budget=budget,
            lease=grant.credentials,
            correlation_id=CorrelationId.new(),
        )

        assert answer.decision.action is LeadAction.ANSWER
        assert answer.decision.read_only is True
        assert answer.decision.selected_paths == ()
        assert answer.fanout is None
        assert answer.proposed_hypothesis_ids == ()
        assert answer.lead_run is not None
        assert answer.lead_run.assignment.role.value == "answer"
        assert answer.lead_run.assignment.profile.value == "fast_structured"
        assert answer.lead_run.assignment.escalation_count == (
            final.budget_snapshot.usage.model_escalations
        )
        assert all(
            item.actual_model_identity is not None
            and item.actual_model_identity.startswith("deepseek-v4")
            and item.provider_request_id
            and item.retry_count == 0
            for item in answer.lead_run.attempt_telemetry
        )

        after_answer_case = await SqlCaseRepository(factory).get(
            workspace_id,
            started.run.case_id,
        )
        assert after_answer_case is not None
        assert after_answer_case.hypothesis_ids == hypotheses_before_answer
        after_answer_events = await SqlDomainEventStore(factory).list_run(
            workspace_id,
            started.run.id,
        )
        after_answer_types = [event.event_type for event in after_answer_events]
        assert after_answer_types.count("path.started") == 2
        assert after_answer_types.count("lead.answer_started") == 1
        assert after_answer_types.count("lead.answer_completed") == 1
        after_answer_checkpoints = await SqlRunCheckpointRepository(factory).list_run(
            workspace_id,
            started.run.id,
        )
        answer_final = after_answer_checkpoints[-1].checkpoint
        assert answer_final.active_path_task_ids == ()
        assert answer_final.budget_snapshot.usage.path_agents == 2
        assert answer_final.budget_snapshot.usage.tokens == (
            final.budget_snapshot.usage.tokens + answer.lead_run.total_tokens
        )
        assert answer_final.budget_snapshot.usage.model_escalations == (
            final.budget_snapshot.usage.model_escalations
        )

        verification = await CommerceVerificationTurnService(
            data_service=data_service,
            session_factory=factory,
            lease_ttl=lease_ttl,
        ).verify(
            workspace_id,
            started.run.id,
            hypothesis_ids=turn.proposed_hypothesis_ids,
            budget=budget,
            lease=grant.credentials,
            correlation_id=CorrelationId.new(),
        )

        assert verification.run.phase is RunPhase.VERIFYING
        assert verification.verification.actual_model_identity.startswith(
            "deepseek-v4"
        )
        assert verification.verification.provider_request_id
        assert verification.verification.retry_count == 0
        assert "lead_reasoning" not in (
            verification.verification.context.model_dump(mode="json")
        )
        assert verification.goal_decision.stop_reason is not None
        if verification.verification.result.overall_verdict is ClaimVerdict.PASS:
            assert verification.run.status is RunStatus.COMPLETED
        else:
            assert verification.run.status is RunStatus.BLOCKED
        for hypothesis_id in turn.proposed_hypothesis_ids:
            versions = await repository.list_versions(workspace_id, hypothesis_id)
            assert len(versions) == 2
            assert versions[0].status is HypothesisStatus.PROPOSED
            assert versions[1].status is not HypothesisStatus.PROPOSED
        verification_events = await SqlDomainEventStore(factory).list_run(
            workspace_id,
            started.run.id,
        )
        verification_types = [event.event_type for event in verification_events]
        assert "verification.started" in verification_types
        assert "verification.completed" in verification_types
        assert "goal_loop.stopped" in verification_types
        assert verification_types[-1] == "run.lease_released"
    finally:
        await engine.dispose()
