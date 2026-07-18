"""Deterministic schema, quality, and join-risk profiling contracts."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from app.commerce.data.intake import DataIntakeService
from app.commerce.data.profiler import DataProfiler, InferredType, JoinCardinality
from app.commerce.domain.ids import WorkspaceId


def _profile(tmp_path: Path, *sources: Path):
    storage_root = tmp_path / "commerce-storage"
    manifest = DataIntakeService(storage_root=storage_root).ingest(WorkspaceId.new(), tuple(sources))
    return DataProfiler(storage_root=storage_root).profile(manifest)


def test_profiler_reports_types_missing_unique_time_numeric_and_leading_zero(tmp_path: Path):
    source = tmp_path / "orders.csv"
    source.write_text(
        "order_id,zip_code,amount,purchased_at,note\n"
        "o1,01234,10.50,2018-01-01 10:00:00,ok\n"
        "o2,04567,,2018-01-02 11:00:00,\n"
        "o3,00001,20.00,2018-01-03 12:00:00,ok\n",
        encoding="utf-8",
    )

    profile = _profile(tmp_path, source)
    table = profile.table("orders")
    order_id = table.column("order_id")
    zip_code = table.column("zip_code")
    amount = table.column("amount")
    purchased_at = table.column("purchased_at")
    note = table.column("note")

    assert table.row_count == 3
    assert order_id.is_primary_key_candidate is True
    assert order_id.unique_rate == 1.0
    assert zip_code.inferred_type is InferredType.STRING
    assert zip_code.leading_zero_count == 3
    assert zip_code.leading_zero_rate == 1.0
    assert amount.inferred_type is InferredType.DECIMAL
    assert amount.missing_count == 1
    assert amount.missing_rate == pytest.approx(1 / 3)
    assert amount.numeric_min == Decimal("10.50")
    assert amount.numeric_max == Decimal("20.00")
    assert purchased_at.inferred_type is InferredType.DATETIME
    assert purchased_at.is_time_candidate is True
    assert note.missing_count == 1


def test_profiler_counts_duplicate_rows(tmp_path: Path):
    source = tmp_path / "rows.csv"
    source.write_text("id,value\n1,a\n1,a\n2,b\n", encoding="utf-8")

    table = _profile(tmp_path, source).table("rows")

    assert table.duplicate_row_count == 1
    assert table.duplicate_row_rate == pytest.approx(1 / 3)
    assert "id" not in table.primary_key_candidates


def test_profiler_detects_one_to_many_and_many_to_many_join_cardinality(tmp_path: Path):
    orders = tmp_path / "orders.csv"
    orders.write_text("order_id,customer_id\no1,c1\no2,c2\n", encoding="utf-8")
    items = tmp_path / "items.csv"
    items.write_text("order_id,product_id\no1,p1\no1,p2\no2,p2\n", encoding="utf-8")
    events = tmp_path / "events.csv"
    events.write_text("product_id,event\np1,view\np1,cart\np2,view\np2,buy\n", encoding="utf-8")

    profile = _profile(tmp_path, orders, items, events)

    order_join = profile.join("orders", "order_id", "items", "order_id")
    product_join = profile.join("items", "product_id", "events", "product_id")
    assert order_join.cardinality is JoinCardinality.ONE_TO_MANY
    assert order_join.requires_aggregation is True
    assert product_join.cardinality is JoinCardinality.MANY_TO_MANY
    assert product_join.requires_aggregation is True


def test_profiler_reads_json_object_tables_using_manifest_keys(tmp_path: Path):
    source = tmp_path / "bundle.json"
    source.write_text(
        json.dumps(
            {
                "orders": [{"order_id": "o1"}, {"order_id": "o2"}],
                "reviews": [{"order_id": "o1", "score": 5}],
            }
        ),
        encoding="utf-8",
    )

    profile = _profile(tmp_path, source)

    assert profile.table("orders").row_count == 2
    assert profile.table("reviews").row_count == 1


def test_profiler_marks_mixed_columns_without_coercing_values(tmp_path: Path):
    source = tmp_path / "mixed.jsonl"
    source.write_text('{"id":"001","value":10}\n{"id":"002","value":"unknown"}\n', encoding="utf-8")

    table = _profile(tmp_path, source).table("mixed")

    assert table.column("id").inferred_type is InferredType.STRING
    assert table.column("id").leading_zero_count == 2
    assert table.column("value").inferred_type is InferredType.MIXED
