"""Real ReviewExperience Path over scoped metrics and redacted VOC evidence."""

from __future__ import annotations

import hashlib
import json
import re
import time
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Self
from uuid import NAMESPACE_URL, uuid5

from pydantic import Field, ValidationError, model_validator

from app.commerce.agents.budget import BudgetManager
from app.commerce.agents.claim_policy import unsupported_causal_phrases
from app.commerce.agents.contracts import (
    CaseHeader,
    ContextManifest,
    ContextPacket,
    ModelProfile,
    PathType,
    canonical_context_sha256,
    default_path_agent_specs,
    estimate_context_tokens,
)
from app.commerce.agents.model_router import (
    ModelAssignment,
    ModelRole,
    ModelRouter,
    ModelRouteRequest,
    OutputSchemaComplexity,
)
from app.commerce.agents.path_result import (
    ModelExecutionTrace,
    PathCost,
    PathEvidenceItem,
    PathObservation,
    PathResult,
    PathUnknown,
    ToolCallStatus,
    ToolCallTrace,
)
from app.commerce.agents.verified_call import (
    VerifiedCallTelemetry,
    VerifiedModelCaller,
)
from app.commerce.api.data_service import CommerceDataService
from app.commerce.data.capabilities import (
    CapabilityName,
    CapabilityProfile,
    CapabilityStatus,
)
from app.commerce.data.normalized import NormalizedDataset
from app.commerce.domain.enums import CaseSeverity, CaseStatus, SemanticStatus
from app.commerce.domain.ids import (
    CaseId,
    DatasetId,
    EntityId,
    EvidenceId,
    FactId,
    MetricObservationId,
    TraceId,
    WorkspaceId,
)
from app.commerce.domain.models import CommerceModel, EvidenceRelation, Fact
from app.commerce.evaluation.real_model_preflight import RealModelVersionSet
from app.commerce.metrics.registry import (
    MetricEngine,
    MetricName,
    MetricSnapshot,
    MetricWindow,
)

REVIEW_EXPERIENCE_PROMPT_VERSION = "commerce.review-experience-path@1.3.0"
REVIEW_EXPERIENCE_CONTEXT_VERSION = "commerce-review-experience-path-context@1.0.0"
REVIEW_EXPERIENCE_MAX_OUTPUT_TOKENS = 1_800
_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_AUDIT_ROOT = (
    _REPO_ROOT / ".deer-flow" / "commerce" / "evaluation" / "path-agents"
)
_ILLEGAL_OVERCLAIMS = (
    "confirmed counterfeit",
    "confirmed fraud",
    "seller sells counterfeit",
    "确认售假",
    "确认欺诈",
    "卖家就是在售假",
)


class ReviewMetricDigest(CommerceModel):
    baseline_window: MetricWindow
    current_window: MetricWindow
    baseline_order_count: int = Field(ge=0)
    current_order_count: int = Field(ge=0)
    baseline_average_review_score: Decimal = Field(ge=1, le=5)
    current_average_review_score: Decimal = Field(ge=1, le=5)
    baseline_low_rating_rate: Decimal = Field(ge=0, le=1)
    current_low_rating_rate: Decimal = Field(ge=0, le=1)
    baseline_late_delivery_rate: Decimal = Field(ge=0, le=1)
    current_late_delivery_rate: Decimal = Field(ge=0, le=1)
    baseline_average_review_score_id: MetricObservationId
    current_average_review_score_id: MetricObservationId
    baseline_low_rating_rate_id: MetricObservationId
    current_low_rating_rate_id: MetricObservationId
    baseline_late_delivery_rate_id: MetricObservationId
    current_late_delivery_rate_id: MetricObservationId


class ReviewExcerptDigest(CommerceModel):
    order_reference_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    score: int = Field(ge=1, le=2)
    text: str = Field(min_length=1, max_length=280)
    fact_ids: tuple[FactId, ...] = Field(min_length=2)


