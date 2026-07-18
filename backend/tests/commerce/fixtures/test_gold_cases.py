"""Deterministic integrity and metric checks for real Olist Gold Case fixtures."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean

import pytest

from app.commerce.data.gold_cases import load_evaluation_case

REPO_ROOT = Path(__file__).parents[4]
CASES_ROOT = REPO_ROOT / "evals" / "commerce" / "cases"

EXPECTED_COUNTS = {
    "GC-FULFILLMENT-001": {
        "orders": 554,
        "order_items": 563,
        "order_reviews": 549,
        "products": 47,
        "customers": 554,
        "sellers": 1,
    },
    "GC-REVIEW-002": {
        "orders": 35,
        "order_items": 42,
        "order_reviews": 35,
        "products": 11,
        "customers": 35,
        "sellers": 1,
    },
    "GC-CAPABILITY-003": {
        "orders": 554,
        "order_items": 563,
        "products": 47,
        "customers": 554,
        "sellers": 1,
    },
    "GC-PEER-004": {
        "orders": 316,
        "order_items": 331,
        "order_reviews": 317,
        "products": 135,
        "customers": 316,
        "sellers": 6,
    },
}


def _read_tables(case_key: str) -> dict[str, list[dict[str, str]]]:
    evaluation_case = load_evaluation_case(CASES_ROOT / case_key)
    tables = {}
    for file in evaluation_case.input_bundle.files:
        path = CASES_ROOT / case_key / file.relative_path
        with path.open(encoding="utf-8", newline="") as handle:
            tables[file.table_name] = list(csv.DictReader(handle))
    return tables


@pytest.mark.parametrize("case_key", tuple(EXPECTED_COUNTS))
def test_gold_case_contracts_load_without_exposing_expected_behavior(case_key: str):
    evaluation_case = load_evaluation_case(CASES_ROOT / case_key)

    agent_input = evaluation_case.input_bundle.model_dump(mode="json")

    assert evaluation_case.case_key == case_key
    assert "required_facts" not in agent_input
    assert "forbidden_claims" not in agent_input


@pytest.mark.parametrize("case_key, expected", tuple(EXPECTED_COUNTS.items()))
def test_gold_case_row_counts_are_frozen(case_key: str, expected: dict[str, int]):
    tables = _read_tables(case_key)

    assert {name: len(rows) for name, rows in tables.items()} == expected


@pytest.mark.parametrize("case_key", tuple(EXPECTED_COUNTS))
def test_gold_case_tables_are_joinable(case_key: str):
    tables = _read_tables(case_key)
    order_ids = {row["order_id"] for row in tables["orders"]}
    item_order_ids = {row["order_id"] for row in tables["order_items"]}
    product_ids = {row["product_id"] for row in tables["products"]}
    item_product_ids = {row["product_id"] for row in tables["order_items"]}
    customer_ids = {row["customer_id"] for row in tables["customers"]}
    order_customer_ids = {row["customer_id"] for row in tables["orders"]}
    seller_ids = {row["seller_id"] for row in tables["sellers"]}
    item_seller_ids = {row["seller_id"] for row in tables["order_items"]}

    assert item_order_ids == order_ids
    assert item_product_ids == product_ids
    assert order_customer_ids == customer_ids
    assert item_seller_ids == seller_ids
    if "order_reviews" in tables:
        assert {row["order_id"] for row in tables["order_reviews"]} <= order_ids


def _window_metrics(
    tables: dict[str, list[dict[str, str]]],
    start: datetime,
    end: datetime,
) -> dict[str, float | int]:
    reviews_by_order: dict[str, list[int]] = defaultdict(list)
    for review in tables.get("order_reviews", []):
        reviews_by_order[review["order_id"]].append(int(review["review_score"]))

    selected = []
    for order in tables["orders"]:
        purchase = datetime.fromisoformat(order["order_purchase_timestamp"])
        if not start <= purchase < end:
            continue
        approved = datetime.fromisoformat(order["order_approved_at"])
        carrier = datetime.fromisoformat(order["order_delivered_carrier_date"])
        delivered = datetime.fromisoformat(order["order_delivered_customer_date"])
        estimated = datetime.fromisoformat(order["order_estimated_delivery_date"])
        scores = reviews_by_order[order["order_id"]]
        selected.append(
            {
                "late": delivered > estimated,
                "score": mean(scores) if scores else None,
                "handling_hours": (carrier - approved).total_seconds() / 3600,
                "transit_hours": (delivered - carrier).total_seconds() / 3600,
            }
        )

    scores = [row["score"] for row in selected if row["score"] is not None]
    return {
        "order_count": len(selected),
        "late_count": sum(row["late"] for row in selected),
        "late_delivery_rate": sum(row["late"] for row in selected) / len(selected),
        "review_count": len(scores),
        "average_review_score": mean(scores) if scores else 0.0,
        "low_rating_count": sum(score <= 2 for score in scores),
        "low_rating_rate": sum(score <= 2 for score in scores) / len(scores) if scores else 0.0,
        "handling_hours": mean(row["handling_hours"] for row in selected),
        "transit_hours": mean(row["transit_hours"] for row in selected),
    }


def test_fulfillment_case_recomputes_baseline_anomaly_and_recovery():
    tables = _read_tables("GC-FULFILLMENT-001")

    baseline = _window_metrics(tables, datetime(2017, 12, 2), datetime(2018, 1, 31))
    anomaly = _window_metrics(tables, datetime(2018, 1, 31), datetime(2018, 4, 1))
    recovery = _window_metrics(tables, datetime(2018, 4, 1), datetime(2018, 6, 1))

    assert baseline["order_count"] == 141
    assert baseline["late_count"] == 5
    assert baseline["late_delivery_rate"] == pytest.approx(0.03546099290780142)
    assert baseline["average_review_score"] == pytest.approx(4.228571428571429)
    assert baseline["handling_hours"] == pytest.approx(50.06023640661939)
    assert baseline["transit_hours"] == pytest.approx(300.5057781717888)

    assert anomaly["order_count"] == 202
    assert anomaly["late_count"] == 71
    assert anomaly["late_delivery_rate"] == pytest.approx(0.35148514851485146)
    assert anomaly["average_review_score"] == pytest.approx(3.5979899497487438)
    assert anomaly["handling_hours"] == pytest.approx(46.83626512651265)
    assert anomaly["transit_hours"] == pytest.approx(494.83323569856987)

    assert recovery["order_count"] == 211
    assert recovery["late_count"] == 11
    assert recovery["late_delivery_rate"] == pytest.approx(0.052132701421800945)
    assert recovery["average_review_score"] == pytest.approx(4.280952380952381)


def test_review_case_recomputes_non_fulfillment_experience_anomaly():
    tables = _read_tables("GC-REVIEW-002")

    baseline = _window_metrics(tables, datetime(2018, 3, 1), datetime(2018, 4, 1))
    anomaly = _window_metrics(tables, datetime(2018, 4, 1), datetime(2018, 5, 1))

    assert baseline["order_count"] == 17
    assert baseline["late_delivery_rate"] == 0.0
    assert baseline["average_review_score"] == pytest.approx(3.8823529411764706)
    assert baseline["low_rating_rate"] == pytest.approx(0.23529411764705882)

    assert anomaly["order_count"] == 18
    assert anomaly["late_delivery_rate"] == 0.0
    assert anomaly["average_review_score"] == pytest.approx(2.9444444444444446)
    assert anomaly["low_rating_rate"] == pytest.approx(0.4444444444444444)


def test_capability_ablation_removes_review_table_only():
    full_tables = _read_tables("GC-FULFILLMENT-001")
    ablated_tables = _read_tables("GC-CAPABILITY-003")

    assert "order_reviews" in full_tables
    assert "order_reviews" not in ablated_tables
    assert {name: rows for name, rows in full_tables.items() if name != "order_reviews"} == ablated_tables


def test_peer_case_freezes_target_and_outcome_agnostic_peer_membership():
    tables = _read_tables("GC-PEER-004")
    target_seller_id = "e5a3438891c0bfdb9394643f95273d8e"
    items_by_order: dict[str, list[dict[str, str]]] = defaultdict(list)
    for item in tables["order_items"]:
        items_by_order[item["order_id"]].append(item)

    orders_by_seller: dict[str, list[dict[str, str]]] = defaultdict(list)
    for order in tables["orders"]:
        seller_ids = {item["seller_id"] for item in items_by_order[order["order_id"]]}
        assert len(seller_ids) == 1
        orders_by_seller[next(iter(seller_ids))].append(order)

    counts = {seller_id: len(orders) for seller_id, orders in orders_by_seller.items()}
    late = {seller_id: sum(datetime.fromisoformat(order["order_delivered_customer_date"]) > datetime.fromisoformat(order["order_estimated_delivery_date"]) for order in orders) for seller_id, orders in orders_by_seller.items()}

    assert counts[target_seller_id] == 59
    assert late[target_seller_id] == 16
    assert sum(count for seller_id, count in counts.items() if seller_id != target_seller_id) == 257
    assert sum(count for seller_id, count in late.items() if seller_id != target_seller_id) == 19
    assert all(count >= 20 for count in counts.values())
    assert {row["product_category_name"] for row in tables["products"]} == {
        "fashion_bolsas_e_acessorios"
    }
    assert {row["seller_state"] for row in tables["sellers"]} == {"SP"}

    provenance = json.loads(
        (CASES_ROOT / "GC-PEER-004" / "provenance.json").read_text(encoding="utf-8")
    )
    selection = provenance["selection"]
    assert selection["eligibility_uses_late_delivery_result"] is False
    assert selection["single_seller_orders_only"] is True
    assert selection["pure_category_orders_only"] is True
