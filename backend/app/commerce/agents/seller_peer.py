"""Real SellerPeer Path over deterministic cohort and geography tools."""

from __future__ import annotations

import hashlib
import json
import time
from decimal import Decimal
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
    MetricObservationDigest,
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
from app.commerce.domain.enums import (
    CaseSeverity,
    CaseStatus,
    SemanticStatus,
)
from app.commerce.domain.ids import (
    CaseId,
    CohortId,
    DatasetId,
    EntityId,
    EvidenceId,
    MetricObservationId,
    TraceId,
    WorkspaceId,
)
from app.commerce.domain.models import CommerceModel, EvidenceRelation
from app.commerce.evaluation.real_model_preflight import RealModelVersionSet
from app.commerce.metrics.registry import (
    GeographicMetricSnapshot,
    MetricEngine,
    MetricObservation,
    MetricWindow,
    PeerCohortPolicy,
    PeerComparisonSnapshot,
)

SELLER_PEER_PROMPT_VERSION = "commerce.seller-peer-path@1.1.0"
SELLER_PEER_CONTEXT_VERSION = "commerce-seller-peer-path-context@1.0.0"
SELLER_PEER_MAX_OUTPUT_TOKENS = 1_800
_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_AUDIT_ROOT = (
    _REPO_ROOT / ".deer-flow" / "commerce" / "evaluation" / "path-agents"
)


class PeerComparisonDigest(CommerceModel):
    cohort_id: CohortId
    cohort_formula_version: str = Field(min_length=1)
    target_seller_id: str = Field(min_length=1)
    product_category: str = Field(min_length=1)
    seller_state: str | None = Field(default=None, min_length=1)
    window: MetricWindow
    min_orders_per_seller: int = Field(ge=2)
    single_seller_orders_only: Literal[True] = True
    pure_category_orders_only: Literal[True] = True
    match_seller_state: bool
    eligibility_uses_late_delivery_result: Literal[False] = False
    target_order_count: int = Field(ge=1)
    target_late_order_count: int = Field(ge=0)
    target_late_delivery_rate: Decimal = Field(ge=0, le=1)
    target_rate_observation_id: MetricObservationId
    peer_seller_count: int = Field(ge=1)
    peer_order_count: int = Field(ge=1)
    peer_late_order_count: int = Field(ge=0)
    peer_late_delivery_rate: Decimal = Field(ge=0, le=1)
    peer_rate_observation_id: MetricObservationId
    late_delivery_rate_gap: Decimal

    @model_validator(mode="after")
    def keep_rates_and_gap_consistent(self) -> Self:
        target = Decimal(self.target_late_order_count) / Decimal(
            self.target_order_count
        )
        peers = Decimal(self.peer_late_order_count) / Decimal(
            self.peer_order_count
        )
        if self.target_late_delivery_rate != target:
            raise ValueError("Target peer digest rate does not match counts")
        if self.peer_late_delivery_rate != peers:
            raise ValueError("Pooled peer digest rate does not match counts")
        if self.late_delivery_rate_gap != target - peers:
            raise ValueError("Peer digest gap must equal target minus peers")
        return self


class GeographicSegmentDigest(CommerceModel):
    customer_state: str = Field(min_length=1)
    order_count: int = Field(ge=1)
    metric_observation_id: MetricObservationId
    source_fact_count: int = Field(ge=1)


class GeographicDistributionDigest(CommerceModel):
    semantic_status: SemanticStatus
    total_order_count: int | None = Field(default=None, ge=0)
    segments: tuple[GeographicSegmentDigest, ...] = ()
    unknown_reason: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def keep_status_and_total_consistent(self) -> Self:
        if self.semantic_status is SemanticStatus.UNKNOWN:
            if self.segments or self.total_order_count is not None:
                raise ValueError("Unknown geography cannot carry known counts")
            if self.unknown_reason is None:
                raise ValueError("Unknown geography requires a reason")
            return self
        if not self.segments or self.total_order_count is None:
            raise ValueError("Known geography requires segments and a total")
        if sum(item.order_count for item in self.segments) != self.total_order_count:
            raise ValueError("Geographic segment counts must sum to total")
        states = tuple(item.customer_state for item in self.segments)
        if len(states) != len(set(states)):
            raise ValueError("Geographic segment states must be unique")
        return self

    def segment(self, customer_state: str) -> GeographicSegmentDigest:
        for item in self.segments:
            if item.customer_state == customer_state:
                return item
        raise KeyError(f"No geographic segment for state {customer_state}")


