#!/usr/bin/env python3
"""Run a real OpenSKU live validation through the gateway runtime.

This runner intentionally uses the real FastAPI app, auth cookies, CSRF
middleware, run manager, lead-agent factory, ecom-launch agent context, and
configured live model. It is not a unit test and does not mock the LLM.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
RUNS_ROOT = REPO_ROOT / "docs/progress/runs"
DEFAULT_CASE_ID = "live-demo-portable-coffee-tumbler-001"
DEFAULT_DATE = "2026-06-27"

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(BACKEND_ROOT))

from evals.opensku.knowledge_context import (  # noqa: E402
    KnowledgePattern,
    format_knowledge_context,
    load_knowledge_patterns,
    patterns_for_manifest,
    resolve_knowledge_dir,
    select_knowledge_patterns,
)


REQUIRED_ARTIFACTS = [
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

EXTERNAL_SEARCH_TOOLS = {
    "web_search",
    "web_fetch",
    "image_search",
}
ARTIFACT_WRITER_TOOL = "write_opensku_artifact_bundle"


@dataclass
class ParsedStream:
    events: list[dict[str, Any]]
    latest_state: dict[str, Any]
    final_response: str
    model_name: str | None
    model_provider: str | None
    token_usage: dict[str, Any]
    tool_calls: list[dict[str, Any]]
    subagent_types: list[str]
    present_files_called: bool


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a real OpenSKU live agent validation.")
    parser.add_argument("--case-id", default=DEFAULT_CASE_ID)
    parser.add_argument("--case-file", type=Path, default=None, help="Optional OpenSKU benchmark case JSON to stage and use as the live prompt source.")
    parser.add_argument("--date", default=DEFAULT_DATE)
    parser.add_argument("--timeout-seconds", type=float, default=900.0)
    parser.add_argument("--reasoning-effort", default="high", choices=["low", "medium", "high"])
    parser.add_argument("--no-subagents", action="store_true")
    parser.add_argument("--plan-mode", action="store_true", help="Expose write_todos during the live run. Default is off to keep validation bounded.")
    parser.add_argument("--knowledge-dir", type=Path, default=None, help="Optional OpenSKU knowledge directory containing patterns.json for reuse injection.")
    parser.add_argument("--knowledge-limit", type=int, default=5, help="Maximum reusable knowledge patterns to inject.")
    return parser


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_case_file(case_file: Path | None) -> dict[str, Any] | None:
    if case_file is None:
        return None
    data = json.loads(case_file.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"case file must contain a JSON object: {case_file}")
    return data


def public_case_for_upload(case: dict[str, Any]) -> dict[str, Any]:
    hidden_fields = {"expected_decision", "expected_decision_rationale", "scoring_notes"}
    return {key: value for key, value in case.items() if key not in hidden_fields}


def case_brief_for_upload(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "product": {
            "idea": case.get("brief") or case.get("category") or "OpenSKU benchmark case",
            "category": case.get("category") or "unknown",
            "target_price_range": "unavailable in benchmark case",
            "constraints": [
                "Use public benchmark fixtures only.",
                "Do not invent private commerce metrics.",
                "Respect forbidden_claims and required_claims from the case file.",
            ],
        },
        "target_platforms": ["benchmark fixture"],
        "target_customers": ["users implied by the benchmark case"],
        "private_data_status": "Benchmark fixtures are not private merchant telemetry.",
        "language": "Chinese output preferred, filenames and JSON keys in English.",
    }


def _write_upload_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sample_files_for_case(case: dict[str, Any]) -> list[Path]:
    sample_files: list[Path] = []
    for context_field in ["public_context", "uploaded_real"]:
        contexts = case.get(context_field, [])
        if not isinstance(contexts, list):
            continue
        for context in contexts:
            if not isinstance(context, dict):
                continue
            sample_file = context.get("sample_file")
            if isinstance(sample_file, str) and sample_file:
                sample_files.append(REPO_ROOT / sample_file)
    deduped: list[Path] = []
    seen: set[Path] = set()
    for path in sample_files:
        if path in seen:
            continue
        seen.add(path)
        deduped.append(path)
    return deduped


def copy_upload_fixtures(uploads_dir: Path, *, case: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    uploads_dir.mkdir(parents=True, exist_ok=True)
    if case is None:
        sources = [
            REPO_ROOT / "docs/ecom-launch/demo-brief.portable-coffee-tumbler.json",
            REPO_ROOT / "data/opensku/samples/amazon_reviews.jsonl",
            REPO_ROOT / "data/opensku/samples/wands.jsonl",
            REPO_ROOT / "data/opensku/schemas/amazon_reviews.schema.json",
            REPO_ROOT / "data/opensku/schemas/wands.schema.json",
        ]
    else:
        _write_upload_json(uploads_dir / "opensku-case.json", public_case_for_upload(case))
        _write_upload_json(uploads_dir / "opensku-case-brief.json", case_brief_for_upload(case))
        sources = [uploads_dir / "opensku-case.json", uploads_dir / "opensku-case-brief.json", *_sample_files_for_case(case)]
    copied: list[dict[str, Any]] = []
    for source in sources:
        target = uploads_dir / source.name
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        copied.append(
            {
                "name": target.name,
                "virtual_path": f"/mnt/user-data/uploads/{target.name}",
                "host_path": str(target),
                "size_bytes": target.stat().st_size,
                "sha256": sha256_file(target),
            }
        )
    return copied


def build_live_prompt(
    case_id: str,
    *,
    case: dict[str, Any] | None = None,
    injected_knowledge_patterns: Sequence[KnowledgePattern] | None = None,
    knowledge_dir: Path | None = None,
) -> str:
    artifact_list = "\n".join(f"- /mnt/user-data/outputs/{name}" for name in REQUIRED_ARTIFACTS)
    knowledge_context = format_knowledge_context(
        list(injected_knowledge_patterns or []),
        knowledge_dir=knowledge_dir,
    )
    knowledge_section = f"\n\n{knowledge_context}" if knowledge_context else ""
    if case is not None:
        public_paths = "\n".join(
            f"- /mnt/user-data/uploads/{Path(path).name}" for path in sorted({context.get("sample_file", "") for context in case.get("public_context", []) if isinstance(context, dict) and context.get("sample_file")})
        ) or "- None"
        uploaded_paths = "\n".join(
            f"- /mnt/user-data/uploads/{Path(path).name}" for path in sorted({context.get("sample_file", "") for context in case.get("uploaded_real", []) if isinstance(context, dict) and context.get("sample_file")})
        ) or "- None"
        forbidden_claims = "\n".join(f"- {claim}" for claim in case.get("forbidden_claims", []) if isinstance(claim, str)) or "- Do not invent private metrics or unsupported claims."
        required_claims = "\n".join(f"- {claim}" for claim in case.get("required_claims", []) if isinstance(claim, str)) or "- State evidence limitations."
        return f"""Run a real OpenSKU/EcomLaunch Ultra live validation now. Do not answer with a plan only.

