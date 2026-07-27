"""Real DeepSeek V4 semantic candidate service with fail-closed telemetry."""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from langchain.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import Field

from app.commerce.data.profiler import DatasetProfile
from app.commerce.data.semantic_candidates import (
    SemanticCandidateEnvelope,
    SemanticCandidateParseError,
    SemanticCandidateParser,
    keep_candidates_unconfirmed,
)
from app.commerce.data.semantic_mapper import SemanticMappingProfile
from app.commerce.domain.models import CommerceModel
from app.commerce.evaluation.real_model_preflight import (
    DEFAULT_MODEL_ALIAS,
    EXPECTED_PROVIDER_CLASS,
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
from deerflow.config.app_config import AppConfig
from deerflow.models.lifecycle import close_model_clients
from deerflow.reflection import resolve_class

SEMANTIC_CANDIDATE_PROMPT_VERSION = "commerce-semantic-candidate@1.0.0"
SEMANTIC_CANDIDATE_CONTEXT_VERSION = "commerce-semantic-candidate-context@1.0.0"
SEMANTIC_CANDIDATE_MAX_OUTPUT_TOKENS = 1024
_REPO_ROOT = Path(__file__).resolve().parents[4]


class CandidateRunStatus(StrEnum):
    PASSED = "passed"
    BLOCKED = "blocked"
    PARSE_FAILED = "parse_failed"


class SemanticCandidateTelemetry(CommerceModel):
    schema_version: str = "1.0"
    run_id: str = Field(min_length=1)
    status: CandidateRunStatus
    checked_at: datetime
    configured_alias: str = Field(min_length=1)
    configured_model: str = Field(min_length=1)
    provider_class: str = Field(min_length=1)
    endpoint: str = Field(min_length=1)
    actual_model_identity: str | None = Field(default=None, min_length=1)
    identity_evidence_source: str | None = Field(default=None, min_length=1)
    provider_request_id: str | None = Field(default=None, min_length=1)
    provider_request_id_source: str | None = Field(default=None, min_length=1)
    provider_response_id: str | None = Field(default=None, min_length=1)
    system_fingerprint: str | None = None
    token_usage: TokenUsage | None = None
    latency_ms: float = Field(ge=0.0)
    request_attempt_count: int = Field(ge=0)
    retry_count: int = Field(ge=0)
    configured_max_retries: int = Field(ge=0)
    stop_reason: str | None = Field(default=None, min_length=1)
    request_nonce_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    response_content_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    error_code: str | None = Field(default=None, min_length=1)
    error_message: str | None = Field(default=None, min_length=1)
    versions: RealModelVersionSet


class SemanticCandidateResult(CommerceModel):
    envelope: SemanticCandidateEnvelope
    mapping_profile: SemanticMappingProfile
    telemetry: SemanticCandidateTelemetry


class SemanticCandidateAuditStore:
    """Persist secret-free telemetry without storing prompts or model text."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def persist(self, telemetry: SemanticCandidateTelemetry) -> Path:
        self._root.mkdir(parents=True, exist_ok=True)
        path = self._root / f"{telemetry.run_id}.json"
        with path.open("x", encoding="utf-8") as file:
            json.dump(telemetry.model_dump(mode="json"), file, ensure_ascii=False, indent=2, sort_keys=True)
            file.write("\n")
        return path


class RealModelBlockedError(RuntimeError):
    """The real DeepSeek V4 gate or candidate call was blocked."""

    def __init__(self, message: str, *, preflight: RealModelPreflightResult | None = None):
        super().__init__(message)
        self.preflight = preflight


class SemanticCandidateService:
    """Ask real DeepSeek V4 for candidates while keeping confirmation deterministic."""

    def __init__(
        self,
        *,
        model_alias: str = DEFAULT_MODEL_ALIAS,
        audit_store: SemanticCandidateAuditStore | None = None,
    ) -> None:
        self._model_alias = model_alias
        configured = os.getenv("COMMERCE_SEMANTIC_CANDIDATE_AUDIT_DIR")
        default_root = _REPO_ROOT / ".deer-flow" / "commerce" / "evaluation" / "semantic-candidates"
        self._audit_store = audit_store or SemanticCandidateAuditStore(
            Path(configured).expanduser() if configured else default_root
        )

    def suggest(
        self,
        profile: DatasetProfile,
        mapping_profile: SemanticMappingProfile | None = None,
    ) -> SemanticCandidateResult:
        preflight = run_real_model_preflight(model_alias=self._model_alias)
        if not preflight.passed:
            raise RealModelBlockedError(
                f"DeepSeek V4 preflight blocked semantic candidate call: {preflight.status.value}",
                preflight=preflight,
            )

        run_id = f"semantic-candidate-{uuid.uuid4().hex}"
        checked_at = datetime.now(UTC)
        versions = RealModelVersionSet(
            prompt_version=SEMANTIC_CANDIDATE_PROMPT_VERSION,
            context_version=SEMANTIC_CANDIDATE_CONTEXT_VERSION,
            router_version="not-applicable@1.0.0",
            skill_version="not-applicable@1.0.0",
        )
        config_path = AppConfig.resolve_config_path()
        load_dotenv(config_path.parent / ".env", override=False)
        load_dotenv(_REPO_ROOT / ".env", override=False)
        config = AppConfig.from_file(str(config_path))
        model_config = config.get_model_config(self._model_alias)
        if model_config is None:
            raise RealModelBlockedError(f"Configured model alias is missing: {self._model_alias}")
        endpoint = str(model_config.api_base or "")
        if model_config.use != EXPECTED_PROVIDER_CLASS or not is_official_deepseek_endpoint(endpoint):
            raise RealModelBlockedError("Semantic candidate provider configuration is not trusted")

        request_attempt_count = 0

        def count_request(_: httpx.Request) -> None:
            nonlocal request_attempt_count
            request_attempt_count += 1

        http_client = httpx.Client(event_hooks={"request": [count_request]})
        started = time.perf_counter()
        request_nonce_sha256 = hashlib.sha256(run_id.encode("utf-8")).hexdigest()
        model = None
        try:
            model_class = resolve_class(model_config.use, BaseChatModel)
            settings = _model_settings_for_preflight(
                model_config,
                http_client=http_client,
                max_output_tokens=SEMANTIC_CANDIDATE_MAX_OUTPUT_TOKENS,
            )
            model = model_class(**settings)
            response = model.invoke(
                [
                    SystemMessage(content=self._system_prompt()),
                    HumanMessage(content=self._user_prompt(profile, run_id)),
                ]
            )
            if not isinstance(response, AIMessage):
                raise TypeError(f"Expected AIMessage, received {type(response).__name__}")
            latency_ms = (time.perf_counter() - started) * 1000
        except Exception as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            failure = _failure_from_exception(exc, api_key=os.getenv("DEEPSEEK_API_KEY", ""))
            telemetry = self._telemetry(
                run_id=run_id,
                checked_at=checked_at,
                status=CandidateRunStatus.BLOCKED,
                model_config=model_config,
                endpoint=endpoint,
                request_attempt_count=request_attempt_count,
                latency_ms=latency_ms,
                request_nonce_sha256=request_nonce_sha256,
                versions=versions,
                error_code=failure.error_code or failure.exception_type,
                error_message=failure.message,
            )
            self._audit_store.persist(telemetry)
            raise RealModelBlockedError(
                f"DeepSeek V4 semantic candidate call failed: {telemetry.error_code}",
            ) from exc
        finally:
            if model is not None:
                close_model_clients(model)
            http_client.close()

        metadata = _mapping(response.response_metadata)
        actual_identity, identity_source = _extract_identity(metadata)
        provider_request_id, request_id_source, provider_response_id = _extract_provider_ids(metadata)
        token_usage = _extract_token_usage(response)
        stop_reason = str(metadata["finish_reason"]) if metadata.get("finish_reason") else None
        fingerprint = str(metadata["system_fingerprint"]) if metadata.get("system_fingerprint") else None
        response_text = response.text
        response_hash = hashlib.sha256(response_text.encode("utf-8")).hexdigest()
        telemetry = self._telemetry(
            run_id=run_id,
            checked_at=checked_at,
            status=CandidateRunStatus.PASSED,
            model_config=model_config,
            endpoint=endpoint,
            request_attempt_count=request_attempt_count,
            latency_ms=latency_ms,
            request_nonce_sha256=request_nonce_sha256,
            versions=versions,
            actual_model_identity=actual_identity,
            identity_evidence_source=identity_source,
            provider_request_id=provider_request_id,
            provider_request_id_source=request_id_source,
            provider_response_id=provider_response_id,
            system_fingerprint=fingerprint,
            token_usage=token_usage,
            stop_reason=stop_reason,
            response_content_sha256=response_hash,
        )
        if not is_verified_deepseek_v4_identity(actual_identity):
            blocked = telemetry.model_copy(
                update={
                    "status": CandidateRunStatus.BLOCKED,
                    "error_code": "server_model_identity_not_deepseek_v4",
                    "error_message": f"Server returned unverified model identity {actual_identity!r}",
                }
            )
            self._audit_store.persist(blocked)
            raise RealModelBlockedError(blocked.error_message or "Unverified model identity")
        missing_telemetry = [
            name
            for name, value in (
                ("provider_request_id", provider_request_id),
                ("provider_response_id", provider_response_id),
                ("token_usage", token_usage),
                ("stop_reason", stop_reason),
            )
            if value is None
        ]
        if missing_telemetry:
            blocked = telemetry.model_copy(
                update={
                    "status": CandidateRunStatus.BLOCKED,
                    "error_code": "required_provider_telemetry_missing",
                    "error_message": f"Provider response omitted: {', '.join(missing_telemetry)}",
                }
            )
            self._audit_store.persist(blocked)
            raise RealModelBlockedError(blocked.error_message or "Provider telemetry missing")
        self._audit_store.persist(telemetry)

        try:
            candidates = SemanticCandidateParser().parse(response_text, profile)
        except SemanticCandidateParseError as exc:
            parse_failed = telemetry.model_copy(
                update={
                    "run_id": f"{run_id}-parse",
                    "status": CandidateRunStatus.PARSE_FAILED,
                    "error_code": "semantic_candidate_json_invalid",
                    "error_message": str(exc),
                }
            )
            self._audit_store.persist(parse_failed)
            raise

        envelope = SemanticCandidateEnvelope(
            dataset_id=str(profile.dataset_id),
            workspace_id=str(profile.workspace_id),
            candidates=candidates,
        )
        return SemanticCandidateResult(
            envelope=envelope,
            mapping_profile=keep_candidates_unconfirmed(
                mapping_profile or self._mapping_profile_for_candidates(profile),
                candidates,
            ),
            telemetry=telemetry,
        )

    @staticmethod
    def _mapping_profile_for_candidates(profile: DatasetProfile) -> SemanticMappingProfile:
        from app.commerce.data.semantic_mapper import SemanticMapper

        return SemanticMapper().map(profile)

    @staticmethod
    def _system_prompt() -> str:
        return (
            "You are a semantic mapping candidate generator. Return JSON only. "
            "Never claim a mapping is confirmed. Suggest only columns present in the supplied profile. "
            'Use exactly {"candidates":[{"table_name":string,"column_name":string,"semantic_field":string,"confidence":number,"reason":string}]}.'
        )

    @staticmethod
    def _user_prompt(profile: DatasetProfile, run_id: str) -> str:
        schema = [
            {
                "table_name": table.table_name,
                "columns": [
                    {
                        "name": column.name,
                        "inferred_type": column.inferred_type.value,
                        "missing_rate": column.missing_rate,
                        "unique_rate": column.unique_rate,
                    }
                    for column in table.columns
                ],
            }
            for table in profile.tables
        ]
        return (
            f"Fresh request nonce: {run_id}. Dataset schema only: "
            f"{json.dumps(schema, ensure_ascii=False, sort_keys=True)}. "
            "Return candidates only for unresolved or ambiguous columns; an empty array is valid."
        )

    @staticmethod
    def _telemetry(*, model_config, **values: Any) -> SemanticCandidateTelemetry:
        return SemanticCandidateTelemetry(
            configured_alias=model_config.name,
            configured_model=model_config.model,
            provider_class=model_config.use,
            configured_max_retries=0,
            retry_count=max(0, values["request_attempt_count"] - 1),
            **values,
        )
