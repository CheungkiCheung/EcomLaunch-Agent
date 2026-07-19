"""Fresh real-DeepSeek-V4 integration for the first Commerce Path Agent."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.commerce.agents.context_loader import ContextPacketLoader
from app.commerce.agents.contracts import AgentBudgetLimit, PathType
from app.commerce.agents.fulfillment import (
    FulfillmentPathAgent,
    PathAgentAuditStore,
    PathAgentRunStatus,
)
from app.commerce.api.analysis_service import CommerceAnalysisService
from app.commerce.api.data_service import CommerceDataService
from app.commerce.api.run_service import CommerceRunService
from app.commerce.data.gold_cases import load_evaluation_case
from app.commerce.domain.ids import CorrelationId, TraceId, WorkspaceId
from app.commerce.metrics.registry import MetricName, MetricWindow
from app.commerce.persistence.runs import SqlRunLeaseRepository
from app.commerce.persistence.schema import create_commerce_schema

REPO_ROOT = Path(__file__).parents[4]
CASE_ROOT = REPO_ROOT / "evals" / "commerce" / "cases" / "GC-FULFILLMENT-001"
SELLER_ID = "4869f7a5dfa277a7dca6462dcf3b52b2"


@pytest.mark.real_model
@pytest.mark.anyio
async def test_real_deepseek_v4_fulfillment_path_returns_traceable_result(tmp_path):
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
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}")
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
            idempotency_key="live-fulfillment-path-agent",
        )
        acquired_at = datetime.now(UTC) + timedelta(seconds=1)
        grant = await SqlRunLeaseRepository(factory).acquire(
            workspace_id,
            started.run.id,
            worker_id="live-fulfillment-path-worker",
            ttl=timedelta(minutes=5),
            acquired_at=acquired_at,
            trace_id=TraceId.new(),
            correlation_id=CorrelationId.new(),
        )
        initial = await ContextPacketLoader(
            data_service=data_service,
            session_factory=factory,
        ).load_initial(
            workspace_id,
            started.run.id,
            budget=AgentBudgetLimit(max_tokens=16_000),
        )
        audit_store = PathAgentAuditStore(
            REPO_ROOT
            / ".deer-flow"
            / "commerce"
            / "evaluation"
            / "path-agents"
        )

        run = await FulfillmentPathAgent(audit_store=audit_store).run(
            initial.packet
        )

        assert grant.credentials.fencing_token == 1
        assert run.telemetry.status is PathAgentRunStatus.PASSED
        assert run.telemetry.actual_model_identity is not None
        assert run.telemetry.actual_model_identity.lower().startswith("deepseek-v4")
        assert run.telemetry.provider_request_id
        assert run.telemetry.provider_response_id
        assert run.telemetry.token_usage is not None
        assert run.telemetry.token_usage.total_tokens > 0
        assert run.telemetry.request_attempt_count == 1
        assert run.telemetry.retry_count == 0
        assert run.telemetry.stop_reason == "stop"
        assert run.telemetry.model_assignment.role.value == "path"
        assert run.telemetry.model_assignment.profile.value == "balanced_tool_user"
        assert run.telemetry.invocation_max_output_tokens == 1_600
        assert Path(run.audit_path).is_file()

        result = run.result
        assert result.path_type is PathType.FULFILLMENT
        assert result.context_sha256 == run.context.manifest.context_sha256
        assert result.model_execution.provider_request_id == (
            run.telemetry.provider_request_id
        )
        assert result.model_execution.actual_model_identity == (
            run.telemetry.actual_model_identity
        )
        assert result.cost.input_tokens == run.telemetry.token_usage.input_tokens
        assert result.cost.output_tokens == run.telemetry.token_usage.output_tokens
        assert result.tool_calls == ()

        baseline_by_name = {
            item.metric_name: item.metric_observation_id
            for item in run.context.analysis.baseline_metrics
        }
        current_by_name = {
            item.metric_name: item.metric_observation_id
            for item in run.context.analysis.current_metrics
        }
        handling_ids = {
            baseline_by_name[MetricName.HANDLING_TIME_HOURS.value],
            current_by_name[MetricName.HANDLING_TIME_HOURS.value],
        }
        transit_ids = {
            baseline_by_name[MetricName.TRANSIT_TIME_HOURS.value],
            current_by_name[MetricName.TRANSIT_TIME_HOURS.value],
        }
        handling = next(
            item
            for item in result.observations
            if handling_ids.issubset(set(item.metric_observation_ids))
        )
        transit = next(
            item
            for item in result.observations
            if transit_ids.issubset(set(item.metric_observation_ids))
        )
        handling_summary = handling.summary.casefold()
        transit_summary = transit.summary.casefold()
        assert "handling" in handling_summary
        assert any(
            term in handling_summary
            for term in ("did not worsen", "decreased", "lower", "improved")
        )
        assert "transit" in transit_summary
        assert any(
            term in transit_summary
            for term in ("increased", "higher", "worsened", "deteriorated")
        )

        rendered = result.model_dump_json().casefold()
        for forbidden in evaluation_case.expected_behavior.forbidden_claims:
            assert not any(term.casefold() in rendered for term in forbidden.terms)
    finally:
        await engine.dispose()