Case id: {case_id}
Benchmark case file: /mnt/user-data/uploads/opensku-case.json
Case launch stage: {case.get("stage", "unknown")}
Case category: {case.get("category", "unknown")}
Case brief:
{case.get("brief", "")}

Public benchmark fixture files:
{public_paths}

Uploaded-data simulation fixture files:
{uploaded_paths}

Important data boundary:
- These uploaded files are public benchmark fixtures or public-fixture-as-uploaded simulation, not private merchant backend telemetry.
- No GMV, CTR, CVR, ROI, CAC, ad spend, sales volume, refund rate, repeat purchase rate, margin, live inventory, live ranking, or verified uplift is available unless the case file explicitly includes the exact field.
- If a metric is unavailable, mark it as unavailable and propose a test to collect it. Do not invent it.
- Diagnose the decision from the case evidence. The expected benchmark decision is intentionally not provided in this prompt.

Decision taxonomy:
- Go: evidence is good enough to run the next bounded launch test.
- Pivot: change target query, audience, channel, positioning, claim, offer, or product-page route while the SKU may still be worth testing.
- Hold: evidence is insufficient; collect missing product, supplier, customer, or market proof before spending more.
- Kill: abandon the SKU or offer because evidence shows a non-salvageable product, supply, compliance, safety, economics, or trust failure.
- Scale: evidence supports increasing volume, budget, channel count, or SKU variants.
- For pre_launch_test search-fit cases, `pre_launch_test search-fit mismatch defaults to Pivot` when the product/query/category pairing is wrong but the SKU could still be tested under another query, category, positioning, or audience wedge.
- `Kill only when the SKU or offer itself is not worth continuing`, such as non-salvageable product quality, impossible supply, compliance/safety failure, or no viable retargeting path. Do not choose Kill merely because the current query is wrong.
- Do not choose Hold solely because private metrics, ad attribution, margin, refund, or repeat-purchase data are unavailable.
- Choose Pivot when available evidence supports a specific change to query, claim, format, offer, channel, or promotion plan.
- Choose Go for a bounded pre_launch_test when public relevance or category-fit evidence supports the next test and no blocking risk is present.
- For supplier_sample, unsupported claims usually mean Pivot the claim set or listing plan, not Hold, when uploaded sample or metadata is enough to continue under safer claims.
- For soft_launch uploaded-data cases, missing attribution is not by itself Hold when order, review, payment, or product rows support a plan change.
{knowledge_section}

Required claims:
{required_claims}

Forbidden claims:
{forbidden_claims}

Execution requirements:
- Use Ultra mode behavior.
- Read /mnt/user-data/uploads/opensku-case.json and the staged fixture files.
- Benchmark-fixture mode is active for this run: do not call web_search, web_fetch, image_search, or broad external research tools. Use the uploaded public fixtures only. External research is out of scope for this validation run and will be tested separately.
- Use all five ecommerce specialist roles through the task tool when available:
  market-voc-researcher, offer-architect, growth-analyst, asset-studio, evidence-checker.
- Keep each specialist task bounded and ask for structured findings.
- Synthesize the final artifacts as launch-director.
- After specialist findings, call write_opensku_artifact_bundle if that tool is available. Pass concise synthesis fields only. Do not use write_file to hand-write the required artifact bundle unless write_opensku_artifact_bundle is unavailable or returns ERROR.
- If write_opensku_artifact_bundle returns status=PASS, call present_files immediately for the generated artifact list. Do not rewrite launch-war-room.html by hand.
- Do not claim row counts or internal artifact counts in the final response unless they were returned by a tool or you read the artifact. Listing filenames is enough.
- Final artifact list must be filenames only. Do not add per-file descriptions, evidence counts, row counts, or entry counts.

Create and present exactly these required artifacts:
{artifact_list}

