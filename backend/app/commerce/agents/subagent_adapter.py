"""Commerce application boundary for bounded DeerFlow subagent execution."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Self

from langchain_core.messages import AIMessage
from langchain_core.tools import BaseTool
from pydantic import Field, ValidationError, model_validator

from app.commerce.agents.contracts import (
    AgentBudgetLimit,
    PathContextPacket,
    PathType,
)
from app.commerce.agents.model_router import ModelAssignment, ModelRole
from app.commerce.agents.path_result import PathResult
from app.commerce.domain.ids import (
    AgentTaskId,
    CaseId,
    CorrelationId,
    RunId,
    TraceId,
    WorkspaceId,
)
from app.commerce.domain.models import CommerceModel
from app.commerce.evaluation.real_model_preflight import (
    TokenUsage,
    _extract_identity,
    _extract_provider_ids,
    _mapping,
    is_verified_deepseek_v4_identity,
)


class CommerceSubagentStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class CommerceSubagentErrorCode(StrEnum):
    TASK_NOT_FOUND = "task_not_found"
    TASK_ID_MISMATCH = "task_id_mismatch"
    HARNESS_FAILED = "harness_failed"
    HARNESS_CANCELLED = "harness_cancelled"
    HARNESS_TIMED_OUT = "harness_timed_out"
    RESULT_MISSING = "result_missing"
    INVALID_JSON = "invalid_json"
    INVALID_PATH_RESULT = "invalid_path_result"
    PATH_TYPE_MISMATCH = "path_type_mismatch"
    CONTEXT_MISMATCH = "context_mismatch"
    MODEL_ASSIGNMENT_MISMATCH = "model_assignment_mismatch"
    SKILL_VERSION_MISMATCH = "skill_version_mismatch"
    SCHEMA_VERSION_MISMATCH = "schema_version_mismatch"
    TOOL_POLICY_MISMATCH = "tool_policy_mismatch"
    TOOL_STREAM_INVALID = "tool_stream_invalid"
    RUNTIME_TELEMETRY_MISSING = "runtime_telemetry_missing"


class CommerceAgentTask(CommerceModel):
    """Secret-free reference contract for one bounded Commerce Path task."""

    schema_version: str = "commerce.agent_task@1.0.0"
    workspace_id: WorkspaceId
    case_id: CaseId
    run_id: RunId
    task_id: AgentTaskId
    path_type: PathType
    subagent_name: str = Field(min_length=1)
    context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    budget: AgentBudgetLimit
    model_assignment: ModelAssignment
    skill_id: str = Field(min_length=1)
    skill_version: str = Field(min_length=1)
    allowed_tools: frozenset[str] = Field(min_length=1)
    expected_result_schema: str = Field(min_length=1)
    lease_worker_id: str = Field(min_length=1, max_length=128)
    fencing_token: int = Field(ge=1)
    trace_id: TraceId
    correlation_id: CorrelationId
    issued_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def enforce_bounded_path_task(self) -> Self:
        if self.model_assignment.role is not ModelRole.PATH:
            raise ValueError("Commerce subagent task requires a Path model assignment")
        if "task" in self.allowed_tools:
            raise ValueError("Commerce subagent cannot use the recursive task tool")
        return self


class CommerceSubagentToolStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class CommerceSubagentToolEvent(CommerceModel):
    """Secret-free terminal Tool event emitted by the DeerFlow runtime."""

    tool_call_id: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    status: CommerceSubagentToolStatus
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    response_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    latency_ms: float = Field(ge=0)
    error_code: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def keep_status_and_error_consistent(self) -> Self:
        if self.request_sha256 == "0" * 64:
            raise ValueError("Tool event is missing its model request trace")
        if self.status is CommerceSubagentToolStatus.SUCCEEDED and self.error_code:
            raise ValueError("Successful Tool event cannot carry an error")
        if self.status is CommerceSubagentToolStatus.FAILED and not self.error_code:
            raise ValueError("Failed Tool event requires error_code")
        return self


class CommerceSubagentOutcome(CommerceModel):
    """Secret-free projection of Harness state and validated Commerce output."""

    schema_version: str = "commerce.subagent_outcome@1.0.0"
    task_id: AgentTaskId
    path_type: PathType
    status: CommerceSubagentStatus
    harness_trace_id: str = Field(min_length=1)
    result: PathResult | None = None
    result_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    tool_events: tuple[CommerceSubagentToolEvent, ...] = ()
    error_code: CommerceSubagentErrorCode | None = None
    error_message: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def keep_status_and_payload_consistent(self) -> Self:
        if self.status is CommerceSubagentStatus.COMPLETED:
            if self.result is None or self.result_sha256 is None:
                raise ValueError("Completed Commerce subagent outcome requires a result")
            if self.error_code is not None or self.error_message is not None:
                raise ValueError("Completed Commerce subagent outcome cannot carry an error")
            return self
        if self.result is not None or self.result_sha256 is not None:
            raise ValueError("Non-completed Commerce subagent outcome cannot carry a result")
        if self.status in {
            CommerceSubagentStatus.BLOCKED,
            CommerceSubagentStatus.FAILED,
            CommerceSubagentStatus.CANCELLED,
            CommerceSubagentStatus.TIMED_OUT,
        } and (self.error_code is None or self.error_message is None):
            raise ValueError("Terminal unsuccessful outcome requires an error")
        if self.status in {
            CommerceSubagentStatus.PENDING,
            CommerceSubagentStatus.RUNNING,
        } and (self.error_code is not None or self.error_message is not None):
            raise ValueError("Non-terminal outcome cannot carry an error")
        return self


class CommerceSubagentContractError(ValueError):
    """Raised before execution when task, context, or Harness policy diverges."""


class CommerceSubagentTelemetryError(CommerceSubagentContractError):
    """Raised when protected runtime evidence is absent or inconsistent."""


ExecutorFactory = Callable[..., Any]
ResultReader = Callable[[str], Any | None]
TaskCallback = Callable[[str], None]
PromptBuilder = Callable[[CommerceAgentTask, PathContextPacket], str]
ResultParser = Callable[[CommerceAgentTask, Any, dict[str, Any] | str], PathResult]


@dataclass(frozen=True)
class RuntimeTelemetrySnapshot:
    """Protected runtime fields needed to hydrate a PathResult."""

    provider_request_id: str
    provider_request_ids: tuple[str, ...]
    actual_model_identity: str
    token_usage: TokenUsage
    latency_ms: float
    stop_reason: str


def extract_runtime_telemetry(
    harness_result: Any,
    *,
    caller: str,
) -> RuntimeTelemetrySnapshot:
    """Extract one fresh, identity-verified model attempt from Harness state."""

    messages = getattr(harness_result, "ai_messages", None) or []
    if not messages:
        raise CommerceSubagentTelemetryError(
            f"{caller} requires at least one fresh model message"
        )
    try:
        validated_messages = tuple(
            AIMessage.model_validate(item) for item in messages
        )
    except Exception as exc:
        raise CommerceSubagentTelemetryError(
            f"{caller} did not receive a valid final AIMessage"
        ) from exc
    if any(
        not is_verified_deepseek_v4_identity(
            _extract_identity(_mapping(item.response_metadata))[0]
        )
        for item in validated_messages
    ):
        raise CommerceSubagentTelemetryError(
            f"{caller} runtime includes an unverified model turn"
        )
    provider_request_ids = tuple(
        _extract_provider_ids(_mapping(item.response_metadata))[0]
        for item in validated_messages
    )
    if any(not value for value in provider_request_ids) or len(
        provider_request_ids
    ) != len(set(provider_request_ids)):
        raise CommerceSubagentTelemetryError(
            f"{caller} runtime Provider Request IDs are missing or duplicated"
        )
    message = validated_messages[-1]

    metadata = _mapping(message.response_metadata)
    actual_identity, _identity_source = _extract_identity(metadata)
    provider_request_id, _request_id_source, _provider_response_id = (
        _extract_provider_ids(metadata)
    )
    stop_reason_value = metadata.get("finish_reason") or metadata.get("stop_reason")
    stop_reason = str(stop_reason_value) if stop_reason_value else None
    records = getattr(harness_result, "token_usage_records", None) or []
    if not is_verified_deepseek_v4_identity(actual_identity):
        raise CommerceSubagentTelemetryError(
            f"{caller} runtime did not expose a verified DeepSeek V4 identity"
        )
    if not provider_request_id or not stop_reason:
        raise CommerceSubagentTelemetryError(
            f"{caller} runtime telemetry is incomplete"
        )
    if not records or len(records) != len(validated_messages):
        raise CommerceSubagentTelemetryError(
            f"{caller} runtime model-turn and token-record counts disagree"
        )
    required_token_fields = {"input_tokens", "output_tokens", "total_tokens"}
    if any(not required_token_fields.issubset(record) for record in records):
        raise CommerceSubagentTelemetryError(
            f"{caller} token collector omitted required usage fields"
        )
    input_tokens = sum(int(record.get("input_tokens", 0)) for record in records)
    output_tokens = sum(int(record.get("output_tokens", 0)) for record in records)
    total_tokens = sum(int(record.get("total_tokens", 0)) for record in records)
    if input_tokens < 1 or total_tokens != input_tokens + output_tokens:
        raise CommerceSubagentTelemetryError(
            f"{caller} token collector has inconsistent aggregate usage"
        )
    token_usage = TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    )

    started_at = getattr(harness_result, "started_at", None)
    completed_at = getattr(harness_result, "completed_at", None)
    if started_at is None or completed_at is None:
        raise CommerceSubagentTelemetryError(
            f"{caller} runtime did not expose start and completion timestamps"
        )
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=UTC)
    if completed_at.tzinfo is None:
        completed_at = completed_at.replace(tzinfo=UTC)
    latency_ms = (completed_at - started_at).total_seconds() * 1000
    if latency_ms < 0:
        raise CommerceSubagentTelemetryError(
            f"{caller} runtime timestamps are not monotonic"
        )
    return RuntimeTelemetrySnapshot(
        provider_request_id=provider_request_id,
        provider_request_ids=provider_request_ids,
        actual_model_identity=actual_identity,
        token_usage=token_usage,
        latency_ms=latency_ms,
        stop_reason=stop_reason,
    )


def _bootstrap_deerflow_subagent_runtime() -> None:
    # DeerFlow currently requires agents to initialize before importing the
    # subagent executor because task_tool participates in the package graph.
    __import__("deerflow.agents")


def _default_executor_factory(**kwargs: Any) -> Any:
    _bootstrap_deerflow_subagent_runtime()
    from deerflow.subagents.executor import SubagentExecutor

    return SubagentExecutor(**kwargs)


def _default_result_reader(task_id: str) -> Any | None:
    _bootstrap_deerflow_subagent_runtime()
    from deerflow.subagents.executor import get_background_task_result

    return get_background_task_result(task_id)


def _default_cancel_requester(task_id: str) -> None:
    _bootstrap_deerflow_subagent_runtime()
    from deerflow.subagents.executor import request_cancel_background_task

    request_cancel_background_task(task_id)


def _default_task_cleaner(task_id: str) -> None:
    _bootstrap_deerflow_subagent_runtime()
    from deerflow.subagents.executor import cleanup_background_task

    cleanup_background_task(task_id)


class CommerceSubagentAdapter:
    """Translate Commerce tasks to DeerFlow without owning business persistence."""

    def __init__(
        self,
        *,
        tools: Sequence[BaseTool],
        app_config: Any | None = None,
        executor_factory: ExecutorFactory = _default_executor_factory,
        result_reader: ResultReader = _default_result_reader,
        cancel_requester: TaskCallback = _default_cancel_requester,
        task_cleaner: TaskCallback = _default_task_cleaner,
        prompt_builder: PromptBuilder | None = None,
        result_parser: ResultParser | None = None,
    ) -> None:
        tools_by_name = {tool.name: tool for tool in tools}
        if len(tools_by_name) != len(tools):
            raise CommerceSubagentContractError("Commerce adapter tools must be unique")
        self._tools = tuple(tools)
        self._tools_by_name = tools_by_name
        self._app_config = app_config
        self._executor_factory = executor_factory
        self._result_reader = result_reader
        self._cancel_requester = cancel_requester
        self._task_cleaner = task_cleaner
        self._prompt_builder = prompt_builder
        self._result_parser = result_parser

    def build_executor(
        self,
        task: CommerceAgentTask,
        context: PathContextPacket,
    ) -> Any:
        self._validate_context(task, context)
        missing_tools = sorted(task.allowed_tools - self._tools_by_name.keys())
        if missing_tools:
            raise CommerceSubagentContractError(
                "Commerce subagent requested unavailable tools: "
                f"{', '.join(missing_tools)}"
            )

        timeout_seconds = max(
            1,
            math.ceil(
                min(
                    task.budget.max_wall_time_seconds,
                    task.model_assignment.timeout_seconds,
                )
            ),
        )
        _bootstrap_deerflow_subagent_runtime()
        from deerflow.subagents.config import SubagentConfig

        config = SubagentConfig(
            name=task.subagent_name,
            description=f"Bounded Commerce {task.path_type.value} investigation",
            system_prompt=self._system_prompt(task),
            tools=sorted(task.allowed_tools),
            disallowed_tools=["task"],
            # Commerce skills are versioned by the application task. Do not inherit
            # unrelated parent skills while the dedicated skill loader is migrated.
            skills=[],
            model=task.model_assignment.model_alias,
            max_turns=task.budget.max_iterations,
            timeout_seconds=timeout_seconds,
            max_output_tokens=task.model_assignment.max_output_tokens,
            model_max_retries=0,
            llm_retry_max_attempts=1,
        )
        return self._executor_factory(
            config=config,
            tools=list(self._tools),
            app_config=self._app_config,
            parent_model=None,
            sandbox_state=None,
            thread_data=None,
            thread_id=str(task.run_id),
            trace_id=str(task.trace_id),
        )

    def build_prompt(
        self,
        task: CommerceAgentTask,
        context: PathContextPacket,
    ) -> str:
        self._validate_context(task, context)
        packet = json.dumps(
            context.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        prompt = (
            "Investigate only the supplied Commerce PathContextPacket. "
            "Use only its allowed tools and trace every claim to supplied Fact or "
            "MetricObservation IDs. Return exactly one JSON object conforming to "
            f"{task.expected_result_schema}. Do not include Markdown or hidden "
            "reasoning. Runtime-owned model identity, provider request, token, "
            "latency, retry, and stop-reason fields must never be invented.\n\n"
            f"PathContextPacket:\n{packet}"
        )
        return self._prompt_builder(task, context) if self._prompt_builder else prompt

    def start(
        self,
        task: CommerceAgentTask,
        context: PathContextPacket,
    ) -> AgentTaskId:
        executor = self.build_executor(task, context)
        harness_task_id = executor.execute_async(
            self.build_prompt(task, context),
            task_id=str(task.task_id),
        )
        if harness_task_id != str(task.task_id):
            raise CommerceSubagentContractError(
                "DeerFlow returned a task ID that does not match Commerce AgentTaskId"
            )
        return task.task_id

    def poll(self, task: CommerceAgentTask) -> CommerceSubagentOutcome:
        result = self._result_reader(str(task.task_id))
        if result is None:
            return self._error_outcome(
                task,
                harness_trace_id=str(task.trace_id),
                status=CommerceSubagentStatus.FAILED,
                error_code=CommerceSubagentErrorCode.TASK_NOT_FOUND,
                error_message="DeerFlow background task was not found",
            )
        return self.consume(task, result)

    def cancel(self, task: CommerceAgentTask) -> None:
        self._cancel_requester(str(task.task_id))

    def cleanup(self, task: CommerceAgentTask) -> None:
        self._task_cleaner(str(task.task_id))

    def consume(
        self,
        task: CommerceAgentTask,
        harness_result: Any,
    ) -> CommerceSubagentOutcome:
        if harness_result.task_id != str(task.task_id):
            return self._error_outcome(
                task,
                harness_trace_id=harness_result.trace_id,
                status=CommerceSubagentStatus.FAILED,
                error_code=CommerceSubagentErrorCode.TASK_ID_MISMATCH,
                error_message="DeerFlow task ID does not match Commerce AgentTaskId",
            )

        status = self._status_value(harness_result.status)
        try:
            tool_events = self._tool_events(task, harness_result)
        except (ValidationError, ValueError, TypeError) as exc:
            return self._blocked_result(
                task,
                harness_result,
                CommerceSubagentErrorCode.TOOL_STREAM_INVALID,
                f"DeerFlow Tool stream is invalid: {exc}",
            )
        if status == "pending":
            return self._lifecycle_outcome(
                task,
                harness_result,
                CommerceSubagentStatus.PENDING,
            )
        if status == "running":
            return self._lifecycle_outcome(
                task,
                harness_result,
                CommerceSubagentStatus.RUNNING,
            )
        if status == "failed":
            return self._error_outcome(
                task,
                harness_trace_id=harness_result.trace_id,
                status=CommerceSubagentStatus.FAILED,
                error_code=CommerceSubagentErrorCode.HARNESS_FAILED,
                error_message=harness_result.error or "DeerFlow subagent failed",
                tool_events=tool_events,
            )
        if status == "cancelled":
            return self._error_outcome(
                task,
                harness_trace_id=harness_result.trace_id,
                status=CommerceSubagentStatus.CANCELLED,
                error_code=CommerceSubagentErrorCode.HARNESS_CANCELLED,
                error_message=harness_result.error or "DeerFlow subagent was cancelled",
                tool_events=tool_events,
            )
        if status == "timed_out":
            return self._error_outcome(
                task,
                harness_trace_id=harness_result.trace_id,
                status=CommerceSubagentStatus.TIMED_OUT,
                error_code=CommerceSubagentErrorCode.HARNESS_TIMED_OUT,
                error_message=harness_result.error or "DeerFlow subagent timed out",
                tool_events=tool_events,
            )
        if harness_result.result is None:
            return self._blocked_result(
                task,
                harness_result,
                CommerceSubagentErrorCode.RESULT_MISSING,
                "Completed DeerFlow subagent returned no structured result",
                tool_events=tool_events,
            )

        try:
            payload: dict[str, Any] | str = json.loads(harness_result.result)
        except json.JSONDecodeError:
            if self._result_parser is None:
                return self._blocked_result(
                    task,
                    harness_result,
                    CommerceSubagentErrorCode.INVALID_JSON,
                    "Completed DeerFlow subagent result is not valid JSON",
                    tool_events=tool_events,
                )
            # A semantic parser may apply a versioned, schema-valid extraction
            # policy (for example fenced JSON) without admitting free-form prose.
            payload = harness_result.result
        try:
            result = (
                self._result_parser(task, harness_result, payload)
                if self._result_parser
                else PathResult.model_validate(payload)
            )
        except CommerceSubagentTelemetryError as exc:
            return self._blocked_result(
                task,
                harness_result,
                CommerceSubagentErrorCode.RUNTIME_TELEMETRY_MISSING,
                str(exc),
                tool_events=tool_events,
            )
        except (
            CommerceSubagentContractError,
            ValidationError,
            ValueError,
            TypeError,
        ) as exc:
            return self._blocked_result(
                task,
                harness_result,
                CommerceSubagentErrorCode.INVALID_PATH_RESULT,
                (
                    "Completed DeerFlow subagent result violates PathResult schema: "
                    f"{exc}"
                ),
                tool_events=tool_events,
            )

        mismatch = self._result_mismatch(task, result)
        if mismatch is not None:
            error_code, error_message = mismatch
            return self._blocked_result(
                task,
                harness_result,
                error_code,
                error_message,
                tool_events=tool_events,
            )
        canonical_result = json.dumps(
            result.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return CommerceSubagentOutcome(
            task_id=task.task_id,
            path_type=task.path_type,
            status=CommerceSubagentStatus.COMPLETED,
            harness_trace_id=harness_result.trace_id,
            result=result,
            result_sha256=hashlib.sha256(canonical_result).hexdigest(),
            tool_events=tool_events,
        )

    @staticmethod
    def _status_value(status: Any) -> str:
        value = getattr(status, "value", status)
        return str(value)

    @staticmethod
    def _system_prompt(task: CommerceAgentTask) -> str:
        tools = ", ".join(sorted(task.allowed_tools))
        return (
            f"You are the bounded {task.path_type.value} Commerce subagent. "
            f"Skill: {task.skill_id}@{task.skill_version}. Allowed tools: {tools}. "
            "Never delegate to another subagent, mutate Commerce state, or claim "
            "causality beyond the supplied evidence."
        )

    @staticmethod
    def _validate_context(
        task: CommerceAgentTask,
        context: PathContextPacket,
    ) -> None:
        if context.case.workspace_id != task.workspace_id:
            raise CommerceSubagentContractError(
                "PathContextPacket Workspace does not match Commerce task"
            )
        if context.case.case_id != task.case_id:
            raise CommerceSubagentContractError(
                "PathContextPacket Case does not match Commerce task"
            )
        if context.path_type is not task.path_type:
            raise CommerceSubagentContractError(
                "PathContextPacket PathType does not match Commerce task"
            )
        if context.manifest.context_sha256 != task.context_sha256:
            raise CommerceSubagentContractError(
                "PathContextPacket context hash does not match Commerce task"
            )
        if context.budget != task.budget:
            raise CommerceSubagentContractError(
                "PathContextPacket Budget does not match Commerce task"
            )
        if context.allowed_tools != task.allowed_tools:
            raise CommerceSubagentContractError(
                "PathContextPacket Tool allowlist does not match Commerce task"
            )
        if context.output_schema != task.expected_result_schema:
            raise CommerceSubagentContractError(
                "PathContextPacket result schema does not match Commerce task"
            )

    @staticmethod
    def _result_mismatch(
        task: CommerceAgentTask,
        result: PathResult,
    ) -> tuple[CommerceSubagentErrorCode, str] | None:
        if result.path_type is not task.path_type:
            return (
                CommerceSubagentErrorCode.PATH_TYPE_MISMATCH,
                "PathResult PathType does not match Commerce task",
            )
        if result.context_sha256 != task.context_sha256:
            return (
                CommerceSubagentErrorCode.CONTEXT_MISMATCH,
                "PathResult context hash does not match Commerce task",
            )
        if result.model_assignment != task.model_assignment:
            return (
                CommerceSubagentErrorCode.MODEL_ASSIGNMENT_MISMATCH,
                "PathResult ModelAssignment does not match Commerce task",
            )
        expected_skill_version = f"{task.skill_id}@{task.skill_version}"
        if result.skill_version != expected_skill_version:
            return (
                CommerceSubagentErrorCode.SKILL_VERSION_MISMATCH,
                "PathResult Skill version does not match Commerce task",
            )
        if result.schema_version != task.expected_result_schema:
            return (
                CommerceSubagentErrorCode.SCHEMA_VERSION_MISMATCH,
                "PathResult schema version does not match Commerce task",
            )
        unauthorized_tools = sorted(
            {
                call.tool_name
                for call in result.tool_calls
                if call.tool_name not in task.allowed_tools
            }
        )
        if unauthorized_tools:
            return (
                CommerceSubagentErrorCode.TOOL_POLICY_MISMATCH,
                "PathResult contains Tool calls outside the Commerce allowlist",
            )
        return None

    @staticmethod
    def _lifecycle_outcome(
        task: CommerceAgentTask,
        harness_result: Any,
        status: CommerceSubagentStatus,
    ) -> CommerceSubagentOutcome:
        return CommerceSubagentOutcome(
            task_id=task.task_id,
            path_type=task.path_type,
            status=status,
            harness_trace_id=harness_result.trace_id,
        )

    def _blocked_result(
        self,
        task: CommerceAgentTask,
        harness_result: Any,
        error_code: CommerceSubagentErrorCode,
        error_message: str,
        tool_events: tuple[CommerceSubagentToolEvent, ...] = (),
    ) -> CommerceSubagentOutcome:
        return self._error_outcome(
            task,
            harness_trace_id=harness_result.trace_id,
            status=CommerceSubagentStatus.BLOCKED,
            error_code=error_code,
            error_message=error_message,
            tool_events=tool_events,
        )

    @staticmethod
    def _tool_events(
        task: CommerceAgentTask,
        harness_result: Any,
    ) -> tuple[CommerceSubagentToolEvent, ...]:
        raw_events = getattr(harness_result, "execution_events", None)
        if not isinstance(raw_events, (list, tuple)):
            return ()
        events: list[CommerceSubagentToolEvent] = []
        seen_call_ids: set[str] = set()
        for raw in raw_events:
            if not isinstance(raw, dict) or raw.get("kind") != "tool.result":
                continue
            event = CommerceSubagentToolEvent.model_validate(
                {key: value for key, value in raw.items() if key != "kind"}
            )
            if event.tool_name not in task.allowed_tools:
                raise ValueError(
                    f"Tool event {event.tool_name} is outside the task allowlist"
                )
            if event.tool_call_id in seen_call_ids:
                raise ValueError(f"Duplicate Tool event {event.tool_call_id}")
            seen_call_ids.add(event.tool_call_id)
            events.append(event)
        return tuple(events)

    @staticmethod
    def _error_outcome(
        task: CommerceAgentTask,
        *,
        harness_trace_id: str,
        status: CommerceSubagentStatus,
        error_code: CommerceSubagentErrorCode,
        error_message: str,
        tool_events: tuple[CommerceSubagentToolEvent, ...] = (),
    ) -> CommerceSubagentOutcome:
        return CommerceSubagentOutcome(
            task_id=task.task_id,
            path_type=task.path_type,
            status=status,
            harness_trace_id=harness_trace_id,
            error_code=error_code,
            error_message=error_message,
            tool_events=tool_events,
        )
