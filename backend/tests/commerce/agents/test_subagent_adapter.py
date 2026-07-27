"""Deterministic Commerce-to-DeerFlow subagent boundary contracts."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

import pytest
from langchain_core.tools import StructuredTool
from pydantic import ValidationError

from app.commerce.agents.contracts import (
    AgentBudgetLimit,
    AnomalyDigest,
    CaseAnalysisDigest,
    CaseHeader,
    ContextManifest,
    MetricObservationDigest,
    ModelProfile,
    PathContextPacket,
    PathType,
)
from app.commerce.agents.model_router import (
    ModelAssignment,
    ModelEffort,
    ModelRole,
    ModelRouteReasonCode,
)
from app.commerce.agents.path_result import (
    ModelExecutionTrace,
    PathCost,
    PathResult,
    PathUnknown,
    ToolCallStatus,
    ToolCallTrace,
)
from app.commerce.agents.subagent_adapter import (
    CommerceAgentTask,
    CommerceSubagentAdapter,
    CommerceSubagentContractError,
    CommerceSubagentErrorCode,
    CommerceSubagentStatus,
    CommerceSubagentToolStatus,
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
    AnomalyId,
    CaseId,
    CorrelationId,
    DatasetId,
    EntityId,
    MetricObservationId,
    RunId,
    TraceId,
    WorkspaceId,
)
from app.commerce.metrics.anomaly import AnomalyDirection, AnomalySeverity
from app.commerce.metrics.registry import MetricName, MetricWindow
from deerflow.subagents.executor import SubagentResult


class HarnessStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


def _assignment(*, alias: str = "deepseek-reasoner") -> ModelAssignment:
    return ModelAssignment(
        role=ModelRole.PATH,
        base_profile=ModelProfile.BALANCED_TOOL_USER,
        profile=ModelProfile.BALANCED_TOOL_USER,
        model_alias=alias,
        effort=ModelEffort.MEDIUM,
        max_output_tokens=4_000,
        timeout_seconds=120,
        reason_codes=frozenset({ModelRouteReasonCode.PROFILE_BINDING}),
        escalation_count=0,
    )


def _context() -> PathContextPacket:
    workspace_id = WorkspaceId.new()
    case_id = CaseId.new()
    dataset_id = DatasetId.new()
    baseline_id = MetricObservationId.new()
    current_id = MetricObservationId.new()
    baseline_window = MetricWindow(
        start=datetime(2026, 1, 1),
        end=datetime(2026, 2, 1),
    )
    current_window = MetricWindow(
        start=datetime(2026, 2, 1),
        end=datetime(2026, 3, 1),
    )
    common_metric = {
        "metric_name": MetricName.LATE_DELIVERY_RATE.value,
        "semantic_status": SemanticStatus.DERIVED,
        "unit": "ratio",
        "formula_version": "late_delivery_rate@1.0.0",
        "sample_size": 100,
        "denominator": 100,
        "source_fact_count": 200,
    }
    analysis = CaseAnalysisDigest(
        dataset_id=dataset_id,
        seller_entity_id=EntityId.new(),
        seller_external_key="seller-a",
        baseline_window=baseline_window,
        current_window=current_window,
        baseline_metrics=(
            MetricObservationDigest(
                metric_observation_id=baseline_id,
                value=Decimal("0.10"),
                numerator=10,
                window_start=baseline_window.start,
                window_end=baseline_window.end,
                **common_metric,
            ),
        ),
        current_metrics=(
            MetricObservationDigest(
                metric_observation_id=current_id,
                value=Decimal("0.30"),
                numerator=30,
                window_start=current_window.start,
                window_end=current_window.end,
                **common_metric,
            ),
        ),
        anomalies=(
            AnomalyDigest(
                anomaly_id=AnomalyId.new(),
                metric_name=MetricName.LATE_DELIVERY_RATE,
                baseline_observation_id=baseline_id,
                current_observation_id=current_id,
                baseline_value=Decimal("0.10"),
                current_value=Decimal("0.30"),
                absolute_change=Decimal("0.20"),
                relative_change=Decimal("2"),
                direction=AnomalyDirection.INCREASE,
                severity=AnomalySeverity.HIGH,
                confidence=0.9,
                baseline_sample_size=100,
                current_sample_size=100,
                sample_adequate=True,
                reason="late delivery rate increased",
            ),
        ),
    )
    capability_profile = CapabilityProfile(
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
    )
    return PathContextPacket(
        case=CaseHeader(
            workspace_id=workspace_id,
            case_id=case_id,
            title="Delivery anomaly",
            severity=CaseSeverity.HIGH,
            status=CaseStatus.INVESTIGATING,
            version=3,
        ),
        goal="Determine which observed fulfillment stage deteriorated",
        manifest=ContextManifest(
            context_version="commerce-fulfillment-path-context@1.0.0",
            workspace_id=workspace_id,
            case_id=case_id,
            dataset_id=dataset_id,
            source_artifact_sha256="a" * 64,
            context_sha256="b" * 64,
            estimated_tokens=900,
            included_metric_observation_ids=(baseline_id, current_id),
            included_anomaly_ids=(analysis.anomalies[0].anomaly_id,),
        ),
        budget=AgentBudgetLimit(
            max_iterations=4,
            max_tool_calls=8,
            max_path_agents=0,
            max_tokens=6_000,
            max_wall_time_seconds=120,
            max_model_escalations=0,
            max_verification_repairs=1,
        ),
        path_type=PathType.FULFILLMENT,
        required_capabilities=frozenset(
            {CapabilityName.FULFILLMENT_DIAGNOSIS}
        ),
        capability_profile=capability_profile,
        analysis=analysis,
        allowed_tools=frozenset({"metric_query", "source_fact_lookup"}),
        forbidden_claims=("Do not infer seller causality from correlation",),
        output_schema="commerce.path_result@1.0.0",
    )


def _task(
    context: PathContextPacket,
    *,
    assignment: ModelAssignment | None = None,
    allowed_tools: frozenset[str] | None = None,
) -> CommerceAgentTask:
    return CommerceAgentTask(
        workspace_id=context.case.workspace_id,
        case_id=context.case.case_id,
        run_id=RunId.new(),
        task_id=AgentTaskId.new(),
        path_type=context.path_type,
        subagent_name="commerce-fulfillment-path",
        context_sha256=context.manifest.context_sha256,
        budget=context.budget,
        model_assignment=assignment or _assignment(),
        skill_id="commerce.fulfillment-investigation",
        skill_version="1.0.0",
        allowed_tools=allowed_tools or context.allowed_tools,
        expected_result_schema=context.output_schema,
        lease_worker_id="commerce-subagent-worker",
        fencing_token=983_451,
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
    )


def _path_result(
    task: CommerceAgentTask,
    *,
    path_type: PathType | None = None,
    context_sha256: str | None = None,
    assignment: ModelAssignment | None = None,
    skill_version: str | None = None,
    schema_version: str | None = None,
    tool_calls: tuple[ToolCallTrace, ...] = (),
) -> PathResult:
    return PathResult(
        schema_version=schema_version or task.expected_result_schema,
        path_type=path_type or task.path_type,
        unknowns=(
            PathUnknown(
                question="Which carrier event changed?",
                reason="Carrier scan events were not uploaded",
                missing_capabilities=("carrier_scan_events",),
            ),
        ),
        tool_calls=tool_calls,
        cost=PathCost(
            input_tokens=120,
            output_tokens=80,
            latency_ms=400,
            tool_call_count=len(tool_calls),
        ),
        trace_id=task.trace_id,
        model_assignment=assignment or task.model_assignment,
        model_execution=ModelExecutionTrace(
            provider_request_id="provider-request-1",
            actual_model_identity="deepseek-v4-flash",
            retry_count=0,
            stop_reason="stop",
            prompt_version="commerce.fulfillment-subagent@1.0.0",
            context_version="commerce-fulfillment-path-context@1.0.0",
        ),
        skill_version=skill_version or f"{task.skill_id}@{task.skill_version}",
        context_sha256=context_sha256 or task.context_sha256,
    )


def _harness_result(
    task: CommerceAgentTask,
    status: HarnessStatus,
    *,
    result: str | None = None,
    task_id: str | None = None,
    error: str | None = None,
    execution_events: list[dict] | None = None,
) -> SubagentResult:
    harness_result = SubagentResult(
        task_id=task_id or str(task.task_id),
        trace_id=str(task.trace_id),
        status=status,
        result=result,
        error=error,
    )
    harness_result.execution_events = execution_events or []
    return harness_result


def _tool(name: str) -> StructuredTool:
    def invoke(query: str) -> str:
        """Return deterministic query output."""

        return query

    return StructuredTool.from_function(invoke, name=name)


def test_agent_task_rejects_non_path_model_and_recursive_task_tool():
    context = _context()
    lead_assignment = _assignment().model_copy(update={"role": ModelRole.LEAD})

    with pytest.raises(ValidationError, match="Path model assignment"):
        _task(context, assignment=lead_assignment)
    with pytest.raises(ValidationError, match="recursive task tool"):
        _task(
            context,
            allowed_tools=frozenset({"metric_query", "task"}),
        )


def test_adapter_builds_bounded_executor_without_inherited_skills_or_tools():
    context = _context()
    task = _task(context)
    adapter = CommerceSubagentAdapter(
        tools=(
            _tool("metric_query"),
            _tool("source_fact_lookup"),
            _tool("unrelated_write_tool"),
            _tool("task"),
        ),
        executor_factory=_RecordingExecutor,
    )

    executor = adapter.build_executor(task, context)

    assert executor.config.name == task.subagent_name
    assert executor.config.model == task.model_assignment.model_alias
    assert executor.config.skills == []
    assert executor.config.disallowed_tools == ["task"]
    assert executor.config.max_turns == task.budget.max_iterations
    assert executor.config.timeout_seconds == 120
    assert executor.config.max_output_tokens == task.model_assignment.max_output_tokens
    assert executor.config.model_max_retries == 0
    assert executor.config.llm_retry_max_attempts == 1
    assert {tool.name for tool in executor.tools} == set(task.allowed_tools)
    assert "task" not in {tool.name for tool in executor.tools}


def test_adapter_projects_secret_free_runtime_tool_events():
    context = _context()
    task = _task(context)
    path_result = _path_result(task)
    adapter = CommerceSubagentAdapter(tools=())
    harness_result = _harness_result(
        task,
        HarnessStatus.COMPLETED,
        result=path_result.model_dump_json(),
        execution_events=[
            {
                "kind": "tool.result",
                "tool_call_id": "call-1",
                "tool_name": "metric_query",
                "status": "succeeded",
                "request_sha256": "a" * 64,
                "response_sha256": "b" * 64,
                "latency_ms": 12.5,
                "error_code": None,
            }
        ],
    )

    outcome = adapter.consume(task, harness_result)

    assert outcome.status is CommerceSubagentStatus.COMPLETED
    assert len(outcome.tool_events) == 1
    assert outcome.tool_events[0].tool_name == "metric_query"
    assert outcome.tool_events[0].status is CommerceSubagentToolStatus.SUCCEEDED


def test_adapter_blocks_tool_stream_outside_task_allowlist():
    context = _context()
    task = _task(context)
    adapter = CommerceSubagentAdapter(tools=())
    harness_result = _harness_result(
        task,
        HarnessStatus.COMPLETED,
        result=_path_result(task).model_dump_json(),
        execution_events=[
            {
                "kind": "tool.result",
                "tool_call_id": "call-1",
                "tool_name": "write_file",
                "status": "succeeded",
                "request_sha256": "a" * 64,
                "response_sha256": "b" * 64,
                "latency_ms": 12.5,
                "error_code": None,
            }
        ],
    )

    outcome = adapter.consume(task, harness_result)

    assert outcome.status is CommerceSubagentStatus.BLOCKED
    assert outcome.error_code is CommerceSubagentErrorCode.TOOL_STREAM_INVALID


def test_adapter_prompt_contains_only_minimal_context_not_runtime_credentials():
    context = _context()
    task = _task(context)
    adapter = CommerceSubagentAdapter(
        tools=(_tool("metric_query"), _tool("source_fact_lookup"))
    )

    prompt = adapter.build_prompt(task, context)

    assert context.goal in prompt
    assert task.context_sha256 in prompt
    assert str(task.run_id) not in prompt
    assert str(task.correlation_id) not in prompt
    assert "983451" not in prompt
    assert "fencing_token" not in prompt
    assert "lease" not in prompt.casefold()


@pytest.mark.parametrize(
    ("change", "message"),
    (
        ({"path_type": PathType.SELLER_PEER}, "PathType"),
        ({"allowed_tools": frozenset({"metric_query"})}, "Tool allowlist"),
        ({"output_schema": "commerce.path_result@2.0.0"}, "result schema"),
    ),
)
def test_adapter_rejects_task_context_contract_mismatch(change, message):
    context = _context()
    task = _task(context)
    changed_context = context.model_copy(update=change)
    adapter = CommerceSubagentAdapter(
        tools=(_tool("metric_query"), _tool("source_fact_lookup"))
    )

    with pytest.raises(CommerceSubagentContractError, match=message):
        adapter.build_executor(task, changed_context)


def test_adapter_rejects_missing_allowlisted_tool_before_start():
    context = _context()
    task = _task(context)
    adapter = CommerceSubagentAdapter(tools=(_tool("metric_query"),))

    with pytest.raises(CommerceSubagentContractError, match="unavailable tools"):
        adapter.build_executor(task, context)


@pytest.mark.parametrize(
    ("harness_status", "commerce_status"),
    (
        (HarnessStatus.PENDING, CommerceSubagentStatus.PENDING),
        (HarnessStatus.RUNNING, CommerceSubagentStatus.RUNNING),
        (HarnessStatus.FAILED, CommerceSubagentStatus.FAILED),
        (HarnessStatus.CANCELLED, CommerceSubagentStatus.CANCELLED),
        (HarnessStatus.TIMED_OUT, CommerceSubagentStatus.TIMED_OUT),
    ),
)
def test_adapter_maps_harness_lifecycle_without_inventing_completion(
    harness_status,
    commerce_status,
):
    context = _context()
    task = _task(context)
    adapter = CommerceSubagentAdapter(tools=())
    error = "runtime stopped" if harness_status in {
        HarnessStatus.FAILED,
        HarnessStatus.CANCELLED,
        HarnessStatus.TIMED_OUT,
    } else None

    outcome = adapter.consume(
        task,
        _harness_result(task, harness_status, error=error),
    )

    assert outcome.status is commerce_status
    assert outcome.result is None
    assert outcome.result_sha256 is None


def test_adapter_accepts_only_a_fully_bound_path_result():
    context = _context()
    task = _task(context)
    result = _path_result(task)
    adapter = CommerceSubagentAdapter(tools=())

    outcome = adapter.consume(
        task,
        _harness_result(
            task,
            HarnessStatus.COMPLETED,
            result=result.model_dump_json(),
        ),
    )

    assert outcome.status is CommerceSubagentStatus.COMPLETED
    assert outcome.result == result
    assert outcome.result_sha256 is not None
    assert outcome.error_code is None
    assert outcome.error_message is None


@pytest.mark.parametrize(
    ("raw_result", "expected_error"),
    (
        ("not json", CommerceSubagentErrorCode.INVALID_JSON),
        ("{}", CommerceSubagentErrorCode.INVALID_PATH_RESULT),
    ),
)
def test_adapter_blocks_malformed_completed_output(raw_result, expected_error):
    context = _context()
    task = _task(context)
    adapter = CommerceSubagentAdapter(tools=())

    outcome = adapter.consume(
        task,
        _harness_result(
            task,
            HarnessStatus.COMPLETED,
            result=raw_result,
        ),
    )

    assert outcome.status is CommerceSubagentStatus.BLOCKED
    assert outcome.error_code is expected_error
    assert outcome.result is None


@pytest.mark.parametrize(
    ("result_factory", "expected_error"),
    (
        (
            lambda task: _path_result(task, path_type=PathType.SELLER_PEER),
            CommerceSubagentErrorCode.PATH_TYPE_MISMATCH,
        ),
        (
            lambda task: _path_result(task, context_sha256="c" * 64),
            CommerceSubagentErrorCode.CONTEXT_MISMATCH,
        ),
        (
            lambda task: _path_result(task, assignment=_assignment(alias="other-model")),
            CommerceSubagentErrorCode.MODEL_ASSIGNMENT_MISMATCH,
        ),
        (
            lambda task: _path_result(
                task,
                skill_version="commerce.fulfillment-investigation@2.0.0",
            ),
            CommerceSubagentErrorCode.SKILL_VERSION_MISMATCH,
        ),
        (
            lambda task: _path_result(
                task,
                schema_version="commerce.path_result@2.0.0",
            ),
            CommerceSubagentErrorCode.SCHEMA_VERSION_MISMATCH,
        ),
        (
            lambda task: _path_result(
                task,
                tool_calls=(
                    ToolCallTrace(
                        tool_name="unapproved_write_tool",
                        status=ToolCallStatus.DENIED,
                        request_sha256="d" * 64,
                        latency_ms=2,
                        error_code="policy_denied",
                    ),
                ),
            ),
            CommerceSubagentErrorCode.TOOL_POLICY_MISMATCH,
        ),
    ),
)
def test_adapter_blocks_result_that_is_not_bound_to_the_task(
    result_factory,
    expected_error,
):
    context = _context()
    task = _task(context)
    adapter = CommerceSubagentAdapter(tools=())

    outcome = adapter.consume(
        task,
        _harness_result(
            task,
            HarnessStatus.COMPLETED,
            result=result_factory(task).model_dump_json(),
        ),
    )

    assert outcome.status is CommerceSubagentStatus.BLOCKED
    assert outcome.error_code is expected_error
    assert outcome.result is None


def test_adapter_fails_closed_on_task_identity_mismatch():
    context = _context()
    task = _task(context)
    adapter = CommerceSubagentAdapter(tools=())

    outcome = adapter.consume(
        task,
        _harness_result(
            task,
            HarnessStatus.COMPLETED,
            task_id=str(AgentTaskId.new()),
            result=_path_result(task).model_dump_json(),
        ),
    )

    assert outcome.status is CommerceSubagentStatus.FAILED
    assert outcome.error_code is CommerceSubagentErrorCode.TASK_ID_MISMATCH
    assert outcome.result is None


def test_adapter_blocks_completed_status_without_result():
    context = _context()
    task = _task(context)
    adapter = CommerceSubagentAdapter(tools=())

    outcome = adapter.consume(
        task,
        _harness_result(task, HarnessStatus.COMPLETED),
    )

    assert outcome.status is CommerceSubagentStatus.BLOCKED
    assert outcome.error_code is CommerceSubagentErrorCode.RESULT_MISSING


class _RecordingExecutor:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.config = kwargs["config"]
        allowed = set(self.config.tools or ())
        disallowed = set(self.config.disallowed_tools or ())
        self.tools = [
            tool
            for tool in kwargs["tools"]
            if tool.name in allowed and tool.name not in disallowed
        ]
        self.started_prompt: str | None = None

    def execute_async(self, prompt: str, task_id: str | None = None) -> str:
        self.started_prompt = prompt
        assert task_id is not None
        return task_id


def test_adapter_starts_polls_cancels_and_cleans_up_using_commerce_task_id():
    context = _context()
    task = _task(context)
    completed = _harness_result(
        task,
        HarnessStatus.COMPLETED,
        result=_path_result(task).model_dump_json(),
    )
    cancelled: list[str] = []
    cleaned: list[str] = []
    adapter = CommerceSubagentAdapter(
        tools=(_tool("metric_query"), _tool("source_fact_lookup")),
        executor_factory=_RecordingExecutor,
        result_reader=lambda task_id: completed if task_id == str(task.task_id) else None,
        cancel_requester=cancelled.append,
        task_cleaner=cleaned.append,
    )

    started_task_id = adapter.start(task, context)
    outcome = adapter.poll(task)
    adapter.cancel(task)
    adapter.cleanup(task)

    assert started_task_id == task.task_id
    assert outcome.status is CommerceSubagentStatus.COMPLETED
    assert cancelled == [str(task.task_id)]
    assert cleaned == [str(task.task_id)]


def test_adapter_poll_fails_closed_when_harness_task_is_missing():
    context = _context()
    task = _task(context)
    adapter = CommerceSubagentAdapter(tools=(), result_reader=lambda _: None)

    outcome = adapter.poll(task)

    assert outcome.status is CommerceSubagentStatus.FAILED
    assert outcome.error_code is CommerceSubagentErrorCode.TASK_NOT_FOUND
