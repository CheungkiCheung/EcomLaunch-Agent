"""Deterministic anomaly severity, confidence, and Case-merge contracts."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.commerce.data.gold_cases import load_evaluation_case
from app.commerce.data.intake import DataIntakeService
from app.commerce.data.normalized import OlistAdapter
from app.commerce.data.profiler import DataProfiler
from app.commerce.data.semantic_mapper import SemanticMapper
from app.commerce.domain.enums import SemanticStatus
from app.commerce.domain.ids import EntityId, FactId, MetricObservationId, WorkspaceId
from app.commerce.domain.models import MetricObservation
from app.commerce.metrics.anomaly import (
    AnomalyDetector,
    AnomalySeverity,
    build_case_candidate,
)
from app.commerce.metrics.registry import MetricEngine, MetricName, MetricSnapshot, MetricWindow

REPO_ROOT = Path(__file__).parents[4]
CASES_ROOT = REPO_ROOT / "evals" / "commerce" / "cases"


def _snapshots(tmp_path: Path, case_key: str, seller_id: str, baseline: MetricWindow, current: MetricWindow):
    case_dir = CASES_ROOT / case_key
    evaluation_case = load_evaluation_case(case_dir)
    sources = tuple(case_dir / file.relative_path for file in evaluation_case.input_bundle.files)
    storage_root = tmp_path / case_key
    manifest = DataIntakeService(storage_root=storage_root).ingest(WorkspaceId.new(), sources)
    profile = DataProfiler(storage_root=storage_root).profile(manifest)
    mappings = SemanticMapper().map(profile)
    normalized = OlistAdapter(storage_root=storage_root).normalize(manifest, mappings)
    engine = MetricEngine()
    return (
        engine.compute_seller_window(normalized, seller_id=seller_id, window=baseline),
        engine.compute_seller_window(normalized, seller_id=seller_id, window=current),
    )


def test_fulfillment_anomaly_separates_transit_from_handling(tmp_path: Path):
    baseline, current = _snapshots(
        tmp_path,
        "GC-FULFILLMENT-001",
        "4869f7a5dfa277a7dca6462dcf3b52b2",
        MetricWindow(start=datetime(2017, 12, 2), end=datetime(2018, 1, 31)),
        MetricWindow(start=datetime(2018, 1, 31), end=datetime(2018, 4, 1)),
    )

    signals = AnomalyDetector().detect(baseline, current)
    by_metric = {signal.metric_name: signal for signal in signals}

    assert by_metric[MetricName.LATE_DELIVERY_RATE].severity.rank >= AnomalySeverity.HIGH.rank
    assert by_metric[MetricName.TRANSIT_TIME_HOURS].severity.rank >= AnomalySeverity.HIGH.rank
    assert by_metric[MetricName.AVERAGE_REVIEW_SCORE].severity.rank >= AnomalySeverity.HIGH.rank
    assert MetricName.HANDLING_TIME_HOURS not in by_metric
    assert by_metric[MetricName.TRANSIT_TIME_HOURS].confidence >= 0.8


def test_review_anomaly_does_not_create_late_delivery_signal(tmp_path: Path):
    baseline, current = _snapshots(
        tmp_path,
        "GC-REVIEW-002",
        "0b90b6df587eb83608a64ea8b390cf07",
        MetricWindow(start=datetime(2018, 3, 1), end=datetime(2018, 4, 1)),
        MetricWindow(start=datetime(2018, 4, 1), end=datetime(2018, 5, 1)),
    )

    signals = AnomalyDetector().detect(baseline, current)
    metrics = {signal.metric_name for signal in signals}

    assert MetricName.AVERAGE_REVIEW_SCORE in metrics
    assert MetricName.LOW_RATING_RATE in metrics
    assert MetricName.LATE_DELIVERY_RATE not in metrics


def _small_snapshot(value: float, *, start: datetime, end: datetime) -> MetricSnapshot:
    seller = EntityId.new()
    observation = MetricObservation(
        id=MetricObservationId.new(),
        workspace_id=WorkspaceId.new(),
        entity_id=seller,
        metric_name=MetricName.AVERAGE_REVIEW_SCORE.value,
        semantic_status=SemanticStatus.DERIVED,
        value=value,
        unit="score",
        formula_version="average_review_score@1.0.0",
        source_fact_ids=(FactId.new(),),
        window_start=start,
        window_end=end,
        sample_size=3,
    )
    return MetricSnapshot(
        seller_id="seller-small",
        seller_entity_id=seller,
        window=MetricWindow(start=start, end=end),
        observations=(observation,),
    )


def test_small_sample_cannot_create_high_confidence_severe_anomaly():
    baseline = _small_snapshot(5.0, start=datetime(2018, 1, 1), end=datetime(2018, 2, 1))
    current = _small_snapshot(1.0, start=datetime(2018, 2, 1), end=datetime(2018, 3, 1))

    signal = AnomalyDetector().detect(baseline, current)[0]

    assert signal.severity.rank <= AnomalySeverity.LOW.rank
    assert signal.confidence <= 0.4
    assert signal.sample_adequate is False


def test_repeated_detection_merges_into_one_case_candidate(tmp_path: Path):
    baseline, current = _snapshots(
        tmp_path,
        "GC-REVIEW-002",
        "0b90b6df587eb83608a64ea8b390cf07",
        MetricWindow(start=datetime(2018, 3, 1), end=datetime(2018, 4, 1)),
        MetricWindow(start=datetime(2018, 4, 1), end=datetime(2018, 5, 1)),
    )
    signals = AnomalyDetector().detect(baseline, current)

    first = build_case_candidate(current, signals[:1])
    repeated = build_case_candidate(current, signals)
    merged = first.merge(repeated)

    assert merged.fingerprint == first.fingerprint == repeated.fingerprint
    assert len(merged.signal_ids) == len(signals)
    assert merged.version == first.version + 1
    assert merged.suggested_case_id == first.suggested_case_id
