"""Fresh real-model Fulfillment Path Agent with strict structured output."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Self
from uuid import NAMESPACE_URL, uuid5

import httpx
from dotenv import load_dotenv
from langchain.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import Field, ValidationError, model_validator

from app.commerce.agents.budget import BudgetManager
from app.commerce.agents.contracts import (
    CaseAnalysisDigest,
    ContextManifest,
    LeadContextPacket,
    PathContextPacket,
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
)
from app.commerce.data.capabilities import CapabilityProfile
from app.commerce.domain.enums import SemanticStatus
from app.commerce.domain.ids import EvidenceId, MetricObservationId, TraceId
from app.commerce.domain.models import CommerceModel, EvidenceRelation
from app.commerce.evaluation.real_model_preflight import (
    DEFAULT_MODEL_ALIAS,
    EXPECTED_PROVIDER_CLASS,
    ProviderFailure,
    RealModelPreflightResult,
    RealModelVersionSet,
    TokenUsage,
    _extract_identity,
    _extract_provider_ids,
    _extract_token_usage,
    _failure_from_exception,
    _mapping,
    _model_settings_for_preflight,
    is_official_deepseek_endpoint,
    is_verified_deepseek_v4_identity,
    run_real_model_preflight,
)
from app.commerce.metrics.registry import MetricName
from deerflow.config.app_config import AppConfig
from deerflow.reflection import resolve_class

FULFILLMENT_PROMPT_VERSION = "commerce.fulfillment-path@1.0.0"
FULFILLMENT_PATH_CONTEXT_VERSION = "commerce-fulfillment-path-context@1.0.0"
FULFILLMENT_MAX_OUTPUT_TOKENS = 1_600

_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_AUDIT_ROOT = (
    _REPO_ROOT / ".deer-flow" / "commerce" / "evaluation" / "path-agents"
)
_FULFILLMENT_METRICS = frozenset(
    {
        MetricName.ORDER_COUNT.value,
        MetricName.LATE_DELIVERY_RATE.value,
        MetricName.HANDLING_TIME_HOURS.value,
        MetricName.TRANSIT_TIME_HOURS.value,
        MetricName.DELIVERY_DURATION_HOURS.value,
    }
)
_REQUIRED_COMPARISONS = frozenset(
    {
        MetricName.LATE_DELIVERY_RATE.value,
        MetricName.HANDLING_TIME_HOURS.value,
        MetricName.TRANSIT_TIME_HOURS.value,
    }
)


class PathAgentRunStatus(StrEnum):
    PASSED = "passed"
    BLOCKED = "blocked"
    PARSE_FAILED = "parse_failed"


class PathAgentTelemetry(CommerceModel):
    schema_version: str = "commerce.path-agent-telemetry@1.0.0"
    run_id: str = Field(min_length=1)
    preflight_run_id: str = Field(min_length=1)
    status: PathAgentRunStatus
    path_type: PathType
    checked_at: datetime
    model_assignment: ModelAssignment
    invocation_max_output_tokens: int = Field(ge=1)
    configured_alias: str = Field(min_length=1)
    configured_model: str = Field(min_length=1)
    provider_class: str = Field(min_length=1)
    endpoint: str = Field(min_length=1)
    actual_model_identity: str | None = Field(default=None, min_length=1)
    identity_evidence_source: str | None = Field(default=None, min_length=1)
    provider_request_id: str | None = Field(default=None, min_length=1)
    provider_request_id_source: str | None = Field(default=None, min_length=1)
    provider_response_id: str | None = Field(default=None, min_length=1)
    system_fingerprint: str | None = Field(default=None, min_length=1)
    token_usage: TokenUsage | None = None
    latency_ms: float = Field(ge=0.0)
    request_attempt_count: int = Field(ge=0)
    retry_count: int = Field(ge=0)
    configured_max_retries: int = Field(ge=0)
    stop_reason: str | None = Field(default=None, min_length=1)
    request_nonce_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    response_content_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    path_result_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    error_code: str | None = Field(default=None, min_length=1)
    error_message: str | None = Field(default=None, min_length=1)
    versions: RealModelVersionSet

    @model_validator(mode="after")
    def require_real_model_evidence_for_pass(self) -> Self:
        if self.retry_count != max(0, self.request_attempt_count - 1):
            raise ValueError("retry_count must equal request_attempt_count - 1")
        if self.model_assignment.role is not ModelRole.PATH:
            raise ValueError("Path telemetry requires a Path model assignment")
        if self.invocation_max_output_tokens > self.model_assignment.max_output_tokens:
            raise ValueError("Invocation output cap cannot exceed Model Assignment")
        if self.status is not PathAgentRunStatus.PASSED:
            if self.error_code is None or self.error_message is None:
                raise ValueError("Blocked or parse-failed Path run requires an error")
            return self
        required = {
            "actual_model_identity": self.actual_model_identity,
            "identity_evidence_source": self.identity_evidence_source,
            "provider_request_id": self.provider_request_id,
            "provider_request_id_source": self.provider_request_id_source,
            "provider_response_id": self.provider_response_id,
            "token_usage": self.token_usage,
            "stop_reason": self.stop_reason,
            "response_content_sha256": self.response_content_sha256,
            "path_result_sha256": self.path_result_sha256,
        }
        missing = [name for name, value in required.items() if value is None]
        if missing:
            raise ValueError(
                f"Passed Path Agent telemetry is missing: {', '.join(missing)}"
            )
        if self.request_attempt_count != 1 or self.retry_count != 0:
            raise ValueError("Passed Path Agent request must be one fresh no-retry call")
        if self.provider_class != EXPECTED_PROVIDER_CLASS:
            raise ValueError("Passed Path Agent requires the approved provider class")
        if not is_official_deepseek_endpoint(self.endpoint):
            raise ValueError("Passed Path Agent requires the official DeepSeek endpoint")
        if not is_verified_deepseek_v4_identity(self.actual_model_identity):
            raise ValueError("Passed Path Agent requires server-side DeepSeek V4 identity")
        if self.error_code is not None or self.error_message is not None:
            raise ValueError("Passed Path Agent telemetry cannot carry an error")
        return self


class PathAgentAuditStore:
    """Persist immutable secret-free telemetry, never Prompt or response text."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = root or _DEFAULT_AUDIT_ROOT

    def persist(self, telemetry: PathAgentTelemetry) -> Path:
        self._root.mkdir(parents=True, exist_ok=True)
        path = self._root / f"{telemetry.run_id}.json"
        with path.open("x", encoding="utf-8") as file:
            json.dump(
                telemetry.model_dump(mode="json"),
                file,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            file.write("\n")
        return path


class RealPathAgentBlockedError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        preflight: RealModelPreflightResult | None = None,
        telemetry: PathAgentTelemetry | None = None,
    ) -> None:
        super().__init__(message)
        self.preflight = preflight
        self.telemetry = telemetry


