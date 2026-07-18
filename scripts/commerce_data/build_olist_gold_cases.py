#!/usr/bin/env python3
"""Build small, deterministic Commerce Gold Cases from the real Olist CSVs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean
from uuid import NAMESPACE_URL, uuid5

RAW_SHA256 = {
    "olist_customers_dataset.csv": "983a422239e1712ded753b3bf9ecf47dc73f144d306029dcfa99e70a226883d2",
    "olist_order_items_dataset.csv": "0bc4d068c4fe38cbb01bd90e8746e3c613fe7b4baef75fab7b0e329701c3e279",
    "olist_order_reviews_dataset.csv": "012b61c7593e34f51fa614efdf802b9c7056ce6aae5307ddb93236e7cfc797d7",
    "olist_orders_dataset.csv": "8df58ef3d2d7e9944010f7beecd9b75367f5588ec6e3c91cec19ae3345ef9ecf",
    "olist_products_dataset.csv": "3e6569628a17fbc75fd206ee357b59e20364b9afa90f5b6cd5b4d624c58aa9cc",
    "olist_sellers_dataset.csv": "1f643d2b950373b85735e7794b20986f528d7a000432e7c6f9bcbb44d0846a0e",
}

MISSING_PRIVATE_FIELDS = (
    "exposure",
    "click",
    "add_to_cart",
    "ad_spend",
    "inventory",
    "profit",
)


@dataclass(frozen=True)
class RawTable:
    fieldnames: tuple[str, ...]
    rows: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class CaseSpec:
    case_key: str
    title: str
    seller_id: str
    start: datetime
    end: datetime
    include_reviews: bool
    prompt: str


@dataclass(frozen=True)
class PeerCaseSpec:
    case_key: str
    title: str
    seller_id: str
    start: datetime
    end: datetime
    product_category: str
    seller_state: str
    min_orders_per_seller: int
    prompt: str


CASE_SPECS = (
    CaseSpec(
        case_key="GC-FULFILLMENT-001",
        title="Carrier transit degradation with later natural recovery",
        seller_id="4869f7a5dfa277a7dca6462dcf3b52b2",
        start=datetime(2017, 12, 2),
        end=datetime(2018, 6, 1),
        include_reviews=True,
        prompt="最近一段时间履约和评分出现异常，请定位主要问题、反驳不成立的原因，并给出可验证的后续动作。",
    ),
    CaseSpec(
        case_key="GC-REVIEW-002",
        title="Review experience degradation without delivery lateness",
        seller_id="0b90b6df587eb83608a64ea8b390cf07",
        start=datetime(2018, 3, 1),
        end=datetime(2018, 5, 1),
        include_reviews=True,
        prompt="评分和低分评价突然恶化，但我不确定是否与物流有关。请基于数据调查原因并说明证据边界。",
    ),
    CaseSpec(
        case_key="GC-CAPABILITY-003",
        title="Fulfillment diagnosis with review capability ablated",
        seller_id="4869f7a5dfa277a7dca6462dcf3b52b2",
        start=datetime(2017, 12, 2),
        end=datetime(2018, 6, 1),
        include_reviews=False,
        prompt="请在当前已上传数据的能力范围内调查履约异常；缺失信息必须明确说明，并给出精确补数建议。",
    ),
    PeerCaseSpec(
        case_key="GC-PEER-004",
        title="Same-category same-state seller delivery outlier",
        seller_id="e5a3438891c0bfdb9394643f95273d8e",
        start=datetime(2018, 1, 1),
        end=datetime(2018, 7, 1),
        product_category="fashion_bolsas_e_acessorios",
        seller_state="SP",
        min_orders_per_seller=20,
        prompt="该卖家的延迟率看起来偏高。请与同时间、同品类、同卖家州且样本充足的真实卖家进行对标，说明差距、地域分布和证据边界。",
    ),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_table(path: Path) -> RawTable:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = tuple(dict(row) for row in reader)
        return RawTable(fieldnames=tuple(reader.fieldnames or ()), rows=rows)


def normalize_cell(value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in normalized.split("\n")).rstrip()


def write_table(path: Path, table: RawTable) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=table.fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(
            {key: normalize_cell(value) for key, value in row.items()}
            for row in table.rows
        )


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def fact(name: str, expected_value, *, tolerance: float | None = None) -> dict:
    payload = {
        "name": name,
        "semantic_status": "derived",
        "expected_value": expected_value,
    }
    if tolerance is not None:
        payload["tolerance"] = tolerance
    return payload


def unknown_fact(name: str, reason: str) -> dict:
    return {
        "name": name,
        "semantic_status": "unknown",
        "expected_value": None,
        "unknown_reason_contains": reason,
    }


def private_metric_forbidden_claim() -> dict:
    return {
        "code": "no-unavailable-private-metrics",
        "kind": "unsupported_private_metric",
        "description": "Do not invent GMV, CTR, CVR, ROI, ad spend, inventory, profit, or causal uplift.",
        "match_mode": "any_term",
        "terms": (
            "confirmed roi",
            "verified uplift",
            "真实gmv",
            "实际转化率",
            "广告roi已提升",
        ),
    }


def expected_behavior(case_key: str) -> dict:
    if case_key == "GC-FULFILLMENT-001":
        return {
            "required_facts": (
                fact("baseline.order_count", 141),
                fact("baseline.late_delivery_rate", 0.03546099290780142, tolerance=1e-12),
                fact("baseline.average_review_score", 4.228571428571429, tolerance=1e-12),
                fact("baseline.handling_hours", 50.06023640661939, tolerance=1e-9),
                fact("baseline.transit_hours", 300.5057781717888, tolerance=1e-9),
                fact("anomaly.order_count", 202),
                fact("anomaly.late_delivery_rate", 0.35148514851485146, tolerance=1e-12),
                fact("anomaly.average_review_score", 3.5979899497487438, tolerance=1e-12),
                fact("anomaly.handling_hours", 46.83626512651265, tolerance=1e-9),
                fact("anomaly.transit_hours", 494.83323569856987, tolerance=1e-9),
                fact("recovery.order_count", 211),
                fact("recovery.late_delivery_rate", 0.052132701421800945, tolerance=1e-12),
                fact("recovery.average_review_score", 4.280952380952381, tolerance=1e-12),
                unknown_fact("followup.causal_effect", "no controlled intervention"),
            ),
            "forbidden_claims": (
                {
                    "code": "no-seller-handling-blame",
                    "kind": "unsupported_causal",
                    "description": "Seller handling did not worsen during the anomaly window.",
                    "match_mode": "any_term",
                    "terms": (
                        "seller handling caused the delay",
                        "seller dispatch capacity caused the delay",
                        "卖家处理时长恶化导致",
                        "卖家出库能力不足导致",
                    ),
                },
                {
                    "code": "no-causal-action-effect",
                    "kind": "unsupported_causal",
                    "description": "Natural recovery cannot prove an Action caused improvement.",
                    "match_mode": "any_term",
                    "terms": (
                        "action caused the recovery",
                        "intervention proved effective",
                        "行动导致恢复",
                        "措施已被证明有效",
                    ),
                },
                private_metric_forbidden_claim(),
            ),
            "expected_capabilities": ("fulfillment_diagnosis", "review_experience"),
            "expected_path_agents": ("FulfillmentPathAgent", "ReviewExperiencePathAgent"),
            "skipped_path_agents": ("SellerPeerPathAgent",),
            "expected_follow_up_outcome": "inconclusive",
        }

    if case_key == "GC-REVIEW-002":
        return {
            "required_facts": (
                fact("baseline.order_count", 17),
                fact("baseline.late_delivery_rate", 0.0, tolerance=0.0),
                fact("baseline.average_review_score", 3.8823529411764706, tolerance=1e-12),
                fact("baseline.low_rating_rate", 0.23529411764705882, tolerance=1e-12),
                fact("anomaly.order_count", 18),
                fact("anomaly.late_delivery_rate", 0.0, tolerance=0.0),
                fact("anomaly.average_review_score", 2.9444444444444446, tolerance=1e-12),
                fact("anomaly.low_rating_rate", 0.4444444444444444, tolerance=1e-12),
            ),
            "forbidden_claims": (
                {
                    "code": "no-confirmed-counterfeit-or-fraud",
                    "kind": "unsupported_illegal_conduct",
                    "description": "Review allegations support suspicion, not a confirmed counterfeit or fraud finding.",
                    "match_mode": "any_term",
                    "terms": (
                        "confirmed counterfeit",
                        "confirmed fraud",
                        "seller sells counterfeit",
                        "确认售假",
                        "确认欺诈",
                        "卖家就是在售假",
                    ),
                },
                {
                    "code": "no-delivery-root-cause",
                    "kind": "unsupported_causal",
                    "description": "Both windows have zero late deliveries.",
                    "match_mode": "any_term",
                    "terms": (
                        "delivery delay caused the rating decline",
                        "logistics lateness caused the decline",
                        "物流延迟导致评分下降",
                        "配送延误是根因",
                    ),
                },
                private_metric_forbidden_claim(),
            ),
            "expected_capabilities": ("fulfillment_diagnosis", "review_experience"),
            "expected_path_agents": ("ReviewExperiencePathAgent",),
            "skipped_path_agents": ("FulfillmentPathAgent", "SellerPeerPathAgent"),
        }

    if case_key == "GC-CAPABILITY-003":
        return {
            "required_facts": (
                fact("baseline.order_count", 141),
                fact("baseline.late_delivery_rate", 0.03546099290780142, tolerance=1e-12),
                fact("anomaly.order_count", 202),
                fact("anomaly.late_delivery_rate", 0.35148514851485146, tolerance=1e-12),
                fact("anomaly.handling_hours", 46.83626512651265, tolerance=1e-9),
                fact("anomaly.transit_hours", 494.83323569856987, tolerance=1e-9),
                unknown_fact("anomaly.average_review_score", "order_reviews"),
            ),
            "forbidden_claims": (
                {
                    "code": "no-review-decline-without-review-data",
                    "kind": "capability_overclaim",
                    "description": "Review decline cannot be claimed after the review table is removed.",
                    "match_mode": "any_term",
                    "terms": (
                        "review score declined",
                        "rating declined",
                        "评分下降",
                        "低分率上升",
                    ),
                },
                private_metric_forbidden_claim(),
            ),
            "expected_capabilities": ("fulfillment_diagnosis",),
            "expected_path_agents": ("FulfillmentPathAgent",),
            "skipped_path_agents": ("ReviewExperiencePathAgent", "SellerPeerPathAgent"),
            "capability_ablation": {
                "removed_files": ("order_reviews",),
                "baseline_capabilities": ("fulfillment_diagnosis", "review_experience"),
                "expected_capabilities": ("fulfillment_diagnosis",),
            },
        }

    if case_key == "GC-PEER-004":
        return {
            "required_facts": (
                fact("peer.target_order_count", 59),
                fact("peer.target_late_delivery_rate", 16 / 59, tolerance=1e-12),
                fact("peer.peer_seller_count", 5),
                fact("peer.peer_order_count", 257),
                fact("peer.peer_late_delivery_rate", 19 / 257, tolerance=1e-12),
                fact("peer.late_delivery_rate_gap", (16 / 59) - (19 / 257), tolerance=1e-12),
                fact("geography.SP.order_count", 26),
                fact("geography.MG.order_count", 8),
                fact("geography.RJ.order_count", 7),
            ),
            "forbidden_claims": (
                {
                    "code": "no-peer-gap-causal-blame",
                    "kind": "unsupported_causal",
                    "description": "A matched peer gap is diagnostic evidence, not proof that seller-controlled behavior caused lateness.",
                    "match_mode": "any_term",
                    "terms": (
                        "peer gap proves the seller caused delays",
                        "seller operations definitively caused the gap",
                        "对标差距证明卖家导致延迟",
                        "可以确认是卖家自身造成",
                    ),
                },
                {
                    "code": "no-peer-causal-action-effect",
                    "kind": "unsupported_causal",
                    "description": "The frozen peer comparison has no controlled Action follow-up.",
                    "match_mode": "any_term",
                    "terms": (
                        "action closed the peer gap",
                        "intervention improved the seller",
                        "行动已缩小对标差距",
                        "措施已经改善卖家表现",
                    ),
                },
                private_metric_forbidden_claim(),
            ),
            "expected_capabilities": (
                "fulfillment_diagnosis",
                "review_experience",
                "seller_peer_comparison",
            ),
            "expected_path_agents": ("FulfillmentPathAgent", "SellerPeerPathAgent"),
            "skipped_path_agents": ("ReviewExperiencePathAgent",),
        }

    raise ValueError(f"Unknown Gold Case: {case_key}")


def metrics_for_window(
    orders: tuple[dict[str, str], ...],
    reviews: tuple[dict[str, str], ...],
    start: datetime,
    end: datetime,
) -> dict[str, float | int]:
    reviews_by_order: dict[str, list[int]] = defaultdict(list)
    for review in reviews:
        reviews_by_order[review["order_id"]].append(int(review["review_score"]))

    selected = []
    for order in orders:
        purchase = parse_dt(order["order_purchase_timestamp"])
        if not start <= purchase < end:
            continue
        approved = parse_dt(order["order_approved_at"])
        carrier = parse_dt(order["order_delivered_carrier_date"])
        delivered = parse_dt(order["order_delivered_customer_date"])
        estimated = parse_dt(order["order_estimated_delivery_date"])
        scores = reviews_by_order[order["order_id"]]
        selected.append(
            {
                "late": delivered > estimated,
                "score": mean(scores) if scores else None,
                "handling": (carrier - approved).total_seconds() / 3600,
                "transit": (delivered - carrier).total_seconds() / 3600,
            }
        )

    scores = [row["score"] for row in selected if row["score"] is not None]
    return {
        "order_count": len(selected),
        "late_count": sum(row["late"] for row in selected),
        "late_delivery_rate": sum(row["late"] for row in selected) / len(selected),
        "average_review_score": mean(scores) if scores else 0.0,
        "low_rating_rate": sum(score <= 2 for score in scores) / len(scores) if scores else 0.0,
        "handling_hours": mean(row["handling"] for row in selected),
        "transit_hours": mean(row["transit"] for row in selected),
    }


def assert_close(actual: float | int, expected: float | int, tolerance: float = 1e-9) -> None:
    if abs(actual - expected) > tolerance:
        raise ValueError(f"Frozen Olist metric drifted: actual={actual!r}, expected={expected!r}")


def verify_frozen_metrics(case_key: str, tables: dict[str, RawTable]) -> None:
    orders = tables["orders"].rows
    reviews = tables.get("order_reviews", RawTable((), ())).rows
    if case_key in {"GC-FULFILLMENT-001", "GC-CAPABILITY-003"}:
        baseline = metrics_for_window(orders, reviews, datetime(2017, 12, 2), datetime(2018, 1, 31))
        anomaly = metrics_for_window(orders, reviews, datetime(2018, 1, 31), datetime(2018, 4, 1))
        recovery = metrics_for_window(orders, reviews, datetime(2018, 4, 1), datetime(2018, 6, 1))
        assert_close(baseline["order_count"], 141)
        assert_close(baseline["late_delivery_rate"], 0.03546099290780142)
        assert_close(anomaly["order_count"], 202)
        assert_close(anomaly["late_delivery_rate"], 0.35148514851485146)
        assert_close(anomaly["handling_hours"], 46.83626512651265)
        assert_close(anomaly["transit_hours"], 494.83323569856987)
        assert_close(recovery["order_count"], 211)
        if case_key == "GC-FULFILLMENT-001":
            assert_close(baseline["average_review_score"], 4.228571428571429)
            assert_close(anomaly["average_review_score"], 3.5979899497487438)
            assert_close(recovery["average_review_score"], 4.280952380952381)
        return

    if case_key == "GC-PEER-004":
        items_by_order: dict[str, list[dict[str, str]]] = defaultdict(list)
        for item in tables["order_items"].rows:
            items_by_order[item["order_id"]].append(item)
        orders_by_seller: dict[str, list[dict[str, str]]] = defaultdict(list)
        customers_by_id = {row["customer_id"]: row for row in tables["customers"].rows}
        target_states: dict[str, int] = defaultdict(int)
        target_seller_id = "e5a3438891c0bfdb9394643f95273d8e"
        for order in tables["orders"].rows:
            seller_ids = {item["seller_id"] for item in items_by_order[order["order_id"]]}
            if len(seller_ids) != 1:
                raise ValueError("Peer fixture contains a multi-seller order")
            seller_id = next(iter(seller_ids))
            orders_by_seller[seller_id].append(order)
            if seller_id == target_seller_id:
                target_states[customers_by_id[order["customer_id"]]["customer_state"]] += 1

        target_orders = orders_by_seller[target_seller_id]
        peer_orders = [
            order
            for seller_id, orders_for_seller in orders_by_seller.items()
            if seller_id != target_seller_id
            for order in orders_for_seller
        ]

        def late_count(selected_orders: list[dict[str, str]]) -> int:
            return sum(
                parse_dt(order["order_delivered_customer_date"])
                > parse_dt(order["order_estimated_delivery_date"])
                for order in selected_orders
            )

        assert_close(len(target_orders), 59)
        assert_close(late_count(target_orders), 16)
        assert_close(len(orders_by_seller) - 1, 5)
        assert_close(len(peer_orders), 257)
        assert_close(late_count(peer_orders), 19)
        assert_close(target_states["SP"], 26)
        assert_close(target_states["MG"], 8)
        assert_close(target_states["RJ"], 7)
        return

    baseline = metrics_for_window(orders, reviews, datetime(2018, 3, 1), datetime(2018, 4, 1))
    anomaly = metrics_for_window(orders, reviews, datetime(2018, 4, 1), datetime(2018, 5, 1))
    assert_close(baseline["order_count"], 17)
    assert_close(baseline["late_delivery_rate"], 0.0)
    assert_close(baseline["average_review_score"], 3.8823529411764706)
    assert_close(baseline["low_rating_rate"], 0.23529411764705882)
    assert_close(anomaly["order_count"], 18)
    assert_close(anomaly["late_delivery_rate"], 0.0)
    assert_close(anomaly["average_review_score"], 2.9444444444444446)
    assert_close(anomaly["low_rating_rate"], 0.4444444444444444)


def filter_table(table: RawTable, predicate) -> RawTable:
    return RawTable(table.fieldnames, tuple(row for row in table.rows if predicate(row)))


def build_case(spec: CaseSpec, raw: dict[str, RawTable], output_root: Path) -> None:
    items = raw["olist_order_items_dataset.csv"]
    orders = raw["olist_orders_dataset.csv"]

    order_sellers: dict[str, set[str]] = defaultdict(set)
    seller_order_ids: set[str] = set()
    for item in items.rows:
        order_sellers[item["order_id"]].add(item["seller_id"])
        if item["seller_id"] == spec.seller_id:
            seller_order_ids.add(item["order_id"])

    selected_orders = filter_table(
        orders,
        lambda row: row["order_id"] in seller_order_ids
        and row["order_status"] == "delivered"
        and spec.start <= parse_dt(row["order_purchase_timestamp"]) < spec.end
        and len(order_sellers[row["order_id"]]) == 1,
    )
    selected_order_ids = {row["order_id"] for row in selected_orders.rows}
    selected_items = filter_table(items, lambda row: row["order_id"] in selected_order_ids)
    product_ids = {row["product_id"] for row in selected_items.rows}
    customer_ids = {row["customer_id"] for row in selected_orders.rows}
    seller_ids = {row["seller_id"] for row in selected_items.rows}

    tables = {
        "orders": selected_orders,
        "order_items": selected_items,
        "products": filter_table(raw["olist_products_dataset.csv"], lambda row: row["product_id"] in product_ids),
        "customers": filter_table(raw["olist_customers_dataset.csv"], lambda row: row["customer_id"] in customer_ids),
        "sellers": filter_table(raw["olist_sellers_dataset.csv"], lambda row: row["seller_id"] in seller_ids),
    }
    if spec.include_reviews:
        tables["order_reviews"] = filter_table(
            raw["olist_order_reviews_dataset.csv"],
            lambda row: row["order_id"] in selected_order_ids,
        )

    verify_frozen_metrics(spec.case_key, tables)

    case_dir = output_root / spec.case_key
    if case_dir.exists():
        shutil.rmtree(case_dir)
    input_dir = case_dir / "input"
    input_dir.mkdir(parents=True)

    input_files = []
    for table_name in ("orders", "order_items", "order_reviews", "products", "customers", "sellers"):
        if table_name not in tables:
            continue
        path = input_dir / f"{table_name}.csv"
        write_table(path, tables[table_name])
        input_files.append(
            {
                "name": table_name,
                "relative_path": f"input/{table_name}.csv",
                "table_name": table_name,
                "sha256": sha256(path),
                "row_count": len(tables[table_name].rows),
                "columns": tables[table_name].fieldnames,
            }
        )

    declared_missing = list(MISSING_PRIVATE_FIELDS)
    if not spec.include_reviews:
        declared_missing.extend(("review_score", "review_comment_title", "review_comment_message"))

    write_json(
        case_dir / "case-metadata.json",
        {
            "id": f"evalcase_{uuid5(NAMESPACE_URL, f'commerce:{spec.case_key}').hex}",
            "case_key": spec.case_key,
            "version": "1.0.0",
            "title": spec.title,
        },
    )
    write_json(
        case_dir / "input-bundle.json",
        {
            "schema_version": "1.0",
            "source_type": "public_benchmark_fixture",
            "not_a_live_merchant_integration": True,
            "files": input_files,
            "user_prompt": spec.prompt,
            "declared_missing_fields": declared_missing,
        },
    )
    write_json(case_dir / "expected-behavior.json", expected_behavior(spec.case_key))
    write_json(
        case_dir / "provenance.json",
        {
            "dataset": "Olist Brazilian E-Commerce Public Dataset",
            "source_url": "https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce",
            "license_note": "Kaggle metadata reports CC BY-NC-SA 4.0; research/portfolio fixture only.",
            "raw_sha256": RAW_SHA256,
            "selection": {
                "seller_id": spec.seller_id,
                "purchase_start_inclusive": spec.start.isoformat(),
                "purchase_end_exclusive": spec.end.isoformat(),
                "order_status": "delivered",
                "single_seller_orders_only": True,
                "reviews_included": spec.include_reviews,
            },
            "fixture_normalization": "CSV cells normalize CRLF/CR to LF and remove per-line trailing whitespace.",
            "generated_row_counts": {name: len(table.rows) for name, table in tables.items()},
        },
    )


def build_peer_case(spec: PeerCaseSpec, raw: dict[str, RawTable], output_root: Path) -> None:
    items = raw["olist_order_items_dataset.csv"]
    orders = raw["olist_orders_dataset.csv"]
    product_categories = {
        row["product_id"]: row["product_category_name"]
        for row in raw["olist_products_dataset.csv"].rows
    }
    seller_states = {
        row["seller_id"]: row["seller_state"]
        for row in raw["olist_sellers_dataset.csv"].rows
    }
    items_by_order: dict[str, list[dict[str, str]]] = defaultdict(list)
    for item in items.rows:
        items_by_order[item["order_id"]].append(item)

    candidate_orders_by_seller: dict[str, list[dict[str, str]]] = defaultdict(list)
    for order in orders.rows:
        order_items = items_by_order[order["order_id"]]
        seller_ids = {item["seller_id"] for item in order_items}
        categories = {product_categories.get(item["product_id"], "") for item in order_items}
        if order["order_status"] != "delivered" or len(seller_ids) != 1:
            continue
        if not order["order_delivered_customer_date"] or not order["order_estimated_delivery_date"]:
            continue
        if not spec.start <= parse_dt(order["order_purchase_timestamp"]) < spec.end:
            continue
        if categories != {spec.product_category}:
            continue
        seller_id = next(iter(seller_ids))
        if seller_states.get(seller_id) != spec.seller_state:
            continue
        candidate_orders_by_seller[seller_id].append(order)

    eligible_seller_ids = {
        seller_id
        for seller_id, seller_orders in candidate_orders_by_seller.items()
        if len(seller_orders) >= spec.min_orders_per_seller
    }
    if spec.seller_id not in eligible_seller_ids:
        raise ValueError("Frozen peer target no longer satisfies cohort eligibility")
    if len(eligible_seller_ids) < 2:
        raise ValueError("Frozen peer cohort no longer has an eligible peer")

    selected_order_ids = {
        order["order_id"]
        for seller_id in eligible_seller_ids
        for order in candidate_orders_by_seller[seller_id]
    }
    selected_orders = filter_table(orders, lambda row: row["order_id"] in selected_order_ids)
    selected_items = filter_table(items, lambda row: row["order_id"] in selected_order_ids)
    product_ids = {row["product_id"] for row in selected_items.rows}
    customer_ids = {row["customer_id"] for row in selected_orders.rows}

    tables = {
        "orders": selected_orders,
        "order_items": selected_items,
        "order_reviews": filter_table(
            raw["olist_order_reviews_dataset.csv"],
            lambda row: row["order_id"] in selected_order_ids,
        ),
        "products": filter_table(
            raw["olist_products_dataset.csv"],
            lambda row: row["product_id"] in product_ids,
        ),
        "customers": filter_table(
            raw["olist_customers_dataset.csv"],
            lambda row: row["customer_id"] in customer_ids,
        ),
        "sellers": filter_table(
            raw["olist_sellers_dataset.csv"],
            lambda row: row["seller_id"] in eligible_seller_ids,
        ),
    }
    verify_frozen_metrics(spec.case_key, tables)

    case_dir = output_root / spec.case_key
    if case_dir.exists():
        shutil.rmtree(case_dir)
    input_dir = case_dir / "input"
    input_dir.mkdir(parents=True)

    input_files = []
    for table_name in ("orders", "order_items", "order_reviews", "products", "customers", "sellers"):
        path = input_dir / f"{table_name}.csv"
        write_table(path, tables[table_name])
        input_files.append(
            {
                "name": table_name,
                "relative_path": f"input/{table_name}.csv",
                "table_name": table_name,
                "sha256": sha256(path),
                "row_count": len(tables[table_name].rows),
                "columns": tables[table_name].fieldnames,
            }
        )

    write_json(
        case_dir / "case-metadata.json",
        {
            "id": f"evalcase_{uuid5(NAMESPACE_URL, f'commerce:{spec.case_key}').hex}",
            "case_key": spec.case_key,
            "version": "1.0.0",
            "title": spec.title,
        },
    )
    write_json(
        case_dir / "input-bundle.json",
        {
            "schema_version": "1.0",
            "source_type": "public_benchmark_fixture",
            "not_a_live_merchant_integration": True,
            "files": input_files,
            "user_prompt": spec.prompt,
            "declared_missing_fields": list(MISSING_PRIVATE_FIELDS),
        },
    )
    write_json(case_dir / "expected-behavior.json", expected_behavior(spec.case_key))
    write_json(
        case_dir / "provenance.json",
        {
            "dataset": "Olist Brazilian E-Commerce Public Dataset",
            "source_url": "https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce",
            "license_note": "Kaggle metadata reports CC BY-NC-SA 4.0; research/portfolio fixture only.",
            "raw_sha256": RAW_SHA256,
            "selection": {
                "target_seller_id": spec.seller_id,
                "purchase_start_inclusive": spec.start.isoformat(),
                "purchase_end_exclusive": spec.end.isoformat(),
                "product_category": spec.product_category,
                "seller_state": spec.seller_state,
                "min_orders_per_seller": spec.min_orders_per_seller,
                "order_status": "delivered",
                "single_seller_orders_only": True,
                "pure_category_orders_only": True,
                "eligibility_uses_late_delivery_result": False,
                "eligible_seller_ids": sorted(eligible_seller_ids),
            },
            "fixture_normalization": "CSV cells normalize CRLF/CR to LF and remove per-line trailing whitespace.",
            "generated_row_counts": {name: len(table.rows) for name, table in tables.items()},
        },
    )


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=Path("/tmp/olist-kaggle"))
    parser.add_argument("--output-dir", type=Path, default=repo_root / "evals" / "commerce" / "cases")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    for filename, expected_hash in RAW_SHA256.items():
        path = args.source_dir / filename
        if not path.is_file():
            raise SystemExit(f"Missing Olist source file: {path}")
        actual_hash = sha256(path)
        if actual_hash != expected_hash:
            raise SystemExit(f"Olist source hash mismatch for {filename}: {actual_hash}")

    raw = {filename: read_table(args.source_dir / filename) for filename in RAW_SHA256}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for spec in CASE_SPECS:
        if isinstance(spec, PeerCaseSpec):
            build_peer_case(spec, raw, args.output_dir)
        else:
            build_case(spec, raw, args.output_dir)
        print(f"built {spec.case_key}")


if __name__ == "__main__":
    main()
