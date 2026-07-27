"""Deterministic ReviewExperience-to-DeerFlow Subagent contracts."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage

from app.commerce.agents.contracts import CaseHeader
from app.commerce.agents.review_experience import (
    ReviewExperiencePathAgent,
    ReviewReferenceScope,
)
from app.commerce.agents.review_experience_subagent import (
    ReviewExperienceSubagentSpec,
    build_review_experience_read_tools,
)
from app.commerce.agents.subagent_adapter import CommerceSubagentStatus
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
from app.commerce.metrics.registry import MetricWindow

REPO_ROOT = Path(__file__).parents[4]
CASE_ROOT = REPO_ROOT / "evals" / "commerce" / "cases" / "GC-REVIEW-002"
TARGET_SELLER_ID = "0b90b6df587eb83608a64ea8b390cf07"


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
        lease_worker_id="review-subagent-worker",
        fencing_token=1,
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
    )
    return spec, task


def _draft(spec):
    context = spec.plan.context
    metrics = context.metrics
    excerpt = context.review_signals.excerpts[0]
    return {
        "observations": [
            {
                "summary": "Average review score moved from 3.88 to 2.94.",
                "confidence": 0.97,
                "fact_ids": [],
                "metric_observation_ids": [
                    metrics.baseline_average_review_score_id,
                    metrics.current_average_review_score_id,
                ],
            },
            {
                "summary": "Low-rating rate moved from 23.53% to 44.44%.",
                "confidence": 0.97,
                "fact_ids": [],
                "metric_observation_ids": [
                    metrics.baseline_low_rating_rate_id,
                    metrics.current_low_rating_rate_id,
                ],
            },
            {
                "summary": (
                    "Late-delivery rate remained 0% in both windows; delivery "
                    "lateness is not supported for this observed review deterioration."
                ),
                "confidence": 0.96,
                "fact_ids": [],
                "metric_observation_ids": [
                    metrics.baseline_late_delivery_rate_id,
                    metrics.current_late_delivery_rate_id,
                ],
            },
            {
                "summary": (
                    "Low-rating text contains unverified customer VOC about generic "
                    "or missing items; authenticity remains unverified and requires "
                    "separate verification."
                ),
                "confidence": 0.82,
                "fact_ids": list(excerpt.fact_ids),
                "metric_observation_ids": [],
            },
        ],
        "unknowns": [
            {
                "question": "Are the product authenticity reports substantiated?",
                "reason": "Review text is an allegation rather than verified evidence.",
                "missing_capabilities": ["product_authentication"],
            }
        ],
        "suggested_next_paths": ["fulfillment"],
    }


def _scoped_draft():
    return {
        "observations": [
            {
                "summary": (
                    "Average review score decreased while the low-rating rate "
                    "increased across the supplied windows."
                ),
                "confidence": 0.97,
                "reference_scopes": [ReviewReferenceScope.REVIEW_METRICS],
                "fact_ids": [],
                "metric_observation_ids": [],
            },
            {
                "summary": (
                    "Late-delivery rate remained zero in both supplied windows."
                ),
                "confidence": 0.96,
                "reference_scopes": [
                    ReviewReferenceScope.LATE_DELIVERY_METRICS
                ],
                "fact_ids": [],
                "metric_observation_ids": [],
            },
            {
                "summary": (
                    "Low-rating excerpts contain bounded customer VOC allegations; "
                    "they are not verified operational facts."
                ),
                "confidence": 0.82,
                "reference_scopes": [ReviewReferenceScope.VOC_EXCERPTS],
                "fact_ids": [],
                "metric_observation_ids": [],
            },
        ],
        "unknowns": [
            {
                "question": "Are the VOC allegations substantiated?",
                "reason": "Review text alone cannot establish the underlying event.",
                "missing_capabilities": ["independent_verification"],
            }
        ],
        "suggested_next_paths": ["fulfillment"],
    }


def _harness_result(task, draft, *, result_text: str | None = None):
    started_at = datetime.now(UTC)
    semantic_text = result_text or json.dumps(draft)
    message = AIMessage(
        content=semantic_text,
        response_metadata={
            "model_name": "deepseek-v4-flash",
            "headers": {"x-request-id": "review-request-1"},
            "id": "review-response-1",
            "finish_reason": "stop",
        },
        usage_metadata={
            "input_tokens": 700,
            "output_tokens": 260,
            "total_tokens": 960,
        },
    )
    return SimpleNamespace(
        task_id=str(task.task_id),
        trace_id=str(task.trace_id),
        status="completed",
        result=semantic_text,
        error=None,
        started_at=started_at,
        completed_at=started_at + timedelta(milliseconds=1200),
        ai_messages=[message.model_dump()],
        execution_events=[],
        token_usage_records=[
            {
                "source_run_id": "review-model-run-1",
                "caller": "subagent:commerce-review-experience-path",
                "input_tokens": 700,
                "output_tokens": 260,
                "total_tokens": 960,
            }
        ],
    )


@pytest.mark.anyio
async def test_review_subagent_hydrates_runtime_and_preserves_tool_traces(tmp_path):
    spec, task = await _spec_and_task(tmp_path)
    adapter = spec.build_adapter(
        tools=build_review_experience_read_tools(spec.plan.context)
    )

    outcome = adapter.consume(task, _harness_result(task, _draft(spec)))

    assert outcome.status is CommerceSubagentStatus.COMPLETED
    assert outcome.result is not None
    assert outcome.result.trace_id == task.trace_id
    assert outcome.result.model_execution.provider_request_id == "review-request-1"
    assert outcome.result.model_execution.actual_model_identity == "deepseek-v4-flash"
    assert outcome.result.cost.input_tokens == 700
    assert outcome.result.cost.output_tokens == 260
    assert outcome.result.cost.latency_ms >= 1200
    assert tuple(item.tool_name for item in outcome.result.tool_calls) == (
        "metric_query",
        "review_signal_query",
    )
    assert outcome.result.cost.tool_call_count == 2
    assert set(outcome.result.evidence[3].fact_ids).issubset(
        spec.plan.context.manifest.included_fact_ids
    )


@pytest.mark.anyio
async def test_review_subagent_resolves_semantic_reference_scopes_server_side(
    tmp_path,
):
    spec, task = await _spec_and_task(tmp_path)
    adapter = spec.build_adapter(
        tools=build_review_experience_read_tools(spec.plan.context)
    )

    outcome = adapter.consume(
        task,
        _harness_result(task, _scoped_draft()),
    )

    assert outcome.status is CommerceSubagentStatus.COMPLETED
    assert outcome.result is not None
    metrics = spec.plan.context.metrics
    assert set(outcome.result.observations[0].metric_observation_ids) == {
        metrics.baseline_average_review_score_id,
        metrics.current_average_review_score_id,
        metrics.baseline_low_rating_rate_id,
        metrics.current_low_rating_rate_id,
    }
    assert set(outcome.result.observations[1].metric_observation_ids) == {
        metrics.baseline_late_delivery_rate_id,
        metrics.current_late_delivery_rate_id,
    }
    assert set(outcome.result.observations[2].fact_ids) == set(
        spec.plan.context.manifest.included_fact_ids
    )


@pytest.mark.anyio
async def test_review_subagent_prompt_and_tools_are_bounded(tmp_path):
    spec, task = await _spec_and_task(tmp_path)
    tools = build_review_experience_read_tools(spec.plan.context)
    adapter = spec.build_adapter(tools=tools)

    prompt = adapter.build_prompt(task, spec.plan.context)
    outputs = {
        tool.name: json.loads(tool.invoke({"query": "current review state"}))
        for tool in tools
    }

    assert str(task.task_id) in prompt
    assert "Every observations element" in prompt
    assert '"reference_scopes"' in prompt
    assert "review excerpt Fact ID" in prompt
    assert '"provider_request_id":' not in prompt
    assert '"actual_model_identity":' not in prompt
    assert set(outputs) == {
        "metric_query",
        "review_signal_query",
        "source_fact_lookup",
    }
    assert outputs["metric_query"]["metrics"]["current_order_count"] == 18
    assert outputs["review_signal_query"]["review_signals"]["excerpts"]
    assert outputs["source_fact_lookup"]["status"] == "not_observed"


@pytest.mark.anyio
async def test_review_subagent_reports_schema_location_without_raw_output(tmp_path):
    spec, task = await _spec_and_task(tmp_path)
    adapter = spec.build_adapter(
        tools=build_review_experience_read_tools(spec.plan.context)
    )
    invalid = _draft(spec)
    invalid["unexpected_policy"] = "must not be persisted"

    outcome = adapter.consume(task, _harness_result(task, invalid))

    assert outcome.status is CommerceSubagentStatus.BLOCKED
    assert "unexpected_policy:extra_forbidden" in (outcome.error_message or "")
    assert "must not be persisted" not in (outcome.error_message or "")


@pytest.mark.anyio
async def test_review_subagent_repairs_only_trailing_json_commas(tmp_path):
    spec, task = await _spec_and_task(tmp_path)
    adapter = spec.build_adapter(
        tools=build_review_experience_read_tools(spec.plan.context)
    )
    draft = _draft(spec)
    trailing_comma = json.dumps(draft)[:-1] + ",}"

    outcome = adapter.consume(
        task,
        _harness_result(task, draft, result_text=trailing_comma),
    )

    assert outcome.status is CommerceSubagentStatus.COMPLETED
    assert outcome.result is not None
    assert outcome.result.model_execution.provider_request_ids == (
        "review-request-1",
    )


@pytest.mark.anyio
async def test_review_subagent_drops_unreferenced_observation_noise(tmp_path):
    spec, task = await _spec_and_task(tmp_path)
    adapter = spec.build_adapter(
        tools=build_review_experience_read_tools(spec.plan.context)
    )
    draft = _draft(spec)
    draft["observations"].extend(
        (
            {
                "summary": "This boundary has no source reference.",
                "confidence": 0.5,
                "fact_ids": [],
                "metric_observation_ids": [],
            },
            {
                "summary": "This recommendation also has no source reference.",
                "confidence": 0.5,
                "fact_ids": [],
                "metric_observation_ids": [],
            },
        )
    )

    outcome = adapter.consume(task, _harness_result(task, draft))

    assert outcome.status is CommerceSubagentStatus.COMPLETED
    assert outcome.result is not None
    assert len(outcome.result.observations) == 4
    assert all(
        item.fact_ids or item.metric_observation_ids
        for item in outcome.result.observations
    )


@pytest.mark.anyio
async def test_review_context_can_bind_to_persisted_case_identity(tmp_path):
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
