"""Fresh real DeepSeek V4 behavior gate for ReviewExperiencePathAgent."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from app.commerce.agents.claim_policy import unsupported_causal_phrases
from app.commerce.agents.review_experience import (
    ReviewExperienceAuditStore,
    ReviewExperiencePathAgent,
)
from app.commerce.api.data_service import CommerceDataService
from app.commerce.data.gold_cases import load_evaluation_case
from app.commerce.domain.ids import WorkspaceId
from app.commerce.metrics.registry import MetricWindow

REPO_ROOT = Path(__file__).parents[4]
CASE_ROOT = REPO_ROOT / "evals" / "commerce" / "cases" / "GC-REVIEW-002"
TARGET_SELLER_ID = "0b90b6df587eb83608a64ea8b390cf07"


@pytest.mark.real_model
@pytest.mark.anyio
async def test_real_review_agent_separates_voc_signals_from_delivery_and_illegal_findings(
    tmp_path,
):
    evaluation_case = load_evaluation_case(CASE_ROOT)
    workspace_id = WorkspaceId.new()
    data_service = CommerceDataService(storage_root=tmp_path / "commerce-storage")
    view = data_service.ingest_uploads(
        workspace_id,
        tuple(
            (Path(file.relative_path).name, (CASE_ROOT / file.relative_path).read_bytes())
            for file in evaluation_case.input_bundle.files
        ),
    )
    agent = ReviewExperiencePathAgent(
        data_service=data_service,
        audit_store=ReviewExperienceAuditStore(
            REPO_ROOT / ".deer-flow/commerce/evaluation/path-agents"
        ),
    )
    plan = await agent.prepare(
        workspace_id,
        view.manifest.dataset_id,
        seller_id=TARGET_SELLER_ID,
        baseline_window=MetricWindow(
            start=datetime(2018, 3, 1), end=datetime(2018, 4, 1)
        ),
        current_window=MetricWindow(
            start=datetime(2018, 4, 1), end=datetime(2018, 5, 1)
        ),
    )
    run = await agent.run_prepared(plan)

    assert run.telemetry.actual_model_identity is not None
    assert run.telemetry.actual_model_identity.startswith("deepseek-v4")
    assert run.telemetry.provider_request_id
    assert run.telemetry.token_usage is not None
    assert run.telemetry.request_attempt_count == 1
    assert run.telemetry.retry_count == 0
    assert Path(run.audit_path).is_file()
    assert tuple(item.tool_name for item in run.result.tool_calls) == (
        "metric_query",
        "review_signal_query",
    )
    assert run.result.cost.tool_call_count == 2

    metrics = run.context.metrics
    review_metric_ids = {
        metrics.baseline_average_review_score_id,
        metrics.current_average_review_score_id,
        metrics.baseline_low_rating_rate_id,
        metrics.current_low_rating_rate_id,
    }
    cited_metrics = {
        metric_id
        for item in run.result.observations
        for metric_id in item.metric_observation_ids
    }
    assert review_metric_ids.issubset(cited_metrics)
    late_ids = {
        metrics.baseline_late_delivery_rate_id,
        metrics.current_late_delivery_rate_id,
    }
    assert any(
        late_ids.issubset(set(item.metric_observation_ids))
        for item in run.result.observations
    )
    excerpt_fact_ids = {
        fact_id
        for item in run.context.review_signals.excerpts
        for fact_id in item.fact_ids
    }
    assert excerpt_fact_ids & {
        fact_id for item in run.result.observations for fact_id in item.fact_ids
    }

    rendered = run.result.model_dump_json().casefold()
    assert any(term in rendered for term in ("3.88", "3.882"))
    assert any(term in rendered for term in ("2.94", "2.944"))
    assert any(term in rendered for term in ("23.5", "23.53", "0.235"))
    assert any(term in rendered for term in ("44.4", "44.44", "0.444"))
    assert "late" in rendered or "delivery" in rendered
    assert any(term in rendered for term in ("0%", "0.0", "0.00", "zero"))
    assert any(term in rendered for term in ("authenticity", "counterfeit", "fake", "pirate", "generic"))
    assert any(term in rendered for term in ("missing", "not received", "quantity", "short"))
    assert any(term in rendered for term in ("allegation", "reported", "review signal", "requires verification"))
    assert not any(
        term in rendered
        for term in (
            "confirmed counterfeit",
            "confirmed fraud",
            "seller sells counterfeit",
            "确认售假",
            "确认欺诈",
            "卖家就是在售假",
            "delivery delay caused the rating decline",
            "logistics lateness caused the decline",
            "物流延迟导致评分下降",
            "配送延误是根因",
        )
    )
    assert not any(
        unsupported_causal_phrases(item.summary)
        for item in run.result.observations
    )
    assert any(
        term in rendered
        for term in (
            "diagnostic",
            "not causal",
            "unverified",
            "requires verification",
            "no finding",
            "not supported",
        )
    )

    hidden = evaluation_case.expected_behavior
    required_facts = {item.name: item for item in hidden.required_facts}
    assert required_facts["baseline.late_delivery_rate"].expected_value == 0
    assert required_facts["anomaly.late_delivery_rate"].expected_value == 0
    assert "expected_behavior" not in plan.context.model_dump_json().casefold()
