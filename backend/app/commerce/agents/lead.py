"""Structured Lead synthesis over persisted Path Evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Self
from uuid import NAMESPACE_URL, uuid5

from pydantic import Field, ValidationError, model_validator

from app.commerce.agents.budget import BudgetManager
from app.commerce.agents.claim_policy import unsupported_causal_phrases
from app.commerce.agents.contracts import (
    ContextManifest,
    ContextPacket,
    EvidenceDigest,
    HypothesisDigest,
    LeadContextPacket,
    ModelProfile,
    PathContextPacket,
    PathEvidenceScope,
    PathType,
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
from app.commerce.data.capabilities import CapabilityName, CapabilityProfile, CapabilityStatus
from app.commerce.domain.events import DomainEventEnvelope
from app.commerce.domain.ids import AgentTaskId, EvidenceId, HypothesisId
from app.commerce.domain.models import CommerceModel
from app.commerce.evaluation.real_model_preflight import RealModelVersionSet

LEAD_PROMPT_VERSION = "commerce.lead-synthesis@1.3.0"
LEAD_REPAIR_PROMPT_VERSION = "commerce.lead-synthesis-repair@1.0.0"
LEAD_PATH_CONTEXT_VERSION = "commerce-lead-path-synthesis-context@1.0.0"
PERSISTED_LEAD_CONTEXT_VERSION = "commerce-persisted-lead-context@1.0.0"
LEAD_MAX_OUTPUT_TOKENS = 1_800
_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_AUDIT_ROOT = (
    _REPO_ROOT / ".deer-flow" / "commerce" / "evaluation" / "lead-synthesis"
)

LeadSynthesisStatus = VerifiedCallStatus


class LeadClaim(CommerceModel):
    hypothesis_id: HypothesisId
    statement: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    evidence_ids: tuple[EvidenceId, ...] = Field(min_length=1)
    diagnostic_only: bool = True


class LeadUnknown(CommerceModel):
    question: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class LeadSynthesisResult(CommerceModel):
    schema_version: str = "commerce.lead-synthesis@1.0.0"
    claims: tuple[LeadClaim, ...] = ()
    unknowns: tuple[LeadUnknown, ...] = ()
    suggested_next_paths: tuple[PathType, ...] = ()
    context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def require_claim_or_unknown(self) -> Self:
        if not self.claims and not self.unknowns:
            raise ValueError("Lead synthesis requires a claim or explicit Unknown")
        return self


class PersistedLeadContextPacket(ContextPacket):
    """Fresh Lead input built only from persisted, Path-scoped Evidence."""

    capabilities: frozenset[CapabilityName] = frozenset()
    capability_profile: CapabilityProfile
    evidence: tuple[EvidenceDigest, ...] = ()
    hypotheses: tuple[HypothesisDigest, ...] = ()
    path_scopes: tuple[PathEvidenceScope, ...] = ()

    @model_validator(mode="after")
    def enforce_persisted_path_boundary(self) -> Self:
        if self.capability_profile.workspace_id != self.case.workspace_id:
            raise ValueError("Lead Capability Profile Workspace must match Case")
        if self.capability_profile.dataset_id != self.manifest.dataset_id:
            raise ValueError("Lead Capability Profile Dataset must match Manifest")
        routable = frozenset(
            assessment.name
            for assessment in self.capability_profile.capabilities
            if assessment.status
            in {CapabilityStatus.AVAILABLE, CapabilityStatus.PARTIAL}
        )
        if self.capabilities != routable:
            raise ValueError("Lead capabilities must match routable Capability Profile")

        task_ids = tuple(scope.task_id for scope in self.path_scopes)
        context_hashes = tuple(scope.context_sha256 for scope in self.path_scopes)
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("Persisted Lead Path task IDs must be unique")
        if len(context_hashes) != len(set(context_hashes)):
            raise ValueError("Persisted Lead Path context hashes must be unique")
        for scope in self.path_scopes:
            if (
                scope.workspace_id != self.case.workspace_id
                or scope.case_id != self.case.case_id
                or scope.dataset_id != self.manifest.dataset_id
                or scope.source_artifact_sha256
                != self.manifest.source_artifact_sha256
            ):
                raise ValueError("Persisted Path scope identity must match Lead context")

        scoped_evidence_ids = tuple(
            evidence_id
            for scope in self.path_scopes
            for evidence_id in scope.evidence_ids
        )
        if len(scoped_evidence_ids) != len(set(scoped_evidence_ids)):
            raise ValueError("Persisted Evidence cannot belong to multiple Path scopes")
        if tuple(item.evidence_id for item in self.evidence) != scoped_evidence_ids:
            raise ValueError("Lead Evidence must exactly match persisted Path scopes")
        if self.manifest.included_evidence_ids != scoped_evidence_ids:
            raise ValueError("Lead Manifest Evidence must match persisted Path scopes")

        evidence_by_id = {item.evidence_id: item for item in self.evidence}
        for scope in self.path_scopes:
            allowed_facts = set(scope.included_fact_ids)
            allowed_metrics = set(scope.included_metric_observation_ids)
            for evidence_id in scope.evidence_ids:
                item = evidence_by_id[evidence_id]
                if not set(item.fact_ids).issubset(allowed_facts) or not set(
                    item.metric_observation_ids
                ).issubset(allowed_metrics):
                    raise ValueError(
                        "Lead Evidence references IDs outside its persisted Path scope"
                    )

        expected_facts = _merge_scope_ids(
            scope.included_fact_ids for scope in self.path_scopes
        )
        expected_metrics = _merge_scope_ids(
            scope.included_metric_observation_ids for scope in self.path_scopes
        )
        expected_anomalies = _merge_scope_ids(
            scope.included_anomaly_ids for scope in self.path_scopes
        )
        if self.manifest.included_fact_ids != expected_facts:
            raise ValueError("Lead Manifest Facts must match persisted Path scopes")
        if self.manifest.included_metric_observation_ids != expected_metrics:
            raise ValueError("Lead Manifest Metrics must match persisted Path scopes")
        if self.manifest.included_anomaly_ids != expected_anomalies:
            raise ValueError("Lead Manifest Anomalies must match persisted Path scopes")

        known_evidence = set(scoped_evidence_ids)
        if any(
            not set(hypothesis.evidence_ids).issubset(known_evidence)
            for hypothesis in self.hypotheses
        ):
            raise ValueError("Lead Hypothesis references Evidence outside Path scopes")
        return self


LeadSynthesisContext = LeadContextPacket | PersistedLeadContextPacket


class LeadAuditRecord(CommerceModel):
    telemetry: VerifiedCallTelemetry
    attempt_telemetry: tuple[VerifiedCallTelemetry, ...] = Field(min_length=1)
    context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class LeadAuditStore:
    def __init__(self, root: Path | None = None) -> None:
        self._root = root or _DEFAULT_AUDIT_ROOT

    def persist(self, record: LeadAuditRecord) -> Path:
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


class LeadSynthesisRun(CommerceModel):
    assignment: ModelAssignment
    context: LeadSynthesisContext
    result: LeadSynthesisResult
    telemetry: VerifiedCallTelemetry
    attempt_telemetry: tuple[VerifiedCallTelemetry, ...] = Field(min_length=1)
    result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    audit_path: str = Field(min_length=1)

    @model_validator(mode="after")
    def keep_attempt_telemetry_complete(self) -> Self:
        if self.attempt_telemetry[-1] != self.telemetry:
            raise ValueError("Lead final telemetry must match the last model attempt")
        if len(self.attempt_telemetry) > 2:
            raise ValueError("Lead synthesis supports at most one structured repair")
        return self

    @property
    def total_tokens(self) -> int:
        return sum(
            item.token_usage.total_tokens
            for item in self.attempt_telemetry
            if item.token_usage is not None
        )

    @property
    def total_latency_ms(self) -> float:
        return sum(item.latency_ms for item in self.attempt_telemetry)


class LeadSynthesisPlan(CommerceModel):
    context: LeadSynthesisContext
    assignment: ModelAssignment
    read_only: bool = False
    max_structured_repairs: int = Field(default=0, ge=0, le=1)


class _ClaimCandidate(CommerceModel):
    statement: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    evidence_ids: tuple[EvidenceId, ...] = Field(min_length=1)


class _UnknownCandidate(CommerceModel):
    question: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class _LeadOutput(CommerceModel):
    claims: tuple[_ClaimCandidate, ...] = ()
    unknowns: tuple[_UnknownCandidate, ...] = ()
    suggested_next_paths: tuple[PathType, ...] = ()

    @model_validator(mode="after")
    def require_claim_or_unknown(self) -> Self:
        if not self.claims and not self.unknowns:
            raise ValueError("Lead output requires a claim or explicit Unknown")
        return self


class LeadSynthesisAgent:
    def __init__(self, *, audit_store: LeadAuditStore | None = None) -> None:
        self._audit = audit_store or LeadAuditStore()

    async def prepare(
        self,
        context: LeadSynthesisContext,
        *,
        budget: BudgetManager | None = None,
        read_only: bool = False,
    ) -> LeadSynthesisPlan:
        manager = budget or BudgetManager(context.budget)
        assignment = await ModelRouter().assign(
            ModelRouteRequest(
                role=ModelRole.ANSWER if read_only else ModelRole.LEAD,
                base_profile=(
                    ModelProfile.FAST_STRUCTURED
                    if read_only
                    else ModelProfile.BALANCED_TOOL_USER
                ),
                case_severity=context.case.severity,
                capability_count=len(context.capability_profile.capabilities),
                evidence_path_count=(
                    len({scope.path_type for scope in context.path_scopes})
                    if isinstance(context, PersistedLeadContextPacket)
                    else 1
                ),
                contradiction_count=0,
                schema_complexity=OutputSchemaComplexity.HIGH,
                minimum_output_tokens=512,
            ),
            manager,
        )
        snapshot = manager.snapshot
        remaining_repairs = (
            snapshot.limit.max_repeated_actions
            - snapshot.usage.repeated_actions
        )
        return LeadSynthesisPlan(
            context=context,
            assignment=assignment,
            read_only=read_only,
            max_structured_repairs=min(1, max(0, remaining_repairs)),
        )

    async def synthesize(self, context: LeadSynthesisContext) -> LeadSynthesisRun:
        return await self.run_prepared(await self.prepare(context))

    async def run_prepared(self, plan: LeadSynthesisPlan) -> LeadSynthesisRun:
        context = plan.context
        assignment = plan.assignment
        response = await VerifiedModelCaller().call(
            assignment=assignment,
            system_prompt=self._system_prompt(),
            user_prompt=(
                "Fresh LeadContextPacket. Synthesize claims from Evidence only: "
                f"{context.model_dump_json(exclude_none=True)}"
            ),
            versions=RealModelVersionSet(
                prompt_version=LEAD_PROMPT_VERSION,
                context_version=context.manifest.context_version,
                router_version=assignment.router_version,
                skill_version="commerce.lead-synthesis@1.0.0",
            ),
            run_prefix="lead-synthesis",
            max_output_tokens=LEAD_MAX_OUTPUT_TOKENS,
        )
        attempts = [response.telemetry]
        try:
            output = self._parse(response.text, context)
        except ValueError as error:
            if plan.max_structured_repairs < 1:
                raise
            repaired = await VerifiedModelCaller().call(
                assignment=assignment,
                system_prompt=self._system_prompt(),
                user_prompt=self._repair_prompt(
                    context=context,
                    rejected_draft=response.text,
                    validation_error=str(error),
                ),
                versions=RealModelVersionSet(
                    prompt_version=LEAD_REPAIR_PROMPT_VERSION,
                    context_version=context.manifest.context_version,
                    router_version=assignment.router_version,
                    skill_version="commerce.lead-synthesis@1.0.0",
                ),
                run_prefix="lead-synthesis-repair",
                max_output_tokens=LEAD_MAX_OUTPUT_TOKENS,
            )
            attempts.append(repaired.telemetry)
            response = repaired
            output = self._parse(response.text, context)
        claims = tuple(
            LeadClaim(
                hypothesis_id=HypothesisId(
                    f"hyp_{uuid5(NAMESPACE_URL, f'{context.manifest.context_sha256}:{item.statement}').hex}"
                ),
                statement=item.statement,
                confidence=item.confidence,
                evidence_ids=item.evidence_ids,
            )
            for item in output.claims
        )
        result = LeadSynthesisResult(
            claims=claims,
            unknowns=tuple(
                LeadUnknown(question=item.question, reason=item.reason)
                for item in output.unknowns
            ),
            suggested_next_paths=output.suggested_next_paths,
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
        audit_path = self._audit.persist(
            LeadAuditRecord(
                telemetry=response.telemetry,
                attempt_telemetry=tuple(attempts),
                context_sha256=context.manifest.context_sha256,
                result_sha256=result_hash,
            )
        )
        return LeadSynthesisRun(
            assignment=assignment,
            context=context,
            result=result,
            telemetry=response.telemetry,
            attempt_telemetry=tuple(attempts),
            result_sha256=result_hash,
            audit_path=str(audit_path),
        )

    @staticmethod
    def _system_prompt() -> str:
        return (
            "You are the Commerce Lead synthesis Agent. Return JSON only with no "
            "Markdown or extra keys. Create concise diagnostic claims from supplied "
            "Evidence; every claim must cite Evidence IDs exactly as supplied. "
            "Only copy evd_* strings from the supplied Evidence array into evidence_ids; "
            "never put anom_* or mobs_* identifiers in evidence_ids. "
            "Prefer the most specific Path Evidence that compares stages. Explicitly distinguish "
            "seller handling from carrier transit when those metrics exist. Do not say "
            "an outcome was caused by, driven by, due to, attributable to, explained by, "
            "or resulted from a correlated metric. Use diagnostic localization such as "
            "'observed deterioration is concentrated in transit rather than handling'. "
            "Write direct observation statements without inferential connectors such as "
            "indicating, suggesting, or implying. "
            "Do not introduce a metric or domain absent from the supplied Evidence. "
            "Do not invent GMV, CTR, CVR, ROI, profit, "
            "inventory, ad spend or uplift. Claims are diagnostic hypotheses for fresh "
            "Verification, not final truth. Use exactly: "
            '{"claims":[{"statement":string,"confidence":number,"evidence_ids":'
            '[string]}],"unknowns":[{"question":string,"reason":string}],'
            '"suggested_next_paths":["fulfillment"|"seller_peer"|"review_experience"]}.'
        )

    @staticmethod
    def _repair_prompt(
        *,
        context: LeadSynthesisContext,
        rejected_draft: str,
        validation_error: str,
    ) -> str:
        return (
            "A deterministic validator rejected the previous Lead JSON draft. "
            "Return one corrected JSON object only. Preserve only claims supported "
            "by the same supplied Evidence IDs. Remove causal or inferential "
            "connectors instead of replacing them with synonyms. Do not introduce "
            "new metrics, facts, Evidence IDs, Paths or business outcomes. "
            f"Validator error: {validation_error}\n"
            f"Rejected draft: {rejected_draft}\n"
            "Fresh persisted Lead context: "
            f"{context.model_dump_json(exclude_none=True)}"
        )

    @classmethod
    def _parse(
        cls,
        response_text: str,
        context: LeadSynthesisContext,
    ) -> _LeadOutput:
        payload = cls._decode_json(response_text)
        try:
            output = _LeadOutput.model_validate(payload)
        except ValidationError as exc:
            raise ValueError("Lead output failed structured schema validation") from exc
        allowed = frozenset(item.evidence_id for item in context.evidence)
        if any(not frozenset(item.evidence_ids).issubset(allowed) for item in output.claims):
            raise ValueError("Lead claim cited Evidence outside current Case context")
        causal = tuple(
            (index, unsupported_causal_phrases(item.statement))
            for index, item in enumerate(output.claims)
            if unsupported_causal_phrases(item.statement)
        )
        if causal:
            raise ValueError(
                "Lead claim used unsupported causal language: "
                + "; ".join(
                    f"claim[{index}]={','.join(phrases)}"
                    for index, phrases in causal
                )
            )
        if len(output.suggested_next_paths) != len(set(output.suggested_next_paths)):
            raise ValueError("Lead suggested next Paths must be unique")
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
                raise ValueError("Lead response is not valid JSON") from None
            payload = json.loads(text[start : end + 1])
        if not isinstance(payload, dict):
            raise ValueError("Lead response root must be an object")
        return payload


def build_persisted_lead_context(
    reloaded: LeadContextPacket,
    *,
    path_scopes: tuple[PathEvidenceScope, ...],
    goal: str | None = None,
) -> PersistedLeadContextPacket:
    """Build canonical Lead input from reloaded Case state and persisted Path scopes."""

    available = {item.evidence_id: item for item in reloaded.evidence}
    selected_ids = tuple(
        evidence_id for scope in path_scopes for evidence_id in scope.evidence_ids
    )
    missing = set(selected_ids) - set(available)
    if missing:
        raise ValueError(
            "Persisted Path Evidence is missing from reloaded Case Evidence: "
            + ", ".join(sorted(str(value) for value in missing))
        )
    if len(selected_ids) != len(set(selected_ids)):
        raise ValueError("Persisted Evidence cannot belong to multiple Path scopes")

    for scope in path_scopes:
        if (
            scope.workspace_id != reloaded.case.workspace_id
            or scope.case_id != reloaded.case.case_id
            or scope.dataset_id != reloaded.manifest.dataset_id
            or scope.source_artifact_sha256
            != reloaded.manifest.source_artifact_sha256
        ):
            raise ValueError("Persisted Path scope identity does not match reloaded Case")
        allowed_facts = set(scope.included_fact_ids)
        allowed_metrics = set(scope.included_metric_observation_ids)
        for evidence_id in scope.evidence_ids:
            item = available[evidence_id]
            if not set(item.fact_ids).issubset(allowed_facts) or not set(
                item.metric_observation_ids
            ).issubset(allowed_metrics):
                raise ValueError(
                    "Lead Evidence references IDs outside its persisted Path scope"
                )

    evidence = tuple(available[evidence_id] for evidence_id in selected_ids)
    selected_set = set(selected_ids)
    hypotheses = tuple(
        item
        for item in reloaded.hypotheses
        if item.evidence_ids and set(item.evidence_ids).issubset(selected_set)
    )
    manifest = ContextManifest(
        context_version=PERSISTED_LEAD_CONTEXT_VERSION,
        workspace_id=reloaded.case.workspace_id,
        case_id=reloaded.case.case_id,
        dataset_id=reloaded.manifest.dataset_id,
        source_artifact_sha256=reloaded.manifest.source_artifact_sha256,
        context_sha256="0" * 64,
        estimated_tokens=0,
        included_evidence_ids=selected_ids,
        included_fact_ids=_merge_scope_ids(
            scope.included_fact_ids for scope in path_scopes
        ),
        included_metric_observation_ids=_merge_scope_ids(
            scope.included_metric_observation_ids for scope in path_scopes
        ),
        included_anomaly_ids=_merge_scope_ids(
            scope.included_anomaly_ids for scope in path_scopes
        ),
        redactions=tuple(
            dict.fromkeys(
                (
                    *reloaded.manifest.redactions,
                    "Only persisted Barrier-released Evidence included",
                    "Path reasoning history excluded",
                    "Raw Path ContextPackets excluded",
                )
            )
        ),
    )
    packet = PersistedLeadContextPacket(
        case=reloaded.case,
        goal=goal
        or (
            "Synthesize traceable diagnostic hypotheses only from persisted "
            "Path Evidence; preserve unknowns and avoid causal claims."
        ),
        manifest=manifest,
        budget=reloaded.budget,
        metadata={
            "parent_lead_context_sha256": reloaded.manifest.context_sha256,
            "persisted_path_scope_count": len(path_scopes),
        },
        capabilities=reloaded.capabilities,
        capability_profile=reloaded.capability_profile,
        evidence=evidence,
        hypotheses=hypotheses,
        path_scopes=path_scopes,
    )
    estimated = estimate_context_tokens(packet)
    if estimated > packet.budget.max_tokens:
        raise ValueError("Persisted Lead context exceeds token budget")
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


def _merge_scope_ids(values: Any) -> tuple[Any, ...]:
    return tuple(dict.fromkeys(item for group in values for item in group))


def path_evidence_scopes_from_events(
    events: tuple[DomainEventEnvelope, ...],
) -> tuple[PathEvidenceScope, ...]:
    """Reconstruct terminal Path scopes from the authoritative Case event stream."""

    scopes: list[PathEvidenceScope] = []
    seen_tasks: set[AgentTaskId] = set()
    for event in events:
        if event.event_type != "path.completed":
            continue
        payload = event.payload
        raw_scope = payload.get("evidence_scope")
        if raw_scope is None:
            # Legacy events remain readable only when their Evidence references
            # are independently valid against the base deterministic artifact.
            continue
        try:
            scope = PathEvidenceScope.model_validate(raw_scope)
            payload_task_id = AgentTaskId(str(payload["task_id"]))
            payload_path_type = PathType(str(payload["path_type"]))
            payload_evidence_ids = tuple(
                EvidenceId(str(value)) for value in payload.get("evidence_ids", ())
            )
        except (KeyError, TypeError, ValidationError, ValueError) as exc:
            raise ValueError("Persisted path.completed Evidence scope is invalid") from exc
        if event.case_id is None or event.run_id is None:
            raise ValueError("Persisted Path scope requires Case and Run identity")
        if (
            scope.workspace_id != event.workspace_id
            or scope.case_id != event.case_id
            or scope.run_id != event.run_id
            or scope.task_id != payload_task_id
            or scope.path_type is not payload_path_type
            or scope.evidence_ids != payload_evidence_ids
        ):
            raise ValueError("Persisted Path scope does not match path.completed event")
        if scope.task_id in seen_tasks:
            raise ValueError("Persisted Path scope task IDs must be unique")
        seen_tasks.add(scope.task_id)
        scopes.append(scope)
    return tuple(scopes)


def build_path_scoped_lead_context(
    lead: LeadContextPacket,
    path: PathContextPacket,
    *,
    evidence_ids: frozenset[EvidenceId],
) -> LeadContextPacket:
    """Build one internally consistent Lead packet from completed Path scope."""

    if not evidence_ids:
        raise ValueError("Lead synthesis requires completed Path Evidence")
    lead_identity = (
        lead.case.workspace_id,
        lead.case.case_id,
        lead.case.title,
        lead.case.severity,
        lead.case.status,
    )
    path_identity = (
        path.case.workspace_id,
        path.case.case_id,
        path.case.title,
        path.case.severity,
        path.case.status,
    )
    if lead_identity != path_identity:
        raise ValueError("Lead and Path contexts must describe the same Case identity")
    if lead.case.version < path.case.version:
        raise ValueError("Reloaded Lead Case version cannot precede Path context")
    if lead.manifest.dataset_id != path.manifest.dataset_id:
        raise ValueError("Lead and Path contexts must describe the same Dataset")
    available = {item.evidence_id: item for item in lead.evidence}
    missing = evidence_ids - set(available)
    if missing:
        raise ValueError(
            "Completed Path Evidence is missing from reloaded Lead context: "
            + ", ".join(sorted(str(value) for value in missing))
        )
    evidence = tuple(
        item for item in lead.evidence if item.evidence_id in evidence_ids
    )
    allowed_metrics = frozenset(path.manifest.included_metric_observation_ids)
    if any(
        not frozenset(item.metric_observation_ids).issubset(allowed_metrics)
        for item in evidence
    ):
        raise ValueError("Completed Path Evidence references Metrics outside Path scope")
    fact_ids = tuple(
        dict.fromkeys(fact_id for item in evidence for fact_id in item.fact_ids)
    )
    manifest = lead.manifest.model_copy(
        update={
            "context_version": LEAD_PATH_CONTEXT_VERSION,
            "context_sha256": "0" * 64,
            "estimated_tokens": 0,
            "included_evidence_ids": tuple(
                item.evidence_id for item in evidence
            ),
            "included_fact_ids": fact_ids,
            "included_metric_observation_ids": (
                path.manifest.included_metric_observation_ids
            ),
            "included_anomaly_ids": path.manifest.included_anomaly_ids,
            "redactions": tuple(
                dict.fromkeys(
                    (
                        *lead.manifest.redactions,
                        "Lead Evidence and Analysis scoped to completed Paths",
                    )
                )
            ),
        }
    )
    packet = lead.model_copy(
        update={
            "goal": (
                "Synthesize diagnostic hypotheses only from completed Path Evidence; "
                "preserve uncertainty and avoid causal claims."
            ),
            "manifest": manifest,
            "metadata": {
                "parent_lead_context_sha256": lead.manifest.context_sha256,
                "path_context_sha256": path.manifest.context_sha256,
            },
            "analysis": path.analysis,
            "evidence": evidence,
        }
    )
    estimated = estimate_context_tokens(packet)
    if estimated > packet.budget.max_tokens:
        raise ValueError("Path-scoped Lead context exceeds token budget")
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
