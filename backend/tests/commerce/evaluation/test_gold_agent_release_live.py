"""Unified fresh DeepSeek V4 release gate for four persisted investigation Runs."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

from app.commerce.evaluation.agent_release import run_gold_agent_release_suite

REPO_ROOT = Path(__file__).parents[4]
CASES_ROOT = REPO_ROOT / "evals" / "commerce" / "cases"
CASE_KEYS = (
    "GC-FULFILLMENT-001",
    "GC-REVIEW-002",
    "GC-CAPABILITY-003",
    "GC-PEER-004",
)


@pytest.fixture
def real_deerflow_subagent_executor():
    """Replace the suite-wide circular-import mock with the real executor."""

    __import__("deerflow.agents")
    module_name = "deerflow.subagents.executor"
    package = sys.modules["deerflow.subagents"]
    original_module = sys.modules.get(module_name)
    original_attribute = getattr(package, "executor", None)
    sys.modules.pop(module_name, None)
    if hasattr(package, "executor"):
        delattr(package, "executor")
    module = importlib.import_module(module_name)
    try:
        yield module
    finally:
        sys.modules.pop(module_name, None)
        if original_module is not None:
            sys.modules[module_name] = original_module
        if original_attribute is not None:
            setattr(package, "executor", original_attribute)


@pytest.mark.real_model
@pytest.mark.anyio
async def test_four_gold_cases_complete_persisted_agent_investigation_gate(
    tmp_path,
    real_deerflow_subagent_executor,
):
    report = await run_gold_agent_release_suite(
        case_roots=tuple(CASES_ROOT / key for key in CASE_KEYS),
        workspace_root=tmp_path / "four-gold-agent-release",
    )

    assert report.passed is True
    assert tuple(item.case_key for item in report.cases) == CASE_KEYS
    assert all(item.scorecard.release_gate_eligible for item in report.cases)
    assert all(item.run_status == "completed" for item in report.cases)
    assert all(item.lease_released for item in report.cases)
    assert all(item.actual_paths == item.expected_paths for item in report.cases)
    assert all(item.verification_passed for item in report.cases)
    assert len(report.provider_request_ids) >= 14
    assert len(report.provider_request_ids) == len(set(report.provider_request_ids))
    assert all(
        evidence.actual_model_identity.startswith("deepseek-v4")
        and evidence.retry_count == 0
        for item in report.cases
        for evidence in item.model_evidence
    )
    assert report.total_tokens > 0
    assert report.total_latency_ms > 0
    assert Path(report.audit_path).is_file()
