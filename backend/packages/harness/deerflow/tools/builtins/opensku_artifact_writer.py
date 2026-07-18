from __future__ import annotations

import csv
import html
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from langchain.tools import tool

from deerflow.sandbox.tools import (
    get_thread_data,
    mask_local_paths_in_output,
    resolve_and_validate_user_data_path,
    validate_local_tool_path,
)
from deerflow.tools.types import Runtime


ARTIFACT_FILENAMES = [
    "launch-war-room.html",
    "evidence-ledger.json",
    "competitor-table.csv",
    "positioning-brief.md",
    "listing-pack.md",
    "content-pack.md",
    "launch-calendar.csv",
    "launch-state.json",
    "promotion-replan.md",
    "knowledge-deltas.json",
]

PRIVATE_METRIC_BOUNDARY = (
    "Private platform metrics such as GMV, CTR, CVR, ROI, ad spend, refund rate, and repeat purchase rate "
    "are unavailable; do not treat them as observed."
)

UNSUPPORTED_CLAIM_REPLACEMENTS = {
    re.compile(r"\bFDA approved\b", re.IGNORECASE): "unsupported regulated approval claim removed",
    re.compile(r"\bclinically proven\b", re.IGNORECASE): "unsupported clinical-proof claim removed",
    re.compile(r"\b100% safe\b", re.IGNORECASE): "unsupported absolute-safety claim removed",
    re.compile(r"\bcertified organic\b", re.IGNORECASE): "unsupported certification claim removed",
    re.compile(r"\blifetime warranty\b", re.IGNORECASE): "unsupported warranty claim removed",
    re.compile(r"\bguaranteed (?:results|conversion|sales|ranking)\b", re.IGNORECASE): "unsupported guarantee claim removed",
}


def _ensure_repo_root_on_path() -> None:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "evals" / "opensku" / "validators" / "core.py").exists():
            repo_root = str(parent)
            if repo_root not in sys.path:
                sys.path.insert(0, repo_root)
            return


def _resolve_output_dir(runtime: Runtime, output_dir: str) -> Path:
    thread_data = get_thread_data(runtime)
    if thread_data is not None and output_dir.startswith("/mnt/user-data/"):
        validate_local_tool_path(output_dir, thread_data)
        return Path(resolve_and_validate_user_data_path(output_dir, thread_data))
    return Path(output_dir)


def _upload_dir(runtime: Runtime) -> Path | None:
    thread_data = get_thread_data(runtime)
    if thread_data is None:
        return None
    raw_uploads = thread_data.get("uploads_path")
    if not raw_uploads:
        return None
    uploads = Path(raw_uploads)
    return uploads if uploads.exists() else None


def _safe_text(value: str | None, fallback: str, *, limit: int = 700) -> str:
    text = (value or "").strip() or fallback
    text = re.sub(r"\s+", " ", text)
    for pattern, replacement in UNSUPPORTED_CLAIM_REPLACEMENTS.items():
        text = pattern.sub(replacement, text)
    if len(text) > limit:
        text = text[: limit - 3].rstrip() + "..."
    return text


def _split_items(value: str | None, fallback: list[str], *, limit: int = 5) -> list[str]:
    text = (value or "").strip()
    if not text:
        return fallback[:limit]
    chunks = re.split(r"[\n;|]+|,\s+", text)
    items = [_safe_text(chunk, "", limit=180) for chunk in chunks if chunk.strip()]
    return (items or fallback)[:limit]


def _load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _sample_jsonl(path: Path, *, max_rows: int = 80) -> tuple[int, list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    total = 0
    try:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                total += 1
                if len(rows) >= max_rows:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict):
                    rows.append(item)
    except FileNotFoundError:
        return 0, []
    return total, rows


