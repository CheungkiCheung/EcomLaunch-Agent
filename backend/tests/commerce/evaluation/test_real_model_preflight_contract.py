"""Deterministic contracts for the real DeepSeek V4 release gate.

These tests validate immutable audit data, identity matching, provider-error
classification, redaction, and file persistence.  They never exercise an LLM
or substitute a fake response for one.  The actual provider call is covered by
``test_real_model_preflight_live.py``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import pytest
from pydantic import ValidationError

from app.commerce.evaluation.real_model_preflight import (
    PreflightAuditStore,
    PreflightStatus,
    ProviderFailure,
    RealModelPreflightResult,
    RealModelVersionSet,
    TokenUsage,
    _model_settings_for_preflight,
    classify_provider_failure,
    is_verified_deepseek_v4_identity,
    sanitize_error_message,
)
from deerflow.config.model_config import ModelConfig


def _versions() -> RealModelVersionSet:
    return RealModelVersionSet(
        prompt_version="commerce-real-model-preflight@1.0.0",
        context_version="commerce-preflight-context@1.0.0",
        router_version="not-applicable@1.0.0",
        skill_version="not-applicable@1.0.0",
    )


def _passed_result() -> RealModelPreflightResult:
    return RealModelPreflightResult(
        run_id="preflight-019f743c",
        status=PreflightStatus.PASSED,
        checked_at=datetime(2026, 7, 18, 10, 0, tzinfo=UTC),
        configured_alias="deepseek-reasoner",
        configured_model="deepseek-reasoner",
        provider_class="deerflow.models.patched_deepseek:PatchedChatDeepSeek",
        endpoint="https://api.deepseek.com/v1",
        actual_model_identity="deepseek-v4-flash",
        identity_evidence_source="response_metadata.model_name",
        provider_request_id="request-123",
        provider_request_id_source="response_headers.x-request-id",
        provider_response_id="response-456",
        system_fingerprint="fp_prod",
        token_usage=TokenUsage(input_tokens=8, output_tokens=2, total_tokens=10),
        latency_ms=125.5,
        request_attempt_count=1,
        retry_count=0,
        configured_max_retries=2,
        stop_reason="stop",
        request_nonce_sha256="1" * 64,
        response_content_sha256="0" * 64,
        versions=_versions(),
    )


@pytest.mark.parametrize(
    "identity",
    (
        "deepseek-v4",
        "deepseek-v4-flash",
        "DeepSeek-V4.1-Reasoner",
        "deepseek_v4_preview",
    ),
)
def test_only_explicit_deepseek_v4_family_identities_are_verified(identity: str):
    assert is_verified_deepseek_v4_identity(identity) is True


@pytest.mark.parametrize(
    "identity",
    (
        None,
        "",
        "deepseek-reasoner",
        "deepseek-chat",
        "deepseek-v3",
        "deepseek-v40",
        "vendor/deepseek-v4-flash",
        "I am DeepSeek V4",
    ),
)
def test_aliases_prompt_claims_and_other_versions_are_not_identity_proof(identity: str | None):
    assert is_verified_deepseek_v4_identity(identity) is False


def test_passed_result_requires_complete_fresh_provider_telemetry():
    result = _passed_result()

    assert result.passed is True
    assert result.actual_model_identity == "deepseek-v4-flash"
    assert result.token_usage.total_tokens == 10


@pytest.mark.parametrize(
    "field, value, expected_error",
    (
        ("actual_model_identity", "deepseek-reasoner", "DeepSeek V4"),
        ("provider_request_id", None, "provider_request_id"),
        ("stop_reason", None, "stop_reason"),
        ("token_usage", None, "token_usage"),
        ("request_nonce_sha256", None, "request_nonce_sha256"),
        ("request_attempt_count", 0, "request_attempt_count"),
    ),
)
def test_passed_result_fails_closed_when_required_evidence_is_missing(field, value, expected_error):
    payload = _passed_result().model_dump(mode="python")
    payload[field] = value

    with pytest.raises(ValidationError, match=expected_error):
        RealModelPreflightResult.model_validate(payload)


def test_non_official_endpoint_cannot_be_recorded_as_a_pass():
    payload = _passed_result().model_dump(mode="python")
    payload["endpoint"] = "https://gateway.example.com/v1"

    with pytest.raises(ValidationError, match="official DeepSeek API endpoint"):
        RealModelPreflightResult.model_validate(payload)


@pytest.mark.parametrize(
    "failure, expected",
    (
        (
            ProviderFailure(exception_type="AuthenticationError", status_code=401, error_code="invalid_api_key", message="invalid key"),
            PreflightStatus.BLOCKED_AUTH_FAILED,
        ),
        (
            ProviderFailure(exception_type="APIStatusError", status_code=402, error_code="insufficient_balance", message="payment required"),
            PreflightStatus.BLOCKED_QUOTA_EXHAUSTED,
        ),
        (
            ProviderFailure(exception_type="RateLimitError", status_code=429, error_code="insufficient_quota", message="quota exhausted"),
            PreflightStatus.BLOCKED_QUOTA_EXHAUSTED,
        ),
        (
            ProviderFailure(exception_type="RateLimitError", status_code=429, error_code="rate_limit", message="too many requests"),
            PreflightStatus.BLOCKED_UNAVAILABLE,
        ),
        (
            ProviderFailure(exception_type="APIConnectionError", message="connection refused"),
            PreflightStatus.BLOCKED_UNAVAILABLE,
        ),
        (
            ProviderFailure(exception_type="InternalServerError", status_code=503, message="service unavailable"),
            PreflightStatus.BLOCKED_UNAVAILABLE,
        ),
    ),
)
def test_provider_failures_are_classified_without_model_substitution(failure, expected):
    assert classify_provider_failure(failure) is expected


def test_error_sanitizer_never_persists_credentials():
    message = "Authorization: Bearer ds-secret-key; api_key=ds-secret-key"

    sanitized = sanitize_error_message(message, secrets=("ds-secret-key",))

    assert "ds-secret-key" not in sanitized
    assert "[REDACTED]" in sanitized


def test_preflight_explicitly_disables_response_cache_and_sdk_retries():
    config = ModelConfig(
        name="deepseek-reasoner",
        use="deerflow.models.patched_deepseek:PatchedChatDeepSeek",
        model="deepseek-reasoner",
        api_base="https://api.deepseek.com/v1",
        max_retries=5,
        max_tokens=8192,
    )

    with httpx.Client() as client:
        settings = _model_settings_for_preflight(config, http_client=client)

    assert settings["cache"] is False
    assert settings["max_retries"] == 0
    assert settings["streaming"] is False
    assert settings["max_tokens"] == 64


def test_audit_store_writes_one_immutable_json_record_per_run(tmp_path):
    result = _passed_result()
    store = PreflightAuditStore(tmp_path)

    path = store.persist(result)

    assert path.parent == tmp_path
    assert path.name == "preflight-019f743c.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert payload["actual_model_identity"] == "deepseek-v4-flash"
    assert "api_key" not in json.dumps(payload)

    with pytest.raises(FileExistsError):
        store.persist(result)