class SellerPeerContextPacket(ContextPacket):
    path_type: Literal[PathType.SELLER_PEER] = PathType.SELLER_PEER
    capability_profile: CapabilityProfile
    seller_entity_id: EntityId
    peer_comparison: PeerComparisonDigest
    target_rate: MetricObservationDigest
    peer_rate: MetricObservationDigest
    geography: GeographicDistributionDigest
    allowed_tools: frozenset[str] = Field(min_length=2)
    forbidden_claims: tuple[str, ...] = ()
    output_schema: str = Field(min_length=1)

    @model_validator(mode="after")
    def keep_peer_context_consistent(self) -> Self:
        if self.capability_profile.workspace_id != self.case.workspace_id:
            raise ValueError("SellerPeer Capability Workspace must match Case")
        if self.capability_profile.dataset_id != self.manifest.dataset_id:
            raise ValueError("SellerPeer Capability Dataset must match Manifest")
        capability = self.capability_profile.capability(
            CapabilityName.SELLER_PEER_COMPARISON
        )
        if capability.status is CapabilityStatus.UNAVAILABLE:
            raise ValueError("SellerPeer capability is unavailable")
        if self.target_rate.metric_observation_id != (
            self.peer_comparison.target_rate_observation_id
        ):
            raise ValueError("SellerPeer target Metric ID mismatch")
        if self.peer_rate.metric_observation_id != (
            self.peer_comparison.peer_rate_observation_id
        ):
            raise ValueError("SellerPeer pooled Metric ID mismatch")
        metric_ids = frozenset(self.manifest.included_metric_observation_ids)
        required = {
            self.target_rate.metric_observation_id,
            self.peer_rate.metric_observation_id,
            *(item.metric_observation_id for item in self.geography.segments),
        }
        if not required.issubset(metric_ids):
            raise ValueError("SellerPeer Context metrics must belong to Manifest")
        if (
            self.geography.total_order_count is not None
            and self.geography.total_order_count
            != self.peer_comparison.target_order_count
        ):
            raise ValueError("Geography total must match target comparable orders")
        return self


class SellerPeerPlan(CommerceModel):
    context: SellerPeerContextPacket
    assignment: ModelAssignment
    tool_calls: tuple[ToolCallTrace, ...] = Field(min_length=2, max_length=2)


class SellerPeerAuditRecord(CommerceModel):
    telemetry: VerifiedCallTelemetry
    context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    tool_calls: tuple[ToolCallTrace, ...]


class SellerPeerAuditStore:
    def __init__(self, root: Path | None = None) -> None:
        self._root = root or _DEFAULT_AUDIT_ROOT

    def persist(self, record: SellerPeerAuditRecord) -> Path:
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


class SellerPeerRun(CommerceModel):
    context: SellerPeerContextPacket
    result: PathResult
    telemetry: VerifiedCallTelemetry
    result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    audit_path: str = Field(min_length=1)


class _ObservationCandidate(CommerceModel):
    summary: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    metric_observation_ids: tuple[MetricObservationId, ...] = Field(min_length=1)


class _UnknownCandidate(CommerceModel):
    question: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    missing_capabilities: tuple[str, ...] = ()


class _SellerPeerOutput(CommerceModel):
    observations: tuple[_ObservationCandidate, ...] = Field(min_length=2)
    unknowns: tuple[_UnknownCandidate, ...] = ()
    suggested_next_paths: tuple[PathType, ...] = ()


