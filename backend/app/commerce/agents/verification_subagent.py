"""Fresh-context Commerce verification through the DeerFlow Subagent Harness."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
from pathlib import Path

from pydantic import Field

from app.commerce.agents.budget import BudgetManager
from app.commerce.agents.contracts import (
    AgentBudgetLimit,
    CaseAnalysisDigest,
    ContextManifest,
    LeadContextPacket,
    ModelProfile,
    VerificationPacket,
    canonical_context_sha256,
    estimate_context_tokens,
)
from app.commerce.agents.lead import PersistedLeadContextPacket
from app.commerce.agents.model_router import (
    ModelAssignment,
    ModelRole,
    ModelRouter,
    ModelRouteRequest,
    OutputSchemaComplexity,
)
from app.commerce.agents.subagent_adapter import extract_runtime_telemetry
from app.commerce.agents.verification import (
    ClaimVerdict,
    ClaimVerification,
    VerificationEngine,
    VerificationResult,
    build_verification_claim_inputs,
    verification_max_output_tokens,
)
from app.commerce.domain.ids import AgentTaskId, EvidenceId, RunId, TraceId
from app.commerce.domain.models import CommerceModel
from app.commerce.evaluation.real_model_preflight import (
    TokenUsage,
    run_real_model_preflight,
)

FRESH_VERIFICATION_CONTEXT_VERSION = "commerce-fresh-verification-context@1.1.0"
FRESH_VERIFICATION_PROMPT_VERSION = "commerce.fresh-verification-subagent@1.4.0"
FRESH_VERIFICATION_SKILL_ID = "commerce.claim-verification"
FRESH_VERIFICATION_SKILL_VERSION = "1.0.0"
_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_AUDIT_ROOT = (
    _REPO_ROOT
    / ".deer-flow"
    / "commerce"
    / "evaluation"
    / "verification-subagent"
)


class FreshVerificationContextError(ValueError):
    """Raised when persisted Evidence cannot produce a reproducible packet."""


class FreshVerificationSubagentBlockedError(RuntimeError):
    """Raised when the real-model or Harness gate cannot prove verification."""


class FreshVerificationPlan(CommerceModel):
    context: VerificationPacket
    assignment: ModelAssignment


class FreshVerificationSubagentRun(CommerceModel):
    task_id: AgentTaskId
    assignment: ModelAssignment
    context: VerificationPacket
    result: VerificationResult
    actual_model_identity: str = Field(min_length=1)
    provider_request_id: str = Field(min_length=1)
    token_usage: TokenUsage
    latency_ms: float = Field(ge=0)
    retry_count: int = Field(default=0, ge=0)
    stop_reason: str = Field(min_length=1)
    preflight_run_id: str = Field(min_length=1)
    result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    audit_path: str = Field(min_length=1)


class FreshVerificationAuditStore:
    def __init__(self, root: Path | None = None) -> None:
        self._root = root or _DEFAULT_AUDIT_ROOT

    def persist(self, run: FreshVerificationSubagentRun) -> Path:
        self._root.mkdir(parents=True, exist_ok=True)
        path = self._root / f"{run.task_id}.json"
        with path.open("x", encoding="utf-8") as file:
            json.dump(
                run.model_dump(mode="json", exclude={"audit_path"}),
                file,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            file.write("\n")
        return path


def build_fresh_verification_packet(
    *,
    base: LeadContextPacket,
    persisted: PersistedLeadContextPacket,
    claims: tuple[str, ...],
    claim_evidence_ids: tuple[tuple[EvidenceId, ...], ...],
) -> VerificationPacket:
    """Rebuild Verifier input from persisted Evidence and deterministic metrics."""

    if not claims:
        raise FreshVerificationContextError("Fresh Verification requires claims")
    if base.case != persisted.case:
        raise FreshVerificationContextError(
            "Base and persisted Lead contexts must describe the same Case version"
        )
    if base.manifest.dataset_id != persisted.manifest.dataset_id:
        raise FreshVerificationContextError(
            "Base and persisted Lead contexts must describe the same Dataset"
        )

    referenced_metric_ids = tuple(
        dict.fromkeys(
            metric_id
            for evidence in persisted.evidence
            for metric_id in evidence.metric_observation_ids
        )
    )
    referenced_fact_ids = tuple(
        dict.fromkeys(
            fact_id
            for evidence in persisted.evidence
            for fact_id in evidence.fact_ids
        )
    )
    available_metrics = {
        item.metric_observation_id: item
        for item in (
            *base.analysis.baseline_metrics,
            *base.analysis.current_metrics,
            *base.analysis.supplemental_metrics,
        )
    }
    missing_metrics = set(referenced_metric_ids) - set(available_metrics)
    if missing_metrics:
        raise FreshVerificationContextError(
            "Persisted Evidence metrics cannot be reconstructed from the base "
            "deterministic analysis: "
            + ", ".join(sorted(str(value) for value in missing_metrics))
        )
    baseline_metrics = tuple(
        item
        for item in base.analysis.baseline_metrics
        if item.metric_observation_id in referenced_metric_ids
    )
    current_metrics = tuple(
        item
        for item in base.analysis.current_metrics
        if item.metric_observation_id in referenced_metric_ids
    )
    supplemental_metrics = tuple(
        item
        for item in base.analysis.supplemental_metrics
        if item.metric_observation_id in referenced_metric_ids
    )
    if (
        not baseline_metrics
        and not current_metrics
        and not supplemental_metrics
        and not referenced_fact_ids
    ):
        raise FreshVerificationContextError(
            "Fresh Verification requires referenced persisted Facts or deterministic "
            "Metrics"
        )
    selected_metric_ids = set(referenced_metric_ids)
    analysis = CaseAnalysisDigest(
        dataset_id=base.analysis.dataset_id,
        seller_entity_id=base.analysis.seller_entity_id,
        seller_external_key=base.analysis.seller_external_key,
        baseline_window=base.analysis.baseline_window,
        current_window=base.analysis.current_window,
        baseline_metrics=baseline_metrics,
        current_metrics=current_metrics,
        supplemental_metrics=supplemental_metrics,
        anomalies=tuple(
            item
            for item in base.analysis.anomalies
            if item.anomaly_id in persisted.manifest.included_anomaly_ids
            and item.baseline_observation_id in selected_metric_ids
            and item.current_observation_id in selected_metric_ids
        ),
        trigger=base.analysis.trigger,
    )
    manifest = ContextManifest(
        context_version=FRESH_VERIFICATION_CONTEXT_VERSION,
        workspace_id=base.case.workspace_id,
        case_id=base.case.case_id,
        dataset_id=base.manifest.dataset_id,
        source_artifact_sha256=base.manifest.source_artifact_sha256,
        context_sha256="0" * 64,
        estimated_tokens=0,
        included_evidence_ids=tuple(
            item.evidence_id for item in persisted.evidence
        ),
        included_fact_ids=referenced_fact_ids,
        included_metric_observation_ids=referenced_metric_ids,
        included_anomaly_ids=tuple(item.anomaly_id for item in analysis.anomalies),
        redactions=tuple(
            dict.fromkeys(
                (
                    *persisted.manifest.redactions,
                    "Lead reasoning history excluded",
                    "Unpersisted intermediate messages excluded",
                )
            )
        ),
    )
    boundaries = tuple(
        f"{item.name.value}: {item.status.value}; missing_required="
        f"{','.join(sorted(value.value for value in item.missing_required_fields)) or 'none'}"
        for item in base.capability_profile.capabilities
    )
    packet = VerificationPacket(
        case=base.case,
        goal="Verify every proposed claim against fresh persisted Evidence and deterministic metrics.",
        manifest=manifest,
        budget=AgentBudgetLimit(
            max_iterations=2,
            max_tool_calls=0,
            max_path_agents=0,
            max_tokens=8_000,
            max_wall_time_seconds=180,
            max_model_escalations=0,
            max_repeated_actions=1,
        ),
        metadata={
            "base_context_sha256": base.manifest.context_sha256,
            "persisted_lead_context_sha256": persisted.manifest.context_sha256,
        },
        claims=build_verification_claim_inputs(
            claims=claims,
            claim_evidence_ids=claim_evidence_ids,
            evidence=persisted.evidence,
        ),
        capability_profile=base.capability_profile,
        analysis=analysis,
        evidence=persisted.evidence,
        capability_boundaries=boundaries,
        policy_constraints=(
            "Correlation is diagnostic and does not prove causality.",
            "Reject claims whose cited Evidence or Metric is absent from this packet.",
            "Review text is an unverified experience signal and cannot confirm fraud, counterfeiting, or illegality.",
            "Do not invent GMV, CTR, CVR, ROI, ad spend, inventory, profit, or uplift.",
        ),
    )
    estimated = estimate_context_tokens(packet)
    if estimated > packet.budget.max_tokens:
        raise FreshVerificationContextError(
            "Fresh Verification context exceeds token budget"
        )
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


class FreshVerificationSubagent:
    """Execute independent claim verification as a real DeerFlow Subagent."""

    def __init__(
        self,
        *,
        audit_store: FreshVerificationAuditStore | None = None,
    ) -> None:
        self._audit = audit_store or FreshVerificationAuditStore()

    async def prepare(
        self,
        packet: VerificationPacket,
        *,
        budget: BudgetManager,
    ) -> FreshVerificationPlan:
        assignment = await ModelRouter().assign(
            ModelRouteRequest(
                role=ModelRole.VERIFIER,
                base_profile=ModelProfile.BALANCED_TOOL_USER,
                case_severity=packet.case.severity,
                capability_count=len(packet.capability_profile.capabilities),
                evidence_path_count=min(3, max(1, len(packet.evidence))),
                schema_complexity=OutputSchemaComplexity.HIGH,
                minimum_output_tokens=512,
            ),
            budget,
        )
        return FreshVerificationPlan(context=packet, assignment=assignment)

    async def run(
        self,
        plan: FreshVerificationPlan,
        *,
        run_id: RunId,
        task_id: AgentTaskId,
        trace_id: TraceId,
    ) -> FreshVerificationSubagentRun:
        preflight = await asyncio.to_thread(
            run_real_model_preflight,
            model_alias=plan.assignment.model_alias,
        )
        if not preflight.passed:
            raise FreshVerificationSubagentBlockedError(
                f"Fresh Verification preflight blocked: {preflight.status.value}"
            )
        __import__("deerflow.agents")
        from deerflow.subagents.config import SubagentConfig
        from deerflow.subagents.executor import SubagentExecutor

        config = SubagentConfig(
            name="commerce-fresh-verification",
            description="Independent persisted-Evidence claim verification",
            system_prompt=VerificationEngine._system_prompt(),
            tools=[],
            disallowed_tools=["task"],
            skills=[],
            model=plan.assignment.model_alias,
            max_turns=2,
            timeout_seconds=max(
                1,
                math.ceil(
                    min(
                        plan.context.budget.max_wall_time_seconds,
                        plan.assignment.timeout_seconds,
                    )
                ),
            ),
            max_output_tokens=min(
                verification_max_output_tokens(len(plan.context.claims)),
                plan.assignment.max_output_tokens,
            ),
            model_max_retries=0,
            llm_retry_max_attempts=1,
        )
        executor = SubagentExecutor(
            config=config,
            tools=[],
            app_config=None,
            parent_model=None,
            sandbox_state=None,
            thread_data=None,
            thread_id=str(run_id),
            trace_id=str(trace_id),
        )
        harness_result = await asyncio.to_thread(
            executor.execute,
            "Return only the required verification JSON for this fresh packet: "
            + plan.context.model_dump_json(exclude_none=True),
        )
        status = str(getattr(harness_result.status, "value", harness_result.status))
        if status != "completed" or not harness_result.result:
            raise FreshVerificationSubagentBlockedError(
                "DeerFlow Verification Subagent did not complete: "
                + (harness_result.error or status)
            )
        runtime = extract_runtime_telemetry(
            harness_result,
            caller="Fresh Verification Subagent",
        )
        candidates = VerificationEngine._parse(
            harness_result.result,
            plan.context,
        )
        claims = tuple(
            ClaimVerification(
                claim_index=item.claim_index,
                claim=plan.context.claims[item.claim_index].statement,
                verdict=item.verdict,
                issue_codes=item.issue_codes,
                reason=item.reason,
                evidence_ids=item.evidence_ids,
                fact_ids=item.fact_ids,
                metric_observation_ids=item.metric_observation_ids,
            )
            for item in candidates
        )
        overall = (
            ClaimVerdict.REJECT
            if any(item.verdict is ClaimVerdict.REJECT for item in claims)
            else ClaimVerdict.REPAIR
            if any(item.verdict is ClaimVerdict.REPAIR for item in claims)
            else ClaimVerdict.PASS
        )
        result = VerificationResult(
            overall_verdict=overall,
            claims=claims,
            context_sha256=plan.context.manifest.context_sha256,
        )
        result_sha256 = hashlib.sha256(
            json.dumps(
                result.model_dump(mode="json"),
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        provisional = FreshVerificationSubagentRun(
            task_id=task_id,
            assignment=plan.assignment,
            context=plan.context,
            result=result,
            actual_model_identity=runtime.actual_model_identity,
            provider_request_id=runtime.provider_request_id,
            token_usage=runtime.token_usage,
            latency_ms=runtime.latency_ms,
            retry_count=0,
            stop_reason=runtime.stop_reason,
            preflight_run_id=preflight.run_id,
            result_sha256=result_sha256,
            audit_path="pending",
        )
        audit_path = self._audit.persist(provisional)
        return provisional.model_copy(update={"audit_path": str(audit_path)})
