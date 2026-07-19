"""Structured Lead synthesis over persisted Path Evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from pydantic import Field, ValidationError

from app.commerce.agents.budget import BudgetManager
from app.commerce.agents.contracts import LeadContextPacket, ModelProfile, PathType
from app.commerce.agents.model_router import (
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
from app.commerce.domain.ids import EvidenceId, HypothesisId
from app.commerce.domain.models import CommerceModel
from app.commerce.evaluation.real_model_preflight import RealModelVersionSet

LEAD_PROMPT_VERSION = "commerce.lead-synthesis@1.0.0"
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
    claims: tuple[LeadClaim, ...] = Field(min_length=1)
    unknowns: tuple[LeadUnknown, ...] = ()
    suggested_next_paths: tuple[PathType, ...] = ()
    context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class LeadAuditRecord(CommerceModel):
    telemetry: VerifiedCallTelemetry
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
    result: LeadSynthesisResult
    telemetry: VerifiedCallTelemetry
    audit_path: str = Field(min_length=1)


class _ClaimCandidate(CommerceModel):
    statement: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    evidence_ids: tuple[EvidenceId, ...] = Field(min_length=1)


class _UnknownCandidate(CommerceModel):
    question: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class _LeadOutput(CommerceModel):
    claims: tuple[_ClaimCandidate, ...] = Field(min_length=1)
    unknowns: tuple[_UnknownCandidate, ...] = ()
    suggested_next_paths: tuple[PathType, ...] = ()


class LeadSynthesisAgent:
    def __init__(self, *, audit_store: LeadAuditStore | None = None) -> None:
        self._audit = audit_store or LeadAuditStore()

    async def synthesize(self, context: LeadContextPacket) -> LeadSynthesisRun:
        assignment = await ModelRouter().assign(
            ModelRouteRequest(
                role=ModelRole.LEAD,
                base_profile=ModelProfile.BALANCED_TOOL_USER,
                case_severity=context.case.severity,
                capability_count=len(context.capability_profile.capabilities),
                evidence_path_count=1,
                contradiction_count=0,
                schema_complexity=OutputSchemaComplexity.HIGH,
                minimum_output_tokens=512,
            ),
            BudgetManager(context.budget),
        )
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
                context_sha256=context.manifest.context_sha256,
                result_sha256=result_hash,
            )
        )
        return LeadSynthesisRun(
            result=result,
            telemetry=response.telemetry,
            audit_path=str(audit_path),
        )

    @staticmethod
    def _system_prompt() -> str:
        return (
            "You are the Commerce Lead synthesis Agent. Return JSON only with no "
            "Markdown or extra keys. Create concise diagnostic claims from supplied "
            "Evidence; every claim must cite Evidence IDs exactly as supplied. Prefer "
            "the most specific Path Evidence that compares stages. Explicitly distinguish "
            "seller handling from carrier transit when those metrics exist. Do not say "
            "correlation caused an outcome and do not invent GMV, CTR, CVR, ROI, profit, "
            "inventory, ad spend or uplift. Claims are diagnostic hypotheses for fresh "
            "Verification, not final truth. Use exactly: "
            '{"claims":[{"statement":string,"confidence":number,"evidence_ids":'
            '[string]}],"unknowns":[{"question":string,"reason":string}],'
            '"suggested_next_paths":["fulfillment"|"seller_peer"|"review_experience"]}.'
        )

    @classmethod
    def _parse(
        cls,
        response_text: str,
        context: LeadContextPacket,
    ) -> _LeadOutput:
        payload = cls._decode_json(response_text)
        try:
            output = _LeadOutput.model_validate(payload)
        except ValidationError as exc:
            raise ValueError("Lead output failed structured schema validation") from exc
        allowed = frozenset(item.evidence_id for item in context.evidence)
        if any(not frozenset(item.evidence_ids).issubset(allowed) for item in output.claims):
            raise ValueError("Lead claim cited Evidence outside current Case context")
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
