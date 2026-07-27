"""Fresh real-model parity between the legacy Path Agent and DeerFlow Subagent."""

from __future__ import annotations

import asyncio
import importlib
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.commerce.agents.context_loader import ContextPacketLoader
from app.commerce.agents.contracts import AgentBudgetLimit, PathType
from app.commerce.agents.fulfillment import FulfillmentPathAgent
from app.commerce.agents.fulfillment_subagent import (
    FulfillmentSubagentSpec,
    build_fulfillment_read_tools,
)
from app.commerce.agents.subagent_adapter import CommerceSubagentStatus
from app.commerce.api.analysis_service import CommerceAnalysisService
from app.commerce.api.data_service import CommerceDataService
from app.commerce.api.run_service import CommerceRunService
from app.commerce.data.gold_cases import load_evaluation_case
from app.commerce.domain.ids import CorrelationId, TraceId, WorkspaceId
from app.commerce.evaluation.real_model_preflight import (
    PreflightStatus,
    run_real_model_preflight,
)
from app.commerce.metrics.registry import MetricName, MetricWindow
from app.commerce.persistence.runs import SqlRunLeaseRepository
from app.commerce.persistence.schema import create_commerce_schema

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
async def test_new_fulfillment_subagent_preserves_legacy_gold_case_coverage(
    tmp_path,
    real_deerflow_subagent_executor,
):
    """The migration may change execution, but not the evidence contract."""

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
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'parity.db'}")
    await create_commerce_schema(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    adapter = None
    task = None
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
            idempotency_key="live-fulfillment-subagent-parity",
        )
        grant = await SqlRunLeaseRepository(factory).acquire(
            workspace_id,
            started.run.id,
            worker_id="live-fulfillment-subagent-parity-worker",
            ttl=timedelta(minutes=5),
            acquired_at=datetime.now(UTC),
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

        legacy = await FulfillmentPathAgent().run(initial.packet)
        assert legacy.telemetry.status.value == "passed"

        plan = await FulfillmentPathAgent().prepare(initial.packet)
        spec = FulfillmentSubagentSpec(plan)
        task = spec.build_task(
            run_id=started.run.id,
            lease_worker_id=grant.credentials.worker_id,
            fencing_token=grant.credentials.fencing_token,
            trace_id=TraceId.new(),
            correlation_id=CorrelationId.new(),
        )
        adapter = spec.build_adapter(tools=build_fulfillment_read_tools(plan.context))
        preflight = await asyncio.to_thread(run_real_model_preflight)
        assert preflight.status is PreflightStatus.PASSED, preflight.model_dump_json()
        adapter.start(task, plan.context)

        outcome = None
        for _ in range(240):
            outcome = adapter.poll(task)
            if outcome.status not in {
                CommerceSubagentStatus.PENDING,
                CommerceSubagentStatus.RUNNING,
            }:
                break
            await asyncio.sleep(0.25)

        assert outcome is not None
        assert outcome.status is CommerceSubagentStatus.COMPLETED, outcome.model_dump_json()
        assert outcome.result is not None
        migrated = outcome.result

        assert migrated.path_type is legacy.result.path_type is PathType.FULFILLMENT
        assert migrated.context_sha256 == legacy.context.manifest.context_sha256
        assert migrated.model_assignment == legacy.telemetry.model_assignment
        assert migrated.model_execution.actual_model_identity
        assert migrated.model_execution.actual_model_identity.casefold().startswith("deepseek-v4")
        assert migrated.model_execution.retry_count == 0
        assert migrated.cost.input_tokens > 0
        assert migrated.cost.output_tokens > 0
        assert migrated.cost.latency_ms > 0

        metric_by_id = {
            item.metric_observation_id: item.metric_name
            for item in (
                *plan.context.analysis.baseline_metrics,
                *plan.context.analysis.current_metrics,
            )
        }

        def covered_names(result):
            return {
                metric_by_id[observation_id]
                for observation in result.observations
                for observation_id in observation.metric_observation_ids
                if observation_id in metric_by_id
            }

        required = {
            MetricName.LATE_DELIVERY_RATE.value,
            MetricName.HANDLING_TIME_HOURS.value,
            MetricName.TRANSIT_TIME_HOURS.value,
        }
        assert required.issubset(covered_names(legacy.result))
        assert required.issubset(covered_names(migrated))
        assert covered_names(migrated) >= required
        assert len(migrated.unknowns) >= 1
        assert len(legacy.result.unknowns) >= 1
        assert all(
            event.tool_name in task.allowed_tools for event in outcome.tool_events
        )
        rendered = migrated.model_dump_json().casefold()
        for forbidden in evaluation_case.expected_behavior.forbidden_claims:
            assert not any(term.casefold() in rendered for term in forbidden.terms)
    finally:
        if adapter is not None and task is not None:
            adapter.cleanup(task)
        await engine.dispose()