Artifact contract:
- evidence-ledger.json must be a JSON array. Each item must include id, evidence_type, source_type, confidence, and metric. Use ids like EVID-BRIEF-001. evidence_type must be one of observed_public, uploaded_real, estimated, unavailable, assumption. Public benchmark rows should be observed_public or assumption, not uploaded_real.
- competitor-table.csv columns must include: competitor, observed_claim, evidence_id, confidence, limitation. Each evidence_id must be one exact EVID-... id already present in evidence-ledger.json. Do not put a descriptive label, price band, claim text, or competitor name in evidence_id.
- launch-calendar.csv columns must include: day, objective, experiment, asset, channel, validation_signal_to_collect, decision_rule, owner, expected_output. Validation signals must avoid unsupported private metrics. Use observable proxy signals such as saved comments, qualitative objections, sample preorders with manually uploaded evidence later, creator feedback, survey responses, or uploaded case-supported fields.
- positioning-brief.md must include exact case-sensitive literal labels: Decision: and Evidence limitations:
- listing-pack.md and content-pack.md must include the exact case-sensitive literal label Claim readiness: at least once. Do not rely only on Claim Readiness or claim_status.
- launch-state.json must be a JSON object with stage, decision, and evidence_ids.
- promotion-replan.md must include sections named exactly: observed signal, interpretation, plan change, next test, stop/continue rule.
- knowledge-deltas.json must be a JSON array. Each item must include type, maturity, and source_case_id or source_run_id. type must be one of decision, guideline, pitfall, process, model. maturity must be draft, verified, or proven.
- launch-war-room.html must be a complete HTML document.

Before present_files:
- Self-audit the files for parseable JSON/CSV, required headings, evidence id consistency, private metric leakage, and unsupported claims.
- Prefer write_opensku_artifact_bundle for complete bundle creation; it already writes the required JSON, CSV, Markdown, and HTML files and runs the validator.
- Run validate_opensku_artifacts on /mnt/user-data/outputs if the tool is available. If it returns FAIL, fix the listed artifacts and run validate_opensku_artifacts again before present_files. If that tool is not available, state that external validation is required and still perform the self-audit.
- After validate_opensku_artifacts returns PASS, call present_files immediately. Do not perform extra polishing, unrelated reads, or another synthesis loop.
- If a todo tool is available, complete all todos before calling present_files.
- After present_files succeeds, do not call any other tool. Send the final Chinese response immediately and stop.

Final response language: Chinese.
Final response must briefly state launch stage, decision (Go/Pivot/Hold/Kill/Scale), next-loop test, promotion adjustment, data limitations, and the artifact list. Do not paste full artifact contents into chat.
"""
    return f"""Run a real OpenSKU/EcomLaunch Ultra live validation now. Do not answer with a plan only.

Case id: {case_id}
Launch stage to diagnose: idea_only unless the evidence clearly proves another stage.
Product brief: /mnt/user-data/uploads/demo-brief.portable-coffee-tumbler.json
Public benchmark fixtures:
- /mnt/user-data/uploads/amazon_reviews.jsonl
- /mnt/user-data/uploads/wands.jsonl

Important data boundary:
- These uploaded files are public benchmark fixtures, not private merchant backend telemetry.
- No GMV, CTR, CVR, ROI, CAC, ad spend, sales volume, refund rate, repeat purchase rate, margin, live inventory, live ranking, or verified uplift is available.
- If a metric is unavailable, mark it as unavailable and propose a test to collect it. Do not invent it.
{knowledge_section}

Execution requirements:
- Use Ultra mode behavior.
- Read the uploaded brief and benchmark fixture files.
- Benchmark-fixture mode is active for this run: do not call web_search, web_fetch, image_search, or broad external research tools. Use the uploaded public fixtures only. External research is out of scope for this validation run and will be tested separately.
- Use all five ecommerce specialist roles through the task tool when available:
  market-voc-researcher, offer-architect, growth-analyst, asset-studio, evidence-checker.
- Keep each specialist task bounded and ask for structured findings.
- Synthesize the final artifacts as launch-director.
- After specialist findings, call write_opensku_artifact_bundle if that tool is available. Pass concise synthesis fields only. Do not use write_file to hand-write the required artifact bundle unless write_opensku_artifact_bundle is unavailable or returns ERROR.
- If write_opensku_artifact_bundle returns status=PASS, call present_files immediately for the generated artifact list. Do not rewrite launch-war-room.html by hand.
- Do not claim row counts or internal artifact counts in the final response unless they were returned by a tool or you read the artifact. Listing filenames is enough.
- Final artifact list must be filenames only. Do not add per-file descriptions, evidence counts, row counts, or entry counts.

Create and present exactly these required artifacts:
{artifact_list}

Artifact contract:
- evidence-ledger.json must be a JSON array. Each item must include id, evidence_type, source_type, confidence, and metric. Use ids like EVID-BRIEF-001. evidence_type must be one of observed_public, uploaded_real, estimated, unavailable, assumption. Public benchmark rows should be observed_public or assumption, not uploaded_real.
- competitor-table.csv columns must include: competitor, observed_claim, evidence_id, confidence, limitation. Each evidence_id must be one exact EVID-... id already present in evidence-ledger.json. Do not put a descriptive label, price band, claim text, or competitor name in evidence_id.
- launch-calendar.csv columns must include: day, objective, experiment, asset, channel, validation_signal_to_collect, decision_rule, owner, expected_output. Since no uploaded_real private metrics exist, validation_signal_to_collect must avoid private metrics such as CTR/CVR/ROI/GMV/ad spend/refund rate. Use observable proxy signals such as saved comments, qualitative objections, sample preorders with manually uploaded evidence later, creator feedback, or survey responses.
- positioning-brief.md must include exact case-sensitive literal labels: Decision: and Evidence limitations:
- listing-pack.md and content-pack.md must include the exact case-sensitive literal label Claim readiness: at least once. Do not rely only on Claim Readiness or claim_status.
- launch-state.json must be a JSON object with stage, decision, and evidence_ids.
- promotion-replan.md must include sections named exactly: observed signal, interpretation, plan change, next test, stop/continue rule.
- knowledge-deltas.json must be a JSON array. Each item must include type, maturity, and source_case_id or source_run_id. type must be one of decision, guideline, pitfall, process, model. maturity must be draft, verified, or proven.
- launch-war-room.html must be a complete HTML document.

