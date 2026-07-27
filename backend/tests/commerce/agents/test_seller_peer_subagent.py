"""Deterministic SellerPeer-to-DeerFlow Subagent contracts."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage

from app.commerce.agents.contracts import CaseHeader
from app.commerce.agents.seller_peer import SellerPeerPathAgent
from app.commerce.agents.seller_peer_subagent import (
    SellerPeerSubagentSpec,
    build_seller_peer_read_tools,
)
from app.commerce.agents.subagent_adapter import (
    CommerceSubagentStatus,
    extract_runtime_telemetry,
)
from app.commerce.api.data_service import CommerceDataService
from app.commerce.data.gold_cases import load_evaluation_case
from app.commerce.domain.enums import CaseSeverity, CaseStatus
from app.commerce.domain.ids import (
    CaseId,
    CorrelationId,
    RunId,
    TraceId,
    WorkspaceId,
)
from app.commerce.metrics.registry import MetricWindow, PeerCohortPolicy

REPO_ROOT = Path(__file__).parents[4]
CASE_ROOT = REPO_ROOT / "evals" / "commerce" / "cases" / "GC-PEER-004"
TARGET_SELLER_ID = "e5a3438891c0bfdb9394643f95273d8e"


async def _spec_and_task(tmp_path):
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
        lease_worker_id="seller-peer-subagent-worker",
        fencing_token=1,
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
    )
    return spec, task


def _draft(spec):
    context = spec.plan.context
    peer = context.peer_comparison
    geography = tuple(
        sorted(
            context.geography.segments,
            key=lambda item: (-item.order_count, item.customer_state),
        )[:3]
    )
    return {
        "observations": [
            {
                "summary": (
                    "Target late-delivery rate is 27.12% versus 7.39% for five "
                    "matched peers over 257 pooled orders, a 19.72 percentage-point "
                    "diagnostic gap; eligibility used the fixed cohort policy and "
                    "not the late-delivery outcome, so this comparison is not causal."
                ),
                "confidence": 0.96,
                "metric_observation_ids": [
                    peer.target_rate_observation_id,
                    peer.peer_rate_observation_id,
                ],
            },
            {
                "summary": (
                    "Comparable target orders are concentrated in the supplied "
                    "top customer states."
                ),
                "confidence": 0.94,
                "metric_observation_ids": [
                    item.metric_observation_id for item in geography
                ],
            },
        ],
        "unknowns": [
            {
                "question": "Which observed fulfillment stage explains the gap?",
                "reason": "Peer comparison is diagnostic and stage events are absent.",
                "missing_capabilities": ["carrier_scan_events"],
            }
        ],
        "suggested_next_paths": ["fulfillment"],
    }


def _harness_result(task, draft):
    started_at = datetime.now(UTC)
    message = AIMessage(
        content=json.dumps(draft),
        response_metadata={
            "model_name": "deepseek-v4-flash",
            "headers": {"x-request-id": "seller-peer-request-1"},
            "id": "seller-peer-response-1",
            "finish_reason": "stop",
        },
        usage_metadata={
            "input_tokens": 500,
            "output_tokens": 180,
            "total_tokens": 680,
        },
    )
    return SimpleNamespace(
        task_id=str(task.task_id),
        trace_id=str(task.trace_id),
        status="completed",
        result=json.dumps(draft),
        error=None,
        started_at=started_at,
        completed_at=started_at + timedelta(milliseconds=900),
        ai_messages=[message.model_dump()],
        execution_events=[],
        token_usage_records=[
            {
                "source_run_id": "seller-peer-model-run-1",
                "caller": "subagent:commerce-seller-peer-path",
                "input_tokens": 500,
                "output_tokens": 180,
                "total_tokens": 680,
            }
        ],
    )


@pytest.mark.anyio
async def test_seller_peer_subagent_hydrates_runtime_and_preserves_tool_traces(
    tmp_path,
):
    spec, task = await _spec_and_task(tmp_path)
    adapter = spec.build_adapter(
        tools=build_seller_peer_read_tools(spec.plan.context)
    )

    outcome = adapter.consume(task, _harness_result(task, _draft(spec)))

    assert outcome.status is CommerceSubagentStatus.COMPLETED
    assert outcome.result is not None
    assert outcome.result.trace_id == task.trace_id
    assert outcome.result.model_execution.provider_request_id == (
        "seller-peer-request-1"
    )
    assert outcome.result.model_execution.actual_model_identity == (
        "deepseek-v4-flash"
    )
    assert outcome.result.cost.input_tokens == 500
    assert outcome.result.cost.output_tokens == 180
    assert outcome.result.cost.latency_ms >= 900
    assert tuple(item.tool_name for item in outcome.result.tool_calls) == (
        "peer_cohort_query",
        "geographic_order_count_query",
    )
    assert outcome.result.cost.tool_call_count == 2


@pytest.mark.anyio
async def test_seller_peer_subagent_prompt_and_tools_are_bounded(tmp_path):
    spec, task = await _spec_and_task(tmp_path)
    tools = build_seller_peer_read_tools(spec.plan.context)
    adapter = spec.build_adapter(tools=tools)

    prompt = adapter.build_prompt(task, spec.plan.context)
    outputs = {
        tool.name: json.loads(tool.invoke({"query": "current comparison"}))
        for tool in tools
    }

    assert str(task.task_id) in prompt
    assert '"provider_request_id":' not in prompt
    assert '"actual_model_identity":' not in prompt
    assert set(outputs) == {
        "metric_query",
        "peer_cohort_query",
        "geographic_order_count_query",
        "source_fact_lookup",
    }
    assert outputs["peer_cohort_query"]["peer_comparison"]["peer_order_count"] == 257
    assert outputs["geographic_order_count_query"]["geography"]["segments"]
    assert outputs["source_fact_lookup"]["status"] == "not_observed"


def test_runtime_telemetry_aggregates_distinct_tool_turns_without_counting_retries():
    started_at = datetime.now(UTC)
    messages = [
        AIMessage(
            content="",
            response_metadata={
                "model_name": "deepseek-v4-flash",
                "headers": {"x-request-id": "tool-turn-request"},
                "id": "tool-turn-response",
                "finish_reason": "tool_calls",
            },
            usage_metadata={
                "input_tokens": 100,
                "output_tokens": 20,
                "total_tokens": 120,
            },
        ),
        AIMessage(
            content="{}",
            response_metadata={
                "model_name": "deepseek-v4-flash",
                "headers": {"x-request-id": "final-turn-request"},
                "id": "final-turn-response",
                "finish_reason": "stop",
            },
            usage_metadata={
                "input_tokens": 200,
                "output_tokens": 60,
                "total_tokens": 260,
            },
        ),
    ]
    harness_result = SimpleNamespace(
        ai_messages=[item.model_dump() for item in messages],
        token_usage_records=[
            {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
            {"input_tokens": 200, "output_tokens": 60, "total_tokens": 260},
        ],
        started_at=started_at,
        completed_at=started_at + timedelta(seconds=2),
    )

    telemetry = extract_runtime_telemetry(
        harness_result,
        caller="SellerPeer Subagent",
    )

    assert telemetry.provider_request_id == "final-turn-request"
    assert telemetry.provider_request_ids == (
        "tool-turn-request",
        "final-turn-request",
    )
    assert telemetry.token_usage.input_tokens == 300
    assert telemetry.token_usage.output_tokens == 80
    assert telemetry.token_usage.total_tokens == 380
    assert telemetry.latency_ms == 2000


@pytest.mark.anyio
async def test_seller_peer_context_can_bind_to_persisted_case_identity(tmp_path):
    spec, _task = await _spec_and_task(tmp_path)
    original = spec.plan.context
    case = CaseHeader(
        workspace_id=original.case.workspace_id,
        case_id=CaseId.new(),
        title="Persisted commerce case",
        severity=CaseSeverity.HIGH,
        status=CaseStatus.INVESTIGATING,
        version=4,
    )

    rebound_spec = spec.bind_to_case(case)
    rebound = rebound_spec.plan.context

    assert rebound.case == case
    assert rebound.manifest.case_id == case.case_id
    assert rebound.manifest.context_sha256 != original.manifest.context_sha256
    assert rebound.manifest.estimated_tokens > 0
    assert spec.plan.context == original