class ReviewSignalDigest(CommerceModel):
    reviewed_order_count: int = Field(ge=0)
    low_rating_count: int = Field(ge=0)
    low_rating_with_text_count: int = Field(ge=0)
    excerpts: tuple[ReviewExcerptDigest, ...] = ()

    @model_validator(mode="after")
    def keep_counts_consistent(self) -> Self:
        if self.low_rating_count > self.reviewed_order_count:
            raise ValueError("Low-rating count cannot exceed reviewed orders")
        if self.low_rating_with_text_count > self.low_rating_count:
            raise ValueError("Text-bearing low ratings cannot exceed low ratings")
        if len(self.excerpts) > self.low_rating_with_text_count:
            raise ValueError("Review excerpts cannot exceed text-bearing low ratings")
        return self


class ReviewExperienceContextPacket(ContextPacket):
    path_type: Literal[PathType.REVIEW_EXPERIENCE] = PathType.REVIEW_EXPERIENCE
    capability_profile: CapabilityProfile
    seller_entity_id: EntityId
    seller_external_key: str = Field(min_length=1)
    metrics: ReviewMetricDigest
    review_signals: ReviewSignalDigest
    allowed_tools: frozenset[str] = Field(min_length=2)
    forbidden_claims: tuple[str, ...] = ()
    output_schema: str = Field(min_length=1)

    @model_validator(mode="after")
    def keep_review_context_consistent(self) -> Self:
        if self.capability_profile.workspace_id != self.case.workspace_id:
            raise ValueError("Review Capability Workspace must match Case")
        if self.capability_profile.dataset_id != self.manifest.dataset_id:
            raise ValueError("Review Capability Dataset must match Manifest")
        capability = self.capability_profile.capability(
            CapabilityName.REVIEW_EXPERIENCE
        )
        if capability.status is CapabilityStatus.UNAVAILABLE:
            raise ValueError("ReviewExperience capability is unavailable")
        metric_ids = {
            self.metrics.baseline_average_review_score_id,
            self.metrics.current_average_review_score_id,
            self.metrics.baseline_low_rating_rate_id,
            self.metrics.current_low_rating_rate_id,
            self.metrics.baseline_late_delivery_rate_id,
            self.metrics.current_late_delivery_rate_id,
        }
        if not metric_ids.issubset(
            set(self.manifest.included_metric_observation_ids)
        ):
            raise ValueError("Review metrics must belong to Context Manifest")
        fact_ids = {
            fact_id
            for item in self.review_signals.excerpts
            for fact_id in item.fact_ids
        }
        if fact_ids != set(self.manifest.included_fact_ids):
            raise ValueError("Review excerpt Facts must exactly match Context Manifest")
        return self


class ReviewExperiencePlan(CommerceModel):
    context: ReviewExperienceContextPacket
    assignment: ModelAssignment
    tool_calls: tuple[ToolCallTrace, ...] = Field(min_length=2, max_length=2)


class ReviewExperienceAuditRecord(CommerceModel):
    telemetry: VerifiedCallTelemetry
    context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    tool_calls: tuple[ToolCallTrace, ...]


