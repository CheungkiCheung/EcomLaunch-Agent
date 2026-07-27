"""Fresh DeepSeek V4 regression plus holdout Experiment release gate."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.commerce.evaluation.experiment import ExperimentDecision
from app.commerce.evaluation.run_experiment import run_experiment_suite

REPO_ROOT = Path(__file__).parents[4]
CASES_ROOT = REPO_ROOT / "evals" / "commerce" / "cases"
CASE_KEYS = (
    "GC-FULFILLMENT-001",
    "GC-REVIEW-002",
    "GC-CAPABILITY-003",
    "GC-PEER-004",
)


@pytest.mark.real_model
@pytest.mark.anyio
async def test_fresh_deepseek_v4_candidate_passes_regression_and_holdouts(
    tmp_path,
):
    result = await run_experiment_suite(
        case_roots=tuple(CASES_ROOT / key for key in CASE_KEYS),
        registry_root=tmp_path / "experiments",
        repetitions=2,
    )

    candidate_runs = tuple(item for item in result.runs if item.record.variant_name == "candidate")
    all_evidence = tuple(evidence for item in result.runs for evidence in item.record.all_model_evidence)
    request_ids = tuple(item.provider_request_id for item in all_evidence)

    assert len(result.runs) == 16
    assert len(candidate_runs) == 8
    assert {item.record.case_key for item in candidate_runs} == set(CASE_KEYS)
    assert all(item.record.scorecard.release_gate_eligible for item in candidate_runs)
    assert result.report.candidate.hard_gate_failures == 0
    assert result.report.candidate.pass_rate == 1
    assert result.report.decision is ExperimentDecision.PROMOTE_CANDIDATE
    assert len(request_ids) == 32
    assert len(request_ids) == len(set(request_ids))
    assert all(item.actual_model_identity.startswith("deepseek-v4") for item in all_evidence)
    assert all(item.retry_count == 0 for item in all_evidence)