class PathAgentParseError(ValueError):
    def __init__(self, message: str, *, telemetry: PathAgentTelemetry | None = None):
        super().__init__(message)
        self.telemetry = telemetry


class FulfillmentObservationCandidate(CommerceModel):
    summary: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    metric_observation_ids: tuple[MetricObservationId, ...] = Field(min_length=1)


class FulfillmentUnknownCandidate(CommerceModel):
    question: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    missing_capabilities: tuple[str, ...] = ()


class FulfillmentModelOutput(CommerceModel):
    observations: tuple[FulfillmentObservationCandidate, ...] = Field(min_length=1)
    unknowns: tuple[FulfillmentUnknownCandidate, ...] = ()
    suggested_next_paths: tuple[PathType, ...] = ()

    @model_validator(mode="after")
    def reject_duplicate_next_paths(self) -> Self:
        if len(self.suggested_next_paths) != len(set(self.suggested_next_paths)):
            raise ValueError("suggested_next_paths must be unique")
        if PathType.FULFILLMENT in self.suggested_next_paths:
            raise ValueError("Fulfillment Path cannot suggest itself as the next Path")
        return self


class FulfillmentPathRun(CommerceModel):
    context: PathContextPacket
    result: PathResult
    telemetry: PathAgentTelemetry
    audit_path: str = Field(min_length=1)


class FulfillmentPathPlan(CommerceModel):
    context: PathContextPacket
    assignment: ModelAssignment