Before present_files:
- Self-audit the files for parseable JSON/CSV, required headings, evidence id consistency, private metric leakage, and unsupported claims.
- Prefer write_opensku_artifact_bundle for complete bundle creation; it already writes the required JSON, CSV, Markdown, and HTML files and runs the validator.
- Run validate_opensku_artifacts on /mnt/user-data/outputs if the tool is available. If it returns FAIL, fix the listed artifacts and run validate_opensku_artifacts again before present_files. If that tool is not available, state that external validation is required and still perform the self-audit.
- After validate_opensku_artifacts returns PASS, call present_files immediately. Do not perform extra polishing, unrelated reads, or another synthesis loop.
- If a todo tool is available, complete all todos before calling present_files.
- After present_files succeeds, do not call any other tool. Send the final Chinese response immediately and stop.

Final response language: Chinese.
Final response must briefly state launch stage, decision (Go/Pivot/Hold/Kill/Scale), next-loop test, promotion adjustment, data limitations, and the artifact list. Do not paste full artifact contents into chat.
"""


def parse_sse(transcript: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for frame in transcript.split("\n\n"):
        if not frame.strip():
            continue
        event_name = "message"
        event_id = None
        data_lines: list[str] = []
        for line in frame.splitlines():
            if line.startswith("event: "):
                event_name = line[len("event: ") :]
            elif line.startswith("id: "):
                event_id = line[len("id: ") :]
            elif line.startswith("data: "):
                data_lines.append(line[len("data: ") :])
        raw_data = "\n".join(data_lines)
        parsed_data: Any = raw_data
        if raw_data:
            try:
                parsed_data = json.loads(raw_data)
            except json.JSONDecodeError:
                parsed_data = raw_data
        events.append({"event": event_name, "id": event_id, "data": parsed_data})
    return events


def parse_stream(transcript: str) -> ParsedStream:
    events = parse_sse(transcript)
    latest_state: dict[str, Any] = {}
    for event in events:
        data = event.get("data")
        if event.get("event") == "values" and isinstance(data, dict):
            latest_state = data
    return parse_state(latest_state, events=events)


def parse_state(latest_state: dict[str, Any], *, events: list[dict[str, Any]] | None = None) -> ParsedStream:
    messages = latest_state.get("messages", []) if isinstance(latest_state, dict) else []
    final_response = ""
    model_name = None
    model_provider = None
    token_usage: dict[str, Any] = {}
    tool_calls: list[dict[str, Any]] = []
    subagent_types: list[str] = []
    present_files_called = False

    for message in messages:
        if not isinstance(message, dict):
            continue
        for call in message.get("tool_calls", []) or []:
            if not isinstance(call, dict):
                continue
            name = call.get("name")
            args = call.get("args") if isinstance(call.get("args"), dict) else {}
            tool_calls.append({"name": name, "args": args})
            if name == "task" and isinstance(args, dict):
                subagent_type = args.get("subagent_type")
                if isinstance(subagent_type, str):
                    subagent_types.append(subagent_type)
            if name == "present_files":
                present_files_called = True

        if message.get("type") == "ai" and isinstance(message.get("content"), str) and message.get("content", "").strip():
            final_response = message["content"]
            metadata = message.get("response_metadata") or {}
            if isinstance(metadata, dict):
                model_name = metadata.get("model_name") or model_name
                model_provider = metadata.get("model_provider") or model_provider
                usage = metadata.get("token_usage")
                if isinstance(usage, dict):
                    token_usage = usage

    return ParsedStream(
        events=events or [],
        latest_state=latest_state,
        final_response=final_response,
        model_name=model_name,
        model_provider=model_provider,
        token_usage=token_usage,
        tool_calls=tool_calls,
        subagent_types=subagent_types,
        present_files_called=present_files_called,
    )


def parse_run_messages(run_messages_json: Any) -> ParsedStream:
    records = run_messages_json.get("data", []) if isinstance(run_messages_json, dict) else []
    final_response = ""
    model_name = None
    model_provider = None
    token_usage: dict[str, Any] = {}
    tool_calls: list[dict[str, Any]] = []
    subagent_types: list[str] = []
    present_files_called = False

    if not isinstance(records, list):
        records = []

    for record in records:
        if not isinstance(record, dict):
            continue
        message = record.get("content")
        if not isinstance(message, dict):
            continue

        for call in message.get("tool_calls", []) or []:
            if not isinstance(call, dict):
                continue
            name = call.get("name")
            args = call.get("args") if isinstance(call.get("args"), dict) else {}
            tool_calls.append({"name": name, "args": args})
            if name == "task":
                subagent_type = args.get("subagent_type")
                if isinstance(subagent_type, str):
                    subagent_types.append(subagent_type)
            if name == "present_files":
                present_files_called = True

        metadata = message.get("response_metadata") or {}
        if isinstance(metadata, dict):
            model_name = metadata.get("model_name") or model_name
            model_provider = metadata.get("model_provider") or model_provider
            usage = metadata.get("token_usage")
            if isinstance(usage, dict):
                token_usage = usage

        content = message.get("content")
        if message.get("type") == "ai" and isinstance(content, str) and content.strip() and not message.get("tool_calls"):
            final_response = content

    return ParsedStream(
        events=[],
        latest_state={},
        final_response=final_response,
        model_name=model_name,
        model_provider=model_provider,
        token_usage=token_usage,
        tool_calls=tool_calls,
        subagent_types=subagent_types,
        present_files_called=present_files_called,
    )


def merge_parsed_streams(state_parsed: ParsedStream, message_parsed: ParsedStream) -> ParsedStream:
    seen_tool_calls: set[str] = set()
    tool_calls: list[dict[str, Any]] = []
    for call in [*message_parsed.tool_calls, *state_parsed.tool_calls]:
        key = json.dumps(call, sort_keys=True, ensure_ascii=False, default=str)
        if key in seen_tool_calls:
            continue
        seen_tool_calls.add(key)
        tool_calls.append(call)

    subagent_types = sorted(set([*message_parsed.subagent_types, *state_parsed.subagent_types]))
    return ParsedStream(
        events=state_parsed.events,
        latest_state=state_parsed.latest_state,
        final_response=state_parsed.final_response or message_parsed.final_response,
        model_name=state_parsed.model_name or message_parsed.model_name,
        model_provider=state_parsed.model_provider or message_parsed.model_provider,
        token_usage=state_parsed.token_usage or message_parsed.token_usage,
        tool_calls=tool_calls,
        subagent_types=subagent_types,
        present_files_called=state_parsed.present_files_called or message_parsed.present_files_called,
    )


def build_artifact_manifest(
    *,
    case_id: str,
    run_id: str | None,
    thread_id: str,
    user_id: str,
    outputs_dir: Path,
    parsed: ParsedStream,
    uploaded_files: list[dict[str, Any]],
    injected_knowledge_patterns: Sequence[KnowledgePattern] | None = None,
    knowledge_dir: Path | None = None,
) -> dict[str, Any]:
    artifacts = []
    if outputs_dir.exists():
        for path in sorted(p for p in outputs_dir.iterdir() if p.is_file()):
            artifacts.append(
                {
                    "name": path.name,
                    "host_path": str(path),
                    "virtual_path": f"/mnt/user-data/outputs/{path.name}",
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    state_artifacts = parsed.latest_state.get("artifacts", []) if isinstance(parsed.latest_state, dict) else []
    return {
        "case_id": case_id,
        "run_id": run_id,
        "thread_id": thread_id,
        "user_id": user_id,
        "model_provider": parsed.model_provider,
        "model_name": parsed.model_name,
        "token_usage": parsed.token_usage,
        "present_files_called": parsed.present_files_called,
        "tool_call_names": [call["name"] for call in parsed.tool_calls],
        "subagent_types": parsed.subagent_types,
        "uploaded_files": uploaded_files,
        "knowledge_dir": str(knowledge_dir) if knowledge_dir is not None else None,
        "injected_knowledge_patterns": patterns_for_manifest(list(injected_knowledge_patterns or [])),
        "outputs_dir": str(outputs_dir),
        "artifacts": artifacts,
        "state_artifacts": state_artifacts,
    }


def run_validator(outputs_dir: Path) -> tuple[int, str]:
    from evals.opensku.validators.core import validate_artifact_bundle

    result = validate_artifact_bundle(outputs_dir)
    lines = [
        f"bundle={outputs_dir}",
        f"artifact_count={result.artifact_count}",
        f"status={'PASS' if result.ok else 'FAIL'}",
    ]
    for error in result.errors:
        lines.append(f"- {error}")
    return (0 if result.ok else 1), "\n".join(lines) + "\n"


def missing_final_response_requirements(final_response: str) -> list[str]:
    text = final_response.lower()
    checks = {
        "launch_stage": ["stage", "阶段", "上新"],
        "decision": ["decision", "决策", "判定", "hold", "go", "pivot", "kill", "scale"],
        "next_loop_test": ["next-loop", "next test", "下一循环", "下一轮", "验证冲刺", "首轮验证"],
        "promotion_adjustment": ["promotion", "推广", "投放", "replan"],
        "data_limitations": [
            "data limitation",
            "数据限制",
            "数据局限",
            "数据边界",
            "指标限制",
            "私域指标",
            "私有商户指标",
            "无价格数据",
            "销售额",
            "不可用",
            "unavailable",
        ],
    }
    missing = [name for name, options in checks.items() if not any(option in text for option in options)]
    missing.extend(f"artifact:{name}" for name in REQUIRED_ARTIFACTS if name.lower() not in text)
    return missing


def final_response_consistency_errors(final_response: str, outputs_dir: Path) -> list[str]:
    errors: list[str] = []
    artifact_count_matches = [
        int(match.group(1))
        for match in re.finditer(
            r"(?:产出物|产出|artifact|artifacts)[^\n]{0,60}?(\d+)\s*(?:件|个|files?)",
            final_response,
            re.IGNORECASE,
        )
    ]
    for claimed_count in artifact_count_matches:
        if claimed_count != len(REQUIRED_ARTIFACTS):
            errors.append(
                f"final response claims {claimed_count} artifacts, expected {len(REQUIRED_ARTIFACTS)}"
            )

    ledger_path = outputs_dir / "evidence-ledger.json"
    if ledger_path.exists():
        try:
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
            evidence_count = len(ledger) if isinstance(ledger, list) else None
        except json.JSONDecodeError:
            evidence_count = None
        if evidence_count is not None:
            escaped = re.escape("evidence-ledger.json")
            patterns = [
                rf"{escaped}[^\n]{{0,120}}?(\d+)\s*(?:条|个|items?|records?|entries?)",
                rf"(\d+)\s*(?:条|个|items?|records?|entries?)[^\n]{{0,120}}?{escaped}",
            ]
            for pattern in patterns:
                for match in re.finditer(pattern, final_response, re.IGNORECASE):
                    claimed_count = int(match.group(1))
                    if claimed_count != evidence_count:
                        errors.append(
                            f"final response claims evidence-ledger.json has {claimed_count} entries, expected {evidence_count}"
                        )
    return errors


def write_run_evidence(
    *,
    run_dir: Path,
    case_id: str,
    run_id: str | None,
    thread_id: str,
    user_id: str,
    uploads_dir: Path,
    outputs_dir: Path,
    uploaded_files: list[dict[str, Any]],
    transcript: str,
    parsed: ParsedStream,
    manifest: dict[str, Any],
    validator_exit_code: int,
    validator_output: str,
    run_status: str,
    poll_log: list[dict[str, Any]],
    reasoning_effort: str,
    subagent_enabled: bool,
    plan_mode: bool,
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "raw-run-events.json").write_text(transcript, encoding="utf-8")
    (run_dir / "final-response.md").write_text(parsed.final_response.strip() + "\n", encoding="utf-8")
    (run_dir / "artifacts-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (run_dir / "validator-output.txt").write_text(validator_output, encoding="utf-8")

    missing_artifacts = sorted(set(REQUIRED_ARTIFACTS) - {item["name"] for item in manifest["artifacts"]})
    external_search_tool_calls = [name for name in manifest["tool_call_names"] if name in EXTERNAL_SEARCH_TOOLS]
    required_subagents = {
        "market-voc-researcher",
        "offer-architect",
        "growth-analyst",
        "asset-studio",
        "evidence-checker",
    }
    missing_subagents = sorted(required_subagents - set(parsed.subagent_types))
    artifact_writer_called = ARTIFACT_WRITER_TOOL in manifest["tool_call_names"]
    missing_final_response = missing_final_response_requirements(parsed.final_response)
    final_response_errors = final_response_consistency_errors(parsed.final_response, outputs_dir)
    status = (
        "PASS"
        if validator_exit_code == 0
        and not missing_artifacts
        and not missing_subagents
        and not external_search_tool_calls
        and artifact_writer_called
        and parsed.present_files_called
        and not missing_final_response
        and not final_response_errors
        else "FAIL"
    )
    if run_status != "success":
        status = "FAIL"
    run_log = f"""# OpenSKU Live Agent Run