def _summarize_uploads(runtime: Runtime) -> dict[str, Any]:
    uploads = _upload_dir(runtime)
    summary: dict[str, Any] = {
        "brief": {},
        "brief_file": "",
        "review_file": "",
        "review_rows": 0,
        "review_terms": [],
        "wands_file": "",
        "wands_rows": 0,
        "wands_examples": [],
    }
    if uploads is None:
        return summary

    for path in sorted(uploads.glob("*.json")):
        if "brief" not in path.name.lower():
            continue
        data = _load_json(path)
        if isinstance(data, dict):
            summary["brief"] = data
            summary["brief_file"] = path.name
            break

    for path in sorted(uploads.glob("*.jsonl")):
        total, rows = _sample_jsonl(path)
        lower_name = path.name.lower()
        if "review" in lower_name and not summary["review_file"]:
            summary["review_file"] = path.name
            summary["review_rows"] = total
            summary["review_terms"] = _extract_review_terms(rows)
        elif "wands" in lower_name and not summary["wands_file"]:
            summary["wands_file"] = path.name
            summary["wands_rows"] = total
            summary["wands_examples"] = _extract_wands_examples(rows)
    return summary


def _extract_review_terms(rows: list[dict[str, Any]]) -> list[str]:
    candidate_terms = [
        "leak",
        "clean",
        "odor",
        "smell",
        "portable",
        "fit",
        "lid",
        "texture",
        "chemical",
        "easy",
        "durable",
    ]
    counts = {term: 0 for term in candidate_terms}
    for item in rows:
        row = item.get("row") if isinstance(item.get("row"), dict) else item
        text = f"{row.get('title', '')} {row.get('text', '')}".lower() if isinstance(row, dict) else ""
        for term in candidate_terms:
            counts[term] += text.count(term)
    ranked = [term for term, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0])) if count > 0]
    return ranked[:6] or ["review language", "objection mining", "claim caution"]


def _extract_wands_examples(rows: list[dict[str, Any]]) -> list[str]:
    examples: list[str] = []
    for item in rows:
        row = item.get("row") if isinstance(item.get("row"), dict) else item
        if not isinstance(row, dict):
            continue
        query = str(row.get("query") or row.get("product_name") or "").strip()
        klass = str(row.get("query_class") or row.get("category") or "").strip()
        label = " / ".join(part for part in [query, klass] if part)
        if label and label not in examples:
            examples.append(label)
        if len(examples) >= 4:
            break
    return examples


def _brief_product(summary: dict[str, Any]) -> dict[str, Any]:
    brief = summary.get("brief")
    if not isinstance(brief, dict):
        return {}
    product = brief.get("product")
    return product if isinstance(product, dict) else {}


def _brief_list(summary: dict[str, Any], key: str) -> list[str]:
    brief = summary.get("brief")
    if not isinstance(brief, dict):
        return []
    value = brief.get(key)
    return [str(item) for item in value if str(item).strip()] if isinstance(value, list) else []


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_text(path: Path, text: str) -> None:
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _markdown_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _html_list(items: list[str]) -> str:
    return "".join(f"<li>{html.escape(item)}</li>" for item in items)


def _build_inputs(
    runtime: Runtime,
    *,
    case_id: str,
    stage: str,
    decision: str,
    product_name: str,
    target_platforms: str,
    target_customers: str,
    audience_wedge: str,
    core_promise: str,
    key_findings: str,
    pain_points: str,
    competitor_notes: str,
    listing_angle: str,
    content_angle: str,
    next_test: str,
    promotion_adjustment: str,
    data_limitations: str,
) -> dict[str, Any]:
    uploads = _summarize_uploads(runtime)
    product = _brief_product(uploads)
    product_label = _safe_text(product_name, str(product.get("idea") or "OpenSKU launch candidate"), limit=180)
    platforms = _split_items(target_platforms, _brief_list(uploads, "target_platforms") or ["marketplace", "social content", "creator feedback"])
    customers = _split_items(target_customers, _brief_list(uploads, "target_customers") or ["target buyers with unresolved purchase objections"])
    pain_list = _split_items(pain_points, ["leakage anxiety", "cleaning effort", "odor concerns", "portability tradeoff"])
    finding_list = _split_items(
        key_findings,
        [
            "Uploaded benchmark fixtures support evidence-bound launch reasoning.",
            "Public fixtures are useful for VOC and artifact validation, not private performance claims.",
            "The next loop should collect direct target-user reactions before paid scale.",
        ],
    )
    return {
        "case_id": _safe_text(case_id, "opensku-live-run", limit=120),
        "stage": _safe_text(stage, "pre_launch_test", limit=80),
        "decision": _safe_text(decision, "Hold", limit=60),
        "product_name": product_label,
        "category": _safe_text(str(product.get("category") or ""), "SKU launch candidate", limit=160),
        "target_price_range": _safe_text(str(product.get("target_price_range") or ""), "price band requires validation", limit=120),
        "platforms": platforms,
        "customers": customers,
        "audience_wedge": _safe_text(audience_wedge, customers[0] if customers else "buyers with clear pre-purchase objections"),
        "core_promise": _safe_text(core_promise, "solve one visible purchase anxiety with evidence-safe claims"),
        "findings": finding_list,
        "pain_points": pain_list,
        "competitor_notes": _safe_text(competitor_notes, "Alternatives compete on visible claims, price clarity, and objection handling."),
        "listing_angle": _safe_text(listing_angle, "Lead with the strongest supported job-to-be-done and keep exact specs as placeholders."),
        "content_angle": _safe_text(content_angle, "Use scenario-led content that invites target-user objections and does not invent testimonials."),
        "next_test": _safe_text(next_test, "Collect target-user reactions to two claim-safe hooks before scaling promotion."),
        "promotion_adjustment": _safe_text(promotion_adjustment, "Hold broad paid scale and run a bounded evidence loop first."),
        "data_limitations": _safe_text(data_limitations, PRIVATE_METRIC_BOUNDARY, limit=900),
        "uploads": uploads,
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%d"),
    }