class ReviewExperienceAuditStore:
    def __init__(self, root: Path | None = None) -> None:
        self._root = root or _DEFAULT_AUDIT_ROOT

    def persist(self, record: ReviewExperienceAuditRecord) -> Path:
        self._root.mkdir(parents=True, exist_ok=True)
        path = self._root / f"{record.telemetry.run_id}.json"
        with path.open("x", encoding="utf-8") as file:
            json.dump(
                record.model_dump(mode="json"),
                file,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            file.write("\n")
        return path


class ReviewExperienceRun(CommerceModel):
    context: ReviewExperienceContextPacket
    result: PathResult
    telemetry: VerifiedCallTelemetry
    result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    audit_path: str = Field(min_length=1)


class ReviewReferenceScope(StrEnum):
    REVIEW_METRICS = "review_metrics"
    LATE_DELIVERY_METRICS = "late_delivery_metrics"
    VOC_EXCERPTS = "voc_excerpts"


class _ObservationCandidate(CommerceModel):
    summary: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    reference_scopes: frozenset[ReviewReferenceScope] = frozenset()
    fact_ids: tuple[FactId, ...] = ()
    metric_observation_ids: tuple[MetricObservationId, ...] = ()

    @model_validator(mode="after")
    def require_reference(self) -> Self:
        if (
            not self.reference_scopes
            and not self.fact_ids
            and not self.metric_observation_ids
        ):
            raise ValueError(
                "Review observation requires a semantic scope, Fact, or Metric "
                "reference"
            )
        return self


class _UnknownCandidate(CommerceModel):
    question: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    missing_capabilities: tuple[str, ...] = ()


class _ReviewOutput(CommerceModel):
    observations: tuple[_ObservationCandidate, ...] = Field(min_length=3)
    unknowns: tuple[_UnknownCandidate, ...] = ()
    suggested_next_paths: tuple[PathType, ...] = ()


class ReviewExperiencePathAgent:
    def __init__(
        self,
        *,
        data_service: CommerceDataService,
        audit_store: ReviewExperienceAuditStore | None = None,
    ) -> None:
        self._data = data_service
        self._audit = audit_store or ReviewExperienceAuditStore()
        self._engine = MetricEngine()
        self._spec = next(
            item
            for item in default_path_agent_specs()
            if item.path_type is PathType.REVIEW_EXPERIENCE
        )

    async def prepare(
        self,
        workspace_id: WorkspaceId,
        dataset_id: DatasetId,
        *,
        seller_id: str,
        baseline_window: MetricWindow,
        current_window: MetricWindow,
    ) -> ReviewExperiencePlan:
        context, tool_calls = self._build_context(
            workspace_id,
            dataset_id,
            seller_id=seller_id,
            baseline_window=baseline_window,
            current_window=current_window,
        )
        assignment = await ModelRouter().assign(
            ModelRouteRequest(
                role=ModelRole.PATH,
                base_profile=ModelProfile.BALANCED_TOOL_USER,
                case_severity=context.case.severity,
                capability_count=1,
                evidence_path_count=1,
                schema_complexity=OutputSchemaComplexity.HIGH,
                needs_tool_use=True,
                minimum_output_tokens=512,
            ),
            BudgetManager(context.budget),
        )
        return ReviewExperiencePlan(
            context=context,
            assignment=assignment,
            tool_calls=tool_calls,
        )

    async def run_prepared(self, plan: ReviewExperiencePlan) -> ReviewExperienceRun:
        response = await VerifiedModelCaller().call(
            assignment=plan.assignment,
            system_prompt=self._system_prompt(),
            user_prompt=(
                "Deterministic metric_query and review_signal_query outputs are "
                "embedded in this fresh ReviewExperienceContextPacket: "
                f"{plan.context.model_dump_json(exclude_none=True)}"
            ),
            versions=RealModelVersionSet(
                prompt_version=REVIEW_EXPERIENCE_PROMPT_VERSION,
                context_version=plan.context.manifest.context_version,
                router_version=plan.assignment.router_version,
                skill_version="commerce.review-experience-investigation@1.0.0",
            ),
            run_prefix="review-experience-path",
            max_output_tokens=REVIEW_EXPERIENCE_MAX_OUTPUT_TOKENS,
        )
        output = self._parse(response.text, plan.context)
        token_usage = response.telemetry.token_usage
        assert token_usage is not None
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
                    f"evd_{uuid5(NAMESPACE_URL, f'{plan.context.manifest.context_sha256}:{item.summary}').hex}"
                ),
                summary=item.summary,
                relation=EvidenceRelation.CONTEXT,
                semantic_status=SemanticStatus.DERIVED,
                confidence=item.confidence,
                fact_ids=item.fact_ids,
                metric_observation_ids=item.metric_observation_ids,
            )
            for item in output.observations
        )
        result = PathResult(
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
            tool_calls=plan.tool_calls,
            cost=PathCost(
                input_tokens=token_usage.input_tokens,
                output_tokens=token_usage.output_tokens,
                latency_ms=(
                    response.telemetry.latency_ms
                    + sum(item.latency_ms for item in plan.tool_calls)
                ),
                tool_call_count=len(plan.tool_calls),
            ),
            trace_id=TraceId.new(),
            model_assignment=plan.assignment,
            model_execution=ModelExecutionTrace(
                provider_request_id=response.telemetry.provider_request_id or "missing",
                actual_model_identity=response.telemetry.actual_model_identity or "missing",
                retry_count=response.telemetry.retry_count,
                stop_reason=response.telemetry.stop_reason or "missing",
                prompt_version=REVIEW_EXPERIENCE_PROMPT_VERSION,
                context_version=plan.context.manifest.context_version,
            ),
            skill_version="commerce.review-experience-investigation@1.0.0",
            context_sha256=plan.context.manifest.context_sha256,
        )
        result_hash = _sha256(result.model_dump(mode="json"))
        audit_path = self._audit.persist(
            ReviewExperienceAuditRecord(
                telemetry=response.telemetry,
                context_sha256=plan.context.manifest.context_sha256,
                result_sha256=result_hash,
                tool_calls=plan.tool_calls,
            )
        )
        return ReviewExperienceRun(
            context=plan.context,
            result=result,
            telemetry=response.telemetry,
            result_sha256=result_hash,
            audit_path=str(audit_path),
        )

    def _build_context(
        self,
        workspace_id: WorkspaceId,
        dataset_id: DatasetId,
        *,
        seller_id: str,
        baseline_window: MetricWindow,
        current_window: MetricWindow,
    ) -> tuple[ReviewExperienceContextPacket, tuple[ToolCallTrace, ...]]:
        if baseline_window.end > current_window.start:
            raise ValueError("Review baseline must end no later than current window")
        view = self._data.get_view(workspace_id, dataset_id)
        capability = view.capabilities.capability(CapabilityName.REVIEW_EXPERIENCE)
        if capability.status is CapabilityStatus.UNAVAILABLE:
            raise ValueError("Dataset cannot execute ReviewExperiencePathAgent")
        normalized = self._data.normalize(workspace_id, dataset_id)

        metric_request = {
            "dataset_id": str(dataset_id),
            "seller_id": seller_id,
            "baseline_window": baseline_window.model_dump(mode="json"),
            "current_window": current_window.model_dump(mode="json"),
            "metric_names": [
                MetricName.ORDER_COUNT.value,
                MetricName.AVERAGE_REVIEW_SCORE.value,
                MetricName.LOW_RATING_RATE.value,
                MetricName.LATE_DELIVERY_RATE.value,
            ],
        }
        started = time.perf_counter()
        baseline = self._engine.compute_seller_window(
            normalized,
            seller_id=seller_id,
            window=baseline_window,
        )
        current = self._engine.compute_seller_window(
            normalized,
            seller_id=seller_id,
            window=current_window,
        )
        metric_tool = ToolCallTrace(
            tool_name="metric_query",
            status=ToolCallStatus.SUCCEEDED,
            request_sha256=_sha256(metric_request),
            response_sha256=_sha256(
                {
                    "baseline": baseline.model_dump(mode="json"),
                    "current": current.model_dump(mode="json"),
                }
            ),
            latency_ms=(time.perf_counter() - started) * 1000,
        )

        signal_request = {
            "dataset_id": str(dataset_id),
            "seller_id": seller_id,
            "window": current_window.model_dump(mode="json"),
            "score_lte": 2,
            "max_excerpts": 8,
            "redaction_version": "review-redaction@1.0.0",
        }
        started = time.perf_counter()
        review_signals = _review_signals(
            normalized,
            seller_id=seller_id,
            window=current_window,
            max_excerpts=8,
        )
        signal_tool = ToolCallTrace(
            tool_name="review_signal_query",
            status=ToolCallStatus.SUCCEEDED,
            request_sha256=_sha256(signal_request),
            response_sha256=_sha256(review_signals.model_dump(mode="json")),
            latency_ms=(time.perf_counter() - started) * 1000,
        )
        context = self._context_from_tools(
            workspace_id,
            dataset_id,
            view.capabilities,
            seller_id,
            baseline,
            current,
            review_signals,
            source_manifest_sha256=_sha256(view.manifest.model_dump(mode="json")),
        )
        return context, (metric_tool, signal_tool)

    def _context_from_tools(
        self,
        workspace_id: WorkspaceId,
        dataset_id: DatasetId,
        capabilities: CapabilityProfile,
        seller_id: str,
        baseline: MetricSnapshot,
        current: MetricSnapshot,
        review_signals: ReviewSignalDigest,
        *,
        source_manifest_sha256: str,
    ) -> ReviewExperienceContextPacket:
        baseline_review = baseline.metric(MetricName.AVERAGE_REVIEW_SCORE)
        current_review = current.metric(MetricName.AVERAGE_REVIEW_SCORE)
        baseline_low = baseline.metric(MetricName.LOW_RATING_RATE)
        current_low = current.metric(MetricName.LOW_RATING_RATE)
        baseline_late = baseline.metric(MetricName.LATE_DELIVERY_RATE)
        current_late = current.metric(MetricName.LATE_DELIVERY_RATE)
        baseline_count = baseline.metric(MetricName.ORDER_COUNT)
        current_count = current.metric(MetricName.ORDER_COUNT)
        observations = (
            baseline_review,
            current_review,
            baseline_low,
            current_low,
            baseline_late,
            current_late,
        )
        if any(
            item.semantic_status is not SemanticStatus.DERIVED
            or item.value is None
            for item in observations
        ):
            raise ValueError("ReviewExperience requires known review and delivery metrics")
        metrics = ReviewMetricDigest(
            baseline_window=baseline.window,
            current_window=current.window,
            baseline_order_count=int(baseline_count.value),
            current_order_count=int(current_count.value),
            baseline_average_review_score=Decimal(str(baseline_review.value)),
            current_average_review_score=Decimal(str(current_review.value)),
            baseline_low_rating_rate=Decimal(str(baseline_low.value)),
            current_low_rating_rate=Decimal(str(current_low.value)),
            baseline_late_delivery_rate=Decimal(str(baseline_late.value)),
            current_late_delivery_rate=Decimal(str(current_late.value)),
            baseline_average_review_score_id=baseline_review.id,
            current_average_review_score_id=current_review.id,
            baseline_low_rating_rate_id=baseline_low.id,
            current_low_rating_rate_id=current_low.id,
            baseline_late_delivery_rate_id=baseline_late.id,
            current_late_delivery_rate_id=current_late.id,
        )
        review_drop = metrics.baseline_average_review_score - (
            metrics.current_average_review_score
        )
        low_increase = metrics.current_low_rating_rate - (
            metrics.baseline_low_rating_rate
        )
        severity = (
            CaseSeverity.CRITICAL
            if review_drop >= Decimal("1.20") or low_increase >= Decimal("0.40")
            else CaseSeverity.HIGH
            if review_drop >= Decimal("0.60") or low_increase >= Decimal("0.20")
            else CaseSeverity.MEDIUM
        )
        case_key = (
            f"review-experience:{dataset_id}:{seller_id}:"
            f"{baseline.window.start.isoformat()}:{current.window.end.isoformat()}"
        )
        case_id = CaseId(f"case_{uuid5(NAMESPACE_URL, case_key).hex}")
        fact_ids = tuple(
            dict.fromkeys(
                fact_id
                for item in review_signals.excerpts
                for fact_id in item.fact_ids
            )
        )
        metric_ids = tuple(item.id for item in observations)
        manifest = ContextManifest(
            context_version=REVIEW_EXPERIENCE_CONTEXT_VERSION,
            workspace_id=workspace_id,
            case_id=case_id,
            dataset_id=dataset_id,
            source_artifact_sha256=source_manifest_sha256,
            context_sha256="0" * 64,
            estimated_tokens=0,
            included_fact_ids=fact_ids,
            included_metric_observation_ids=metric_ids,
            redactions=(
                "review emails, URLs and phone-like sequences redacted",
                "review excerpts truncated to 280 characters",
                "raw order IDs replaced by SHA-256",
                "Gold evaluation labels excluded",
            ),
        )
        packet = ReviewExperienceContextPacket(
            case=CaseHeader(
                workspace_id=workspace_id,
                case_id=case_id,
                title="Review experience degradation investigation",
                severity=severity,
                status=CaseStatus.NEW,
                version=1,
            ),
            goal=(
                "Explain the observed review-score and low-rating deterioration, "
                "separate VOC allegations from verified facts, and test whether "
                "delivery lateness is supported."
            ),
            manifest=manifest,
            budget=self._spec.default_budget,
            metadata={"review_redaction_version": "review-redaction@1.0.0"},
            capability_profile=capabilities,
            seller_entity_id=current.seller_entity_id,
            seller_external_key=seller_id,
            metrics=metrics,
            review_signals=review_signals,
            allowed_tools=self._spec.allowed_tools,
            forbidden_claims=self._spec.forbidden_claims,
            output_schema=self._spec.output_schema,
        )
        estimated = estimate_context_tokens(packet)
        if estimated > packet.budget.max_tokens:
            raise ValueError("ReviewExperience context exceeds token budget")
        return packet.model_copy(
            update={
                "manifest": packet.manifest.model_copy(
                    update={
                        "estimated_tokens": estimated,
                        "context_sha256": canonical_context_sha256(packet),
                    }
                )
            }
        )

    @staticmethod
    def _system_prompt() -> str:
        return (
            "You are the Commerce ReviewExperience Path Agent. Return JSON only with "
            "no Markdown or extra keys. Compare baseline/current average review score "
            "and low-rating rate with exact values and MetricObservation IDs. Check both "
            "late-delivery rates and state directly when they remain zero, so logistics "
            "lateness is not supported as the observed rating deterioration explanation. "
            "Summarize bounded low-rating review themes using supplied Fact IDs. Treat "
            "generic/fake/pirate/authenticity wording and missing/non-receipt wording as "
            "customer allegations or VOC signals requiring verification. State that "
            "authenticity allegations remain unverified and no finding of illegality can "
            "be made; avoid repeating prohibited definitive labels even in a negated "
            "sentence. Do not convert review text into verified operational facts. Some review "
            "allegations may conflict with delivered-order records; state that boundary. "
            "Use direct observations without caused, driven, attributable, indicating, "
            "suggesting or implying language. Every observations element must choose "
            "one or more non-empty reference_scopes: review_metrics for review-score "
            "and low-rating comparisons, late_delivery_metrics for the late-rate "
            "comparison, and voc_excerpts for bounded review themes. The server maps "
            "those scopes to supplied MetricObservation IDs and review excerpt Fact ID "
            "lineage; never copy or invent opaque IDs. Include at least one bounded VOC "
            "observation using voc_excerpts. Merge evidence "
            "boundaries into cited observations; put recommendations or unsupported follow-up "
            "questions in unknowns, never in standalone observations. Do not invent GMV, CTR, CVR, ROI, "
            "ad spend, inventory, profit or uplift. Use exactly: "
            '{"observations":[{"summary":string,"confidence":number,'
            '"reference_scopes":[string]}],'
            '"unknowns":[{"question":string,"reason":string,'
            '"missing_capabilities":[string]}],'
            '"suggested_next_paths":["fulfillment"]}.'
        )

    @classmethod
    def _parse(
        cls,
        response_text: str,
        context: ReviewExperienceContextPacket,
    ) -> _ReviewOutput:
        payload = cls._decode_json(response_text)
        observations = payload.get("observations")
        if isinstance(observations, list):
            payload = {
                **payload,
                "observations": [
                    item
                    for item in observations
                    if not (
                        isinstance(item, dict)
                        and not item.get("reference_scopes")
                        and not item.get("fact_ids")
                        and not item.get("metric_observation_ids")
                    )
                ],
            }
        try:
            output = _ReviewOutput.model_validate(payload)
        except ValidationError as exc:
            signature = ";".join(
                f"{'.'.join(str(part) for part in error['loc'])}:{error['type']}"
                for error in exc.errors(
                    include_url=False,
                    include_context=False,
                    include_input=False,
                )
            )
            raise ValueError(
                "ReviewExperience output failed schema validation: "
                f"{signature}"
            ) from None
        metrics = context.metrics
        review_metric_ids = (
            metrics.baseline_average_review_score_id,
            metrics.current_average_review_score_id,
            metrics.baseline_low_rating_rate_id,
            metrics.current_low_rating_rate_id,
        )
        late_metric_ids = (
            metrics.baseline_late_delivery_rate_id,
            metrics.current_late_delivery_rate_id,
        )
        voc_fact_ids = tuple(
            dict.fromkeys(
                fact_id
                for excerpt in context.review_signals.excerpts
                for fact_id in excerpt.fact_ids
            )
        )
        normalized_observations = tuple(
            item.model_copy(
                update={
                    "fact_ids": tuple(
                        dict.fromkeys(
                            (
                                *item.fact_ids,
                                *(
                                    voc_fact_ids
                                    if ReviewReferenceScope.VOC_EXCERPTS
                                    in item.reference_scopes
                                    else ()
                                ),
                            )
                        )
                    ),
                    "metric_observation_ids": tuple(
                        dict.fromkeys(
                            (
                                *item.metric_observation_ids,
                                *(
                                    review_metric_ids
                                    if ReviewReferenceScope.REVIEW_METRICS
                                    in item.reference_scopes
                                    else ()
                                ),
                                *(
                                    late_metric_ids
                                    if ReviewReferenceScope.LATE_DELIVERY_METRICS
                                    in item.reference_scopes
                                    else ()
                                ),
                            )
                        )
                    ),
                }
            )
            for item in output.observations
        )
        output = output.model_copy(
            update={"observations": normalized_observations}
        )
        allowed_facts = frozenset(context.manifest.included_fact_ids)
        allowed_metrics = frozenset(context.manifest.included_metric_observation_ids)
        if any(
            not frozenset(item.fact_ids).issubset(allowed_facts)
            or not frozenset(item.metric_observation_ids).issubset(allowed_metrics)
            for item in output.observations
        ):
            raise ValueError("Review observation cited evidence outside context")
        rendered = " ".join(item.summary.casefold() for item in output.observations)
        if any(phrase in rendered for phrase in _ILLEGAL_OVERCLAIMS):
            raise ValueError("Review output confirmed unsupported illegal conduct")
        if any(
            unsupported_causal_phrases(item.summary)
            for item in output.observations
        ):
            raise ValueError("Review output used unsupported causal language")
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
        cited_metrics = [set(item.metric_observation_ids) for item in output.observations]
        if any(not any(pair.issubset(ids) for ids in cited_metrics) for pair in required_pairs):
            raise ValueError("Review output must compare review, low-rating and late metrics")
        late_pair = required_pairs[2]
        late_observations = tuple(
            item
            for item in output.observations
            if late_pair.issubset(set(item.metric_observation_ids))
        )
        if not any(
            "0" in item.summary or "zero" in item.summary.casefold()
            for item in late_observations
        ):
            raise ValueError("Review late-rate observation must state the zero value")
        excerpt_facts = {
            fact_id
            for item in context.review_signals.excerpts
            for fact_id in item.fact_ids
        }
        if not excerpt_facts.intersection(
            fact_id for item in output.observations for fact_id in item.fact_ids
        ):
            raise ValueError("Review output must cite scoped review excerpt Facts")
        if PathType.REVIEW_EXPERIENCE in output.suggested_next_paths:
            raise ValueError("ReviewExperience Path cannot suggest itself")
        if len(output.suggested_next_paths) != len(set(output.suggested_next_paths)):
            raise ValueError("ReviewExperience suggested Paths must be unique")
        return output

    @staticmethod
    def _decode_json(response_text: str) -> dict[str, Any]:
        text = response_text.strip()
        if text.startswith("```"):
            lines = text.splitlines()[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        start, end = text.find("{"), text.rfind("}")
        candidate = text if start < 0 or end <= start else text[start : end + 1]
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError as exc:
            repaired = re.sub(r",\s*([}\]])", r"\1", candidate)
            if repaired == candidate:
                raise ValueError(
                    "ReviewExperience response is not valid JSON"
                ) from exc
            try:
                payload = json.loads(repaired)
            except json.JSONDecodeError as repaired_exc:
                raise ValueError(
                    "ReviewExperience response is not valid JSON"
                ) from repaired_exc
        if not isinstance(payload, dict):
            raise ValueError("ReviewExperience response root must be an object")
        return payload


def _review_signals(
    normalized: NormalizedDataset,
    *,
    seller_id: str,
    window: MetricWindow,
    max_excerpts: int,
) -> ReviewSignalDigest:
    facts_by_entity: dict[EntityId, dict[str, Fact]] = {}
    for fact in normalized.facts:
        facts_by_entity.setdefault(fact.entity_id, {})[fact.name] = fact
    seller_order_ids = {
        str(facts["order_item.order_id"].value)
        for facts in facts_by_entity.values()
        if "order_item.order_id" in facts
        and "seller.id" in facts
        and str(facts["seller.id"].value) == seller_id
    }
    selected_order_ids = {
        str(facts["order.id"].value)
        for facts in facts_by_entity.values()
        if "order.id" in facts
        and "order.purchased_at" in facts
        and str(facts["order.id"].value) in seller_order_ids
        and window.start <= facts["order.purchased_at"].value < window.end
    }
    reviewed = 0
    low_rating = 0
    candidates: list[ReviewExcerptDigest] = []
    for facts in facts_by_entity.values():
        order_fact = facts.get("review.order_id")
        score_fact = facts.get("review.score")
        if (
            order_fact is None
            or score_fact is None
            or str(order_fact.value) not in selected_order_ids
        ):
            continue
        reviewed += 1
        score = int(score_fact.value)
        if score > 2:
            continue
        low_rating += 1
        text_facts = tuple(
            item
            for name in ("review.title", "review.comment")
            if (item := facts.get(name)) is not None
            and item.semantic_status is SemanticStatus.OBSERVED
            and item.value is not None
            and str(item.value).strip()
        )
        if not text_facts:
            continue
        text = _redact_review_text(
            " — ".join(str(item.value).strip() for item in text_facts)
        )
        candidates.append(
            ReviewExcerptDigest(
                order_reference_sha256=hashlib.sha256(
                    str(order_fact.value).encode("utf-8")
                ).hexdigest(),
                score=score,
                text=text,
                fact_ids=(score_fact.id, *(item.id for item in text_facts)),
            )
        )
    candidates.sort(key=lambda item: item.order_reference_sha256)
    return ReviewSignalDigest(
        reviewed_order_count=reviewed,
        low_rating_count=low_rating,
        low_rating_with_text_count=len(candidates),
        excerpts=tuple(candidates[:max_excerpts]),
    )


def _redact_review_text(value: str) -> str:
    text = re.sub(r"https?://\S+|www\.\S+", "[URL]", value, flags=re.IGNORECASE)
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[EMAIL]", text)
    text = re.sub(r"(?<!\d)\+?\d[\d\s().-]{7,}\d(?!\d)", "[PHONE]", text)
    return " ".join(text.split())[:280]


def _sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
