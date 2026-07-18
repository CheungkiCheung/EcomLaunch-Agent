#!/usr/bin/env python3
"""Generate OpenSKU-Bench cases from Phase 1 public samples."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLES_DIR = REPO_ROOT / "data/opensku/samples"
CASES_DIR = REPO_ROOT / "evals/opensku/cases"

BASE_ARTIFACTS = [
    "launch-war-room.html",
    "evidence-ledger.json",
    "competitor-table.csv",
    "positioning-brief.md",
    "listing-pack.md",
    "content-pack.md",
    "launch-calendar.csv",
]

LOOP_ARTIFACTS = [
    "launch-state.json",
    "promotion-replan.md",
    "knowledge-deltas.json",
]

FORBIDDEN_PRIVATE_METRICS = [
    "Do not state GMV, CTR, CVR, ROI, CAC, ad spend, margin, refund rate, repeat purchase rate, or verified uplift unless those exact fields are present.",
    "Do not call public benchmark rows live merchant telemetry.",
]

UNSUPPORTED_SPEC_CLAIMS = [
    "Do not claim safety, compliance, material, compatibility, warranty, policy, or medical benefits unless the cited field explicitly supports the claim.",
    "Do not promote exact product specs when the evidence only contains review text or partial metadata.",
]


def load_samples() -> dict[str, dict[str, list[dict[str, Any]]]]:
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for path in sorted(SAMPLES_DIR.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            item = json.loads(line)
            grouped.setdefault(item["dataset"], {}).setdefault(item["component"], []).append(item["row"])
    return grouped


def clean_text(value: Any, fallback: str, max_len: int = 96) -> str:
    text = str(value or fallback).replace("\n", " ").replace("\r", " ").strip()
    if not text:
        text = fallback
    return text if len(text) <= max_len else text[: max_len - 1] + "..."


def evidence_ref(
    dataset: str,
    component: str,
    row_index: int,
    fields: list[str],
    source_type: str,
    note: str,
) -> dict[str, Any]:
    return {
        "source_type": source_type,
        "dataset": dataset,
        "component": component,
        "sample_file": f"data/opensku/samples/{dataset}.jsonl",
        "row_index": row_index,
        "fields": fields,
        "note": note,
    }


def make_case(
    case_id: str,
    stage: str,
    category: str,
    brief: str,
    expected_decision: str,
    expected_decision_rationale: str,
    source_dataset: list[str],
    public_context: list[dict[str, Any]] | None = None,
    uploaded_real: list[dict[str, Any]] | None = None,
    required_claims: list[str] | None = None,
    forbidden_claims: list[str] | None = None,
    scoring_notes: dict[str, Any] | None = None,
    evaluation_tags: list[str] | None = None,
    loop_artifacts: bool = False,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "stage": stage,
        "category": category,
        "brief": brief,
        "public_context": public_context or [],
        "uploaded_real": uploaded_real or [],
        "expected_decision": expected_decision,
        "expected_decision_rationale": expected_decision_rationale,
        "required_artifacts": BASE_ARTIFACTS + (LOOP_ARTIFACTS if loop_artifacts else []),
        "required_claims": required_claims
        or [
            "State that the evidence comes from public benchmark fixtures.",
            "Name at least one material limitation of the available evidence.",
        ],
        "forbidden_claims": forbidden_claims or [],
        "scoring_notes": scoring_notes
        or {
            "primary_failure_mode": "ungrounded recommendation",
            "must_reference_evidence": True,
        },
        "source_dataset": source_dataset,
        "evaluation_tags": evaluation_tags or [],
    }


def build_cases(samples: dict[str, dict[str, list[dict[str, Any]]]]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    amazon_reviews = samples["amazon_reviews"]["all_beauty_reviews"]
    amazon_meta = samples["amazon_reviews"]["all_beauty_metadata"]
    wands_query = samples["wands"]["query"]
    wands_product = samples["wands"]["product"]
    wands_label = samples["wands"]["label"]
    olist_orders = samples["olist"]["orders"]
    olist_items = samples["olist"]["order_items"]
    olist_reviews = samples["olist"]["order_reviews"]
    olist_payments = samples["olist"]["order_payments"]
    olist_products = samples["olist"]["products"]

    for i in range(6):
        review = amazon_reviews[i % len(amazon_reviews)]
        meta = amazon_meta[i % len(amazon_meta)]
        query = wands_query[i % len(wands_query)]
        title = clean_text(review.get("title"), "review signal")
        product_title = clean_text(meta.get("title"), "metadata product")
        category = clean_text(meta.get("main_category") or query.get("query_class"), "consumer product")
        decision = ["Hold", "Pivot", "Go", "Hold", "Pivot", "Kill"][i]
        cases.append(
            make_case(
                case_id=f"opensku-idea-{i + 1:03d}",
                stage="idea_only",
                category=category,
                brief=(
                    f"Assess an idea-only SKU opportunity around {product_title}. "
                    f"Use public review signal '{title}' and the WANDS query "
                    f"'{clean_text(query.get('query'), 'search query')}' as early demand context."
                ),
                expected_decision=decision,
                expected_decision_rationale=(
                    "The case has public VOC/search evidence but no supplier sample, "
                    "private margin, conversion, or inventory data, so the decision must stay bounded."
                ),
                source_dataset=["amazon_reviews", "wands"],
                public_context=[
                    evidence_ref(
                        "amazon_reviews",
                        "all_beauty_reviews",
                        i % len(amazon_reviews),
                        ["rating", "title", "text", "verified_purchase"],
                        "public_benchmark_fixture",
                        "VOC and rating context.",
                    ),
                    evidence_ref(
                        "amazon_reviews",
                        "all_beauty_metadata",
                        i % len(amazon_meta),
                        ["title", "description", "features", "price", "average_rating"],
                        "public_benchmark_fixture",
                        "Product metadata context.",
                    ),
                    evidence_ref(
                        "wands",
                        "query",
                        i % len(wands_query),
                        ["query", "query_class"],
                        "public_benchmark_fixture",
                        "Search-language context.",
                    ),
                ],
                forbidden_claims=FORBIDDEN_PRIVATE_METRICS if i < 3 else [],
                scoring_notes={
                    "primary_failure_mode": "overstating market proof from review/search evidence",
                    "must_reference_evidence": True,
                    "expected_limitations": ["no private sales data", "no ad attribution"],
                },
                evaluation_tags=[
                    "public_signal_context",
                    "stage_diagnosis",
                ]
                + (["forbidden_metric_trap"] if i < 3 else []),
            )
        )

    for i in range(6):
        meta = amazon_meta[i % len(amazon_meta)]
        product = wands_product[i % len(wands_product)]
        category = clean_text(
            meta.get("main_category") or product.get("product_class"),
            "supplier sample",
        )
        product_title = clean_text(meta.get("title") or product.get("product_name"), "sample product")
        cases.append(
            make_case(
                case_id=f"opensku-supplier-{i + 1:03d}",
                stage="supplier_sample",
                category=category,
                brief=(
                    f"Evaluate a supplier sample for {product_title}. The user uploaded a "
                    "sample sheet derived from public metadata and wants listing claims checked before pre-launch."
                ),
                expected_decision=["Hold", "Pivot", "Hold", "Go", "Pivot", "Hold"][i],
                expected_decision_rationale=(
                    "The sample has product metadata and feature text, but exact spec, safety, "
                    "policy, and compatibility claims must be limited to cited fields."
                ),
                source_dataset=["amazon_reviews", "wands"],
                public_context=[
                    evidence_ref(
                        "wands",
                        "product",
                        i % len(wands_product),
                        ["product_name", "product_class", "product_description", "product_features"],
                        "public_benchmark_fixture",
                        "Comparable public product attribute context.",
                    )
                ],
                uploaded_real=[
                    evidence_ref(
                        "amazon_reviews",
                        "all_beauty_metadata",
                        i % len(amazon_meta),
                        ["title", "description", "features", "details", "price"],
                        "public_fixture_as_uploaded_simulation",
                        "Simulates user-uploaded supplier/sample metadata.",
                    )
                ],
                forbidden_claims=UNSUPPORTED_SPEC_CLAIMS
                + (FORBIDDEN_PRIVATE_METRICS if i < 2 else []),
                scoring_notes={
                    "primary_failure_mode": "unsupported product/spec/policy claim",
                    "must_reference_evidence": True,
                    "must_refuse_exact_claims_without_fields": True,
                },
                evaluation_tags=[
                    "uploaded_data_simulation",
                    "unsupported_claim_trap",
                    "stage_diagnosis",
                ]
                + (["forbidden_metric_trap"] if i < 2 else []),
            )
        )

    for i in range(6):
        query = wands_query[i % len(wands_query)]
        product = wands_product[i % len(wands_product)]
        label = wands_label[i % len(wands_label)]
        query_text = clean_text(query.get("query"), "query")
        product_name = clean_text(product.get("product_name"), "candidate product")
        decision = ["Go", "Pivot", "Hold", "Go", "Pivot", "Hold"][i]
        cases.append(
            make_case(
                case_id=f"opensku-prelaunch-{i + 1:03d}",
                stage="pre_launch_test",
                category=clean_text(query.get("query_class") or product.get("product_class"), "search fit"),
                brief=(
                    f"Plan a pre-launch test for query '{query_text}' against candidate product "
                    f"'{product_name}'. The case should evaluate search fit without claiming live ranking."
                ),
                expected_decision=decision,
                expected_decision_rationale=(
                    "WANDS supplies public query, product, and relevance context. It supports "
                    "search-fit planning but not paid-search performance or live marketplace rank."
                ),
                source_dataset=["wands"],
                public_context=[
                    evidence_ref(
                        "wands",
                        "query",
                        i % len(wands_query),
                        ["query", "query_class"],
                        "public_benchmark_fixture",
                        "Query intent context.",
                    ),
                    evidence_ref(
                        "wands",
                        "product",
                        i % len(wands_product),
                        ["product_name", "product_class", "product_description", "product_features"],
                        "public_benchmark_fixture",
                        "Candidate product context.",
                    ),
                    evidence_ref(
                        "wands",
                        "label",
                        i % len(wands_label),
                        ["query_id", "product_id", "label"],
                        "public_benchmark_fixture",
                        "Public relevance judgement context.",
                    ),
                ],
                forbidden_claims=FORBIDDEN_PRIVATE_METRICS
                + (UNSUPPORTED_SPEC_CLAIMS if i < 2 else []),
                scoring_notes={
                    "primary_failure_mode": "confusing relevance labels with live conversion",
                    "must_reference_evidence": True,
                    "must_keep_launch_calendar_as_test_plan": True,
                },
                evaluation_tags=[
                    "public_signal_context",
                    "stage_diagnosis",
                ]
                + (["forbidden_metric_trap"] if i < 3 else [])
                + (["unsupported_claim_trap"] if i < 2 else []),
            )
        )

    for i in range(8):
        order = olist_orders[i % len(olist_orders)]
        item = olist_items[i % len(olist_items)]
        review = olist_reviews[i % len(olist_reviews)]
        payment = olist_payments[i % len(olist_payments)]
        product = olist_products[i % len(olist_products)]
        category = clean_text(product.get("product_category_name"), "olist category")
        decision = ["Hold", "Pivot", "Scale", "Hold", "Pivot", "Scale", "Hold", "Pivot"][i]
        cases.append(
            make_case(
                case_id=f"opensku-softlaunch-{i + 1:03d}",
                stage="soft_launch",
                category=category,
                brief=(
                    f"Diagnose a soft-launch snapshot for category '{category}' using uploaded "
                    "order, item, payment, review, and product rows derived from the Olist fixture."
                ),
                expected_decision=decision,
                expected_decision_rationale=(
                    "The uploaded simulation has order/review/payment/product evidence, but no "
                    "channel attribution, ad spend, margin, refund, or repeat purchase fields."
                ),
                source_dataset=["olist"],
                uploaded_real=[
                    evidence_ref(
                        "olist",
                        "orders",
                        i % len(olist_orders),
                        ["order_status", "order_purchase_timestamp", "order_delivered_customer_date", "order_estimated_delivery_date"],
                        "public_fixture_as_uploaded_simulation",
                        "Simulates uploaded order lifecycle evidence.",
                    ),
                    evidence_ref(
                        "olist",
                        "order_items",
                        i % len(olist_items),
                        ["price", "freight_value", "product_id", "seller_id"],
                        "public_fixture_as_uploaded_simulation",
                        "Simulates uploaded order-item economics evidence.",
                    ),
                    evidence_ref(
                        "olist",
                        "order_reviews",
                        i % len(olist_reviews),
                        ["review_score", "review_comment_title", "review_comment_message"],
                        "public_fixture_as_uploaded_simulation",
                        "Simulates uploaded customer-feedback evidence.",
                    ),
                    evidence_ref(
                        "olist",
                        "order_payments",
                        i % len(olist_payments),
                        ["payment_type", "payment_installments", "payment_value"],
                        "public_fixture_as_uploaded_simulation",
                        "Simulates uploaded payment evidence.",
                    ),
                    evidence_ref(
                        "olist",
                        "products",
                        i % len(olist_products),
                        ["product_category_name", "product_weight_g", "product_length_cm", "product_width_cm"],
                        "public_fixture_as_uploaded_simulation",
                        "Simulates uploaded product catalog evidence.",
                    ),
                ],
                forbidden_claims=FORBIDDEN_PRIVATE_METRICS,
                scoring_notes={
                    "primary_failure_mode": "inventing private growth metrics from order rows",
                    "must_reference_evidence": True,
                    "must_compute_only_supported_derived_metrics": True,
                },
                evaluation_tags=[
                    "uploaded_data_simulation",
                    "forbidden_metric_trap",
                    "stage_diagnosis",
                    "promotion_replan",
                    "knowledge_delta",
                ],
                loop_artifacts=True,
            )
        )

    for i in range(4):
        order = olist_orders[i % len(olist_orders)]
        review = olist_reviews[i % len(olist_reviews)]
        query = wands_query[i % len(wands_query)]
        category = clean_text(query.get("query_class"), "scale category")
        decision = ["Scale", "Hold", "Pivot", "Scale"][i]
        cases.append(
            make_case(
                case_id=f"opensku-scale-{i + 1:03d}",
                stage="scale_iterate",
                category=category,
                brief=(
                    f"Assess whether a launch loop should scale or replan after public order/review "
                    f"signals and search context for '{clean_text(query.get('query'), 'query')}'."
                ),
                expected_decision=decision,
                expected_decision_rationale=(
                    "Scale decisions require loop evidence and explicit limitations. The case can "
                    "use public order/review/search fixtures but cannot infer causal uplift."
                ),
                source_dataset=["olist", "wands"],
                public_context=[
                    evidence_ref(
                        "olist",
                        "orders",
                        i % len(olist_orders),
                        ["order_status", "order_purchase_timestamp", "order_estimated_delivery_date"],
                        "public_benchmark_fixture",
                        "Order lifecycle context for loop diagnosis.",
                    ),
                    evidence_ref(
                        "olist",
                        "order_reviews",
                        i % len(olist_reviews),
                        ["review_score", "review_comment_title", "review_comment_message"],
                        "public_benchmark_fixture",
                        "Review context for knowledge deltas.",
                    ),
                    evidence_ref(
                        "wands",
                        "query",
                        i % len(wands_query),
                        ["query", "query_class"],
                        "public_benchmark_fixture",
                        "Search context for scale positioning.",
                    ),
                ],
                forbidden_claims=FORBIDDEN_PRIVATE_METRICS,
                scoring_notes={
                    "primary_failure_mode": "claiming causal uplift from public fixture context",
                    "must_reference_evidence": True,
                    "must_include_replan_or_knowledge_delta": True,
                },
                evaluation_tags=[
                    "public_signal_context",
                    "forbidden_metric_trap",
                    "stage_diagnosis",
                    "promotion_replan",
                    "knowledge_delta",
                ],
                loop_artifacts=True,
            )
        )

    return cases


def write_cases(cases: list[dict[str, Any]]) -> None:
    CASES_DIR.mkdir(parents=True, exist_ok=True)
    for old_case in CASES_DIR.glob("*.json"):
        old_case.unlink()
    for case in cases:
        path = CASES_DIR / f"{case['case_id']}.json"
        path.write_text(
            json.dumps(case, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def main() -> int:
    samples = load_samples()
    cases = build_cases(samples)
    write_cases(cases)
    print(f"wrote_cases={len(cases)}")
    print(f"cases_dir={CASES_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

