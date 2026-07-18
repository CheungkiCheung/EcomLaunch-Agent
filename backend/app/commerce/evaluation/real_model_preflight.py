"""Fail-closed DeepSeek V4 identity and telemetry preflight.

Commerce model and Agent tests may run only after this module has made a fresh
request to the configured official DeepSeek provider and persisted sufficient
evidence that the server actually returned a DeepSeek V4-family model.  Local
aliases, model-authored claims, old traces, response replay, and fallback models
are deliberately not accepted as identity evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Self
from urllib.parse import urlparse

import httpx
import yaml
from dotenv import load_dotenv
from langchain.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import Field, model_validator

from app.commerce.domain.models import CommerceModel
from deerflow.config.app_config import AppConfig
from deerflow.config.model_config import ModelConfig
from deerflow.reflection import resolve_class

EXPECTED_PROVIDER_CLASS = "deerflow.models.patched_deepseek:PatchedChatDeepSeek"
OFFICIAL_DEEPSEEK_HOST = "api.deepseek.com"
DEFAULT_MODEL_ALIAS = "deepseek-reasoner"
PREFLIGHT_PROMPT_VERSION = "commerce-real-model-preflight@1.0.0"
PREFLIGHT_CONTEXT_VERSION = "commerce-preflight-context@1.0.0"
PREFLIGHT_RESPONSE_MARKER = "DEEPSEEK_V4_PREFLIGHT_OK"
PREFLIGHT_MAX_OUTPUT_TOKENS = 64
PREFLIGHT_TIMEOUT_SECONDS = 60.0

_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_AUDIT_ROOT = _REPO_ROOT / ".deer-flow" / "commerce" / "evaluation" / "real-model-preflight"
_DEEPSEEK_V4_IDENTITY = re.compile(r"^deepseek[-_]v4(?:$|[-_.])", re.IGNORECASE)
_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[^\s;,]+"),
    re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)[^\s;,]+"),
)


class PreflightStatus(StrEnum):
    """Machine-readable release-gate state."""

    PASSED = "passed"
    BLOCKED_UNAVAILABLE = "blocked_real_model_unavailable"
    BLOCKED_IDENTITY_UNVERIFIED = "blocked_real_model_identity_unverified"
    BLOCKED_QUOTA_EXHAUSTED = "blocked_real_model_quota_exhausted"
    BLOCKED_AUTH_FAILED = "blocked_real_model_auth_failed"


class TokenUsage(CommerceModel):
    """Provider-reported token accounting for the fresh preflight request."""

    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)

    @model_validator(mode="after")
    def require_consistent_total(self) -> Self:
        if self.total_tokens != self.input_tokens + self.output_tokens:
            raise ValueError("total_tokens must equal input_tokens + output_tokens")
        return self


class RealModelVersionSet(CommerceModel):
    """Independent versions needed to attribute a real-model result."""

    prompt_version: str = Field(min_length=1)
    context_version: str = Field(min_length=1)
    router_version: str = Field(min_length=1)
    skill_version: str = Field(min_length=1)


class ProviderFailure(CommerceModel):
    """Secret-free provider exception details used by deterministic classification."""

    exception_type: str = Field(min_length=1)
    status_code: int | None = Field(default=None, ge=100, le=599)
    error_code: str | None = Field(default=None, min_length=1)
    message: str = ""


class RealModelPreflightResult(CommerceModel):
    """Immutable persisted evidence for one fresh preflight attempt."""

    schema_version: str = "1.0"
    run_id: str = Field(min_length=1)
    status: PreflightStatus
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
    system_fingerprint: str | None = Field(default=None, min_length=1)
    token_usage: TokenUsage | None = None
    latency_ms: float = Field(ge=0.0)
    request_attempt_count: int = Field(ge=0)
    retry_count: int = Field(ge=0)
    configured_max_retries: int = Field(ge=0)
    stop_reason: str | None = Field(default=None, min_length=1)
    http_status_code: int | None = Field(default=None, ge=100, le=599)
    error_code: str | None = Field(default=None, min_length=1)
    error_message: str | None = Field(default=None, min_length=1)
    request_nonce_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    response_content_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    versions: RealModelVersionSet

    @property
    def passed(self) -> bool:
        return self.status is PreflightStatus.PASSED

    @model_validator(mode="after")
    def fail_closed_on_incomplete_pass_evidence(self) -> Self:
        if self.retry_count != max(0, self.request_attempt_count - 1):
            raise ValueError("retry_count must equal request_attempt_count - 1")

        if not self.passed:
            if self.error_code is None or self.error_message is None:
                raise ValueError("Blocked preflight result requires error_code and error_message")
            return self

        if not is_official_deepseek_endpoint(self.endpoint):
            raise ValueError("Passed preflight requires the official DeepSeek API endpoint")
        if self.provider_class != EXPECTED_PROVIDER_CLASS:
            raise ValueError("Passed preflight requires the approved PatchedChatDeepSeek provider class")
        if not is_verified_deepseek_v4_identity(self.actual_model_identity):
            raise ValueError("Passed preflight requires explicit server-side DeepSeek V4 identity")

        required_fields = {
            "identity_evidence_source": self.identity_evidence_source,
            "provider_request_id": self.provider_request_id,
            "provider_request_id_source": self.provider_request_id_source,
            "provider_response_id": self.provider_response_id,
            "token_usage": self.token_usage,
            "stop_reason": self.stop_reason,
            "request_nonce_sha256": self.request_nonce_sha256,
            "response_content_sha256": self.response_content_sha256,
        }
        missing = [name for name, value in required_fields.items() if value is None]
        if missing:
            raise ValueError(f"Passed preflight is missing required telemetry: {', '.join(missing)}")
        if self.request_attempt_count < 1:
            raise ValueError("Passed preflight requires request_attempt_count of at least one")
        if self.token_usage is not None and self.token_usage.input_tokens < 1:
            raise ValueError("Passed preflight requires provider-reported input tokens")
        if self.error_code is not None or self.error_message is not None:
            raise ValueError("Passed preflight cannot carry an error")
        return self


class PreflightAuditStore:
    """Write one immutable, secret-free JSON record for every preflight run."""

    def __init__(self, root: Path):
        self._root = root

    def persist(self, result: RealModelPreflightResult) -> Path:
        self._root.mkdir(parents=True, exist_ok=True)
        path = self._root / f"{result.run_id}.json"
        payload = result.model_dump(mode="json")
        with path.open("x", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2, sort_keys=True)
            file.write("\n")
        return path


def is_verified_deepseek_v4_identity(identity: str | None) -> bool:
    """Accept only an explicit server-returned DeepSeek V4-family identifier."""

    if not identity:
        return False
    return _DEEPSEEK_V4_IDENTITY.match(identity.strip()) is not None


def is_official_deepseek_endpoint(endpoint: str) -> bool:
    parsed = urlparse(endpoint)
    return parsed.scheme == "https" and parsed.hostname == OFFICIAL_DEEPSEEK_HOST


def classify_provider_failure(failure: ProviderFailure) -> PreflightStatus:
    """Classify a real provider failure without retrying or changing models."""

    exception_type = failure.exception_type.casefold()
    code = (failure.error_code or "").casefold()
    message = failure.message.casefold()
    combined = f"{exception_type} {code} {message}"

    if failure.status_code in {401, 403} or any(term in combined for term in ("authentication", "invalid_api_key", "unauthorized", "permissiondenied")):
        return PreflightStatus.BLOCKED_AUTH_FAILED

    quota_terms = (
        "insufficient_balance",
        "insufficient balance",
        "insufficient_quota",
        "quota exhausted",
        "quota_exhausted",
        "out of credits",
        "payment required",
        "billing",
    )
    if failure.status_code == 402 or any(term in combined for term in quota_terms):
        return PreflightStatus.BLOCKED_QUOTA_EXHAUSTED

    return PreflightStatus.BLOCKED_UNAVAILABLE


def sanitize_error_message(message: str, *, secrets: Sequence[str] = ()) -> str:
    """Remove known credentials and common authorization forms before persistence."""

    sanitized = message
    for secret in secrets:
        if secret:
            sanitized = sanitized.replace(secret, "[REDACTED]")
    for pattern in _SECRET_PATTERNS:
        sanitized = pattern.sub(r"\1[REDACTED]", sanitized)
    sanitized = " ".join(sanitized.split())
    return sanitized[:1000] or "Provider request failed without an error message"


def _default_versions() -> RealModelVersionSet:
    return RealModelVersionSet(
        prompt_version=PREFLIGHT_PROMPT_VERSION,
        context_version=PREFLIGHT_CONTEXT_VERSION,
        router_version="not-applicable@1.0.0",
        skill_version="not-applicable@1.0.0",
    )


def _default_audit_store() -> PreflightAuditStore:
    configured = os.getenv("COMMERCE_REAL_MODEL_AUDIT_DIR")
    return PreflightAuditStore(Path(configured).expanduser() if configured else _DEFAULT_AUDIT_ROOT)


def _raw_model_target(config_path: Path, alias: str) -> tuple[str, str, str]:
    """Read non-secret target metadata even when credential interpolation fails."""

    try:
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return "<unreadable>", "<unreadable>", "<unreadable>"
    models = payload.get("models") or []
    model = next((item for item in models if isinstance(item, dict) and item.get("name") == alias), None)
    if model is None:
        return "<missing>", "<missing>", "<missing>"
    return (
        str(model.get("model") or "<missing>"),
        str(model.get("use") or "<missing>"),
        str(model.get("api_base") or model.get("base_url") or "<missing>"),
    )


def _model_settings_for_preflight(
    model_config: ModelConfig,
    *,
    http_client: httpx.Client,
    max_output_tokens: int = PREFLIGHT_MAX_OUTPUT_TOKENS,
) -> dict[str, Any]:
    """Create a minimal one-attempt model configuration from the real target."""

    settings = model_config.model_dump(
        exclude_none=True,
        exclude={
            "use",
            "name",
            "display_name",
            "description",
            "supports_thinking",
            "supports_reasoning_effort",
            "when_thinking_enabled",
            "when_thinking_disabled",
            "thinking",
            "supports_vision",
            "stream_chunk_timeout",
        },
    )
    if model_config.when_thinking_disabled:
        settings.update(model_config.when_thinking_disabled)
    settings.update(
        {
            "temperature": 0,
            "max_tokens": max_output_tokens,
            "max_retries": 0,
            "timeout": min(float(settings.get("timeout", PREFLIGHT_TIMEOUT_SECONDS)), PREFLIGHT_TIMEOUT_SECONDS),
            "streaming": False,
            "cache": False,
            "include_response_headers": True,
            "http_client": http_client,
        }
    )
    return settings


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _extract_token_usage(message: AIMessage) -> TokenUsage | None:
    usage = _mapping(message.usage_metadata)
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    total_tokens = usage.get("total_tokens")

    if not all(isinstance(value, int) for value in (input_tokens, output_tokens, total_tokens)):
        provider_usage = _mapping(message.response_metadata.get("token_usage"))
        input_tokens = provider_usage.get("prompt_tokens")
        output_tokens = provider_usage.get("completion_tokens")
        total_tokens = provider_usage.get("total_tokens")

    if not all(isinstance(value, int) for value in (input_tokens, output_tokens, total_tokens)):
        return None
    try:
        return TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )
    except ValueError:
        return None


def _extract_header(metadata: Mapping[str, Any], *names: str) -> tuple[str | None, str | None]:
    raw_headers = _mapping(metadata.get("headers"))
    headers = {str(key).casefold(): str(value) for key, value in raw_headers.items()}
    for name in names:
        value = headers.get(name.casefold())
        if value:
            return value, f"response_headers.{name.casefold()}"
    return None, None


def _extract_identity(metadata: Mapping[str, Any]) -> tuple[str | None, str | None]:
    for key in ("model_name", "model"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip(), f"response_metadata.{key}"
    value, source = _extract_header(metadata, "x-deepseek-model", "x-model-name", "x-model")
    return value, source


def _extract_provider_ids(metadata: Mapping[str, Any]) -> tuple[str | None, str | None, str | None]:
    request_id, source = _extract_header(metadata, "x-request-id", "x-deepseek-request-id", "request-id")
    response_id = metadata.get("id")
    provider_response_id = str(response_id) if response_id else None
    if request_id is None and provider_response_id is not None:
        request_id = provider_response_id
        source = "response_metadata.id"
    return request_id, source, provider_response_id


def _failure_from_exception(exc: Exception, *, api_key: str) -> ProviderFailure:
    status_code = getattr(exc, "status_code", None)
    if not isinstance(status_code, int):
        status_code = None
    body = getattr(exc, "body", None)
    body_mapping = _mapping(body)
    error_mapping = _mapping(body_mapping.get("error"))
    error_code = error_mapping.get("code") or body_mapping.get("code") or getattr(exc, "code", None)
    return ProviderFailure(
        exception_type=type(exc).__name__,
        status_code=status_code,
        error_code=str(error_code) if error_code else None,
        message=sanitize_error_message(str(exc), secrets=(api_key,)),
    )


def _blocked_result(
    *,
    run_id: str,
    checked_at: datetime,
    status: PreflightStatus,
    alias: str,
    configured_model: str,
    provider_class: str,
    endpoint: str,
    configured_max_retries: int,
    request_attempt_count: int,
    latency_ms: float,
    error_code: str,
    error_message: str,
    versions: RealModelVersionSet,
    actual_model_identity: str | None = None,
    identity_evidence_source: str | None = None,
    provider_request_id: str | None = None,
    provider_request_id_source: str | None = None,
    provider_response_id: str | None = None,
    system_fingerprint: str | None = None,
    token_usage: TokenUsage | None = None,
    stop_reason: str | None = None,
    http_status_code: int | None = None,
    request_nonce_sha256: str | None = None,
    response_content_sha256: str | None = None,
) -> RealModelPreflightResult:
    return RealModelPreflightResult(
        run_id=run_id,
        status=status,
        checked_at=checked_at,
        configured_alias=alias,
        configured_model=configured_model,
        provider_class=provider_class,
        endpoint=endpoint,
        actual_model_identity=actual_model_identity,
        identity_evidence_source=identity_evidence_source,
        provider_request_id=provider_request_id,
        provider_request_id_source=provider_request_id_source,
        provider_response_id=provider_response_id,
        system_fingerprint=system_fingerprint,
        token_usage=token_usage,
        latency_ms=latency_ms,
        request_attempt_count=request_attempt_count,
        retry_count=max(0, request_attempt_count - 1),
        configured_max_retries=configured_max_retries,
        stop_reason=stop_reason,
        http_status_code=http_status_code,
        error_code=error_code,
        error_message=error_message,
        request_nonce_sha256=request_nonce_sha256,
        response_content_sha256=response_content_sha256,
        versions=versions,
    )


def run_real_model_preflight(
    *,
    model_alias: str = DEFAULT_MODEL_ALIAS,
    config_path: str | None = None,
    app_config: AppConfig | None = None,
    audit_store: PreflightAuditStore | None = None,
    versions: RealModelVersionSet | None = None,
) -> RealModelPreflightResult:
    """Make one fresh DeepSeek request, persist its audit, and return the gate result."""

    run_id = f"preflight-{uuid.uuid4().hex}"
    checked_at = datetime.now(UTC)
    versions = versions or _default_versions()
    store = audit_store or _default_audit_store()
    resolved_config_path = AppConfig.resolve_config_path(config_path)
    load_dotenv(resolved_config_path.parent / ".env", override=False)
    load_dotenv(_REPO_ROOT / ".env", override=False)

    raw_model, raw_provider, raw_endpoint = _raw_model_target(resolved_config_path, model_alias)
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        result = _blocked_result(
            run_id=run_id,
            checked_at=checked_at,
            status=PreflightStatus.BLOCKED_AUTH_FAILED,
            alias=model_alias,
            configured_model=raw_model,
            provider_class=raw_provider,
            endpoint=raw_endpoint,
            configured_max_retries=0,
            request_attempt_count=0,
            latency_ms=0.0,
            error_code="deepseek_api_key_missing",
            error_message="DEEPSEEK_API_KEY is not available; no model request was attempted",
            versions=versions,
        )
        store.persist(result)
        return result

    try:
        config = app_config or AppConfig.from_file(str(resolved_config_path))
        model_config = config.get_model_config(model_alias)
    except Exception as exc:
        failure = _failure_from_exception(exc, api_key=api_key)
        result = _blocked_result(
            run_id=run_id,
            checked_at=checked_at,
            status=classify_provider_failure(failure),
            alias=model_alias,
            configured_model=raw_model,
            provider_class=raw_provider,
            endpoint=raw_endpoint,
            configured_max_retries=0,
            request_attempt_count=0,
            latency_ms=0.0,
            error_code=failure.error_code or "model_configuration_invalid",
            error_message=failure.message,
            http_status_code=failure.status_code,
            versions=versions,
        )
        store.persist(result)
        return result

    if model_config is None:
        result = _blocked_result(
            run_id=run_id,
            checked_at=checked_at,
            status=PreflightStatus.BLOCKED_UNAVAILABLE,
            alias=model_alias,
            configured_model=raw_model,
            provider_class=raw_provider,
            endpoint=raw_endpoint,
            configured_max_retries=0,
            request_attempt_count=0,
            latency_ms=0.0,
            error_code="configured_model_alias_missing",
            error_message=f"Configured model alias {model_alias!r} was not found",
            versions=versions,
        )
        store.persist(result)
        return result

    configured_model = model_config.model
    provider_class = model_config.use
    settings_preview = model_config.model_dump(exclude_none=True)
    endpoint = str(settings_preview.get("api_base") or settings_preview.get("base_url") or raw_endpoint)
    configured_max_retries = int(settings_preview.get("max_retries", 0))

    if provider_class != EXPECTED_PROVIDER_CLASS or not is_official_deepseek_endpoint(endpoint):
        result = _blocked_result(
            run_id=run_id,
            checked_at=checked_at,
            status=PreflightStatus.BLOCKED_IDENTITY_UNVERIFIED,
            alias=model_alias,
            configured_model=configured_model,
            provider_class=provider_class,
            endpoint=endpoint,
            configured_max_retries=configured_max_retries,
            request_attempt_count=0,
            latency_ms=0.0,
            error_code="untrusted_provider_configuration",
            error_message="DeepSeek V4 identity cannot be verified through a non-approved provider class or non-official endpoint",
            versions=versions,
        )
        store.persist(result)
        return result

    request_attempt_count = 0

    def count_request(_: httpx.Request) -> None:
        nonlocal request_attempt_count
        request_attempt_count += 1

    http_client = httpx.Client(event_hooks={"request": [count_request]})
    request_nonce_sha256 = hashlib.sha256(run_id.encode("utf-8")).hexdigest()
    started = time.perf_counter()
    try:
        model_class = resolve_class(provider_class, BaseChatModel)
        model = model_class(**_model_settings_for_preflight(model_config, http_client=http_client))
        response = model.invoke(
            [
                SystemMessage(content="You are serving a provider identity preflight. Follow the response format exactly."),
                HumanMessage(content=f"Fresh request nonce: {run_id}. Return exactly: {PREFLIGHT_RESPONSE_MARKER}"),
            ]
        )
        if not isinstance(response, AIMessage):
            raise TypeError(f"Expected AIMessage from provider, received {type(response).__name__}")
        latency_ms = (time.perf_counter() - started) * 1000
    except Exception as exc:
        latency_ms = (time.perf_counter() - started) * 1000
        failure = _failure_from_exception(exc, api_key=api_key)
        result = _blocked_result(
            run_id=run_id,
            checked_at=checked_at,
            status=classify_provider_failure(failure),
            alias=model_alias,
            configured_model=configured_model,
            provider_class=provider_class,
            endpoint=endpoint,
            configured_max_retries=configured_max_retries,
            request_attempt_count=request_attempt_count,
            latency_ms=latency_ms,
            error_code=failure.error_code or failure.exception_type,
            error_message=failure.message,
            http_status_code=failure.status_code,
            request_nonce_sha256=request_nonce_sha256,
            versions=versions,
        )
        store.persist(result)
        return result
    finally:
        http_client.close()

    metadata = _mapping(response.response_metadata)
    actual_model_identity, identity_source = _extract_identity(metadata)
    provider_request_id, request_id_source, provider_response_id = _extract_provider_ids(metadata)
    token_usage = _extract_token_usage(response)
    stop_reason_value = metadata.get("finish_reason")
    stop_reason = str(stop_reason_value) if stop_reason_value else None
    fingerprint_value = metadata.get("system_fingerprint")
    system_fingerprint = str(fingerprint_value) if fingerprint_value else None
    response_text = response.text
    response_content_sha256 = hashlib.sha256(response_text.encode("utf-8")).hexdigest()

    if not is_verified_deepseek_v4_identity(actual_model_identity):
        result = _blocked_result(
            run_id=run_id,
            checked_at=checked_at,
            status=PreflightStatus.BLOCKED_IDENTITY_UNVERIFIED,
            alias=model_alias,
            configured_model=configured_model,
            provider_class=provider_class,
            endpoint=endpoint,
            configured_max_retries=configured_max_retries,
            request_attempt_count=request_attempt_count,
            latency_ms=latency_ms,
            error_code="server_model_identity_not_deepseek_v4",
            error_message=f"Server returned unverified model identity {actual_model_identity!r}",
            versions=versions,
            actual_model_identity=actual_model_identity,
            identity_evidence_source=identity_source,
            provider_request_id=provider_request_id,
            provider_request_id_source=request_id_source,
            provider_response_id=provider_response_id,
            system_fingerprint=system_fingerprint,
            token_usage=token_usage,
            stop_reason=stop_reason,
            http_status_code=200,
            request_nonce_sha256=request_nonce_sha256,
            response_content_sha256=response_content_sha256,
        )
        store.persist(result)
        return result

    if response_text.strip() != PREFLIGHT_RESPONSE_MARKER:
        result = _blocked_result(
            run_id=run_id,
            checked_at=checked_at,
            status=PreflightStatus.BLOCKED_UNAVAILABLE,
            alias=model_alias,
            configured_model=configured_model,
            provider_class=provider_class,
            endpoint=endpoint,
            configured_max_retries=configured_max_retries,
            request_attempt_count=request_attempt_count,
            latency_ms=latency_ms,
            error_code="preflight_response_marker_mismatch",
            error_message="Provider response did not match the versioned preflight marker",
            versions=versions,
            actual_model_identity=actual_model_identity,
            identity_evidence_source=identity_source,
            provider_request_id=provider_request_id,
            provider_request_id_source=request_id_source,
            provider_response_id=provider_response_id,
            system_fingerprint=system_fingerprint,
            token_usage=token_usage,
            stop_reason=stop_reason,
            http_status_code=200,
            request_nonce_sha256=request_nonce_sha256,
            response_content_sha256=response_content_sha256,
        )
        store.persist(result)
        return result

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
        result = _blocked_result(
            run_id=run_id,
            checked_at=checked_at,
            status=PreflightStatus.BLOCKED_UNAVAILABLE,
            alias=model_alias,
            configured_model=configured_model,
            provider_class=provider_class,
            endpoint=endpoint,
            configured_max_retries=configured_max_retries,
            request_attempt_count=request_attempt_count,
            latency_ms=latency_ms,
            error_code="required_provider_telemetry_missing",
            error_message=f"Provider response omitted required telemetry: {', '.join(missing_telemetry)}",
            versions=versions,
            actual_model_identity=actual_model_identity,
            identity_evidence_source=identity_source,
            provider_request_id=provider_request_id,
            provider_request_id_source=request_id_source,
            provider_response_id=provider_response_id,
            system_fingerprint=system_fingerprint,
            token_usage=token_usage,
            stop_reason=stop_reason,
            http_status_code=200,
            request_nonce_sha256=request_nonce_sha256,
            response_content_sha256=response_content_sha256,
        )
        store.persist(result)
        return result

    result = RealModelPreflightResult(
        run_id=run_id,
        status=PreflightStatus.PASSED,
        checked_at=checked_at,
        configured_alias=model_alias,
        configured_model=configured_model,
        provider_class=provider_class,
        endpoint=endpoint,
        actual_model_identity=actual_model_identity,
        identity_evidence_source=identity_source,
        provider_request_id=provider_request_id,
        provider_request_id_source=request_id_source,
        provider_response_id=provider_response_id,
        system_fingerprint=system_fingerprint,
        token_usage=token_usage,
        latency_ms=latency_ms,
        request_attempt_count=request_attempt_count,
        retry_count=max(0, request_attempt_count - 1),
        configured_max_retries=configured_max_retries,
        stop_reason=stop_reason,
        http_status_code=200,
        request_nonce_sha256=request_nonce_sha256,
        response_content_sha256=response_content_sha256,
        versions=versions,
    )
    store.persist(result)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the fail-closed real DeepSeek V4 preflight")
    parser.add_argument("--model-alias", default=DEFAULT_MODEL_ALIAS)
    parser.add_argument("--config-path")
    parser.add_argument("--audit-dir")
    args = parser.parse_args(argv)

    store = PreflightAuditStore(Path(args.audit_dir).expanduser()) if args.audit_dir else None
    result = run_real_model_preflight(
        model_alias=args.model_alias,
        config_path=args.config_path,
        audit_store=store,
    )
    print(result.model_dump_json(indent=2))
    return 0 if result.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
