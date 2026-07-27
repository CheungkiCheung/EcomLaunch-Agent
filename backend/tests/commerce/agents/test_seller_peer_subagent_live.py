"""Fresh DeepSeek V4 integration for the SellerPeer DeerFlow Subagent."""

from __future__ import annotations

import asyncio
import importlib
import sys
from datetime import datetime
from pathlib import Path

import pytest

from app.commerce.agents.seller_peer import SellerPeerPathAgent
from app.commerce.agents.seller_peer_subagent import (
    SellerPeerSubagentSpec,
    build_seller_peer_read_tools,
)
from app.commerce.agents.subagent_adapter import CommerceSubagentStatus
from app.commerce.api.data_service import CommerceDataService
from app.commerce.data.gold_cases import load_evaluation_case
from app.commerce.domain.ids import CorrelationId, RunId, TraceId, WorkspaceId
from app.commerce.evaluation.real_model_preflight import (
    PreflightStatus,
    run_real_model_preflight,
)
from app.commerce.metrics.registry import MetricWindow, PeerCohortPolicy

REPO_ROOT = Path(__file__).parents[4]
CASE_ROOT = REPO_ROOT / "evals" / "commerce" / "cases" / "GC-PEER-004"
TARGET_SELLER_ID = "e5a3438891c0bfdb9394643f95273d8e"


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
async def test_fresh_deepseek_v4_seller_peer_subagent_returns_traceable_result(
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
    plan = await SellerPeerPathAgent(data_service=data_service).prepare(
        workspace_id,
        view.manifest.dataset_id,
        seller_id=TARGET_SELLER_ID,
        window=MetricWindow(
            start=datetime(2018, 1, 1),
            end=datetime(2018, 7, 1),
        ),
        policy=PeerCohortPolicy(
            product_category="fashion_bolsas_e_acessorios",
            min_orders_per_seller=20,
        ),
    )
    spec = SellerPeerSubagentSpec(plan)
    task = spec.build_task(
        run_id=RunId.new(),
        lease_worker_id="live-seller-peer-subagent-worker",
        fencing_token=1,
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
    )
    adapter = spec.build_adapter(
        tools=build_seller_peer_read_tools(plan.context)
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
        assert result.path_type.value == "seller_peer"
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
        peer_ids = {
            plan.context.peer_comparison.target_rate_observation_id,
            plan.context.peer_comparison.peer_rate_observation_id,
        }
        assert any(
            peer_ids.issubset(set(item.metric_observation_ids))
            for item in result.observations
        )
        top_geography_ids = {
            plan.context.geography.segment(state).metric_observation_id
            for state in ("SP", "MG", "RJ")
        }
        cited = {
            metric_id
            for item in result.observations
            for metric_id in item.metric_observation_ids
        }
        assert top_geography_ids.issubset(cited)
        assert all(event.tool_name in task.allowed_tools for event in outcome.tool_events)
    finally:
        adapter.cleanup(task)
