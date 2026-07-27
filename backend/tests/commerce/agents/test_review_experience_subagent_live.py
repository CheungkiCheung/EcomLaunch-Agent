"""Fresh DeepSeek V4 integration for the ReviewExperience DeerFlow Subagent."""

from __future__ import annotations

import asyncio
import importlib
import sys
from datetime import datetime
from pathlib import Path

import pytest

from app.commerce.agents.review_experience import ReviewExperiencePathAgent
from app.commerce.agents.review_experience_subagent import (
    ReviewExperienceSubagentSpec,
    build_review_experience_read_tools,
)
from app.commerce.agents.subagent_adapter import CommerceSubagentStatus
from app.commerce.api.data_service import CommerceDataService
from app.commerce.data.gold_cases import load_evaluation_case
from app.commerce.domain.ids import CorrelationId, RunId, TraceId, WorkspaceId
from app.commerce.evaluation.real_model_preflight import (
    PreflightStatus,
    run_real_model_preflight,
)
from app.commerce.metrics.registry import MetricWindow

REPO_ROOT = Path(__file__).parents[4]
CASE_ROOT = REPO_ROOT / "evals" / "commerce" / "cases" / "GC-REVIEW-002"
TARGET_SELLER_ID = "0b90b6df587eb83608a64ea8b390cf07"


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
async def test_fresh_deepseek_v4_review_experience_subagent_returns_traceable_result(
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
    plan = await ReviewExperiencePathAgent(data_service=data_service).prepare(
        workspace_id,
        view.manifest.dataset_id,
        seller_id=TARGET_SELLER_ID,
        baseline_window=MetricWindow(
            start=datetime(2018, 3, 1),
            end=datetime(2018, 4, 1),
        ),
        current_window=MetricWindow(
            start=datetime(2018, 4, 1),
            end=datetime(2018, 5, 1),
        ),
    )
    spec = ReviewExperienceSubagentSpec(plan)
    task = spec.build_task(
        run_id=RunId.new(),
        lease_worker_id="live-review-experience-subagent-worker",
        fencing_token=1,
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
    )
    adapter = spec.build_adapter(
        tools=build_review_experience_read_tools(plan.context)
    )
    try:
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
        result = outcome.result
        assert result.path_type.value == "review_experience"
        assert result.trace_id == task.trace_id
        assert result.model_execution.actual_model_identity.casefold().startswith(
            "deepseek-v4"
        )
        assert result.model_execution.provider_request_id
        assert result.model_execution.retry_count == 0
        assert result.cost.input_tokens > 0
        assert result.cost.output_tokens > 0
        assert result.cost.latency_ms > 0
        assert result.cost.tool_call_count == 2
        metrics = plan.context.metrics
        required_pairs = (
            {
                metrics.baseline_average_review_score_id,
                metrics.current_average_review_score_id,
            },
            {
                metrics.baseline_low_rating_rate_id,
                metrics.current_low_rating_rate_id,
            },
            {
                metrics.baseline_late_delivery_rate_id,
                metrics.current_late_delivery_rate_id,
            },
        )
        cited = [set(item.metric_observation_ids) for item in result.observations]
        assert all(any(pair.issubset(ids) for ids in cited) for pair in required_pairs)
        excerpt_fact_ids = {
            fact_id
            for item in plan.context.review_signals.excerpts
            for fact_id in item.fact_ids
        }
        assert excerpt_fact_ids & {
            fact_id for item in result.observations for fact_id in item.fact_ids
        }
        rendered = result.model_dump_json().casefold()
        assert "0" in rendered or "zero" in rendered
        assert all(event.tool_name in task.allowed_tools for event in outcome.tool_events)
    finally:
        adapter.cleanup(task)