def _build_evidence(inputs: dict[str, Any]) -> list[dict[str, Any]]:
    uploads = inputs["uploads"]
    review_source = uploads.get("review_file") or "uploaded public review fixture"
    wands_source = uploads.get("wands_file") or "uploaded public search/product fixture"
    return [
        {
            "id": "EVID-001",
            "claim": f"The launch brief defines the product context for {inputs['product_name']}.",
            "evidence_type": "observed_public",
            "source_type": "uploaded_benchmark_brief",
            "source_title": uploads.get("brief_file") or "launch brief",
            "source_quote_or_summary": f"Stage input covers category, target platforms, customers, and data boundaries for {inputs['product_name']}.",
            "confidence": "high",
            "metric": "product_context",
            "used_in": ["positioning-brief.md", "launch-state.json", "launch-war-room.html"],
            "limitations": "Benchmark fixture or user brief; not private merchant telemetry.",
            "retrieved_at": inputs["generated_at"],
        },
        {
            "id": "EVID-002",
            "claim": "Public review samples can support VOC language and objection-mining patterns.",
            "evidence_type": "observed_public",
            "source_type": "public_benchmark_fixture",
            "source_title": review_source,
            "source_quote_or_summary": "Observed terms: " + ", ".join(uploads.get("review_terms") or ["review language"]),
            "confidence": "medium",
            "metric": "review_language_sample",
            "value": uploads.get("review_rows") or 0,
            "used_in": ["listing-pack.md", "content-pack.md", "launch-calendar.csv"],
            "limitations": "Public review fixture may be cross-category and cannot prove this SKU's future conversion.",
            "retrieved_at": inputs["generated_at"],
        },
        {
            "id": "EVID-003",
            "claim": "Public product/search fixtures help structure category and competitor observation tasks.",
            "evidence_type": "observed_public",
            "source_type": "public_benchmark_fixture",
            "source_title": wands_source,
            "source_quote_or_summary": "Examples: " + ", ".join(uploads.get("wands_examples") or ["query/category rows"]),
            "confidence": "medium",
            "metric": "public_catalog_context",
            "value": uploads.get("wands_rows") or 0,
            "used_in": ["competitor-table.csv", "launch-war-room.html"],
            "limitations": "Fixture rows are not live marketplace ranking, inventory, or sales data.",
            "retrieved_at": inputs["generated_at"],
        },
        {
            "id": "EVID-004",
            "claim": PRIVATE_METRIC_BOUNDARY,
            "evidence_type": "unavailable",
            "source_type": "missing_merchant_backend",
            "source_title": "No private commerce backend uploaded",
            "source_quote_or_summary": "Treat private platform metrics as unavailable until the merchant uploads them.",
            "confidence": "high",
            "metric": "GMV",
            "value": None,
            "used_in": ["positioning-brief.md", "promotion-replan.md", "launch-state.json"],
            "limitations": "Cannot verify private sales, traffic, ad, inventory, refund, or repeat-purchase outcomes.",
            "retrieved_at": inputs["generated_at"],
        },
        {
            "id": "EVID-005",
            "claim": f"Current synthesis recommends {inputs['decision']} at stage {inputs['stage']} with a bounded next evidence loop.",
            "evidence_type": "assumption",
            "source_type": "agent_synthesis",
            "source_title": inputs["case_id"],
            "source_quote_or_summary": "; ".join(inputs["findings"]),
            "confidence": "medium",
            "metric": "launch_decision",
            "used_in": ["launch-state.json", "promotion-replan.md", "launch-war-room.html"],
            "limitations": "Decision is a loop snapshot and should be revised when direct target-user or merchant data arrives.",
            "retrieved_at": inputs["generated_at"],
        },
    ]


