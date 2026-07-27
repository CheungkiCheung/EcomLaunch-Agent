"""ReviewExperience Path adapter for the DeerFlow Subagent runtime."""

from __future__ import annotations

import json
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from langchain_core.tools import StructuredTool

from app.commerce.agents.contracts import CaseHeader, PathType, bind_context_to_case
from app.commerce.agents.path_result import (
    ModelExecutionTrace,
    PathCost,
    PathEvidenceItem,
    PathObservation,
    PathResult,
    PathUnknown,
)
from app.commerce.agents.review_experience import (
    REVIEW_EXPERIENCE_PROMPT_VERSION,
    ReviewExperienceContextPacket,
    ReviewExperiencePathAgent,
    ReviewExperiencePlan,
)
from app.commerce.agents.subagent_adapter import (
    CommerceAgentTask,
    CommerceSubagentAdapter,
    CommerceSubagentContractError,
    extract_runtime_telemetry,
)
from app.commerce.domain.enums import SemanticStatus
from app.commerce.domain.ids import (
    AgentTaskId,
    CorrelationId,
    EvidenceId,
    RunId,
    TraceId,
)
from app.commerce.domain.models import EvidenceRelation

REVIEW_EXPERIENCE_SKILL_ID = "commerce.review-experience-investigation"
REVIEW_EXPERIENCE_SKILL_VERSION = "1.0.0"


class ReviewExperienceSubagentResultNormalizer:
    """Validate semantic output and bind it to runtime-owned metadata."""

    def __init__(self, plan: ReviewExperiencePlan) -> None:
        self._context = plan.context
        self._plan = plan

    def __call__(
        self,
        task: CommerceAgentTask,
        harness_result: Any,
        payload: dict[str, Any] | str,
    ) -> PathResult:
        if task.path_type is not PathType.REVIEW_EXPERIENCE:
            raise CommerceSubagentContractError(
                "ReviewExperience normalizer received a non-ReviewExperience task"
            )
        semantic_text = (
            payload
            if isinstance(payload, str)
            else json.dumps(payload, ensure_ascii=False)
        )
        output = ReviewExperiencePathAgent._parse(semantic_text, self._context)
        runtime = extract_runtime_telemetry(
            harness_result,
            caller="ReviewExperience Subagent",
        )
        observations = tuple(
            PathObservation(
                summary=item.summary,
                semantic_status=SemanticStatus.DERIVED,
                confidence=item.confidence,
                fact_ids=item.fact_ids,
                metric_observation_ids=item.metric_observation_ids,
            )
            for item in output.observations
        )
        evidence = tuple(
            PathEvidenceItem(
                evidence_id=EvidenceId(
                    f"evd_{uuid5(NAMESPACE_URL, f'{task.context_sha256}:{index}:{item.summary}').hex}"
                ),
                summary=item.summary,
                relation=EvidenceRelation.CONTEXT,
                semantic_status=SemanticStatus.DERIVED,
                confidence=item.confidence,
                fact_ids=item.fact_ids,
                metric_observation_ids=item.metric_observation_ids,
            )
            for index, item in enumerate(output.observations)
        )
        return PathResult(
            path_type=PathType.REVIEW_EXPERIENCE,
            observations=observations,
            evidence=evidence,
            unknowns=tuple(
                PathUnknown(
                    question=item.question,
                    reason=item.reason,
                    missing_capabilities=item.missing_capabilities,
                )
                for item in output.unknowns
            ),
            suggested_next_paths=output.suggested_next_paths,
            tool_calls=self._plan.tool_calls,
            cost=PathCost(
                input_tokens=runtime.token_usage.input_tokens,
                output_tokens=runtime.token_usage.output_tokens,
                latency_ms=runtime.latency_ms
                + sum(item.latency_ms for item in self._plan.tool_calls),
                tool_call_count=len(self._plan.tool_calls),
            ),
            trace_id=task.trace_id,
            model_assignment=task.model_assignment,
            model_execution=ModelExecutionTrace(
                provider_request_id=runtime.provider_request_id,
                provider_request_ids=runtime.provider_request_ids,
                actual_model_identity=runtime.actual_model_identity,
                retry_count=0,
                stop_reason=runtime.stop_reason,
                prompt_version=REVIEW_EXPERIENCE_PROMPT_VERSION,
                context_version=self._context.manifest.context_version,
            ),
            skill_version=(
                f"{REVIEW_EXPERIENCE_SKILL_ID}@{REVIEW_EXPERIENCE_SKILL_VERSION}"
            ),
            context_sha256=task.context_sha256,
        )


