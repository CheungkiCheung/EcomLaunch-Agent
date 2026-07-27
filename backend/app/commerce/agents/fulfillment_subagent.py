"""Fulfillment Path adapter for the DeerFlow Subagent runtime."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import StructuredTool

from app.commerce.agents.contracts import PathContextPacket, PathType
from app.commerce.agents.fulfillment import (
    FULFILLMENT_PROMPT_VERSION,
    FulfillmentPathAgent,
    FulfillmentPathPlan,
)
from app.commerce.agents.path_result import PathResult
from app.commerce.agents.subagent_adapter import (
    CommerceAgentTask,
    CommerceSubagentAdapter,
    CommerceSubagentContractError,
    extract_runtime_telemetry,
)
from app.commerce.domain.ids import AgentTaskId, CorrelationId, RunId, TraceId


class FulfillmentSubagentResultNormalizer:
    """Turn a semantic Fulfillment draft into a runtime-bound PathResult."""

    def __init__(self, context: PathContextPacket) -> None:
        self._context = context
        self._agent = FulfillmentPathAgent()

    def __call__(
        self,
        task: CommerceAgentTask,
        harness_result: Any,
        payload: dict[str, Any],
    ) -> PathResult:
        if task.path_type is not PathType.FULFILLMENT:
            raise CommerceSubagentContractError(
                "Fulfillment normalizer received a non-Fulfillment task"
            )
        try:
            semantic_text = (
                payload
                if isinstance(payload, str)
                else json.dumps(payload, ensure_ascii=False)
            )
            output = self._agent._parse_output(semantic_text, self._context)
        except Exception as exc:
            raise ValueError(
                "Fulfillment semantic draft violates its structured schema"
            ) from exc

        runtime = extract_runtime_telemetry(
            harness_result,
            caller="Fulfillment Subagent",
        )
        result = self._agent._build_result(
            output,
            context=self._context,
            assignment=task.model_assignment,
            provider_request_id=runtime.provider_request_id,
            actual_model_identity=runtime.actual_model_identity,
            stop_reason=runtime.stop_reason,
            token_usage=runtime.token_usage,
            latency_ms=runtime.latency_ms,
        )
        # The legacy builder creates a standalone Path trace. In the Harness
        # contract the Commerce Task trace is authoritative for all persisted
        # Evidence and Domain Events, so bind the normalized result to it.
        return result.model_copy(
            update={
                "trace_id": task.trace_id,
                "model_execution": result.model_execution.model_copy(
                    update={
                        "provider_request_ids": runtime.provider_request_ids,
                    }
                ),
            }
        )


class FulfillmentSubagentSpec:
    """Versioned DeerFlow-facing spec for the first migrated Commerce Path."""

    name = "commerce-fulfillment-path"
    prompt_version = FULFILLMENT_PROMPT_VERSION

    def __init__(self, plan: FulfillmentPathPlan) -> None:
        self.plan = plan
        self._normalizer = FulfillmentSubagentResultNormalizer(plan.context)

    def build_task(
        self,
        *,
        run_id: RunId,
        lease_worker_id: str,
        fencing_token: int,
        trace_id: TraceId,
        correlation_id: CorrelationId,
        task_id: AgentTaskId | None = None,
    ) -> CommerceAgentTask:
        context = self.plan.context
        return CommerceAgentTask(
            workspace_id=context.case.workspace_id,
            case_id=context.case.case_id,
            run_id=run_id,
            task_id=task_id or AgentTaskId.new(),
            path_type=PathType.FULFILLMENT,
            subagent_name=self.name,
            context_sha256=context.manifest.context_sha256,
            budget=context.budget,
            model_assignment=self.plan.assignment,
            skill_id="commerce.fulfillment-investigation",
            skill_version="1.0.0",
            allowed_tools=context.allowed_tools,
            expected_result_schema=context.output_schema,
            lease_worker_id=lease_worker_id,
            fencing_token=fencing_token,
            trace_id=trace_id,
            correlation_id=correlation_id,
        )

    def build_adapter(self, *, tools: tuple[Any, ...]) -> CommerceSubagentAdapter:
        def prompt_builder(task: CommerceAgentTask, packet: PathContextPacket) -> str:
            rendered = json.dumps(
                packet.model_dump(mode="json"),
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            return (
                f"{FulfillmentPathAgent._system_prompt()}\n\n"
                "The runtime owns Provider ID, actual model identity, token usage, "
                "latency, retry count, and stop reason. Return only the semantic "
                "FulfillmentModelOutput draft; never invent runtime fields. "
                f"Fresh task nonce: {task.task_id}.\nPathContextPacket:\n{rendered}"
            )

        return CommerceSubagentAdapter(
            tools=tools,
            prompt_builder=prompt_builder,
            result_parser=self._normalizer,
        )


def build_fulfillment_read_tools(context: PathContextPacket) -> tuple[StructuredTool, ...]:
    """Build read-only deterministic tools scoped to one Path context."""

    metric_payload = {
        "baseline": [item.model_dump(mode="json") for item in context.analysis.baseline_metrics],
        "current": [item.model_dump(mode="json") for item in context.analysis.current_metrics],
    }

    def metric_query(query: str) -> str:
        """Return only deterministic metric digests already present in context."""

        return json.dumps(
            {"query": query, "metrics": metric_payload},
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    def source_fact_lookup(query: str) -> str:
        """Report that no raw source Fact is available in this Path context."""

        return json.dumps(
            {
                "query": query,
                "status": "not_observed",
                "reason": "Fulfillment Subagent context contains metric digests only",
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    return (
        StructuredTool.from_function(metric_query, name="metric_query"),
        StructuredTool.from_function(source_fact_lookup, name="source_fact_lookup"),
    )