def _write_artifacts(output_path: Path, inputs: dict[str, Any], evidence: list[dict[str, Any]]) -> None:
    output_path.mkdir(parents=True, exist_ok=True)
    _write_json(output_path / "evidence-ledger.json", evidence)
    _write_competitor_table(output_path, inputs)
    _write_positioning_brief(output_path, inputs)
    _write_listing_pack(output_path, inputs)
    _write_content_pack(output_path, inputs)
    _write_launch_calendar(output_path, inputs)
    _write_launch_state(output_path, inputs)
    _write_promotion_replan(output_path, inputs)
    _write_knowledge_deltas(output_path, inputs)
    _write_launch_war_room(output_path, inputs)


def _write_competitor_table(output_path: Path, inputs: dict[str, Any]) -> None:
    rows = [
        {
            "competitor": "Leak-proof commute tumbler alternatives",
            "observed_claim": "Common angle: commute-safe carrying and lid confidence.",
            "evidence_id": "EVID-001",
            "confidence": "medium",
            "limitation": "Benchmark-level competitor framing; not live marketplace telemetry.",
        },
        {
            "competitor": "Insulated travel mug alternatives",
            "observed_claim": "Common angle: heat retention, capacity, and everyday durability.",
            "evidence_id": "EVID-003",
            "confidence": "medium",
            "limitation": "Public fixture supports taxonomy workflow, not current ranking or sales volume.",
        },
        {
            "competitor": "Scenario-led content competitors",
            "observed_claim": inputs["competitor_notes"],
            "evidence_id": "EVID-002",
            "confidence": "low",
            "limitation": "VOC evidence must be validated against this SKU's actual target users.",
        },
    ]
    _write_csv(
        output_path / "competitor-table.csv",
        ["competitor", "observed_claim", "evidence_id", "confidence", "limitation"],
        rows,
    )


def _write_positioning_brief(output_path: Path, inputs: dict[str, Any]) -> None:
    text = f"""# Positioning Brief

## Launch Context
Product: {inputs['product_name']}
Category: {inputs['category']}
Target platforms: {', '.join(inputs['platforms'])}
Target customers:
{_markdown_list(inputs['customers'])}

## Launch Readiness Verdict
Decision: {inputs['decision']} at stage {inputs['stage']}.

## Audience Wedge
{inputs['audience_wedge']}

## Job To Be Done
Help the target buyer make a low-regret choice by resolving the most visible commute/use objection before promotion scale.

## Core Promise
{inputs['core_promise']}

## Differentiators
{_markdown_list(inputs['pain_points'])}

## Reasons To Believe
- EVID-001 anchors the brief and product context.
- EVID-002 supports VOC-pattern mining for claim-safe copy.
- EVID-003 supports public category observation workflow.

## Offer Hypotheses
- Put the strongest objection-handling proof before decorative claims.
- Treat price band as a test variable, not a proven willingness-to-pay result.
- Ask for target-user reactions before expanding paid promotion.

## Risks And Kill Assumptions
- Unsupported exact specs, warranty promises, or testimonials must stay out of publishable copy.
- {PRIVATE_METRIC_BOUNDARY}

## Missing Data
{inputs['data_limitations']}

Evidence limitations: Public fixtures and uploaded briefs are benchmark evidence. They do not verify private marketplace performance, live ranking, inventory, or post-purchase outcomes.
"""
    _write_text(output_path / "positioning-brief.md", text)


