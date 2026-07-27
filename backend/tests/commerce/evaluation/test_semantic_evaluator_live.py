"""Fresh DeepSeek V4 semantic evaluation release gate."""

from pathlib import Path

import pytest

from app.commerce.data.gold_cases import load_evaluation_case
from app.commerce.evaluation.semantic import DeepSeekSemanticEvaluator

REPO_ROOT = Path(__file__).parents[4]
CASE_ROOT = REPO_ROOT / "evals" / "commerce" / "cases" / "GC-FULFILLMENT-001"


@pytest.mark.real_model
@pytest.mark.anyio
async def test_fresh_deepseek_v4_semantic_evaluator_preserves_unknown_and_causality():
    evaluation_case = load_evaluation_case(CASE_ROOT)
    answer = (
        "The late-delivery rate recovered in the later window and the configured "
        "monitor target is currently met. The available evidence points to longer "
        "transit time while seller handling time did not worsen. Carrier and route "
        "details remain unknown. Because there is no controlled intervention or "
        "comparison group, the Action outcome remains inconclusive. Keep monitoring "
        "late_delivery_rate and reopen the Case if it exceeds the threshold."
    )

    result = await DeepSeekSemanticEvaluator().evaluate(
        evaluation_case,
        answer,
    )

    assert result.passed is True
    assert result.judgment.useful is True
    assert result.judgment.unknowns_preserved is True
    assert result.judgment.unsupported_causal_claim is False
    assert result.judgment.unsupported_private_metric_claim is False
    assert result.model_evidence.actual_model_identity.startswith("deepseek-v4")
    assert result.model_evidence.provider_request_id
    assert result.model_evidence.retry_count == 0


@pytest.mark.real_model
@pytest.mark.anyio
async def test_fresh_deepseek_v4_semantic_evaluator_rejects_correlation_as_root_cause():
    evaluation_case = load_evaluation_case(CASE_ROOT)
    answer = (
        "Transit time increased during the anomaly window and later recovered. "
        "This was the dominant driver of late delivery and the recovery window "
        "further confirmed carrier transit was the root cause. Seller handling "
        "did not worsen. Continue monitoring transit time."
    )

    result = await DeepSeekSemanticEvaluator().evaluate(
        evaluation_case,
        answer,
    )

    assert result.passed is False
    assert result.judgment.unsupported_causal_claim is True
