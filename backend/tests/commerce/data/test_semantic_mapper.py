"""Deterministic semantic mapping and human-confirmation contracts."""

from __future__ import annotations

from pathlib import Path

from app.commerce.data.intake import DataIntakeService
from app.commerce.data.profiler import DataProfiler
from app.commerce.data.semantic_mapper import (
    MappingSource,
    MappingStatus,
    SemanticField,
    SemanticMapper,
    WorkspaceSemanticStore,
)
from app.commerce.domain.ids import WorkspaceId


def _profile(tmp_path: Path, filename: str, content: str, workspace_id: WorkspaceId | None = None):
    workspace_id = workspace_id or WorkspaceId.new()
    source = tmp_path / filename
    source.write_text(content, encoding="utf-8")
    storage_root = tmp_path / "commerce-storage"
    manifest = DataIntakeService(storage_root=storage_root).ingest(workspace_id, (source,))
    return DataProfiler(storage_root=storage_root).profile(manifest)


def test_olist_order_fields_are_confirmed_by_deterministic_rules(tmp_path: Path):
    profile = _profile(
        tmp_path,
        "orders.csv",
        "order_id,order_purchase_timestamp,order_approved_at,order_delivered_carrier_date,"
        "order_delivered_customer_date,order_estimated_delivery_date\n"
        "o1,2018-01-01 10:00:00,2018-01-01 11:00:00,2018-01-02 10:00:00,"
        "2018-01-05 10:00:00,2018-01-06 00:00:00\n",
    )

    mappings = SemanticMapper().map(profile)

    assert mappings.mapping("orders", "order_id").semantic_field is SemanticField.ORDER_ID
    assert mappings.mapping("orders", "order_delivered_carrier_date").semantic_field is SemanticField.CARRIER_HANDOFF_AT
    assert mappings.mapping("orders", "order_delivered_customer_date").semantic_field is SemanticField.DELIVERED_AT
    assert all(mapping.status is MappingStatus.CONFIRMED for mapping in mappings.mappings)
    assert all(mapping.source is MappingSource.DETERMINISTIC_RULE for mapping in mappings.mappings)


def test_ambiguous_alias_requires_confirmation_instead_of_auto_mapping(tmp_path: Path):
    profile = _profile(tmp_path, "orders.csv", "id,created,eta\no1,2018-01-01,2018-01-10\n")

    mappings = SemanticMapper().map(profile)

    candidate = mappings.mapping("orders", "id")
    assert candidate.semantic_field is SemanticField.ORDER_ID
    assert candidate.status is MappingStatus.NEEDS_CONFIRMATION
    assert candidate.confidence < SemanticMapper.AUTO_CONFIRM_THRESHOLD
    assert mappings.unresolved_columns == frozenset({"orders.created", "orders.eta", "orders.id"})


def test_user_confirmation_is_persisted_and_overrides_unresolved_mapping(tmp_path: Path):
    workspace_id = WorkspaceId.new()
    profile = _profile(tmp_path, "merchant_export.csv", "sale_key,promised_on\ns1,2018-01-10\n", workspace_id)
    store = WorkspaceSemanticStore(storage_root=tmp_path / "semantic-store")

    first = SemanticMapper(semantic_store=store).map(profile)
    assert first.mapping_or_none("merchant_export", "sale_key") is None

    store.confirm(
        workspace_id=workspace_id,
        table_name="merchant_export",
        column_name="sale_key",
        semantic_field=SemanticField.ORDER_ID,
    )

    second = SemanticMapper(semantic_store=WorkspaceSemanticStore(storage_root=tmp_path / "semantic-store")).map(profile)
    confirmed = second.mapping("merchant_export", "sale_key")
    assert confirmed.status is MappingStatus.CONFIRMED
    assert confirmed.source is MappingSource.USER_CONFIRMED
    assert confirmed.confidence == 1.0


def test_order_item_and_review_order_ids_keep_distinct_semantics(tmp_path: Path):
    workspace_id = WorkspaceId.new()
    items = tmp_path / "order_items.csv"
    items.write_text("order_id,seller_id,product_id\no1,s1,p1\n", encoding="utf-8")
    reviews = tmp_path / "order_reviews.csv"
    reviews.write_text("order_id,review_score,review_comment_message\no1,1,missing item\n", encoding="utf-8")
    storage_root = tmp_path / "commerce-storage"
    manifest = DataIntakeService(storage_root=storage_root).ingest(workspace_id, (items, reviews))
    profile = DataProfiler(storage_root=storage_root).profile(manifest)

    mappings = SemanticMapper().map(profile)

    assert mappings.mapping("order_items", "order_id").semantic_field is SemanticField.ORDER_ITEM_ORDER_ID
    assert mappings.mapping("order_reviews", "order_id").semantic_field is SemanticField.REVIEW_ORDER_ID