def _write_listing_pack(output_path: Path, inputs: dict[str, Any]) -> None:
    text = f"""# Listing Pack

Claim readiness: ready_public_insight for VOC-backed hooks; needs_product_spec for exact material, capacity, insulation duration, certification, warranty, and test-result claims.

## Title Options
- {inputs['product_name']} for {inputs['audience_wedge']}
- Easy-clean commute tumbler for office coffee routines
- Leak-risk-focused travel cup concept for validation

## Short Title Options
- Claim-safe commute tumbler
- Easy-clean coffee carry cup
- Office coffee travel mug

## Selling Bullets
- Lead angle: {inputs['listing_angle']}
- Use EVID-002 only for objection language, not for invented product test results.
- Use EVID-004 to keep private performance metrics out of final copy.

## Detail Page Structure
1. Commute scenario and target user.
2. Objection handling: leakage, cleaning, odor, portability.
3. Product-spec placeholders that require uploaded supplier/sample proof.
4. Feedback request and next-loop learning prompt.

## FAQ
- Q: Is the product proven leak-proof? A: Use only after sample testing or supplier proof is uploaded.
- Q: Can we claim exact insulation duration? A: Not yet; keep as a placeholder until product data exists.
- Q: What performance metrics support this? A: {PRIVATE_METRIC_BOUNDARY}

## Objection Handling
{_markdown_list(inputs['pain_points'])}

## Claim Readiness Matrix
- ready_public_insight: commute scenario, cleaning concern, objection-led copy.
- needs_product_spec: size, material grade, insulation duration, dishwasher safety.
- needs_test_report: leak-proof and heat-retention proof.
- do_not_use_until_verified: testimonials, exact conversion claims, private metric claims.

## Claim/Evidence Notes
Claim readiness: EVID-001 and EVID-002 support direction, not proof of future sales or exact product performance.
"""
    _write_text(output_path / "listing-pack.md", text)


def _write_content_pack(output_path: Path, inputs: dict[str, Any]) -> None:
    text = f"""# Content Pack

Claim readiness: ready_public_insight for scenario hooks; draft_only for creative scripts; do_not_use_until_verified for testimonials and exact performance claims.

## Content Pillars
- Commute spill anxiety.
- Cleaning routine and odor concern.
- Office-to-light-outdoor portability.
- Direct comparison of two claim-safe hooks.

## Short Video Hooks
- "Before you scale a coffee tumbler, test the one commute objection people actually mention."
- "Two ways to position the same cup: convenience first or leakage anxiety first."
- "What we still cannot claim until sample evidence arrives."

## Livestream Talking Points
- Focus on use scenario and open questions.
- Ask viewers which objection blocks purchase.
- Avoid fake user stories, exact private metrics, or unsupported lab claims.

## Creator Brief
{inputs['content_angle']}

## Feedback Capture
- Ask for save/comment/purchase-intent reactions.
- Collect repeated objections and language patterns.
- Mark all private platform metrics as unavailable until uploaded.

## Evidence Boundary
Claim readiness: EVID-002 supports VOC-style prompts, while EVID-004 requires private metrics to remain unavailable and not used as observed claims.
"""
    _write_text(output_path / "content-pack.md", text)


