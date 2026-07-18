"""Deterministic Metric Registry and seller-window calculation contracts."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from app.commerce.data.gold_cases import load_evaluation_case
from app.commerce.data.intake import DataIntakeService
from app.commerce.data.normalized import OlistAdapter
from app.commerce.data.profiler import DataProfiler
from app.commerce.data.semantic_mapper import SemanticMapper
from app.commerce.domain.enums import SemanticStatus
from app.commerce.domain.ids import WorkspaceId
from app.commerce.metrics.registry import MetricEngine, MetricName, MetricRegistry, MetricWindow

REPO_ROOT = Path(__file__).parents[4]
CASES_ROOT = REPO_ROOT / "evals" / "commerce" / "cases"


def _normalized_gold_case(tmp_path: Path, case_key: str):
    case_dir = CASES_ROOT / case_key
    evaluation_case = load_evaluation_case(case_dir)
    sources = tuple(case_dir / file.relative_path for file in evaluation_case.input_bundle.files)
    storage_root = tmp_path / case_key
    manifest = DataIntakeService(storage_root=storage_root).ingest(WorkspaceId.new(), sources)
    profile = DataProfiler(storage_root=storage_root).profile(manifest)
    mappings = SemanticMapper().map(profile)
    return OlistAdapter(storage_root=storage_root).normalize(manifest, mappings)


def test_metric_registry_has_unique_versioned_definitions():
    registry = MetricRegistry()

    assert {definition.name for definition in registry.definitions} == set(MetricName)
    assert len({definition.formula_version for definition in registry.definitions}) == len(registry.definitions)
    assert all(definition.required_fields for definition in registry.definitions)


def test_fulfillment_window_metrics_match_frozen_gold_case(tmp_path: Path):
    normalized = _normalized_gold_case(tmp_path, "GC-FULFILLMENT-001")
    engine = MetricEngine()
    seller_id = "4869f7a5dfa277a7dca6462dcf3b52b2"

    baseline = engine.compute_seller_window(
        normalized,
        seller_id=seller_id,
        window=MetricWindow(start=datetime(2017, 12, 2), end=datetime(2018, 1, 31)),
    )
    anomaly = engine.compute_seller_window(
        normalized,
        seller_id=seller_id,
        window=MetricWindow(start=datetime(2018, 1, 31), end=datetime(2018, 4, 1)),
    )

    assert float(baseline.metric(MetricName.ORDER_COUNT).value) == 141
    assert float(baseline.metric(MetricName.LATE_DELIVERY_RATE).value) == pytest.approx(0.03546099290780142)
    assert float(baseline.metric(MetricName.AVERAGE_REVIEW_SCORE).value) == pytest.approx(4.228571428571429)
    assert float(baseline.metric(MetricName.HANDLING_TIME_HOURS).value) == pytest.approx(50.06023640661939)
    assert float(baseline.metric(MetricName.TRANSIT_TIME_HOURS).value) == pytest.approx(300.5057781717888)

    assert float(anomaly.metric(MetricName.ORDER_COUNT).value) == 202
    assert float(anomaly.metric(MetricName.LATE_DELIVERY_RATE).value) == pytest.approx(0.35148514851485146)
    assert float(anomaly.metric(MetricName.AVERAGE_REVIEW_SCORE).value) == pytest.approx(3.5979899497487438)
    assert float(anomaly.metric(MetricName.HANDLING_TIME_HOURS).value) == pytest.approx(46.83626512651265)
    assert float(anomaly.metric(MetricName.TRANSIT_TIME_HOURS).value) == pytest.approx(494.83323569856987)


def test_known_metric_observation_is_versioned_and_traceable(tmp_path: Path):
    normalized = _normalized_gold_case(tmp_path, "GC-REVIEW-002")
    snapshot = MetricEngine().compute_seller_window(
        normalized,
        seller_id="0b90b6df587eb83608a64ea8b390cf07",
        window=MetricWindow(start=datetime(2018, 4, 1), end=datetime(2018, 5, 1)),
    )

    metric = snapshot.metric(MetricName.LOW_RATING_RATE)

    assert metric.semantic_status is SemanticStatus.DERIVED
    assert metric.formula_version == "low_rating_rate@1.0.0"
    assert metric.sample_size == 18
    assert metric.numerator == 8
    assert metric.denominator == 18
    assert metric.source_fact_ids
    assert metric.window_start == datetime(2018, 4, 1)
    assert metric.window_end == datetime(2018, 5, 1)


def test_missing_review_capability_produces_unknown_metrics_not_zero(tmp_path: Path):
    normalized = _normalized_gold_case(tmp_path, "GC-CAPABILITY-003")
    snapshot = MetricEngine().compute_seller_window(
        normalized,
        seller_id="4869f7a5dfa277a7dca6462dcf3b52b2",
        window=MetricWindow(start=datetime(2018, 1, 31), end=datetime(2018, 4, 1)),
    )

    review_score = snapshot.metric(MetricName.AVERAGE_REVIEW_SCORE)
    low_rating = snapshot.metric(MetricName.LOW_RATING_RATE)

    assert review_score.semantic_status is SemanticStatus.UNKNOWN
    assert review_score.value is None
    assert "review.score" in (review_score.unknown_reason or "")
    assert low_rating.semantic_status is SemanticStatus.UNKNOWN
    assert low_rating.value is None
