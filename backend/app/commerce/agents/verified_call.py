"""Reusable Commerce adapter for one fresh identity-verified DeepSeek V4 call."""

from __future__ import annotations

import asyncio
import hashlib
import os
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Self

import httpx
from dotenv import load_dotenv
from langchain.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import Field, model_validator

from app.commerce.agents.model_router import ModelAssignment
from app.commerce.domain.models import CommerceModel
from app.commerce.evaluation.real_model_preflight import (
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
from deerflow.config.app_config import AppConfig
from deerflow.models.lifecycle import close_model_clients
from deerflow.reflection import resolve_class

_REPO_ROOT = Path(__file__).resolve().parents[4]


class VerifiedCallStatus(StrEnum):
    PASSED = "passed"
    BLOCKED = "blocked"


class VerifiedCallTelemetry(CommerceModel):
    schema_version: str = "commerce.verified-model-call@1.0.0"
    run_id: str = Field(min_length=1)
    preflight_run_id: str = Field(min_length=1)
    status: VerifiedCallStatus
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
    latency_ms: float = Field(ge=0)
    request_attempt_count: int = Field(ge=0)
    retry_count: int = Field(ge=0)
    configured_max_retries: int = Field(ge=0)
    stop_reason: str | None = Field(default=None, min_length=1)
    request_nonce_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    response_content_sha256: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    versions: RealModelVersionSet
    error_code: str | None = Field(default=None, min_length=1)
    error_message: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_call_evidence(self) -> Self:
        if self.retry_count != max(0, self.request_attempt_count - 1):
            raise ValueError("retry_count must equal request_attempt_count - 1")
        if self.invocation_max_output_tokens > self.model_assignment.max_output_tokens:
            raise ValueError("Invocation output cap exceeds Model Assignment")
        if self.status is VerifiedCallStatus.BLOCKED:
            if self.error_code is None or self.error_message is None:
                raise ValueError("Blocked verified call requires an error")
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
        }
        missing = [name for name, value in required.items() if value is None]
        if missing:
            raise ValueError(f"Verified call telemetry is missing: {', '.join(missing)}")
        if self.request_attempt_count != 1 or self.retry_count != 0:
            raise ValueError("Verified call must use one fresh no-retry request")
        if self.provider_class != EXPECTED_PROVIDER_CLASS:
            raise ValueError("Verified call requires approved provider class")
        if not is_official_deepseek_endpoint(self.endpoint):
            raise ValueError("Verified call requires official DeepSeek endpoint")
        if not is_verified_deepseek_v4_identity(self.actual_model_identity):
            raise ValueError("Verified call requires server-side DeepSeek V4 identity")
        if self.error_code is not None or self.error_message is not None:
            raise ValueError("Passed verified call cannot carry an error")
        return self


@dataclass(frozen=True)
class VerifiedModelResponse:
    text: str
    telemetry: VerifiedCallTelemetry
    preflight: RealModelPreflightResult


class VerifiedModelCallBlockedError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        preflight: RealModelPreflightResult | None = None,
        telemetry: VerifiedCallTelemetry | None = None,
    ) -> None:
        super().__init__(message)
        self.preflight = preflight
        self.telemetry = telemetry


@dataclass(frozen=True)
class _Invocation:
    response: AIMessage | None
    model_config: Any
    endpoint: str
    request_attempt_count: int
    latency_ms: float
    failure: ProviderFailure | None = None