Date: {DEFAULT_DATE}
Case id: {case_id}
Status: {status}

## Why

Phase 4 needs one real run through the production gateway path before the agent contract can be considered hardened. This run verifies auth, CSRF, gateway context injection, lead-agent construction, ecom-launch skill loading, live model access, subagent routing, artifact writing, present_files, and external artifact validation.

## Runtime Evidence

- run_id: {run_id}
- thread_id: {thread_id}
- user_id: {user_id}
- model_provider: {parsed.model_provider}
- model_name: {parsed.model_name}
- reasoning_effort: {reasoning_effort}
- mode: ultra
- agent_name: ecom-launch
- subagent_enabled: {str(subagent_enabled).lower()}
- is_plan_mode: {str(plan_mode).lower()}
- opensku_benchmark_fixture_mode: true
- disable_external_search: true
- run_status: {run_status}
- uploads_dir: {uploads_dir}
- outputs_dir: {outputs_dir}

## Uploaded Fixtures

{json.dumps(uploaded_files, ensure_ascii=False, indent=2)}

## Tool Evidence

- present_files_called: {parsed.present_files_called}
- artifact_writer_called: {artifact_writer_called}
- subagent_types: {sorted(set(parsed.subagent_types))}
- missing_subagents: {missing_subagents}
- tool_call_names: {[call["name"] for call in parsed.tool_calls]}
- external_search_tool_calls: {external_search_tool_calls}
- knowledge_dir: {manifest.get("knowledge_dir")}
- injected_knowledge_patterns: {json.dumps(manifest.get("injected_knowledge_patterns", []), ensure_ascii=False)}
- missing_final_response_requirements: {missing_final_response}
- final_response_consistency_errors: {final_response_errors}

