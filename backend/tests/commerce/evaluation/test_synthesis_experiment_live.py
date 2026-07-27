"""Fresh DeepSeek V4 control/candidate Experiment release evidence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.commerce.evaluation.experiment import ExperimentDecision
from app.commerce.evaluation.run_experiment import run_default_experiment

REPO_ROOT = Path(__file__).parents[4]
CASE_ROOT = REPO_ROOT / "evals" / "commerce" / "cases" / "GC-FULFILLMENT-001"


@pytest.mark.real_model
@pytest.mark.anyio
async def test_fresh_deepseek_v4_control_candidate_experiment_is_auditable(
    tmp_path,
):
    result = await run_default_experiment(
        case_root=CASE_ROOT,
        registry_root=tmp_path / "experiments",
        repetitions=2,
    )

    assert result.definition_path.is_file()
    assert result.report_path.is_file()
    assert len(result.runs) == 4
    assert result.report.decision in set(ExperimentDecision)
    assert {item.record.variant_name for item in result.runs} == {
        "control",
        "candidate",
    }
    all_evidence = tuple(evidence for item in result.runs for evidence in item.record.all_model_evidence)
    request_ids = tuple(item.provider_request_id for item in all_evidence)
    assert len(request_ids) == 8
    assert len(request_ids) == len(set(request_ids))
    assert all(item.actual_model_identity.startswith("deepseek-v4") for item in all_evidence)
    assert all(item.retry_count == 0 for item in all_evidence)
    candidate_runs = [item for item in result.runs if item.record.variant_name == "candidate"]
    assert all(item.record.scorecard.dimension_scores["semantic_evaluator"] == 1 for item in candidate_runs)
    assert all(item.record.scorecard.release_gate_eligible for item in candidate_runs)
    for item in result.runs:
        payload = json.loads(item.audit_path.read_text(encoding="utf-8"))
        assert payload["raw_output"]
        assert payload["trace"]["context_sha256"]
        assert payload["record"]["raw_output_sha256"]
        assert payload["record"]["trace_sha256"]
