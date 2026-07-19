"""Fresh-context claim verification using one real DeepSeek V4 request."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from pathlib import Path
from typing import Any, Self

from pydantic import Field, ValidationError, model_validator

from app.commerce.agents.budget import BudgetManager
from app.commerce.agents.claim_policy import unsupported_causal_phrases
from app.commerce.agents.contracts import (
    AgentBudgetLimit,
    ContextManifest,
    LeadContextPacket,
    ModelProfile,
    VerificationPacket,
    canonical_context_sha256,
    estimate_context_tokens,
)
from app.commerce.agents.model_router import (
    ModelAssignment,
    ModelRole,
    ModelRouter,
    ModelRouteRequest,
    OutputSchemaComplexity,
)
from app.commerce.agents.verified_call import (
    VerifiedCallStatus,
    VerifiedCallTelemetry,
    VerifiedModelCaller,
)
from app.commerce.domain.ids import MetricObservationId
from app.commerce.domain.models import CommerceModel
from app.commerce.evaluation.real_model_preflight import RealModelVersionSet

VERIFICATION_PROMPT_VERSION = "commerce.verification@1.1.0"
VERIFICATION_CONTEXT_VERSION = "commerce-verification-context@1.0.0"
VERIFICATION_MAX_OUTPUT_TOKENS = 1_600
_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_AUDIT_ROOT = (
    _REPO_ROOT / ".deer-flow" / "commerce" / "evaluation" / "verification"
)

VerificationRunStatus = VerifiedCallStatus


class ClaimVerdict(StrEnum):
    PASS = "pass"
    REJECT = "reject"
    REPAIR = "repair"


class VerificationIssueCode(StrEnum):
    METRIC_CONTRADICTION = "metric_contradiction"
    UNSUPPORTED_CAUSAL_LANGUAGE = "unsupported_causal_language"
    MISSING_EVIDENCE = "missing_evidence"
    CAPABILITY_OVERCLAIM = "capability_overclaim"
    POLICY_VIOLATION = "policy_violation"


class ClaimVerification(CommerceModel):
    claim_index: int = Field(ge=0)
    claim: str = Field(min_length=1)
    verdict: ClaimVerdict
    issue_codes: frozenset[VerificationIssueCode] = frozenset()
    reason: str = Field(min_length=1)
    metric_observation_ids: tuple[MetricObservationId, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def require_issue_for_non_pass(self) -> Self:
        if self.verdict is ClaimVerdict.PASS and self.issue_codes:
            raise ValueError("Passing claim cannot carry issue codes")
        if self.verdict is not ClaimVerdict.PASS and not self.issue_codes:
            raise ValueError("Rejected or repairable claim requires issue codes")
        return self


class VerificationResult(CommerceModel):
    schema_version: str = "commerce.verification-result@1.0.0"
    overall_verdict: ClaimVerdict
    claims: tuple[ClaimVerification, ...] = Field(min_length=1)
    context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def derive_overall_verdict(self) -> Self:
        expected = (
            ClaimVerdict.REJECT
            if any(item.verdict is ClaimVerdict.REJECT for item in self.claims)
            else ClaimVerdict.REPAIR
            if any(item.verdict is ClaimVerdict.REPAIR for item in self.claims)
            else ClaimVerdict.PASS
        )
        if self.overall_verdict is not expected:
            raise ValueError("Overall verdict must match per-claim verdicts")
        return self


class VerificationAuditRecord(CommerceModel):
    telemetry: VerifiedCallTelemetry
    context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class VerificationAuditStore:
    def __init__(self, root: Path | None = None) -> None:
        self._root = root or _DEFAULT_AUDIT_ROOT

    def persist(self, record: VerificationAuditRecord) -> Path:
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


class VerificationRun(CommerceModel):
    assignment: ModelAssignment
    context: VerificationPacket
    result: VerificationResult
    telemetry: VerifiedCallTelemetry
    result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    audit_path: str = Field(min_length=1)


class VerificationPlan(CommerceModel):
    context: VerificationPacket
    assignment: ModelAssignment


class _ClaimCandidate(CommerceModel):
    claim_index: int = Field(ge=0)
    verdict: ClaimVerdict
    issue_codes: frozenset[VerificationIssueCode] = frozenset()
    reason: str = Field(min_length=1)
    metric_observation_ids: tuple[MetricObservationId, ...] = Field(min_length=1)


class _VerificationOutput(CommerceModel):
    claims: tuple[_ClaimCandidate, ...] = Field(min_length=1)


class VerificationEngine:
    def __init__(
        self,
        *,
        audit_store: VerificationAuditStore | None = None,
    ) -> None:
        self._audit = audit_store or VerificationAuditStore()

    async def prepare(
        self,
        lead: LeadContextPacket,
        *,
        claims: tuple[str, ...],
        budget: BudgetManager | None = None,
    ) -> VerificationPlan:
        context = self._build_context(lead, claims)
        assignment = await ModelRouter().assign(
            ModelRouteRequest(
                role=ModelRole.VERIFIER,
                base_profile=ModelProfile.BALANCED_TOOL_USER,
                case_severity=context.case.severity,
                capability_count=len(context.capability_profile.capabilities),
                evidence_path_count=1,
                schema_complexity=OutputSchemaComplexity.HIGH,
                minimum_output_tokens=512,
            ),
            budget or BudgetManager(context.budget),
        )
        return VerificationPlan(context=context, assignment=assignment)

    async def verify(
        self,
        lead: LeadContextPacket,
        *,
        claims: tuple[str, ...],
    ) -> VerificationRun:
        return await self.run_prepared(await self.prepare(lead, claims=claims))

    async def run_prepared(self, plan: VerificationPlan) -> VerificationRun:
        context = plan.context
        assignment = plan.assignment
        versions = RealModelVersionSet(
            prompt_version=VERIFICATION_PROMPT_VERSION,
            context_version=context.manifest.context_version,
            router_version=assignment.router_version,
            skill_version="commerce.claim-verification@1.0.0",
        )
        response = await VerifiedModelCaller().call(
            assignment=assignment,
            system_prompt=self._system_prompt(),
            user_prompt=(
                "Fresh VerificationPacket with no Lead reasoning history: "
                f"{context.model_dump_json(exclude_none=True)}"
            ),
            versions=versions,
            run_prefix="verification",
            max_output_tokens=VERIFICATION_MAX_OUTPUT_TOKENS,
        )
        candidates = self._parse(response.text, context)
        verified = tuple(
            ClaimVerification(
                claim_index=item.claim_index,
                claim=context.claims[item.claim_index],
                verdict=item.verdict,
                issue_codes=item.issue_codes,
                reason=item.reason,
                metric_observation_ids=item.metric_observation_ids,
            )
            for item in candidates
        )
        overall = (
            ClaimVerdict.REJECT
            if any(item.verdict is ClaimVerdict.REJECT for item in verified)
            else ClaimVerdict.REPAIR
            if any(item.verdict is ClaimVerdict.REPAIR for item in verified)
            else ClaimVerdict.PASS
        )
        result = VerificationResult(
            overall_verdict=overall,
            claims=verified,
            context_sha256=context.manifest.context_sha256,
        )
        result_hash = hashlib.sha256(
            json.dumps(
                result.model_dump(mode="json"),
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
        ).hexdigest()
        record = VerificationAuditRecord(
            telemetry=response.telemetry,
            context_sha256=context.manifest.context_sha256,
            result_sha256=result_hash,
        )
        audit_path = self._audit.persist(record)
        return VerificationRun(
            assignment=assignment,
            context=context,
            result=result,
            telemetry=response.telemetry,
            result_sha256=result_hash,
            audit_path=str(audit_path),
        )

    @staticmethod
    def _build_context(
        lead: LeadContextPacket,
        claims: tuple[str, ...],
    ) -> VerificationPacket:
        manifest = ContextManifest(
            context_version=VERIFICATION_CONTEXT_VERSION,
            workspace_id=lead.case.workspace_id,
            case_id=lead.case.case_id,
            dataset_id=lead.manifest.dataset_id,
            source_artifact_sha256=lead.manifest.source_artifact_sha256,
            context_sha256="0" * 64,
            estimated_tokens=0,
            included_evidence_ids=lead.manifest.included_evidence_ids,
            included_fact_ids=lead.manifest.included_fact_ids,
            included_metric_observation_ids=(
                lead.manifest.included_metric_observation_ids
            ),
            included_anomaly_ids=lead.manifest.included_anomaly_ids,
            redactions=tuple(
                dict.fromkeys(
                    (*lead.manifest.redactions, "Lead reasoning history excluded")
                )
            ),
        )
        boundaries = tuple(
            f"{item.name.value}: {item.status.value}; missing_required="
            f"{','.join(sorted(value.value for value in item.missing_required_fields)) or 'none'}"
            for item in lead.capability_profile.capabilities
        )
        packet = VerificationPacket(
            case=lead.case,
            goal="Verify every proposed claim against fresh deterministic context.",
            manifest=manifest,
            budget=AgentBudgetLimit(
                max_iterations=2,
                max_tool_calls=0,
                max_path_agents=0,
                max_tokens=8_000,
                max_wall_time_seconds=180,
                max_model_escalations=0,
            ),
            metadata={"parent_context_sha256": lead.manifest.context_sha256},
            claims=claims,
            capability_profile=lead.capability_profile,
            analysis=lead.analysis,
            evidence=lead.evidence,
            capability_boundaries=boundaries,
            policy_constraints=(
                "Correlation is diagnostic and does not prove causality.",
                "Reject caused-by, driven-by, due-to, attributable-to, responsible-for, or resulted-from language when only diagnostic metrics are supplied.",
                "Do not invent GMV, CTR, CVR, ROI, ad spend, inventory, profit, or uplift.",
            ),
        )
        estimated = estimate_context_tokens(packet)
        if estimated > packet.budget.max_tokens:
            raise ValueError("Verification context exceeds token budget")
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
            "You are an independent fresh-context verifier. You have no access to "
            "Lead reasoning. Evaluate each claim only against the supplied metric "
            "digests, Evidence IDs, capability boundaries and policy constraints. "
            "Return JSON only with no Markdown or extra keys. A claim contradicted "
            "by metrics must be reject/metric_contradiction. A causal claim supported "
            "only by correlation—including caused by, driven by, due to, attributable "
            "to, responsible for, or resulted from—must be "
            "reject/unsupported_causal_language. Every "
            "claim verdict must cite supplied metric_observation_ids. Use exactly: "
            '{"claims":[{"claim_index":integer,"verdict":"pass"|"reject"|"repair",'
            '"issue_codes":["metric_contradiction"|"unsupported_causal_language"|'
            '"missing_evidence"|"capability_overclaim"|"policy_violation"],'
            '"reason":string,"metric_observation_ids":[string]}]}.'
        )

    @classmethod
    def _parse(
        cls,
        response_text: str,
        context: VerificationPacket,
    ) -> tuple[_ClaimCandidate, ...]:
        payload = cls._decode_json(response_text)
        try:
            output = _VerificationOutput.model_validate(payload)
        except ValidationError as exc:
            raise ValueError("Verification output failed schema validation") from exc
        expected_indices = set(range(len(context.claims)))
        actual_indices = {item.claim_index for item in output.claims}
        if actual_indices != expected_indices or len(output.claims) != len(actual_indices):
            raise ValueError("Verification output must contain each claim index exactly once")
        allowed = frozenset(context.manifest.included_metric_observation_ids)
        if any(
            not frozenset(item.metric_observation_ids).issubset(allowed)
            for item in output.claims
        ):
            raise ValueError("Verification cited a Metric outside fresh context")
        incorrectly_passed_causal_claims = tuple(
            item.claim_index
            for item in output.claims
            if item.verdict is ClaimVerdict.PASS
            and unsupported_causal_phrases(context.claims[item.claim_index])
        )
        if incorrectly_passed_causal_claims:
            raise ValueError(
                "Verifier passed unsupported causal language for claims: "
                + ", ".join(
                    str(index) for index in incorrectly_passed_causal_claims
                )
            )
        return tuple(sorted(output.claims, key=lambda item: item.claim_index))

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
                raise ValueError("Verification response is not valid JSON") from None
            payload = json.loads(text[start : end + 1])
        if not isinstance(payload, dict):
            raise ValueError("Verification response root must be an object")
        return payload
