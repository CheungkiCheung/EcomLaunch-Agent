"""Deterministic ReviewExperience context and Tool evidence contracts."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from app.commerce.agents.review_experience import ReviewExperiencePathAgent
from app.commerce.api.data_service import CommerceDataService
from app.commerce.data.gold_cases import load_evaluation_case
from app.commerce.domain.ids import WorkspaceId
from app.commerce.metrics.registry import MetricWindow

REPO_ROOT = Path(__file__).parents[4]
CASE_ROOT = REPO_ROOT / "evals" / "commerce" / "cases" / "GC-REVIEW-002"
TARGET_SELLER_ID = "0b90b6df587eb83608a64ea8b390cf07"


def _uploaded(tmp_path):
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
    return data_service, workspace_id, view


@pytest.mark.anyio
async def test_review_prepare_scopes_metrics_and_redacted_low_rating_excerpts(tmp_path):
    data_service, workspace_id, view = _uploaded(tmp_path)

    plan = await ReviewExperiencePathAgent(data_service=data_service).prepare(
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

    metrics = plan.context.metrics
    assert metrics.baseline_order_count == 17
    assert metrics.current_order_count == 18
    assert float(metrics.baseline_average_review_score) == pytest.approx(3.8823529411764706)
    assert float(metrics.current_average_review_score) == pytest.approx(2.9444444444444446)
    assert float(metrics.baseline_low_rating_rate) == pytest.approx(4 / 17)
    assert float(metrics.current_low_rating_rate) == pytest.approx(8 / 18)
    assert metrics.baseline_late_delivery_rate == 0
    assert metrics.current_late_delivery_rate == 0

    signals = plan.context.review_signals
    assert signals.low_rating_count == 8
    assert signals.low_rating_with_text_count == 7
    assert len(signals.excerpts) == 7
    assert any("genérico" in item.text.casefold() for item in signals.excerpts)
    assert any("pirata" in item.text.casefold() for item in signals.excerpts)
    assert any("não recebi" in item.text.casefold() or "nao recebi" in item.text.casefold() for item in signals.excerpts)
    assert all("@" not in item.text for item in signals.excerpts)
    assert all(len(item.text) <= 280 for item in signals.excerpts)
    assert tuple(item.tool_name for item in plan.tool_calls) == (
        "metric_query",
        "review_signal_query",
    )
    assert all(item.status.value == "succeeded" for item in plan.tool_calls)
    assert set(plan.context.manifest.included_fact_ids) == {
        fact_id for item in signals.excerpts for fact_id in item.fact_ids
    }
    serialized = plan.context.model_dump_json().casefold()
    assert "expected_behavior" not in serialized
    assert "gold_label" not in serialized
