"""Deterministic Olist adapter and normalized-fact contracts."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.commerce.data.gold_cases import load_evaluation_case
from app.commerce.data.intake import DataIntakeService
from app.commerce.data.normalized import EntityType, OlistAdapter
from app.commerce.data.profiler import DataProfiler
from app.commerce.data.semantic_mapper import SemanticField, SemanticMapper
from app.commerce.domain.enums import SemanticStatus
from app.commerce.domain.ids import WorkspaceId

REPO_ROOT = Path(__file__).parents[4]
CASES_ROOT = REPO_ROOT / "evals" / "commerce" / "cases"


def _normalize_gold_case(tmp_path: Path, case_key: str):
    case_dir = CASES_ROOT / case_key
    evaluation_case = load_evaluation_case(case_dir)
    sources = tuple(case_dir / file.relative_path for file in evaluation_case.input_bundle.files)
    storage_root = tmp_path / case_key
    manifest = DataIntakeService(storage_root=storage_root).ingest(WorkspaceId.new(), sources)
    profile = DataProfiler(storage_root=storage_root).profile(manifest)
    mappings = SemanticMapper().map(profile)
    return OlistAdapter(storage_root=storage_root).normalize(manifest, mappings), manifest, mappings


def test_olist_adapter_creates_entity_scoped_facts_not_a_wide_table(tmp_path: Path):
    normalized, _, _ = _normalize_gold_case(tmp_path, "GC-FULFILLMENT-001")

    assert len(normalized.entities_of_type(EntityType.ORDER)) == 554
    assert len(normalized.entities_of_type(EntityType.ORDER_ITEM)) == 563
    assert len(normalized.entities_of_type(EntityType.REVIEW)) == 549
    assert len(normalized.entities_of_type(EntityType.PRODUCT)) == 47
    assert len(normalized.entities_of_type(EntityType.CUSTOMER)) == 554
    assert len(normalized.entities_of_type(EntityType.SELLER)) == 1
    assert not hasattr(normalized, "wide_rows")


def test_normalized_fact_preserves_canonical_and_raw_source_fields(tmp_path: Path):
    normalized, _, _ = _normalize_gold_case(tmp_path, "GC-FULFILLMENT-001")
    order = normalized.entities_of_type(EntityType.ORDER)[0]

    purchased = normalized.fact(order.id, SemanticField.PURCHASED_AT.value)

    assert purchased.semantic_status is SemanticStatus.OBSERVED
    assert isinstance(purchased.value, datetime)
    assert purchased.name == "order.purchased_at"
    assert purchased.semantic_version == "commerce-semantics@1.0.0"
    assert purchased.source is not None
    assert purchased.source.table_name == "orders"
    assert purchased.source.column_name == "order_purchase_timestamp"
    assert "order_id=" in (purchased.source.record_locator or "")


def test_missing_source_cell_becomes_explicit_unknown_fact(tmp_path: Path):
    normalized, _, _ = _normalize_gold_case(tmp_path, "GC-FULFILLMENT-001")

    comments = normalized.facts_named(SemanticField.REVIEW_COMMENT.value)
    unknown_comments = [fact for fact in comments if fact.semantic_status is SemanticStatus.UNKNOWN]

    assert unknown_comments
    assert all(fact.value is None for fact in unknown_comments)
    assert all("empty" in (fact.unknown_reason or "") for fact in unknown_comments)


def test_normalized_entity_and_fact_ids_are_deterministic(tmp_path: Path):
    normalized, manifest, mappings = _normalize_gold_case(tmp_path, "GC-REVIEW-002")
    storage_root = tmp_path / "GC-REVIEW-002"

    repeated = OlistAdapter(storage_root=storage_root).normalize(manifest, mappings)

    assert [entity.id for entity in repeated.entities] == [entity.id for entity in normalized.entities]
    assert [fact.id for fact in repeated.facts] == [fact.id for fact in normalized.facts]


def test_capability_ablation_produces_no_review_entities_or_facts(tmp_path: Path):
    normalized, _, _ = _normalize_gold_case(tmp_path, "GC-CAPABILITY-003")

    assert normalized.entities_of_type(EntityType.REVIEW) == ()
    assert normalized.facts_named(SemanticField.REVIEW_SCORE.value) == ()