class VerifiedModelCaller:
    async def call(
        self,
        *,
        assignment: ModelAssignment,
        system_prompt: str,
        user_prompt: str,
        versions: RealModelVersionSet,
        run_prefix: str,
        max_output_tokens: int,
    ) -> VerifiedModelResponse:
        invocation_cap = min(assignment.max_output_tokens, max_output_tokens)
        preflight = await asyncio.to_thread(
            run_real_model_preflight,
            model_alias=assignment.model_alias,
        )
        if not preflight.passed:
            raise VerifiedModelCallBlockedError(
                f"DeepSeek V4 preflight blocked {run_prefix}: {preflight.status.value}",
                preflight=preflight,
            )
        run_id = f"{run_prefix}-{uuid.uuid4().hex}"
        checked_at = datetime.now(UTC)
        invocation = await asyncio.to_thread(
            self._invoke,
            assignment,
            system_prompt,
            user_prompt,
            invocation_cap,
        )
        common = dict(
            run_id=run_id,
            preflight_run_id=preflight.run_id,
            checked_at=checked_at,
            model_assignment=assignment,
            invocation_max_output_tokens=invocation_cap,
            configured_alias=str(
                getattr(invocation.model_config, "name", assignment.model_alias)
            ),
            configured_model=str(
                getattr(invocation.model_config, "model", "<missing>")
            ),
            provider_class=str(getattr(invocation.model_config, "use", "<missing>")),
            endpoint=invocation.endpoint,
            latency_ms=invocation.latency_ms,
            request_attempt_count=invocation.request_attempt_count,
            retry_count=max(0, invocation.request_attempt_count - 1),
            configured_max_retries=0,
            request_nonce_sha256=hashlib.sha256(run_id.encode()).hexdigest(),
            versions=versions,
        )
        if invocation.failure is not None or invocation.response is None:
            telemetry = VerifiedCallTelemetry(
                status=VerifiedCallStatus.BLOCKED,
                error_code=(
                    invocation.failure.error_code or invocation.failure.exception_type
                    if invocation.failure is not None
                    else "model_response_missing"
                ),
                error_message=(
                    invocation.failure.message
                    if invocation.failure is not None
                    else "Model invocation returned no AIMessage"
                ),
                **common,
            )
            raise VerifiedModelCallBlockedError(
                telemetry.error_message or "Verified model call failed",
                preflight=preflight,
                telemetry=telemetry,
            )
        response = invocation.response
        metadata = _mapping(response.response_metadata)
        actual_identity, identity_source = _extract_identity(metadata)
        provider_request_id, request_id_source, provider_response_id = (
            _extract_provider_ids(metadata)
        )
        usage = _extract_token_usage(response)
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
        response_hash = hashlib.sha256(response_text.encode()).hexdigest()
        missing = [
            name
            for name, value in (
                ("actual_model_identity", actual_identity),
                ("identity_evidence_source", identity_source),
                ("provider_request_id", provider_request_id),
                ("provider_request_id_source", request_id_source),
                ("provider_response_id", provider_response_id),
                ("token_usage", usage),
                ("stop_reason", stop_reason),
            )
            if value is None
        ]
        if not is_verified_deepseek_v4_identity(actual_identity):
            missing.insert(0, "server_model_identity_not_deepseek_v4")
        if missing:
            telemetry = VerifiedCallTelemetry(
                status=VerifiedCallStatus.BLOCKED,
                actual_model_identity=actual_identity,
                identity_evidence_source=identity_source,
                provider_request_id=provider_request_id,
                provider_request_id_source=request_id_source,
                provider_response_id=provider_response_id,
                system_fingerprint=fingerprint,
                token_usage=usage,
                stop_reason=stop_reason,
                response_content_sha256=response_hash,
                error_code="required_real_model_evidence_missing",
                error_message=f"Provider response omitted or failed: {', '.join(missing)}",
                **common,
            )
            raise VerifiedModelCallBlockedError(
                telemetry.error_message or "Verified call telemetry incomplete",
                preflight=preflight,
                telemetry=telemetry,
            )
        telemetry = VerifiedCallTelemetry(
            status=VerifiedCallStatus.PASSED,
            actual_model_identity=actual_identity,
            identity_evidence_source=identity_source,
            provider_request_id=provider_request_id,
            provider_request_id_source=request_id_source,
            provider_response_id=provider_response_id,
            system_fingerprint=fingerprint,
            token_usage=usage,
            stop_reason=stop_reason,
            response_content_sha256=response_hash,
            **common,
        )
        return VerifiedModelResponse(response_text, telemetry, preflight)

    @staticmethod
    def _invoke(
        assignment: ModelAssignment,
        system_prompt: str,
        user_prompt: str,
        max_output_tokens: int,
    ) -> _Invocation:
        config_path = AppConfig.resolve_config_path()
        load_dotenv(config_path.parent / ".env", override=False)
        load_dotenv(_REPO_ROOT / ".env", override=False)
        config = AppConfig.from_file(str(config_path))
        model_config = config.get_model_config(assignment.model_alias)
        if model_config is None:
            return _Invocation(
                None,
                assignment,
                "<missing>",
                0,
                0,
                ProviderFailure(
                    exception_type="ModelConfigurationError",
                    error_code="configured_model_alias_missing",
                    message=f"Missing model alias: {assignment.model_alias}",
                ),
            )
        endpoint = str(model_config.api_base or "")
        if model_config.use != EXPECTED_PROVIDER_CLASS or not is_official_deepseek_endpoint(endpoint):
            return _Invocation(
                None,
                model_config,
                endpoint,
                0,
                0,
                ProviderFailure(
                    exception_type="ModelConfigurationError",
                    error_code="untrusted_provider_configuration",
                    message="Verified caller provider configuration is not trusted",
                ),
            )
        request_attempt_count = 0

        def count_request(_: httpx.Request) -> None:
            nonlocal request_attempt_count
            request_attempt_count += 1

        client = httpx.Client(event_hooks={"request": [count_request]})
        started = time.perf_counter()
        model = None
        try:
            model_class = resolve_class(model_config.use, BaseChatModel)
            settings = _model_settings_for_preflight(
                model_config,
                http_client=client,
                max_output_tokens=max_output_tokens,
            )
            settings["timeout"] = min(
                float(settings["timeout"]), assignment.timeout_seconds
            )
            model = model_class(**settings)
            response = model.invoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ]
            )
            if not isinstance(response, AIMessage):
                raise TypeError(f"Expected AIMessage, got {type(response).__name__}")
            return _Invocation(
                response,
                model_config,
                endpoint,
                request_attempt_count,
                (time.perf_counter() - started) * 1000,
            )
        except Exception as exc:
            return _Invocation(
                None,
                model_config,
                endpoint,
                request_attempt_count,
                (time.perf_counter() - started) * 1000,
                _failure_from_exception(
                    exc, api_key=os.getenv("DEEPSEEK_API_KEY", "")
                ),
            )
        finally:
            if model is not None:
                close_model_clients(model)
            client.close()
