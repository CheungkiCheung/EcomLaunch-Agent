"""Live release-gate test for the configured DeepSeek V4 provider.

This test always makes a fresh provider request.  It must fail, never skip or
fall back, when credentials, quota, service availability, identity evidence,
or required telemetry are unavailable.
"""

from __future__ import annotations

import pytest

from app.commerce.evaluation.real_model_preflight import (
    PreflightStatus,
    run_real_model_preflight,
)


@pytest.mark.real_model
def test_configured_provider_is_a_fresh_identity_verified_deepseek_v4_request():
    result = run_real_model_preflight()

    assert result.status is PreflightStatus.PASSED, result.model_dump_json(indent=2)
    assert result.passed is True
