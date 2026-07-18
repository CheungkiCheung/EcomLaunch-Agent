"""Capability-first DynamicPathRouter contracts using real Gold Case data."""

from __future__ import annotations

from pathlib import Path

from app.commerce.agents.contracts import PathType
from app.commerce.agents.router import (
    CaseSignalSummary,
    DynamicPathRouter,
    RouteReasonCode,
)
from app.commerce.data.capabilities import CapabilityRegistry
from app.commerce.data.gold_cases import load_evaluation_case
from app.commerce.data.intake import DataIntakeService
from app.commerce.data.profiler import DataProfiler
from app.commerce.data.semantic_mapper import SemanticMapper
from app.commerce.domain.ids import WorkspaceId
from app.commerce.metrics.registry import MetricName

REPO_ROOT = Path(__file__).parents[4]
CASES_ROOT = REPO_ROOT / "evals" / "commerce" / "cases"


def _capabilities(tmp_path: Path, case_key: str):
    case_dir = CASES_ROOT / case_key
    evaluation_case = load_evaluation_case(case_dir)
    sources = tuple(case_dir / file.relative_path for file in evaluation_case.input_bundle.files)
    storage_root = tmp_path / case_key
    manifest = DataIntakeService(storage_root=storage_root).ingest(WorkspaceId.new(), sources)
    profile = DataProfiler(storage_root=storage_root).profile(manifest)
    mappings = SemanticMapper().map(profile)
    return CapabilityRegistry().assess(profile, mappings)


def test_review_signal_does_not_launch_fulfillment_even_when_capability_exists(tmp_path):
    capabilities = _capabilities(tmp_path, "GC-REVIEW-002")
    plan = DynamicPathRouter().route(
        capabilities,
        CaseSignalSummary(
            metric_names=frozenset(
                {MetricName.AVERAGE_REVIEW_SCORE, MetricName.LOW_RATING_RATE}
            )
        ),
    )

    assert {assignment.path_type for assignment in plan.assignments} == {
        PathType.REVIEW_EXPERIENCE
    }
    fulfillment = plan.decision(PathType.FULFILLMENT)
    assert RouteReasonCode.NO_RELEVANT_SIGNAL in fulfillment.reason_codes


def test_missing_review_capability_blocks_review_path(tmp_path):
    capabilities = _capabilities(tmp_path, "GC-CAPABILITY-003")
    plan = DynamicPathRouter().route(
        capabilities,
        CaseSignalSummary(
            metric_names=frozenset({MetricName.AVERAGE_REVIEW_SCORE})
        ),
    )

    assert PathType.REVIEW_EXPERIENCE not in {
        assignment.path_type for assignment in plan.assignments
    }
    review = plan.decision(PathType.REVIEW_EXPERIENCE)
    assert RouteReasonCode.CAPABILITY_UNAVAILABLE in review.reason_codes


def test_router_selects_zero_to_three_paths_and_peer_only_when_supported(tmp_path):
    capabilities = _capabilities(tmp_path, "GC-PEER-004")
    router = DynamicPathRouter()

    empty = router.route(capabilities, CaseSignalSummary())
    peer = router.route(
        capabilities,
        CaseSignalSummary(
            metric_names=frozenset(
                {MetricName.LATE_DELIVERY_RATE, MetricName.PEER_LATE_DELIVERY_RATE}
            )
        ),
    )

    assert empty.assignments == ()
    assert 0 < len(peer.assignments) <= 3
    assert PathType.SELLER_PEER in {
        assignment.path_type for assignment in peer.assignments
    }
