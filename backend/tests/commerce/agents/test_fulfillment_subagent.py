"""Deterministic Fulfillment-to-DeerFlow Subagent normalization contracts."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage

from app.commerce.agents.contracts import (
    AgentBudgetLimit,
    CaseAnalysisDigest,
    CaseHeader,
    CaseTriggerDigest,
    CaseTriggerType,
    ContextManifest,
    LeadContextPacket,
    MetricObservationDigest,
    ModelProfile,
    PathContextPacket,
    PathType,
)
from app.commerce.agents.fulfillment import FulfillmentPathAgent, FulfillmentPathPlan
from app.commerce.agents.fulfillment_subagent import (
    FulfillmentSubagentSpec,
    build_fulfillment_read_tools,
)
from app.commerce.agents.model_router import (
    ModelAssignment,
    ModelEffort,
    ModelRole,
    ModelRouteReasonCode,
)
from app.commerce.agents.subagent_adapter import (
    CommerceSubagentErrorCode,
    CommerceSubagentStatus,
)
from app.commerce.data.capabilities import (
    CapabilityAssessment,
    CapabilityName,
    CapabilityProfile,
    CapabilityReasonCode,
    CapabilityStatus,
)
from app.commerce.domain.enums import CaseSeverity, CaseStatus, SemanticStatus
from app.commerce.domain.ids import (
    AgentTaskId,
    CaseId,
    CorrelationId,
    DatasetId,
    EntityId,
    MetricObservationId,
    RunId,
    TraceId,
    WorkspaceId,
)
from app.commerce.metrics.registry import MetricName, MetricWindow


class HarnessStatus(StrEnum):
    COMPLETED = "completed"


def _assignment() -> ModelAssignment:
    return ModelAssignment(
        role=ModelRole.PATH,
        base_profile=ModelProfile.BALANCED_TOOL_USER,
        profile=ModelProfile.BALANCED_TOOL_USER,
        model_alias="deepseek-reasoner",
        effort=ModelEffort.MEDIUM,
        max_output_tokens=1_600,
        timeout_seconds=120,
        reason_codes=frozenset({ModelRouteReasonCode.PROFILE_BINDING}),
        escalation_count=0,
    )


def _context() -> PathContextPacket:
    workspace_id = WorkspaceId.new()
    case_id = CaseId.new()
    dataset_id = DatasetId.new()
    baseline_window = MetricWindow(
        start=datetime(2026, 1, 1),
        end=datetime(2026, 2, 1),
    )
    current_window = MetricWindow(
        start=datetime(2026, 2, 1),
        end=datetime(2026, 3, 1),
    )
    metric_names = (
        MetricName.LATE_DELIVERY_RATE.value,
        MetricName.HANDLING_TIME_HOURS.value,
        MetricName.TRANSIT_TIME_HOURS.value,
    )
    baseline_metrics = tuple(
        MetricObservationDigest(
            metric_observation_id=MetricObservationId.new(),
            metric_name=name,
            semantic_status=SemanticStatus.DERIVED,
            value=Decimal("0.10") if name == MetricName.LATE_DELIVERY_RATE.value else Decimal("24"),
            unit="ratio" if name == MetricName.LATE_DELIVERY_RATE.value else "hours",
            formula_version=f"{name}@1.0.0",
            window_start=baseline_window.start,
            window_end=baseline_window.end,
            sample_size=100,
            source_fact_count=200,
        )
        for name in metric_names
    )
    current_metrics = tuple(
        MetricObservationDigest(
            metric_observation_id=MetricObservationId.new(),
            metric_name=name,
            semantic_status=SemanticStatus.DERIVED,
            value=(
                Decimal("0.30")
                if name == MetricName.LATE_DELIVERY_RATE.value
                else Decimal("20")
                if name == MetricName.HANDLING_TIME_HOURS.value
                else Decimal("40")
            ),
            unit="ratio" if name == MetricName.LATE_DELIVERY_RATE.value else "hours",
            formula_version=f"{name}@1.0.0",
            window_start=current_window.start,
            window_end=current_window.end,
            sample_size=100,
            source_fact_count=200,
        )
        for name in metric_names
    )
    analysis = CaseAnalysisDigest(
        dataset_id=dataset_id,
        seller_entity_id=EntityId.new(),
        seller_external_key="seller-a",
        baseline_window=baseline_window,
        current_window=current_window,
        baseline_metrics=baseline_metrics,
        current_metrics=current_metrics,
    )
    metric_ids = tuple(
        item.metric_observation_id for item in (*baseline_metrics, *current_metrics)
    )
    return PathContextPacket.model_construct(
        schema_version="1.0",
        case=CaseHeader(
            workspace_id=workspace_id,
            case_id=case_id,
            title="Delivery anomaly",
            severity=CaseSeverity.HIGH,
            status=CaseStatus.INVESTIGATING,
            version=2,
        ),
        goal="Determine which fulfillment stage deteriorated",
        manifest=ContextManifest(
            context_version="commerce-fulfillment-path-context@1.0.0",
            workspace_id=workspace_id,
            case_id=case_id,
            dataset_id=dataset_id,
            source_artifact_sha256="a" * 64,
            context_sha256="b" * 64,
            estimated_tokens=1_000,
            included_metric_observation_ids=metric_ids,
        ),
        budget=AgentBudgetLimit(
            max_iterations=4,
            max_tool_calls=8,
            max_path_agents=0,
            max_tokens=6_000,
            max_wall_time_seconds=120,
            max_model_escalations=0,
        ),
        metadata={},
        path_type=PathType.FULFILLMENT,
        required_capabilities=frozenset(
            {CapabilityName.FULFILLMENT_DIAGNOSIS}
        ),
        capability_profile=CapabilityProfile(
            dataset_id=dataset_id,
            workspace_id=workspace_id,
            capabilities=(
                CapabilityAssessment(
                    name=CapabilityName.FULFILLMENT_DIAGNOSIS,
                    path_agent="FulfillmentPathAgent",
                    status=CapabilityStatus.AVAILABLE,
                    reason_codes=frozenset({CapabilityReasonCode.AVAILABLE}),
                    available_fields=frozenset(),
                    missing_required_fields=frozenset(),
                    missing_optional_fields=frozenset(),
                ),
            ),
        ),
        analysis=analysis,
        evidence=(),
        allowed_tools=frozenset({"metric_query", "source_fact_lookup"}),
        forbidden_claims=("Do not infer seller causality from correlation",),
        output_schema="commerce.path_result@1.0.0",
    )


@pytest.mark.anyio
async def test_explicit_fulfillment_request_uses_snapshots_without_fabricating_anomaly():
    path_context = _context()
    lead = LeadContextPacket(
        case=path_context.case,
        goal="Compare the explicitly requested fulfillment windows.",
        manifest=path_context.manifest.model_copy(
            update={"context_version": "commerce-lead-context@1.0.0"}
        ),
        budget=AgentBudgetLimit(max_tokens=16_000),
        capabilities=frozenset({CapabilityName.FULFILLMENT_DIAGNOSIS}),
        capability_profile=path_context.capability_profile,
        analysis=path_context.analysis.model_copy(
            update={
                "trigger": CaseTriggerDigest(
                    trigger_type=CaseTriggerType.EXPLICIT_USER,
                    requested_paths=(PathType.FULFILLMENT,),
                )
            }
        ),
    )

    plan = await FulfillmentPathAgent().prepare(lead)

    assert plan.context.analysis.anomalies == ()
    assert plan.context.manifest.included_anomaly_ids == ()
    assert plan.context.analysis.trigger.trigger_type is CaseTriggerType.EXPLICIT_USER
    assert "explicit" in plan.context.goal.casefold()


def _draft(context: PathContextPacket) -> dict:
    baseline = {
        item.metric_name: item.metric_observation_id
        for item in context.analysis.baseline_metrics
    }
    current = {
        item.metric_name: item.metric_observation_id
        for item in context.analysis.current_metrics
    }
    return {
        "observations": [
            {
                "summary": "Late delivery rate increased in the current window",
                "confidence": 0.94,
                "metric_observation_ids": [
                    baseline[MetricName.LATE_DELIVERY_RATE.value],
                    current[MetricName.LATE_DELIVERY_RATE.value],
                ],
            },
            {
                "summary": "Handling time decreased and did not worsen",
                "confidence": 0.93,
                "metric_observation_ids": [
                    baseline[MetricName.HANDLING_TIME_HOURS.value],
                    current[MetricName.HANDLING_TIME_HOURS.value],
                ],
            },
            {
                "summary": "Transit time increased and worsened",
                "confidence": 0.95,
                "metric_observation_ids": [
                    baseline[MetricName.TRANSIT_TIME_HOURS.value],
                    current[MetricName.TRANSIT_TIME_HOURS.value],
                ],
            },
        ],
        "unknowns": [
            {
                "question": "Which carrier event changed?",
                "reason": "Carrier scans were not uploaded",
                "missing_capabilities": ["carrier_scan_events"],
            }
        ],
        "suggested_next_paths": ["seller_peer"],
    }


def _harness_result(
    task_id: AgentTaskId,
    draft: dict,
    *,
    actual_identity: str | None = "deepseek-v4-flash",
    message_count: int = 1,
    result_text: str | None = None,
):
    semantic_text = result_text or json.dumps(draft)
    messages = []
    records = []
    for index in range(1, message_count + 1):
        metadata = {
            "headers": {"x-request-id": f"provider-request-{index}"},
            "id": f"provider-response-{index}",
            "finish_reason": "stop",
        }
        if actual_identity is not None:
            metadata["model_name"] = actual_identity
        messages.append(
            AIMessage(
                content=semantic_text,
                response_metadata=metadata,
                usage_metadata={
                    "input_tokens": 300,
                    "output_tokens": 120,
                    "total_tokens": 420,
                },
            ).model_dump()
        )
        records.append(
            {
                "source_run_id": f"model-run-{index}",
                "caller": "subagent:commerce-fulfillment-path",
                "input_tokens": 300,
                "output_tokens": 120,
                "total_tokens": 420,
            }
        )
    started_at = datetime.now(UTC)
    return SimpleNamespace(
        task_id=str(task_id),
        trace_id=str(TraceId.new()),
        status=HarnessStatus.COMPLETED,
        result=semantic_text,
        error=None,
        started_at=started_at,
        completed_at=started_at + timedelta(milliseconds=750),
        ai_messages=messages,
        token_usage_records=records,
    )


def _spec_and_task():
    context = _context()
    spec = FulfillmentSubagentSpec(
        FulfillmentPathPlan(context=context, assignment=_assignment())
    )
    task = spec.build_task(
        run_id=RunId.new(),
        task_id=AgentTaskId.new(),
        lease_worker_id="commerce-subagent-worker",
        fencing_token=1,
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
    )
    return spec, task


def test_fulfillment_subagent_normalizes_semantic_draft_with_runtime_telemetry():
    spec, task = _spec_and_task()
    adapter = spec.build_adapter(tools=build_fulfillment_read_tools(spec.plan.context))

    outcome = adapter.consume(
        task,
        _harness_result(task.task_id, _draft(spec.plan.context)),
    )

    assert outcome.status is CommerceSubagentStatus.COMPLETED
    assert outcome.result is not None
    assert outcome.result.path_type is PathType.FULFILLMENT
    assert outcome.result.trace_id == task.trace_id
    assert outcome.result.context_sha256 == task.context_sha256
    assert outcome.result.model_assignment == task.model_assignment
    assert outcome.result.model_execution.provider_request_id == "provider-request-1"
    assert outcome.result.model_execution.actual_model_identity == "deepseek-v4-flash"
    assert outcome.result.model_execution.retry_count == 0
    assert outcome.result.cost.input_tokens == 300
    assert outcome.result.cost.output_tokens == 120
    assert outcome.result.cost.latency_ms == 750


def test_fulfillment_subagent_prompt_requests_only_semantic_draft():
    spec, task = _spec_and_task()
    adapter = spec.build_adapter(tools=build_fulfillment_read_tools(spec.plan.context))

    prompt = adapter.build_prompt(task, spec.plan.context)

    assert str(task.task_id) in prompt
    assert "FulfillmentModelOutput" in prompt
    assert '"provider_request_id":' not in prompt
    assert '"actual_model_identity":' not in prompt
    assert '"retry_count":' not in prompt


def test_fulfillment_subagent_blocks_when_runtime_identity_is_missing():
    spec, task = _spec_and_task()
    adapter = spec.build_adapter(tools=build_fulfillment_read_tools(spec.plan.context))

    outcome = adapter.consume(
        task,
        _harness_result(
            task.task_id,
            _draft(spec.plan.context),
            actual_identity=None,
        ),
    )

    assert outcome.status is CommerceSubagentStatus.BLOCKED
    assert outcome.error_code is CommerceSubagentErrorCode.RUNTIME_TELEMETRY_MISSING
    assert outcome.result is None


def test_fulfillment_subagent_classifies_invalid_semantic_draft_as_path_error():
    spec, task = _spec_and_task()
    adapter = spec.build_adapter(tools=build_fulfillment_read_tools(spec.plan.context))
    invalid_draft = _draft(spec.plan.context)
    invalid_draft["observations"] = invalid_draft["observations"][:-1]

    outcome = adapter.consume(
        task,
        _harness_result(task.task_id, invalid_draft),
    )

    assert outcome.status is CommerceSubagentStatus.BLOCKED
    assert outcome.error_code is CommerceSubagentErrorCode.INVALID_PATH_RESULT
    assert "Fulfillment semantic draft" in (outcome.error_message or "")
    assert outcome.result is None


def test_fulfillment_subagent_accepts_only_schema_valid_fenced_json():
    spec, task = _spec_and_task()
    adapter = spec.build_adapter(tools=build_fulfillment_read_tools(spec.plan.context))
    draft = _draft(spec.plan.context)
    fenced = f"Reasoning summary:\n```json\n{json.dumps(draft)}\n```"

    outcome = adapter.consume(
        task,
        _harness_result(task.task_id, draft, result_text=fenced),
    )

    assert outcome.status is CommerceSubagentStatus.COMPLETED
    assert outcome.result is not None
    assert len(outcome.result.observations) == len(draft["observations"])


def test_fulfillment_subagent_accepts_multiple_fresh_tool_loop_turns():
    spec, task = _spec_and_task()
    adapter = spec.build_adapter(tools=build_fulfillment_read_tools(spec.plan.context))

    outcome = adapter.consume(
        task,
        _harness_result(
            task.task_id,
            _draft(spec.plan.context),
            message_count=2,
        ),
    )

    assert outcome.status is CommerceSubagentStatus.COMPLETED
    assert outcome.result is not None
    assert outcome.result.model_execution.provider_request_id == "provider-request-2"
    assert outcome.result.model_execution.provider_request_ids == (
        "provider-request-1",
        "provider-request-2",
    )
    assert outcome.result.cost.input_tokens == 600
    assert outcome.result.cost.output_tokens == 240


def test_fulfillment_subagent_tools_are_read_only_context_projections():
    context = _context()
    tools = {tool.name: tool for tool in build_fulfillment_read_tools(context)}

    metric_result = json.loads(tools["metric_query"].invoke({"query": "transit"}))
    fact_result = json.loads(
        tools["source_fact_lookup"].invoke({"query": "carrier scan"})
    )

    assert set(tools) == {"metric_query", "source_fact_lookup"}
    assert metric_result["metrics"]["baseline"]
    assert metric_result["metrics"]["current"]
    assert fact_result["status"] == "not_observed"
    assert "carrier scan" in fact_result["query"]