class SellerPeerPathAgent:
    def __init__(
        self,
        *,
        data_service: CommerceDataService,
        audit_store: SellerPeerAuditStore | None = None,
    ) -> None:
        self._data = data_service
        self._audit = audit_store or SellerPeerAuditStore()
        self._engine = MetricEngine()
        self._spec = next(
            item
            for item in default_path_agent_specs()
            if item.path_type is PathType.SELLER_PEER
        )

    async def prepare(
        self,
        workspace_id: WorkspaceId,
        dataset_id: DatasetId,
        *,
        seller_id: str,
        window: MetricWindow,
        policy: PeerCohortPolicy,
    ) -> SellerPeerPlan:
        context, tool_calls = self._build_context(
            workspace_id,
            dataset_id,
            seller_id=seller_id,
            window=window,
            policy=policy,
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
        return SellerPeerPlan(
            context=context,
            assignment=assignment,
            tool_calls=tool_calls,
        )

    async def run_prepared(self, plan: SellerPeerPlan) -> SellerPeerRun:
        response = await VerifiedModelCaller().call(
            assignment=plan.assignment,
            system_prompt=self._system_prompt(),
            user_prompt=(
                "Deterministic peer_cohort_query and geographic_order_count_query "
                "outputs are embedded in this fresh SellerPeerContextPacket: "
                f"{plan.context.model_dump_json(exclude_none=True)}"
            ),
            versions=RealModelVersionSet(
                prompt_version=SELLER_PEER_PROMPT_VERSION,
                context_version=plan.context.manifest.context_version,
                router_version=plan.assignment.router_version,
                skill_version="commerce.seller-peer-investigation@1.0.0",
            ),
            run_prefix="seller-peer-path",
            max_output_tokens=SELLER_PEER_MAX_OUTPUT_TOKENS,
        )
        output = self._parse(response.text, plan.context)
        token_usage = response.telemetry.token_usage
        assert token_usage is not None
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
                    f"evd_{uuid5(NAMESPACE_URL, f'{plan.context.manifest.context_sha256}:{item.summary}').hex}"
                ),
                summary=item.summary,
                relation=EvidenceRelation.CONTEXT,
                semantic_status=SemanticStatus.DERIVED,
                confidence=item.confidence,
                metric_observation_ids=item.metric_observation_ids,
            )
            for item in output.observations
        )
        result = PathResult(
            path_type=PathType.SELLER_PEER,
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
                prompt_version=SELLER_PEER_PROMPT_VERSION,
                context_version=plan.context.manifest.context_version,
            ),
            skill_version="commerce.seller-peer-investigation@1.0.0",
            context_sha256=plan.context.manifest.context_sha256,
        )
        result_hash = _sha256(result.model_dump(mode="json"))
        audit_path = self._audit.persist(
            SellerPeerAuditRecord(
                telemetry=response.telemetry,
                context_sha256=plan.context.manifest.context_sha256,
                result_sha256=result_hash,
                tool_calls=plan.tool_calls,
            )
        )
        return SellerPeerRun(
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
        window: MetricWindow,
        policy: PeerCohortPolicy,
    ) -> tuple[SellerPeerContextPacket, tuple[ToolCallTrace, ...]]:
        view = self._data.get_view(workspace_id, dataset_id)
        capability = view.capabilities.capability(
            CapabilityName.SELLER_PEER_COMPARISON
        )
        if capability.status is CapabilityStatus.UNAVAILABLE:
            raise ValueError("Dataset cannot execute SellerPeerPathAgent")
        normalized = self._data.normalize(workspace_id, dataset_id)

        peer_request = {
            "dataset_id": str(dataset_id),
            "seller_id": seller_id,
            "window": window.model_dump(mode="json"),
            "policy": policy.model_dump(mode="json"),
        }
        started = time.perf_counter()
        peer = self._engine.compute_peer_comparison(
            normalized,
            seller_id=seller_id,
            window=window,
            policy=policy,
        )
        peer_tool = ToolCallTrace(
            tool_name="peer_cohort_query",
            status=ToolCallStatus.SUCCEEDED,
            request_sha256=_sha256(peer_request),
            response_sha256=_sha256(peer.model_dump(mode="json")),
            latency_ms=(time.perf_counter() - started) * 1000,
        )

        geography_request = {
            "dataset_id": str(dataset_id),
            "seller_id": seller_id,
            "window": window.model_dump(mode="json"),
        }
        started = time.perf_counter()
        geography = self._engine.compute_geographic_order_count(
            normalized,
            seller_id=seller_id,
            window=window,
        )
        geography_tool = ToolCallTrace(
            tool_name="geographic_order_count_query",
            status=ToolCallStatus.SUCCEEDED,
            request_sha256=_sha256(geography_request),
            response_sha256=_sha256(geography.model_dump(mode="json")),
            latency_ms=(time.perf_counter() - started) * 1000,
        )
        context = self._context_from_snapshots(
            workspace_id,
            dataset_id,
            view.capabilities,
            peer,
            geography,
            policy,
            source_manifest_sha256=_sha256(view.manifest.model_dump(mode="json")),
        )
        return context, (peer_tool, geography_tool)

    def _context_from_snapshots(
        self,
        workspace_id: WorkspaceId,
        dataset_id: DatasetId,
        capabilities: CapabilityProfile,
        peer: PeerComparisonSnapshot,
        geography: GeographicMetricSnapshot,
        policy: PeerCohortPolicy,
        *,
        source_manifest_sha256: str,
    ) -> SellerPeerContextPacket:
        peer_digest = PeerComparisonDigest(
            cohort_id=peer.cohort_id,
            cohort_formula_version=peer.cohort_formula_version,
            target_seller_id=peer.target_seller_id,
            product_category=peer.product_category,
            seller_state=peer.seller_state,
            window=peer.window,
            min_orders_per_seller=policy.min_orders_per_seller,
            match_seller_state=policy.match_seller_state,
            target_order_count=peer.target.eligible_order_count,
            target_late_order_count=peer.target.late_order_count,
            target_late_delivery_rate=peer.target.late_delivery_rate,
            target_rate_observation_id=peer.target_late_delivery_rate.id,
            peer_seller_count=len(peer.peers),
            peer_order_count=sum(item.eligible_order_count for item in peer.peers),
            peer_late_order_count=sum(item.late_order_count for item in peer.peers),
            peer_late_delivery_rate=Decimal(
                str(peer.peer_late_delivery_rate.value)
            ),
            peer_rate_observation_id=peer.peer_late_delivery_rate.id,
            late_delivery_rate_gap=peer.late_delivery_rate_gap,
        )
        geography_digest = GeographicDistributionDigest(
            semantic_status=geography.semantic_status,
            total_order_count=geography.total_order_count,
            segments=tuple(
                GeographicSegmentDigest(
                    customer_state=item.customer_state,
                    order_count=int(item.observation.value),
                    metric_observation_id=item.observation.id,
                    source_fact_count=len(item.observation.source_fact_ids),
                )
                for item in geography.segments
            ),
            unknown_reason=geography.unknown_reason,
        )
        metric_ids = (
            peer.target_late_delivery_rate.id,
            peer.peer_late_delivery_rate.id,
            *(item.observation.id for item in geography.segments),
        )
        case_key = (
            f"seller-peer:{dataset_id}:{peer.target_seller_id}:"
            f"{peer.window.start.isoformat()}:{peer.window.end.isoformat()}:"
            f"{peer.cohort_id}"
        )
        gap = abs(peer.late_delivery_rate_gap)
        severity = (
            CaseSeverity.CRITICAL
            if gap >= Decimal("0.30")
            else CaseSeverity.HIGH
            if gap >= Decimal("0.15")
            else CaseSeverity.MEDIUM
            if gap >= Decimal("0.05")
            else CaseSeverity.LOW
        )
        case_id = CaseId(f"case_{uuid5(NAMESPACE_URL, case_key).hex}")
        manifest = ContextManifest(
            context_version=SELLER_PEER_CONTEXT_VERSION,
            workspace_id=workspace_id,
            case_id=case_id,
            dataset_id=dataset_id,
            source_artifact_sha256=source_manifest_sha256,
            context_sha256="0" * 64,
            estimated_tokens=0,
            included_metric_observation_ids=metric_ids,
            redactions=(
                "raw peer seller rows omitted",
                "raw customer rows omitted",
                "metric.source_fact_ids replaced by source_fact_count",
                "Gold evaluation labels excluded",
            ),
        )
        packet = SellerPeerContextPacket(
            case=CaseHeader(
                workspace_id=workspace_id,
                case_id=case_id,
                title="Matched seller peer delivery-rate comparison",
                severity=severity,
                status=CaseStatus.NEW,
                version=1,
            ),
            goal=(
                "Compare the target seller with outcome-agnostic matched peers, "
                "summarize customer-state distribution, and state evidence boundaries."
            ),
            manifest=manifest,
            budget=self._spec.default_budget,
            metadata={
                "cohort_id": str(peer.cohort_id),
                "cohort_formula_version": peer.cohort_formula_version,
            },
            capability_profile=capabilities,
            seller_entity_id=peer.target.seller_entity_id,
            peer_comparison=peer_digest,
            target_rate=_metric_digest(peer.target_late_delivery_rate),
            peer_rate=_metric_digest(peer.peer_late_delivery_rate),
            geography=geography_digest,
            allowed_tools=self._spec.allowed_tools,
            forbidden_claims=self._spec.forbidden_claims,
            output_schema=self._spec.output_schema,
        )
        estimated = estimate_context_tokens(packet)
        if estimated > packet.budget.max_tokens:
            raise ValueError("SellerPeer context exceeds token budget")
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
            "You are the Commerce SellerPeer Path Agent. Return JSON only with no "
            "Markdown or extra keys. Compare the target late-delivery rate with the "
            "pooled matched-peer rate and quantify the percentage-point gap. State the "
            "target order count, peer seller count and pooled peer order count. Summarize "
            "the top customer-state counts, including SP, MG and RJ when supplied. Every "
            "observation must cite exact supplied MetricObservation IDs. Explain that "
            "cohort eligibility used time window, pure category, seller state, "
            "single-seller attribution and minimum sample—not late-delivery outcome. "
            "The peer gap is diagnostic, not causal. Use direct observations without "
            "caused, driven, attributable, indicating, suggesting or implying language. "
            "Do not create standalone policy or boundary observations with empty IDs. "
            "Merge cohort eligibility and the diagnostic-not-causal boundary into the "
            "target-versus-peer comparison observation and cite both rate IDs. "
            "Do not invent GMV, CTR, CVR, ROI, ad spend, inventory, profit or uplift. "
            "Use exactly: "
            '{"observations":[{"summary":string,"confidence":number,'
            '"metric_observation_ids":[string]}],"unknowns":[{"question":string,'
            '"reason":string,"missing_capabilities":[string]}],'
            '"suggested_next_paths":["fulfillment"|"review_experience"]}.'
        )

    @classmethod
    def _parse(
        cls,
        response_text: str,
        context: SellerPeerContextPacket,
    ) -> _SellerPeerOutput:
        payload = cls._decode_json(response_text)
        try:
            output = _SellerPeerOutput.model_validate(payload)
        except ValidationError as exc:
            raise ValueError("SellerPeer output failed schema validation") from exc
        allowed = frozenset(context.manifest.included_metric_observation_ids)
        if any(
            not frozenset(item.metric_observation_ids).issubset(allowed)
            for item in output.observations
        ):
            raise ValueError("SellerPeer observation cited a Metric outside context")
        if any(
            unsupported_causal_phrases(item.summary)
            for item in output.observations
        ):
            raise ValueError("SellerPeer observation used unsupported causal language")
        peer_ids = {
            context.peer_comparison.target_rate_observation_id,
            context.peer_comparison.peer_rate_observation_id,
        }
        if not any(
            peer_ids.issubset(set(item.metric_observation_ids))
            for item in output.observations
        ):
            raise ValueError("SellerPeer output must compare target and pooled peer rates")
        top_geography = tuple(
            sorted(
                context.geography.segments,
                key=lambda item: (-item.order_count, item.customer_state),
            )[:3]
        )
        cited = {
            metric_id
            for item in output.observations
            for metric_id in item.metric_observation_ids
        }
        if not {
            item.metric_observation_id for item in top_geography
        }.issubset(cited):
            raise ValueError("SellerPeer output must cite top geographic segments")
        if PathType.SELLER_PEER in output.suggested_next_paths:
            raise ValueError("SellerPeer Path cannot suggest itself")
        if len(output.suggested_next_paths) != len(set(output.suggested_next_paths)):
            raise ValueError("SellerPeer suggested Paths must be unique")
        return output

    @staticmethod
    def _decode_json(response_text: str) -> dict[str, Any]:
        text = response_text.strip()
        if text.startswith("```"):
            lines = text.splitlines()[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            start, end = text.find("{"), text.rfind("}")
            if start < 0 or end <= start:
                raise ValueError("SellerPeer response is not valid JSON") from None
            payload = json.loads(text[start : end + 1])
        if not isinstance(payload, dict):
            raise ValueError("SellerPeer response root must be an object")
        return payload


def _metric_digest(item: MetricObservation) -> MetricObservationDigest:
    return MetricObservationDigest(
        metric_observation_id=item.id,
        metric_name=item.metric_name,
        semantic_status=item.semantic_status,
        value=item.value,
        unit=item.unit,
        formula_version=item.formula_version,
        window_start=item.window_start,
        window_end=item.window_end,
        sample_size=item.sample_size,
        numerator=item.numerator,
        denominator=item.denominator,
        source_fact_count=len(item.source_fact_ids),
        unknown_reason=item.unknown_reason,
    )


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