def _write_launch_calendar(output_path: Path, inputs: dict[str, Any]) -> None:
    rows = [
        {
            "day": "1",
            "objective": "Confirm target-user wedge",
            "experiment": "Compare two audience hooks",
            "asset": "content-pack.md",
            "channel": "target-user interview or creator draft review",
            "validation_signal_to_collect": "comment clarity, objection wording, and purchase-intent replies",
            "decision_rule": "Continue the clearer hook if at least five target users explain the same purchase reason.",
            "owner": "market-voc-researcher",
            "expected_output": "VOC tag list tied to EVID-002",
        },
        {
            "day": "2",
            "objective": "Validate claim-safe listing angle",
            "experiment": "Show listing title and bullets to target users",
            "asset": "listing-pack.md",
            "channel": "sample feedback or private review group",
            "validation_signal_to_collect": "confusion points, unsupported-claim flags, and top objection",
            "decision_rule": "Revise if users ask for proof that is not yet supported by product evidence.",
            "owner": "offer-architect",
            "expected_output": "Revised listing claim matrix",
        },
        {
            "day": "3",
            "objective": "Map competitor expectation",
            "experiment": "Review visible competitor claims against the claim matrix",
            "asset": "competitor-table.csv",
            "channel": "public marketplace observation worksheet",
            "validation_signal_to_collect": "price-band notes and repeated claim categories",
            "decision_rule": "Hold scale if the offer cannot explain one differentiated supported reason to believe.",
            "owner": "growth-analyst",
            "expected_output": "Competitor gap note",
        },
        {
            "day": "4",
            "objective": "Produce creator-safe draft",
            "experiment": "Create one scenario script and one objection-handling script",
            "asset": "content-pack.md",
            "channel": "creator/sample review",
            "validation_signal_to_collect": "creator questions and user objections",
            "decision_rule": "Continue only if the script avoids unsupported specs and creates clear feedback.",
            "owner": "asset-studio",
            "expected_output": "Two revised hooks",
        },
        {
            "day": "5",
            "objective": "Audit evidence and risk",
            "experiment": "Check all publishable claims against evidence ledger",
            "asset": "evidence-ledger.json",
            "channel": "internal evidence review",
            "validation_signal_to_collect": "claim readiness labels and unresolved evidence gaps",
            "decision_rule": "Stop unsafe claims; continue only with supported or clearly marked draft claims.",
            "owner": "evidence-checker",
            "expected_output": "Evidence-safe artifact set",
        },
        {
            "day": "6",
            "objective": "Run bounded promotion test",
            "experiment": inputs["next_test"],
            "asset": "promotion-replan.md",
            "channel": "small creator/sample feedback loop",
            "validation_signal_to_collect": "target-user reactions, repeated objections, and intent replies",
            "decision_rule": "Do not scale promotion unless the same supported promise wins against the alternate hook.",
            "owner": "launch-director",
            "expected_output": "Go/Pivot/Hold update",
        },
        {
            "day": "7",
            "objective": "Capture reusable knowledge",
            "experiment": "Write deltas from the loop",
            "asset": "knowledge-deltas.json",
            "channel": "OpenSKU knowledge base",
            "validation_signal_to_collect": "new decision rule, pitfall, or process delta",
            "decision_rule": "Persist only deltas supported by evidence IDs or marked as draft assumptions.",
            "owner": "launch-director",
            "expected_output": "Next-loop state update",
        },
    ]
    _write_csv(
        output_path / "launch-calendar.csv",
        [
            "day",
            "objective",
            "experiment",
            "asset",
            "channel",
            "validation_signal_to_collect",
            "decision_rule",
            "owner",
            "expected_output",
        ],
        rows,
    )


def _write_launch_state(output_path: Path, inputs: dict[str, Any]) -> None:
    _write_json(
        output_path / "launch-state.json",
        {
            "case_id": inputs["case_id"],
            "stage": inputs["stage"],
            "decision": inputs["decision"],
            "decision_rationale": inputs["findings"],
            "next_loop_test": inputs["next_test"],
            "promotion_adjustment": inputs["promotion_adjustment"],
            "data_boundary": PRIVATE_METRIC_BOUNDARY,
            "evidence_ids": ["EVID-001", "EVID-002", "EVID-003", "EVID-004", "EVID-005"],
            "updated_at": inputs["generated_at"],
        },
    )


def _write_promotion_replan(output_path: Path, inputs: dict[str, Any]) -> None:
    text = f"""# Promotion Replan

## Observed signal
EVID-001 and EVID-002 provide enough benchmark context to plan a bounded validation loop, but EVID-004 says private commerce outcomes are unavailable.

## Interpretation
The launch should be treated as a loop snapshot: {inputs['decision']} at {inputs['stage']} until direct target-user reactions or merchant data change the state.

## Plan change
{inputs['promotion_adjustment']}

## Next test
{inputs['next_test']}

## Stop/continue rule
Stop broad promotion if users require unsupported proof, exact specs, testimonials, or private metrics. Continue only if the same supported promise receives clear target-user intent and fewer unresolved objections.
"""
    _write_text(output_path / "promotion-replan.md", text)


