"""Deterministic Metric Registry and seller-window calculation contracts."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.commerce.data.gold_cases import load_evaluation_case
from app.commerce.data.intake import DataIntakeService
from app.commerce.data.normalized import OlistAdapter
from app.commerce.data.profiler import DataProfiler
from app.commerce.data.semantic_mapper import SemanticMapper
from app.commerce.domain.enums import SemanticStatus
from app.commerce.domain.ids import WorkspaceId
from app.commerce.metrics.registry import (
    MetricEngine,
    MetricName,
    MetricRegistry,
    MetricWindow,
    PeerCohortPolicy,
    PeerCohortUnavailableError,
)

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


def test_peer_cohort_uses_same_category_state_window_and_pools_only_eligible_peers(tmp_path: Path):
    normalized = _normalized_gold_case(tmp_path, "GC-PEER-004")
    target_seller_id = "e5a3438891c0bfdb9394643f95273d8e"

    snapshot = MetricEngine().compute_peer_comparison(
        normalized,
        seller_id=target_seller_id,
        window=MetricWindow(start=datetime(2018, 1, 1), end=datetime(2018, 7, 1)),
        policy=PeerCohortPolicy(
            product_category="fashion_bolsas_e_acessorios",
            min_orders_per_seller=20,
            match_seller_state=True,
            single_seller_orders_only=True,
            pure_category_orders_only=True,
        ),
    )

    assert snapshot.target.seller_id == target_seller_id
    assert snapshot.target.eligible_order_count == 59
    assert snapshot.target.late_order_count == 16
    assert float(snapshot.target_late_delivery_rate.value) == pytest.approx(16 / 59)
    assert snapshot.seller_state == "SP"
    assert snapshot.product_category == "fashion_bolsas_e_acessorios"
    assert tuple(member.seller_id for member in snapshot.peers) == (
        "643214e62b870443ccbe55ab29a4dccf",
        "6560211a19b47992c3666cc44a7e94c0",
        "b372ee768ed69e46ca8cdbd267aa7a38",
        "cab85505710c7cb9b720bceb52b01cee",
        "d57e18d5f73c7ccb7f7339b61166898d",
    )
    assert sum(member.eligible_order_count for member in snapshot.peers) == 257
    assert sum(member.late_order_count for member in snapshot.peers) == 19
    assert float(snapshot.peer_late_delivery_rate.value) == pytest.approx(19 / 257)
    assert float(snapshot.late_delivery_rate_gap) == pytest.approx((16 / 59) - (19 / 257))
    assert snapshot.peer_late_delivery_rate.formula_version == "peer_late_delivery_rate@1.0.0"
    assert snapshot.peer_late_delivery_rate.source_fact_ids


def test_peer_cohort_and_metric_ids_are_stable_for_the_same_input(tmp_path: Path):
    normalized = _normalized_gold_case(tmp_path, "GC-PEER-004")
    engine = MetricEngine()
    request = {
        "seller_id": "e5a3438891c0bfdb9394643f95273d8e",
        "window": MetricWindow(start=datetime(2018, 1, 1), end=datetime(2018, 7, 1)),
        "policy": PeerCohortPolicy(product_category="fashion_bolsas_e_acessorios"),
    }

    first = engine.compute_peer_comparison(normalized, **request)
    second = engine.compute_peer_comparison(normalized, **request)

    assert first.cohort_id == second.cohort_id
    assert first.target_late_delivery_rate.id == second.target_late_delivery_rate.id
    assert first.peer_late_delivery_rate.id == second.peer_late_delivery_rate.id

    invalid = first.model_dump(mode="python")
    invalid["peers"] = (first.target, *first.peers)
    with pytest.raises(ValidationError, match="cannot include the target seller"):
        type(first).model_validate(invalid)


def test_geographic_order_count_executes_customer_state_join_without_double_counting(tmp_path: Path):
    normalized = _normalized_gold_case(tmp_path, "GC-PEER-004")

    snapshot = MetricEngine().compute_geographic_order_count(
        normalized,
        seller_id="e5a3438891c0bfdb9394643f95273d8e",
        window=MetricWindow(start=datetime(2018, 1, 1), end=datetime(2018, 7, 1)),
    )

    assert snapshot.total_order_count == 59
    assert int(snapshot.segment("SP").observation.value) == 26
    assert int(snapshot.segment("MG").observation.value) == 8
    assert int(snapshot.segment("RJ").observation.value) == 7
    assert sum(int(segment.observation.value) for segment in snapshot.segments) == 59
    assert all(segment.observation.formula_version == "geographic_order_count@1.0.0" for segment in snapshot.segments)
    assert all(segment.observation.source_fact_ids for segment in snapshot.segments)


def test_peer_cohort_fails_explicitly_when_minimum_sample_removes_target(tmp_path: Path):
    normalized = _normalized_gold_case(tmp_path, "GC-PEER-004")

    with pytest.raises(PeerCohortUnavailableError, match="Target seller has 59 comparable orders"):
        MetricEngine().compute_peer_comparison(
            normalized,
            seller_id="e5a3438891c0bfdb9394643f95273d8e",
            window=MetricWindow(start=datetime(2018, 1, 1), end=datetime(2018, 7, 1)),
            policy=PeerCohortPolicy(
                product_category="fashion_bolsas_e_acessorios",
                min_orders_per_seller=100,
            ),
        )


def test_peer_policy_cannot_enable_ambiguous_multi_seller_or_mixed_category_attribution():
    with pytest.raises(ValidationError):
        PeerCohortPolicy(
            product_category="fashion_bolsas_e_acessorios",
            single_seller_orders_only=False,
        )

    with pytest.raises(ValidationError):
        PeerCohortPolicy(
            product_category="fashion_bolsas_e_acessorios",
            pure_category_orders_only=False,
        )


def test_missing_customer_state_produces_unknown_geography_not_zero(tmp_path: Path):
    normalized = _normalized_gold_case(tmp_path, "GC-PEER-004")
    without_customer_state = normalized.model_copy(update={"facts": tuple(fact for fact in normalized.facts if fact.name != "customer.state")})

    snapshot = MetricEngine().compute_geographic_order_count(
        without_customer_state,
        seller_id="e5a3438891c0bfdb9394643f95273d8e",
        window=MetricWindow(start=datetime(2018, 1, 1), end=datetime(2018, 7, 1)),
    )

    assert snapshot.semantic_status is SemanticStatus.UNKNOWN
    assert snapshot.total_order_count is None
    assert snapshot.segments == ()
    assert "customer.state" in (snapshot.unknown_reason or "")
