"""Deterministic capability-registry contracts."""

from __future__ import annotations

from pathlib import Path

from app.commerce.data.capabilities import (
    CapabilityName,
    CapabilityReasonCode,
    CapabilityRegistry,
    CapabilityStatus,
)
from app.commerce.data.gold_cases import load_evaluation_case
from app.commerce.data.intake import DataIntakeService
from app.commerce.data.profiler import DataProfiler
from app.commerce.data.semantic_mapper import SemanticMapper
from app.commerce.domain.ids import WorkspaceId

REPO_ROOT = Path(__file__).parents[4]
CASES_ROOT = REPO_ROOT / "evals" / "commerce" / "cases"


def _assess_gold_case(tmp_path: Path, case_key: str):
    case_dir = CASES_ROOT / case_key
    evaluation_case = load_evaluation_case(case_dir)
    sources = tuple(case_dir / file.relative_path for file in evaluation_case.input_bundle.files)
    storage_root = tmp_path / case_key
    manifest = DataIntakeService(storage_root=storage_root).ingest(WorkspaceId.new(), sources)
    profile = DataProfiler(storage_root=storage_root).profile(manifest)
    mappings = SemanticMapper().map(profile)
    return CapabilityRegistry().assess(profile, mappings)


def test_fulfillment_gold_case_has_two_paths_and_blocks_peer_comparison(tmp_path: Path):
    capabilities = _assess_gold_case(tmp_path, "GC-FULFILLMENT-001")

    assert capabilities.capability(CapabilityName.FULFILLMENT_DIAGNOSIS).status is CapabilityStatus.AVAILABLE
    assert capabilities.capability(CapabilityName.REVIEW_EXPERIENCE).status is CapabilityStatus.AVAILABLE
    peer = capabilities.capability(CapabilityName.SELLER_PEER_COMPARISON)
    assert peer.status is CapabilityStatus.UNAVAILABLE
    assert CapabilityReasonCode.INSUFFICIENT_ENTITY_DIVERSITY in peer.reason_codes
    assert capabilities.routable_path_agents == frozenset(
        {"FulfillmentPathAgent", "ReviewExperiencePathAgent"}
    )


def test_review_gold_case_can_skip_fulfillment_by_signal_not_by_capability(tmp_path: Path):
    capabilities = _assess_gold_case(tmp_path, "GC-REVIEW-002")

    assert capabilities.capability(CapabilityName.FULFILLMENT_DIAGNOSIS).status is CapabilityStatus.AVAILABLE
    assert capabilities.capability(CapabilityName.REVIEW_EXPERIENCE).status is CapabilityStatus.AVAILABLE


def test_capability_ablation_removes_review_experience_only(tmp_path: Path):
    full = _assess_gold_case(tmp_path, "GC-FULFILLMENT-001")
    ablated = _assess_gold_case(tmp_path, "GC-CAPABILITY-003")

    review = ablated.capability(CapabilityName.REVIEW_EXPERIENCE)
    assert review.status is CapabilityStatus.UNAVAILABLE
    assert CapabilityReasonCode.MISSING_REQUIRED_SEMANTICS in review.reason_codes
    assert {field.value for field in review.missing_required_fields} >= {"review.order_id", "review.score"}
    assert ablated.capability(CapabilityName.FULFILLMENT_DIAGNOSIS).status is CapabilityStatus.AVAILABLE
    assert full.capability(CapabilityName.REVIEW_EXPERIENCE).status is CapabilityStatus.AVAILABLE
    assert "ReviewExperiencePathAgent" not in ablated.routable_path_agents


def test_review_capability_is_partial_when_text_is_missing(tmp_path: Path):
    orders = tmp_path / "orders.csv"
    orders.write_text(
        "order_id,order_purchase_timestamp,order_approved_at,order_delivered_carrier_date,"
        "order_delivered_customer_date,order_estimated_delivery_date\n"
        "o1,2018-01-01,2018-01-01,2018-01-02,2018-01-05,2018-01-06\n",
        encoding="utf-8",
    )
    reviews = tmp_path / "order_reviews.csv"
    reviews.write_text("order_id,review_score\no1,2\n", encoding="utf-8")
    storage_root = tmp_path / "storage"
    manifest = DataIntakeService(storage_root=storage_root).ingest(WorkspaceId.new(), (orders, reviews))
    profile = DataProfiler(storage_root=storage_root).profile(manifest)
    mappings = SemanticMapper().map(profile)

    assessment = CapabilityRegistry().assess(profile, mappings).capability(CapabilityName.REVIEW_EXPERIENCE)

    assert assessment.status is CapabilityStatus.PARTIAL
    assert CapabilityReasonCode.MISSING_OPTIONAL_SEMANTICS in assessment.reason_codes
    assert {field.value for field in assessment.missing_optional_fields} == {"review.comment", "review.title"}


def test_peer_gold_case_makes_seller_peer_path_available(tmp_path: Path):
    capabilities = _assess_gold_case(tmp_path, "GC-PEER-004")

    peer = capabilities.capability(CapabilityName.SELLER_PEER_COMPARISON)

    assert peer.status is CapabilityStatus.AVAILABLE
    assert peer.reason_codes == frozenset({CapabilityReasonCode.AVAILABLE})
    assert "SellerPeerPathAgent" in capabilities.routable_path_agents