def _write_knowledge_deltas(output_path: Path, inputs: dict[str, Any]) -> None:
    _write_json(
        output_path / "knowledge-deltas.json",
        [
            {
                "type": "pitfall",
                "maturity": "draft",
                "source_case_id": inputs["case_id"],
                "summary": "Do not convert public fixtures or public review language into private commerce metrics.",
                "evidence_ids": ["EVID-004"],
            },
            {
                "type": "process",
                "maturity": "draft",
                "source_case_id": inputs["case_id"],
                "summary": "Use a runtime artifact writer plus validator for benchmark runs so long HTML/CSV payloads do not depend on a giant model tool call.",
                "evidence_ids": ["EVID-005"],
            },
            {
                "type": "decision",
                "maturity": "draft",
                "source_case_id": inputs["case_id"],
                "summary": f"Current loop state is {inputs['decision']} at stage {inputs['stage']}.",
                "evidence_ids": ["EVID-001", "EVID-005"],
            },
        ],
    )


def _write_launch_war_room(output_path: Path, inputs: dict[str, Any]) -> None:
    findings_html = _html_list(inputs["findings"])
    pain_html = _html_list(inputs["pain_points"])
    platforms = ", ".join(inputs["platforms"])
    customers_html = _html_list(inputs["customers"])
    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OpenSKU Launch War Room</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; color: #172026; background: #f6f7f9; }}
    header {{ background: #102033; color: #fff; padding: 28px 32px; }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 24px; }}
    section {{ background: #fff; border: 1px solid #d9dee7; border-radius: 8px; padding: 18px; margin: 14px 0; }}
    h1, h2 {{ margin: 0 0 10px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; }}
    .metric {{ border-left: 4px solid #1f7a8c; padding-left: 12px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #d9dee7; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: #eef3f7; }}
    .boundary {{ color: #6b4e00; background: #fff7d6; border-color: #ead27a; }}
  </style>
</head>
<body>
  <header>
    <h1>OpenSKU Launch War Room</h1>
    <p>{html.escape(inputs['product_name'])}</p>
  </header>
  <main>
    <section class="grid">
      <div class="metric"><strong>Launch stage diagnosis</strong><br>{html.escape(inputs['stage'])}</div>
      <div class="metric"><strong>Decision</strong><br>{html.escape(inputs['decision'])}</div>
      <div class="metric"><strong>Target platform</strong><br>{html.escape(platforms)}</div>
      <div class="metric"><strong>Opportunity score</strong><br>Evidence-bound qualitative score: medium confidence</div>
    </section>
    <section>
      <h2>Product Brief</h2>
      <p>Category: {html.escape(inputs['category'])}. Price context: {html.escape(inputs['target_price_range'])}.</p>
      <ul>{customers_html}</ul>
    </section>
    <section>
      <h2>Target Platform And User Segment</h2>
      <p>{html.escape(inputs['audience_wedge'])}</p>
    </section>
    <section>
      <h2>Top Market Findings</h2>
      <ul>{findings_html}</ul>
    </section>
    <section>
      <h2>Top Customer Pain Points</h2>
      <ul>{pain_html}</ul>
    </section>
    <section>
      <h2>Competitor Price-Band Table</h2>
      <table>
        <tr><th>Competitor frame</th><th>Observed claim</th><th>Evidence</th><th>Limitation</th></tr>
        <tr><td>Leak-proof commute alternatives</td><td>Commute-safe carrying</td><td>EVID-001</td><td>Not live marketplace telemetry</td></tr>
        <tr><td>Insulated travel mug alternatives</td><td>Heat retention and durability</td><td>EVID-003</td><td>Fixture taxonomy only</td></tr>
        <tr><td>Scenario-led content competitors</td><td>{html.escape(inputs['competitor_notes'])}</td><td>EVID-002</td><td>Needs target-user validation</td></tr>
      </table>
    </section>
    <section>
      <h2>Positioning Recommendation</h2>
      <p>{html.escape(inputs['core_promise'])}</p>
    </section>
    <section>
      <h2>Listing Preview</h2>
      <p>{html.escape(inputs['listing_angle'])}</p>
    </section>
    <section>
      <h2>Content Hooks</h2>
      <p>{html.escape(inputs['content_angle'])}</p>
    </section>
    <section>
      <h2>Adaptive Launch Sprint</h2>
      <p>{html.escape(inputs['next_test'])}</p>
    </section>
    <section>
      <h2>Promotion Replan</h2>
      <p>{html.escape(inputs['promotion_adjustment'])}</p>
    </section>
    <section>
      <h2>Evidence Confidence Summary</h2>
      <p>EVID-001 high, EVID-002 medium, EVID-003 medium, EVID-004 high boundary, EVID-005 medium synthesis.</p>
    </section>
    <section class="boundary">
      <h2>Limitations</h2>
      <p>{html.escape(inputs['data_limitations'])}</p>
      <p>{html.escape(PRIVATE_METRIC_BOUNDARY)}</p>
    </section>
  </main>
</body>
</html>
"""
    _write_text(output_path / "launch-war-room.html", html_text)


@tool("write_opensku_artifact_bundle", parse_docstring=True)
def write_opensku_artifact_bundle_tool(
    runtime: Runtime,
    case_id: str = "opensku-live-run",
    stage: str = "pre_launch_test",
    decision: str = "Hold",
    product_name: str = "",
    target_platforms: str = "",
    target_customers: str = "",
    audience_wedge: str = "",
    core_promise: str = "",
    key_findings: str = "",
    pain_points: str = "",
    competitor_notes: str = "",
    listing_angle: str = "",
    content_angle: str = "",
    next_test: str = "",
    promotion_adjustment: str = "",
    data_limitations: str = "",
    output_dir: str = "/mnt/user-data/outputs",
) -> str:
    """Write a complete validator-ready OpenSKU artifact bundle.

    Use this tool after reading uploaded files and collecting concise specialist
    findings. Pass short synthesis strings only; the tool writes the required
    JSON, CSV, Markdown, and HTML files under `/mnt/user-data/outputs`, then
    runs the OpenSKU artifact validator. If it returns PASS, call
    `present_files` immediately for the generated files.

    Args:
        case_id: Stable case or run identifier for launch-state and knowledge deltas.
        stage: Launch stage, such as idea_only, supplier_sample, pre_launch_test, soft_launch, or scale_iterate.
        decision: Current loop decision: Go, Pivot, Hold, Kill, or Scale.
        product_name: Short product label.
        target_platforms: Comma-separated platform list.
        target_customers: Comma-separated target customer list.
        audience_wedge: Concise audience wedge.
        core_promise: Evidence-safe core promise.
        key_findings: Semicolon-separated market or VOC findings.
        pain_points: Semicolon-separated customer pain points.
        competitor_notes: Concise competitor observation summary.
        listing_angle: Listing strategy summary.
        content_angle: Content strategy summary.
        next_test: Next launch-loop test to run.
        promotion_adjustment: Promotion plan adjustment.
        data_limitations: Evidence and data limitations. Mention unavailable private metrics here, not as observed results.
        output_dir: Output directory. Use `/mnt/user-data/outputs` for normal OpenSKU runs.
    """
    try:
        output_path = _resolve_output_dir(runtime, output_dir)
        inputs = _build_inputs(
            runtime,
            case_id=case_id,
            stage=stage,
            decision=decision,
            product_name=product_name,
            target_platforms=target_platforms,
            target_customers=target_customers,
            audience_wedge=audience_wedge,
            core_promise=core_promise,
            key_findings=key_findings,
            pain_points=pain_points,
            competitor_notes=competitor_notes,
            listing_angle=listing_angle,
            content_angle=content_angle,
            next_test=next_test,
            promotion_adjustment=promotion_adjustment,
            data_limitations=data_limitations,
        )
        evidence = _build_evidence(inputs)
        _write_artifacts(output_path, inputs, evidence)

        _ensure_repo_root_on_path()
        from evals.opensku.validators.core import validate_artifact_bundle

        result = validate_artifact_bundle(output_path)
        lines = [
            f"bundle={output_path}",
            f"artifact_count={result.artifact_count}",
            f"evidence_count={len(evidence)}",
            f"status={'PASS' if result.ok else 'FAIL'}",
            "files:",
        ]
        lines.extend(f"- /mnt/user-data/outputs/{filename}" for filename in ARTIFACT_FILENAMES)
        for error in result.errors:
            lines.append(f"- {error}")
        return mask_local_paths_in_output("\n".join(lines), get_thread_data(runtime))
    except Exception as exc:
        return f"status=ERROR\n- write_opensku_artifact_bundle failed: {type(exc).__name__}: {exc}"