class ReviewExperienceSubagentSpec:
    """Versioned DeerFlow-facing spec for review experience investigation."""

    name = "commerce-review-experience-path"
    prompt_version = REVIEW_EXPERIENCE_PROMPT_VERSION

    def __init__(self, plan: ReviewExperiencePlan) -> None:
        self.plan = plan
        self._normalizer = ReviewExperienceSubagentResultNormalizer(plan)

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
            path_type=PathType.REVIEW_EXPERIENCE,
            subagent_name=self.name,
            context_sha256=context.manifest.context_sha256,
            budget=context.budget,
            model_assignment=self.plan.assignment,
            skill_id=REVIEW_EXPERIENCE_SKILL_ID,
            skill_version=REVIEW_EXPERIENCE_SKILL_VERSION,
            allowed_tools=context.allowed_tools,
            expected_result_schema=context.output_schema,
            lease_worker_id=lease_worker_id,
            fencing_token=fencing_token,
            trace_id=trace_id,
            correlation_id=correlation_id,
        )

    def build_adapter(self, *, tools: tuple[Any, ...]) -> CommerceSubagentAdapter:
        def prompt_builder(
            task: CommerceAgentTask,
            context: ReviewExperienceContextPacket,
        ) -> str:
            rendered = json.dumps(
                context.model_dump(mode="json"),
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            return (
                f"{ReviewExperiencePathAgent._system_prompt()}\n\n"
                "The runtime owns Provider ID, actual model identity, token usage, "
                "latency, retry count, and stop reason. Return only the semantic "
                "ReviewExperience output draft; never invent runtime fields. "
                f"Fresh task nonce: {task.task_id}.\nReviewExperienceContextPacket:\n{rendered}"
            )

        return CommerceSubagentAdapter(
            tools=tools,
            prompt_builder=prompt_builder,
            result_parser=self._normalizer,
        )

    def bind_to_case(
        self,
        case: CaseHeader,
        *,
        source_artifact_sha256: str | None = None,
    ) -> ReviewExperienceSubagentSpec:
        """Return a copy bound to the persisted Case lineage for fan-out."""

        rebound = bind_context_to_case(
            self.plan.context,
            case,
            source_artifact_sha256=source_artifact_sha256,
        )
        return ReviewExperienceSubagentSpec(self.plan.model_copy(update={"context": rebound}))


def build_review_experience_read_tools(
    context: ReviewExperienceContextPacket,
) -> tuple[StructuredTool, ...]:
    """Expose deterministic, read-only metric and review-signal projections."""

    metric_payload = context.metrics.model_dump(mode="json")
    signal_payload = context.review_signals.model_dump(mode="json")

    def metric_query(query: str) -> str:
        """Return deterministic baseline/current review metric digests."""

        return json.dumps(
            {"query": query, "metrics": metric_payload},
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    def review_signal_query(query: str) -> str:
        """Return redacted, deterministic low-rating review signals."""

        return json.dumps(
            {"query": query, "review_signals": signal_payload},
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    def source_fact_lookup(query: str) -> str:
        """Report that raw review Facts are represented only by redacted digests."""

        return json.dumps(
            {
                "query": query,
                "status": "not_observed",
                "reason": (
                    "ReviewExperience context exposes redacted excerpts and Fact IDs only"
                ),
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    return (
        StructuredTool.from_function(metric_query, name="metric_query"),
        StructuredTool.from_function(
            review_signal_query,
            name="review_signal_query",
        ),
        StructuredTool.from_function(source_fact_lookup, name="source_fact_lookup"),
    )