## Poll Log

{json.dumps(poll_log, ensure_ascii=False, indent=2)}

## Artifact Evidence

- artifact_count: {len(manifest["artifacts"])}
- missing_required_artifacts: {missing_artifacts}
- artifacts: {[item["name"] for item in manifest["artifacts"]]}

## Validator

Exit code: {validator_exit_code}

```text
{validator_output.strip()}
```

## Decision

{parsed.final_response.strip()}

## Next

If this run passes, Phase 4 can be closed with the contract tests and live evidence. If it fails, fix the agent contract or artifact instructions and rerun the same case until the real validator passes.
"""
    (run_dir / "run-log.md").write_text(run_log, encoding="utf-8")

    notes = f"""# Notes

- This is a live model run, not a mocked replay.
- The benchmark files are public fixtures staged in uploads for this thread. They are not private merchant telemetry.
- The external validator is authoritative for artifact contract acceptance.
- Missing artifacts: {missing_artifacts}
- Missing subagents: {missing_subagents}
- External search tool calls: {external_search_tool_calls}
- Knowledge dir: {manifest.get("knowledge_dir")}
- Injected knowledge patterns: {manifest.get("injected_knowledge_patterns", [])}
- Artifact writer called: {artifact_writer_called}
- Missing final response requirements: {missing_final_response}
- Final response consistency errors: {final_response_errors}
"""
    (run_dir / "notes.md").write_text(notes, encoding="utf-8")


def extract_run_id(content_location: str | None) -> str | None:
    if not content_location:
        return None
    match = re.search(r"/runs/([^/]+)$", content_location)
    return match.group(1) if match else None


def main() -> int:
    args = build_parser().parse_args()
    case_id = args.case_id
    benchmark_case = load_case_file(args.case_file)
    knowledge_dir = resolve_knowledge_dir(args.knowledge_dir) if args.knowledge_dir is not None else None
    injected_knowledge_patterns: list[KnowledgePattern] = []
    if knowledge_dir is not None:
        selector_case = benchmark_case or {"stage": "idea_only", "category": "default live demo"}
        injected_knowledge_patterns = select_knowledge_patterns(
            load_knowledge_patterns(knowledge_dir),
            case=selector_case,
            limit=args.knowledge_limit,
        )
    thread_id = f"opensku-live-{case_id}-{int(time.time())}".replace(".", "-")
    email = f"opensku-live-{uuid.uuid4().hex[:12]}@example.com"
    password = f"OpenSKU-Live-{uuid.uuid4().hex}-123"

    os.chdir(BACKEND_ROOT)

    from app.gateway.app import create_app
    from deerflow.config.paths import get_paths
    from starlette.testclient import TestClient

    with TestClient(create_app()) as client:
        register = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password},
            timeout=60,
        )
        if register.status_code != 201:
            print(register.text)
            return 10
        user_id = register.json()["id"]
        csrf = client.cookies.get("csrf_token")
        if not csrf:
            print("missing csrf token after registration")
            return 11

        paths = get_paths()
        paths.ensure_thread_dirs(thread_id, user_id=user_id)
        uploads_dir = paths.sandbox_uploads_dir(thread_id, user_id=user_id)
        outputs_dir = paths.sandbox_outputs_dir(thread_id, user_id=user_id)
        uploaded_files = copy_upload_fixtures(uploads_dir, case=benchmark_case)

        headers = {"X-CSRF-Token": csrf}
        create_thread = client.post(
            "/api/threads",
            json={"thread_id": thread_id, "assistant_id": "lead_agent", "metadata": {"case_id": case_id}},
            headers=headers,
            timeout=60,
        )
        if create_thread.status_code != 200:
            print(create_thread.text)
            return 12

        body = {
            "assistant_id": "lead_agent",
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": build_live_prompt(
                            case_id,
                            case=benchmark_case,
                            injected_knowledge_patterns=injected_knowledge_patterns,
                            knowledge_dir=knowledge_dir,
                        ),
                    }
                ]
            },
            "config": {"recursion_limit": 140, "configurable": {"thread_id": thread_id}},
            "context": {
                "agent_name": "ecom-launch",
                "mode": "ultra",
                "thinking_enabled": True,
                "is_plan_mode": args.plan_mode,
                "subagent_enabled": not args.no_subagents,
                "reasoning_effort": args.reasoning_effort,
                "opensku_benchmark_fixture_mode": True,
                "disable_external_search": True,
            },
            "stream_mode": ["values"],
            "stream_subgraphs": False,
            "on_disconnect": "cancel",
        }

        poll_log: list[dict[str, Any]] = []
        run_status = "unknown"
        create_run_response = client.post(
            f"/api/threads/{thread_id}/runs",
            json=body,
            headers=headers,
            timeout=60,
        )
        if create_run_response.status_code != 200:
            print(create_run_response.text)
            return 13
        created_run = create_run_response.json()
        run_id = created_run["run_id"]
        run_status = created_run["status"]
        poll_log.append({"elapsed_seconds": 0.0, "status": run_status, "run_id": run_id})

        start = time.monotonic()
        timed_out = False
        while run_status in {"pending", "running"}:
            elapsed = time.monotonic() - start
            if elapsed >= args.timeout_seconds:
                timed_out = True
                cancel = client.post(
                    f"/api/threads/{thread_id}/runs/{run_id}/cancel",
                    params={"wait": True, "action": "interrupt"},
                    headers=headers,
                    timeout=60,
                )
                poll_log.append(
                    {
                        "elapsed_seconds": round(elapsed, 2),
                        "status": "timeout_cancel_requested",
                        "http_status": cancel.status_code,
                        "body": cancel.text[:1000],
                    }
                )
                run_status = "timeout"
                break
            time.sleep(5)
            get_run = client.get(f"/api/threads/{thread_id}/runs/{run_id}", timeout=60)
            if get_run.status_code != 200:
                poll_log.append(
                    {
                        "elapsed_seconds": round(time.monotonic() - start, 2),
                        "status": "poll_error",
                        "http_status": get_run.status_code,
                        "body": get_run.text[:1000],
                    }
                )
                run_status = "poll_error"
                break
            run_body = get_run.json()
            run_status = run_body.get("status", "unknown")
            poll_log.append(
                {
                    "elapsed_seconds": round(time.monotonic() - start, 2),
                    "status": run_status,
                    "total_tokens": run_body.get("total_tokens"),
                    "llm_call_count": run_body.get("llm_call_count"),
                    "message_count": run_body.get("message_count"),
                }
            )

        state_response = client.get(f"/api/threads/{thread_id}/state", timeout=60)
        state_json = state_response.json() if state_response.status_code == 200 else {"error": state_response.text}
        latest_state = state_json.get("values", {}) if isinstance(state_json, dict) else {}
        parsed = parse_state(latest_state if isinstance(latest_state, dict) else {})
        run_messages_response = client.get(f"/api/runs/{run_id}/messages?limit=200", timeout=60)
        run_messages_json = (
            run_messages_response.json()
            if run_messages_response.status_code == 200
            else {"error": run_messages_response.text, "status_code": run_messages_response.status_code}
        )
        parsed = merge_parsed_streams(parsed, parse_run_messages(run_messages_json))
        transcript = json.dumps(
            {
                "run_id": run_id,
                "thread_id": thread_id,
                "run_status": run_status,
                "timed_out": timed_out,
                "poll_log": poll_log,
                "thread_state": state_json,
                "run_messages": run_messages_json,
            },
            ensure_ascii=False,
            indent=2,
        )
        validator_exit_code, validator_output = run_validator(outputs_dir)
        manifest = build_artifact_manifest(
            case_id=case_id,
            run_id=run_id,
            thread_id=thread_id,
            user_id=user_id,
            outputs_dir=outputs_dir,
            parsed=parsed,
            uploaded_files=uploaded_files,
            injected_knowledge_patterns=injected_knowledge_patterns,
            knowledge_dir=knowledge_dir,
        )
        run_dir = RUNS_ROOT / args.date / case_id
        write_run_evidence(
            run_dir=run_dir,
            case_id=case_id,
            run_id=run_id,
            thread_id=thread_id,
            user_id=user_id,
            uploads_dir=uploads_dir,
            outputs_dir=outputs_dir,
            uploaded_files=uploaded_files,
            transcript=transcript,
            parsed=parsed,
            manifest=manifest,
            validator_exit_code=validator_exit_code,
            validator_output=validator_output,
            run_status=run_status,
            poll_log=poll_log,
            reasoning_effort=args.reasoning_effort,
            subagent_enabled=not args.no_subagents,
            plan_mode=args.plan_mode,
        )

        print(f"case_id={case_id}")
        print(f"run_id={run_id}")
        print(f"thread_id={thread_id}")
        print(f"run_dir={run_dir}")
        print(f"outputs_dir={outputs_dir}")
        print(f"model={parsed.model_provider}/{parsed.model_name}")
        print(f"present_files_called={parsed.present_files_called}")
        artifact_writer_called = ARTIFACT_WRITER_TOOL in manifest["tool_call_names"]
        print(f"artifact_writer_called={artifact_writer_called}")
        missing_final_response = missing_final_response_requirements(parsed.final_response)
        final_response_errors = final_response_consistency_errors(parsed.final_response, outputs_dir)
        print(f"missing_final_response_requirements={missing_final_response}")
        print(f"final_response_consistency_errors={final_response_errors}")
        print(f"run_status={run_status}")
        print(f"subagent_types={sorted(set(parsed.subagent_types))}")
        print(f"artifact_count={len(manifest['artifacts'])}")
        print(validator_output, end="")

        required_subagents = {
            "market-voc-researcher",
            "offer-architect",
            "growth-analyst",
            "asset-studio",
            "evidence-checker",
        }
        missing_artifacts = sorted(set(REQUIRED_ARTIFACTS) - {item["name"] for item in manifest["artifacts"]})
        missing_subagents = sorted(required_subagents - set(parsed.subagent_types))
        external_search_tool_calls = [name for name in manifest["tool_call_names"] if name in EXTERNAL_SEARCH_TOOLS]
        final_exit_code = 0
        if (
            run_status != "success"
            or validator_exit_code != 0
            or missing_artifacts
            or missing_subagents
            or external_search_tool_calls
            or not artifact_writer_called
            or not parsed.present_files_called
            or missing_final_response
            or final_response_errors
        ):
            print(
                "LIVE_VALIDATION_FAILED "
                f"missing_artifacts={missing_artifacts} "
                f"missing_subagents={missing_subagents} "
                f"external_search_tool_calls={external_search_tool_calls} "
                f"artifact_writer_called={artifact_writer_called} "
                f"missing_final_response_requirements={missing_final_response} "
                f"final_response_consistency_errors={final_response_errors}"
            )
            final_exit_code = 1
        else:
            print("LIVE_VALIDATION_PASSED")

        # This live-eval CLI hosts the real app in-process via TestClient. Some
        # browser/search tool workers can remain alive briefly after run cancel,
        # causing TestClient shutdown to block on thread joins. Evidence has
        # already been flushed to disk at this point, so force-exit to keep the
        # validation harness bounded.
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(final_exit_code)

    print(f"case_id={case_id}")
    print(f"run_id={run_id}")
    print(f"thread_id={thread_id}")
    print(f"run_dir={run_dir}")
    print(f"outputs_dir={outputs_dir}")
    print(f"model={parsed.model_provider}/{parsed.model_name}")
    print(f"present_files_called={parsed.present_files_called}")
    artifact_writer_called = ARTIFACT_WRITER_TOOL in manifest["tool_call_names"]
    print(f"artifact_writer_called={artifact_writer_called}")
    missing_final_response = missing_final_response_requirements(parsed.final_response)
    final_response_errors = final_response_consistency_errors(parsed.final_response, outputs_dir)
    print(f"missing_final_response_requirements={missing_final_response}")
    print(f"final_response_consistency_errors={final_response_errors}")
    print(f"run_status={run_status}")
    print(f"subagent_types={sorted(set(parsed.subagent_types))}")
    print(f"artifact_count={len(manifest['artifacts'])}")
    print(validator_output, end="")

    required_subagents = {
        "market-voc-researcher",
        "offer-architect",
        "growth-analyst",
        "asset-studio",
        "evidence-checker",
    }
    missing_artifacts = sorted(set(REQUIRED_ARTIFACTS) - {item["name"] for item in manifest["artifacts"]})
    missing_subagents = sorted(required_subagents - set(parsed.subagent_types))
    external_search_tool_calls = [name for name in manifest["tool_call_names"] if name in EXTERNAL_SEARCH_TOOLS]
    if (
        run_status != "success"
        or validator_exit_code != 0
        or missing_artifacts
        or missing_subagents
        or external_search_tool_calls
        or not artifact_writer_called
        or not parsed.present_files_called
        or missing_final_response
        or final_response_errors
    ):
        print(
            "LIVE_VALIDATION_FAILED "
            f"missing_artifacts={missing_artifacts} "
            f"missing_subagents={missing_subagents} "
            f"external_search_tool_calls={external_search_tool_calls} "
            f"artifact_writer_called={artifact_writer_called} "
            f"missing_final_response_requirements={missing_final_response} "
            f"final_response_consistency_errors={final_response_errors}"
        )
        return 1
    print("LIVE_VALIDATION_PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