@dataclass(frozen=True)
class _Invocation:
    response: AIMessage | None
    model_config: Any
    endpoint: str
    request_attempt_count: int
    latency_ms: float
    failure: ProviderFailure | None = None


class FulfillmentPathAgent:
    """Analyze deterministic fulfillment metrics using one fresh DeepSeek V4 call."""

    def __init__(
        self,
        *,
        model_alias: str = DEFAULT_MODEL_ALIAS,
        audit_store: PathAgentAuditStore | None = None,
    ) -> None:
        self._model_alias = model_alias
        self._audit_store = audit_store or PathAgentAuditStore()
        self._spec = next(
            spec
            for spec in default_path_agent_specs()
            if spec.path_type is PathType.FULFILLMENT
        )

    async def run(self, lead: LeadContextPacket) -> FulfillmentPathRun:
        return await self.run_prepared(await self.prepare(lead))

    async def prepare(self, lead: LeadContextPacket) -> FulfillmentPathPlan:
        context = self._build_context(lead)
        budget = BudgetManager(context.budget)
        assignment = await ModelRouter().assign(
            ModelRouteRequest(
                role=ModelRole.PATH,
                base_profile=self._spec.default_model_profile,
                case_severity=context.case.severity,
                capability_count=len(context.required_capabilities),
                evidence_path_count=1,
                schema_complexity=OutputSchemaComplexity.HIGH,
                needs_tool_use=False,
                minimum_output_tokens=512,
            ),
            budget,
        )
        return FulfillmentPathPlan(context=context, assignment=assignment)

    async def run_prepared(
        self,
        plan: FulfillmentPathPlan,
    ) -> FulfillmentPathRun:
        context = plan.context
        assignment = plan.assignment
        preflight = await asyncio.to_thread(
            run_real_model_preflight,
            model_alias=assignment.model_alias,
        )
        if not preflight.passed:
            raise RealPathAgentBlockedError(
                f"DeepSeek V4 preflight blocked Fulfillment Path: {preflight.status.value}",
                preflight=preflight,
            )

        run_id = f"fulfillment-path-{uuid.uuid4().hex}"
        checked_at = datetime.now(UTC)
        versions = RealModelVersionSet(
            prompt_version=FULFILLMENT_PROMPT_VERSION,
            context_version=context.manifest.context_version,
            router_version=assignment.router_version,
            skill_version=f"{self._spec.skill_id}@{self._spec.skill_version}",
        )
        invocation = await asyncio.to_thread(
            self._invoke,
            context,
            assignment,
            run_id,
        )
        nonce_sha256 = hashlib.sha256(run_id.encode("utf-8")).hexdigest()
        if invocation.failure is not None or invocation.response is None:
            telemetry = self._telemetry(
                invocation=invocation,
                preflight=preflight,
                run_id=run_id,
                checked_at=checked_at,
                status=PathAgentRunStatus.BLOCKED,
                context=context,
                assignment=assignment,
                versions=versions,
                request_nonce_sha256=nonce_sha256,
                error_code=(
                    invocation.failure.error_code
                    or invocation.failure.exception_type
                    if invocation.failure is not None
                    else "model_response_missing"
                ),
                error_message=(
                    invocation.failure.message
                    if invocation.failure is not None
                    else "Model invocation returned no AIMessage"
                ),
            )
            self._audit_store.persist(telemetry)
            raise RealPathAgentBlockedError(
                telemetry.error_message or "Fulfillment Path model call failed",
                preflight=preflight,
                telemetry=telemetry,
            )

        response = invocation.response
        metadata = _mapping(response.response_metadata)
        actual_identity, identity_source = _extract_identity(metadata)
        provider_request_id, request_id_source, provider_response_id = (
            _extract_provider_ids(metadata)
        )
        token_usage = _extract_token_usage(response)
        stop_reason = (
            str(metadata["finish_reason"])
            if metadata.get("finish_reason")
            else None
        )
        fingerprint = (
            str(metadata["system_fingerprint"])
            if metadata.get("system_fingerprint")
            else None
        )
        response_text = response.text
        response_hash = hashlib.sha256(response_text.encode("utf-8")).hexdigest()
        missing = [
            name
            for name, value in (
                ("verified DeepSeek V4 identity", actual_identity),
                ("identity_evidence_source", identity_source),
                ("provider_request_id", provider_request_id),
                ("provider_request_id_source", request_id_source),
                ("provider_response_id", provider_response_id),
                ("token_usage", token_usage),
                ("stop_reason", stop_reason),
            )
            if value is None
        ]
        if not is_verified_deepseek_v4_identity(actual_identity):
            missing.insert(0, "server_model_identity_not_deepseek_v4")
        if missing:
            telemetry = self._telemetry(
                invocation=invocation,
                preflight=preflight,
                run_id=run_id,
                checked_at=checked_at,
                status=PathAgentRunStatus.BLOCKED,
                context=context,
                assignment=assignment,
                versions=versions,
                request_nonce_sha256=nonce_sha256,
                actual_model_identity=actual_identity,
                identity_evidence_source=identity_source,
                provider_request_id=provider_request_id,
                provider_request_id_source=request_id_source,
                provider_response_id=provider_response_id,
                system_fingerprint=fingerprint,
                token_usage=token_usage,
                stop_reason=stop_reason,
                response_content_sha256=response_hash,
                error_code="required_real_model_evidence_missing",
                error_message=f"Provider response omitted or failed: {', '.join(missing)}",
            )
            self._audit_store.persist(telemetry)
            raise RealPathAgentBlockedError(
                telemetry.error_message or "Fulfillment Path telemetry incomplete",
                preflight=preflight,
                telemetry=telemetry,
            )

        assert token_usage is not None
        assert provider_request_id is not None
        assert actual_identity is not None
        assert stop_reason is not None
        try:
            model_output = self._parse_output(response_text, context)
            result = self._build_result(
                model_output,
                context=context,
                assignment=assignment,
                provider_request_id=provider_request_id,
                actual_model_identity=actual_identity,
                stop_reason=stop_reason,
                token_usage=token_usage,
                latency_ms=invocation.latency_ms,
            )
        except (PathAgentParseError, ValidationError, ValueError) as exc:
            telemetry = self._telemetry(
                invocation=invocation,
                preflight=preflight,
                run_id=run_id,
                checked_at=checked_at,
                status=PathAgentRunStatus.PARSE_FAILED,
                context=context,
                assignment=assignment,
                versions=versions,
                request_nonce_sha256=nonce_sha256,
                actual_model_identity=actual_identity,
                identity_evidence_source=identity_source,
                provider_request_id=provider_request_id,
                provider_request_id_source=request_id_source,
                provider_response_id=provider_response_id,
                system_fingerprint=fingerprint,
                token_usage=token_usage,
                stop_reason=stop_reason,
                response_content_sha256=response_hash,
                error_code="fulfillment_path_structured_output_invalid",
                error_message=str(exc),
            )
            self._audit_store.persist(telemetry)
            raise PathAgentParseError(str(exc), telemetry=telemetry) from exc

        result_hash = hashlib.sha256(
            json.dumps(
                result.model_dump(mode="json"),
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        telemetry = self._telemetry(
            invocation=invocation,
            preflight=preflight,
            run_id=run_id,
            checked_at=checked_at,
            status=PathAgentRunStatus.PASSED,
            context=context,
            assignment=assignment,
            versions=versions,
            request_nonce_sha256=nonce_sha256,
            actual_model_identity=actual_identity,
            identity_evidence_source=identity_source,
            provider_request_id=provider_request_id,
            provider_request_id_source=request_id_source,
            provider_response_id=provider_response_id,
            system_fingerprint=fingerprint,
            token_usage=token_usage,
            stop_reason=stop_reason,
            response_content_sha256=response_hash,
            path_result_sha256=result_hash,
        )
        audit_path = self._audit_store.persist(telemetry)
        return FulfillmentPathRun(
            context=context,
            result=result,
            telemetry=telemetry,
            audit_path=str(audit_path),
        )

    def _build_context(self, lead: LeadContextPacket) -> PathContextPacket:
        baseline = tuple(
            item
            for item in lead.analysis.baseline_metrics
            if item.metric_name in _FULFILLMENT_METRICS
        )
        current = tuple(
            item
            for item in lead.analysis.current_metrics
            if item.metric_name in _FULFILLMENT_METRICS
        )
        anomalies = tuple(
            item
            for item in lead.analysis.anomalies
            if item.metric_name.value in _FULFILLMENT_METRICS
        )
        if not baseline or not current or not anomalies:
            raise ValueError("Fulfillment Path requires metric snapshots and anomalies")
        analysis = CaseAnalysisDigest(
            dataset_id=lead.analysis.dataset_id,
            seller_entity_id=lead.analysis.seller_entity_id,
            seller_external_key=lead.analysis.seller_external_key,
            baseline_window=lead.analysis.baseline_window,
            current_window=lead.analysis.current_window,
            baseline_metrics=baseline,
            current_metrics=current,
            anomalies=anomalies,
        )
        capability_profile = CapabilityProfile(
            dataset_id=lead.capability_profile.dataset_id,
            workspace_id=lead.capability_profile.workspace_id,
            capabilities=tuple(
                lead.capability_profile.capability(name)
                for name in self._spec.required_capabilities
            ),
        )
        metric_ids = tuple(
            item.metric_observation_id
            for item in (*analysis.baseline_metrics, *analysis.current_metrics)
        )
        metric_id_set = frozenset(metric_ids)
        evidence = tuple(
            item
            for item in lead.evidence
            if frozenset(item.metric_observation_ids) & metric_id_set
        )
        fact_ids = tuple(
            dict.fromkeys(fact_id for item in evidence for fact_id in item.fact_ids)
        )
        manifest = ContextManifest(
            context_version=FULFILLMENT_PATH_CONTEXT_VERSION,
            workspace_id=lead.case.workspace_id,
            case_id=lead.case.case_id,
            dataset_id=lead.manifest.dataset_id,
            source_artifact_sha256=lead.manifest.source_artifact_sha256,
            context_sha256="0" * 64,
            estimated_tokens=0,
            included_evidence_ids=tuple(item.evidence_id for item in evidence),
            included_fact_ids=fact_ids,
            included_metric_observation_ids=metric_ids,
            included_anomaly_ids=tuple(item.anomaly_id for item in anomalies),
            redactions=tuple(
                dict.fromkeys(
                    (
                        *lead.manifest.redactions,
                        "non-fulfillment metrics omitted from Path context",
                    )
                )
            ),
        )
        packet = PathContextPacket(
            case=lead.case,
            goal=(
                "Determine whether the observed fulfillment anomaly is localized "
                "to seller handling, carrier transit, or another observed stage."
            ),
            manifest=manifest,
            budget=self._spec.default_budget,
            metadata={"parent_context_sha256": lead.manifest.context_sha256},
            path_type=PathType.FULFILLMENT,
            required_capabilities=self._spec.required_capabilities,
            capability_profile=capability_profile,
            analysis=analysis,
            evidence=evidence,
            allowed_tools=self._spec.allowed_tools,
            forbidden_claims=self._spec.forbidden_claims,
            output_schema=self._spec.output_schema,
        )
        estimated_tokens = estimate_context_tokens(packet)
        if estimated_tokens > packet.budget.max_tokens:
            raise ValueError(
                f"Fulfillment Path context {estimated_tokens} exceeds token budget"
            )
        return packet.model_copy(
            update={
                "manifest": packet.manifest.model_copy(
                    update={
                        "estimated_tokens": estimated_tokens,
                        "context_sha256": canonical_context_sha256(packet),
                    }
                )
            }
        )

    def _invoke(
        self,
        context: PathContextPacket,
        assignment: ModelAssignment,
        run_id: str,
    ) -> _Invocation:
        config_path = AppConfig.resolve_config_path()
        load_dotenv(config_path.parent / ".env", override=False)
        load_dotenv(_REPO_ROOT / ".env", override=False)
        config = AppConfig.from_file(str(config_path))
        model_config = config.get_model_config(assignment.model_alias)
        if model_config is None:
            failure = ProviderFailure(
                exception_type="ModelConfigurationError",
                error_code="configured_model_alias_missing",
                message=f"Configured model alias is missing: {assignment.model_alias}",
            )
            return _Invocation(None, assignment, "<missing>", 0, 0.0, failure)
        endpoint = str(model_config.api_base or "")
        if (
            model_config.use != EXPECTED_PROVIDER_CLASS
            or not is_official_deepseek_endpoint(endpoint)
        ):
            failure = ProviderFailure(
                exception_type="ModelConfigurationError",
                error_code="untrusted_provider_configuration",
                message="Fulfillment Path provider configuration is not trusted",
            )
            return _Invocation(None, model_config, endpoint, 0, 0.0, failure)

        request_attempt_count = 0

        def count_request(_: httpx.Request) -> None:
            nonlocal request_attempt_count
            request_attempt_count += 1

        http_client = httpx.Client(event_hooks={"request": [count_request]})
        started = time.perf_counter()
        try:
            model_class = resolve_class(model_config.use, BaseChatModel)
            settings = _model_settings_for_preflight(
                model_config,
                http_client=http_client,
                max_output_tokens=min(
                    assignment.max_output_tokens,
                    FULFILLMENT_MAX_OUTPUT_TOKENS,
                ),
            )
            settings["timeout"] = min(
                float(settings["timeout"]),
                assignment.timeout_seconds,
            )
            model = model_class(**settings)
            response = model.invoke(
                [
                    SystemMessage(content=self._system_prompt()),
                    HumanMessage(content=self._user_prompt(context, run_id)),
                ]
            )
            if not isinstance(response, AIMessage):
                raise TypeError(
                    f"Expected AIMessage, received {type(response).__name__}"
                )
            return _Invocation(
                response=response,
                model_config=model_config,
                endpoint=endpoint,
                request_attempt_count=request_attempt_count,
                latency_ms=(time.perf_counter() - started) * 1000,
            )
        except Exception as exc:
            failure = _failure_from_exception(
                exc,
                api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            )
            return _Invocation(
                response=None,
                model_config=model_config,
                endpoint=endpoint,
                request_attempt_count=request_attempt_count,
                latency_ms=(time.perf_counter() - started) * 1000,
                failure=failure,
            )
        finally:
            http_client.close()

    @staticmethod
    def _system_prompt() -> str:
        return (
            "You are FulfillmentPathAgent. Analyze only the deterministic metric "
            "digests in the supplied PathContextPacket. Return JSON only, with no "
            "Markdown and no extra keys. Do not calculate or invent metrics, GMV, "
            "CTR, CVR, ROI, ad spend, inventory, profit, or causal uplift. Treat "
            "correlation as diagnostic, never causal. Every observation must cite "
            "only supplied metric_observation_ids. Produce separate English "
            "observations for late_delivery_rate, handling_time_hours, and "
            "transit_time_hours, comparing baseline with current. If handling time "
            "is lower, explicitly say it decreased and did not worsen. If transit "
            "time is higher, explicitly say it increased or worsened. "
            "Use exactly this schema: "
            '{"observations":[{"summary":string,"confidence":number,'
            '"metric_observation_ids":[string]}],"unknowns":['
            '{"question":string,"reason":string,"missing_capabilities":[string]}],'
            '"suggested_next_paths":["seller_peer"|"review_experience"]}.'
        )

    @staticmethod
    def _user_prompt(context: PathContextPacket, run_id: str) -> str:
        return (
            f"Fresh request nonce: {run_id}. PathContextPacket: "
            f"{context.model_dump_json(exclude_none=True)}"
        )

    @classmethod
    def _parse_output(
        cls,
        response_text: str,
        context: PathContextPacket,
    ) -> FulfillmentModelOutput:
        payload = cls._decode_json(response_text)
        try:
            output = FulfillmentModelOutput.model_validate(payload)
        except ValidationError as exc:
            raise PathAgentParseError(
                "Fulfillment response failed structured schema validation"
            ) from exc
        allowed_ids = frozenset(context.manifest.included_metric_observation_ids)
        for observation in output.observations:
            if not frozenset(observation.metric_observation_ids).issubset(allowed_ids):
                raise PathAgentParseError(
                    "Fulfillment observation referenced a Metric outside Path context"
                )
        baseline = {
            item.metric_name: item.metric_observation_id
            for item in context.analysis.baseline_metrics
        }
        current = {
            item.metric_name: item.metric_observation_id
            for item in context.analysis.current_metrics
        }
        missing_comparisons = []
        for metric_name in sorted(_REQUIRED_COMPARISONS):
            pair = {baseline[metric_name], current[metric_name]}
            if not any(
                pair.issubset(set(item.metric_observation_ids))
                for item in output.observations
            ):
                missing_comparisons.append(metric_name)
        if missing_comparisons:
            raise PathAgentParseError(
                "Fulfillment response omitted required comparisons: "
                f"{', '.join(missing_comparisons)}"
            )
        return output

    @staticmethod
    def _decode_json(response_text: str) -> dict[str, Any]:
        text = response_text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start < 0 or end <= start:
                raise PathAgentParseError(
                    "Fulfillment response is not valid JSON"
                ) from None
            try:
                payload = json.loads(text[start : end + 1])
            except json.JSONDecodeError as exc:
                raise PathAgentParseError(
                    "Fulfillment response is not valid JSON"
                ) from exc
        if not isinstance(payload, dict):
            raise PathAgentParseError("Fulfillment response root must be an object")
        return payload

    def _build_result(
        self,
        output: FulfillmentModelOutput,
        *,
        context: PathContextPacket,
        assignment: ModelAssignment,
        provider_request_id: str,
        actual_model_identity: str,
        stop_reason: str,
        token_usage: TokenUsage,
        latency_ms: float,
    ) -> PathResult:
        observations = tuple(
            PathObservation(
                summary=item.summary,
                semantic_status=SemanticStatus.DERIVED,
                confidence=item.confidence,
                metric_observation_ids=item.metric_observation_ids,
            )
            for item in output.observations
        )
        evidence = tuple(
            PathEvidenceItem(
                evidence_id=EvidenceId(
                    f"evd_{uuid5(NAMESPACE_URL, f'{context.manifest.context_sha256}:{index}:{item.summary}').hex}"
                ),
                summary=item.summary,
                relation=EvidenceRelation.CONTEXT,
                semantic_status=SemanticStatus.DERIVED,
                confidence=item.confidence,
                metric_observation_ids=item.metric_observation_ids,
            )
            for index, item in enumerate(output.observations)
        )
        return PathResult(
            path_type=PathType.FULFILLMENT,
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
            tool_calls=(),
            cost=PathCost(
                input_tokens=token_usage.input_tokens,
                output_tokens=token_usage.output_tokens,
                latency_ms=latency_ms,
                tool_call_count=0,
            ),
            trace_id=TraceId.new(),
            model_assignment=assignment,
            model_execution=ModelExecutionTrace(
                provider_request_id=provider_request_id,
                actual_model_identity=actual_model_identity,
                retry_count=0,
                stop_reason=stop_reason,
                prompt_version=FULFILLMENT_PROMPT_VERSION,
                context_version=context.manifest.context_version,
            ),
            skill_version=f"{self._spec.skill_id}@{self._spec.skill_version}",
            context_sha256=context.manifest.context_sha256,
        )

    @staticmethod
    def _telemetry(
        *,
        invocation: _Invocation,
        preflight: RealModelPreflightResult,
        run_id: str,
        checked_at: datetime,
        status: PathAgentRunStatus,
        context: PathContextPacket,
        assignment: ModelAssignment,
        versions: RealModelVersionSet,
        request_nonce_sha256: str,
        **values: Any,
    ) -> PathAgentTelemetry:
        model_config = invocation.model_config
        return PathAgentTelemetry(
            run_id=run_id,
            preflight_run_id=preflight.run_id,
            status=status,
            path_type=PathType.FULFILLMENT,
            checked_at=checked_at,
            model_assignment=assignment,
            invocation_max_output_tokens=min(
                assignment.max_output_tokens,
                FULFILLMENT_MAX_OUTPUT_TOKENS,
            ),
            configured_alias=str(getattr(model_config, "name", DEFAULT_MODEL_ALIAS)),
            configured_model=str(getattr(model_config, "model", "<missing>")),
            provider_class=str(getattr(model_config, "use", "<missing>")),
            endpoint=invocation.endpoint,
            latency_ms=invocation.latency_ms,
            request_attempt_count=invocation.request_attempt_count,
            retry_count=max(0, invocation.request_attempt_count - 1),
            configured_max_retries=0,
            request_nonce_sha256=request_nonce_sha256,
            context_sha256=context.manifest.context_sha256,
            versions=versions,
            **values,
        )
