"""Measure real-LLM OpenSKU Flash and Ultra product-path performance.

This is intentionally an HTTP-level benchmark: it exercises the same Gateway
SSE contract used by the browser while keeping each run in a fresh thread. The
output contains only timings, counts, tool names, model identifiers, and
artifact filenames; user prompts and model responses are never written to the
report. Deterministic Replay reports are explicitly ineligible as baselines.

Example::

    uv run python scripts/run_opensku_benchmark.py --base-url http://127.0.0.1:8001
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx

PACK_FILES = {
    "launch-war-room.html",
    "evidence-ledger.json",
    "competitor-table.csv",
    "positioning-brief.md",
    "listing-pack.md",
    "content-pack.md",
    "launch-calendar.csv",
}

PROMPT = "我想做一个 99-199 元的通勤咖啡杯，但没有任何店铺后台数据。请用公开信号帮我判断是否值得做 7 天轻量验证，并输出 Launch Validation Pack。"
PROMPT_ID = "launch-validation-pack-commuter-mug-zh-v1"
ULTRA_SPECIALISTS = ["market-voc-researcher", "offer-architect", "asset-studio"]
TIMING_METRICS = (
    "preparing_duration_seconds",
    "first_tool_call_seconds",
    "first_user_visible_text_seconds",
    "elapsed_seconds",
)


def _json_response(response: httpx.Response, label: str) -> Any:
    if response.status_code >= 400:
        raise RuntimeError(f"{label} failed: {response.status_code} {response.text[:500]}")
    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError(f"{label} returned non-JSON response") from exc


def _register(client: httpx.Client) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"opensku-benchmark-{uuid.uuid4().hex[:12]}@example.com",
            "password": "benchmark-local-password-123",
        },
    )
    _json_response(response, "register")
    csrf = client.cookies.get("csrf_token")
    if not csrf:
        raise RuntimeError("register did not set csrf_token")
    return csrf


def _create_thread(client: httpx.Client, csrf: str, index: int) -> str:
    thread_id = f"opensku-benchmark-{index}-{uuid.uuid4().hex[:12]}"
    response = client.post(
        "/api/threads",
        json={"thread_id": thread_id, "metadata": {"agent_name": "ecom-launch"}},
        headers={"X-CSRF-Token": csrf},
    )
    _json_response(response, "create thread")
    return thread_id


def _tool_calls(state: dict[str, Any]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for message in state.get("messages", []):
        if not isinstance(message, dict):
            continue
        for call in message.get("tool_calls") or []:
            if isinstance(call, dict):
                calls.append(call)
    return calls


def _tool_names(state: dict[str, Any]) -> list[str]:
    return [str(call["name"]) for call in _tool_calls(state) if call.get("name")]


def _tool_results(state: dict[str, Any], tool_name: str) -> list[str]:
    call_ids = {str(call.get("id")) for call in _tool_calls(state) if call.get("name") == tool_name and call.get("id")}
    return [str(message.get("content", "")) for message in state.get("messages", []) if isinstance(message, dict) and message.get("type") == "tool" and str(message.get("tool_call_id")) in call_ids]


def _artifact_names(state: dict[str, Any]) -> set[str]:
    return {Path(str(path)).name for path in state.get("artifacts") or []}


def _subagent_sequence(state: dict[str, Any]) -> list[str]:
    sequence: list[str] = []
    for call in _tool_calls(state):
        if call.get("name") != "task":
            continue
        args = call.get("args")
        if isinstance(args, dict) and isinstance(args.get("subagent_type"), str):
            sequence.append(args["subagent_type"])
    return sequence


def _message_text(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())
    return "\n".join(parts)


def _iter_ai_messages(value: Any) -> Iterator[dict[str, Any]]:
    """Yield serialized AI messages from values or updates SSE payloads."""

    if isinstance(value, dict):
        message_type = value.get("type") or value.get("role")
        if message_type in {"ai", "assistant"}:
            yield value
            return
        for item in value.values():
            yield from _iter_ai_messages(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_ai_messages(item)


def _reasoning_text(message: dict[str, Any]) -> str:
    additional = message.get("additional_kwargs")
    if not isinstance(additional, dict):
        return ""
    reasoning = additional.get("reasoning_content")
    return reasoning.strip() if isinstance(reasoning, str) else ""


def _record_stream_event(
    timings: dict[str, float | None],
    event_counts: dict[str, int],
    *,
    event: str,
    data: Any,
    elapsed: float,
) -> None:
    event_counts[event] = event_counts.get(event, 0) + 1
    if timings["first_sse_event_seconds"] is None:
        timings["first_sse_event_seconds"] = elapsed
    if event in {"values", "updates"} and timings["first_state_event_seconds"] is None:
        timings["first_state_event_seconds"] = elapsed

    for message in _iter_ai_messages(data):
        if timings["first_ai_message_seconds"] is None:
            timings["first_ai_message_seconds"] = elapsed
        reasoning = _reasoning_text(message)
        if reasoning and timings["first_reasoning_seconds"] is None:
            timings["first_reasoning_seconds"] = elapsed
        if message.get("tool_calls") and timings["first_tool_call_seconds"] is None:
            timings["first_tool_call_seconds"] = elapsed
        additional = message.get("additional_kwargs")
        hidden = isinstance(additional, dict) and additional.get("hide_from_ui") is True
        if not hidden and _message_text(message) and timings["first_user_visible_text_seconds"] is None:
            timings["first_user_visible_text_seconds"] = elapsed


def _iter_sse(response: httpx.Response) -> Iterator[tuple[str, Any]]:
    event = "message"
    data_lines: list[str] = []
    for line in response.iter_lines():
        if not line:
            if not data_lines:
                event = "message"
                continue
            raw = "\n".join(data_lines)
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                data = raw
            yield event, data
            event = "message"
            data_lines = []
        elif line.startswith(":"):
            continue
        elif line.startswith("event:"):
            event = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            data_lines.append(line.removeprefix("data:").lstrip())
    if data_lines:
        raw = "\n".join(data_lines)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = raw
        yield event, data


def _round_optional(value: float | None) -> float | None:
    return round(value, 3) if value is not None else None


def _run_once(
    client: httpx.Client,
    *,
    csrf: str,
    mode: str,
    index: int,
    timeout_seconds: float,
    model_name: str | None,
) -> dict[str, Any]:
    thread_id = _create_thread(client, csrf, index)
    context = {
        "mode": mode,
        "thinking_enabled": mode == "ultra",
        "is_plan_mode": mode == "ultra",
        "subagent_enabled": mode == "ultra",
    }
    if model_name:
        context["model_name"] = model_name
    body = {
        "assistant_id": "ecom-launch",
        "input": {"messages": [{"role": "user", "content": PROMPT}]},
        "config": {"recursion_limit": 100},
        "context": context,
        # Match the browser's product path. Values hydrate the full state;
        # updates expose the first model/tool state transition without waiting
        # for the final checkpoint.
        "stream_mode": ["values", "updates"],
    }
    started = time.perf_counter()
    timings: dict[str, float | None] = {
        "first_sse_event_seconds": None,
        "first_state_event_seconds": None,
        "first_ai_message_seconds": None,
        "first_reasoning_seconds": None,
        "first_tool_call_seconds": None,
        "first_user_visible_text_seconds": None,
    }
    event_counts: dict[str, int] = {}
    saw_end = False
    with client.stream(
        "POST",
        f"/api/threads/{thread_id}/runs/stream",
        json=body,
        headers={"X-CSRF-Token": csrf},
        timeout=timeout_seconds,
    ) as response:
        if response.status_code >= 400:
            response.read()
            raise RuntimeError(f"{mode} run {index} failed: {response.status_code} {response.text[:500]}")
        for event, data in _iter_sse(response):
            elapsed = time.perf_counter() - started
            _record_stream_event(
                timings,
                event_counts,
                event=event,
                data=data,
                elapsed=elapsed,
            )
            if event == "end":
                saw_end = True
                break
    elapsed = time.perf_counter() - started
    if not saw_end:
        raise RuntimeError(f"{mode} run {index} stream ended without an end event")

    state_response = client.get(f"/api/threads/{thread_id}/state")
    state_payload = _json_response(state_response, f"{mode} state {index}")
    state = state_payload.get("values") if isinstance(state_payload, dict) else None
    if not isinstance(state, dict):
        raise RuntimeError(f"{mode} state {index} did not contain values")
    runs = _json_response(client.get(f"/api/threads/{thread_id}/runs"), "list runs")
    run = runs[0] if runs else {}
    artifact_names = _artifact_names(state)
    tools = _tool_names(state)
    specialists = _subagent_sequence(state)
    task_results = _tool_results(state, "task")
    status_signals = [
        value
        for value in (
            timings["first_reasoning_seconds"],
            timings["first_tool_call_seconds"],
            timings["first_user_visible_text_seconds"],
        )
        if value is not None
    ]
    first_status_signal = min(status_signals) if status_signals else None
    checks = {
        "run_succeeded": run.get("status") == "success",
        "real_llm_called": int(run.get("llm_call_count") or 0) > 0,
        "specialists_in_dependency_order": mode != "ultra" or specialists == ULTRA_SPECIALISTS,
        "specialists_succeeded": mode != "ultra" or (len(task_results) == len(ULTRA_SPECIALISTS) and all(result.startswith("Task Succeeded.") for result in task_results)),
        "seven_artifacts_delivered": artifact_names == PACK_FILES,
        "user_visible_completion": timings["first_user_visible_text_seconds"] is not None,
        "preflight_passed": any("Successfully presented files" in str(message.get("content", "")) for message in state.get("messages", []) if isinstance(message, dict) and message.get("type") == "tool"),
    }
    return {
        "index": index,
        "mode": mode,
        "elapsed_seconds": round(elapsed, 3),
        "first_sse_event_seconds": _round_optional(timings["first_sse_event_seconds"]),
        "first_state_event_seconds": _round_optional(timings["first_state_event_seconds"]),
        "first_ai_message_seconds": _round_optional(timings["first_ai_message_seconds"]),
        "first_reasoning_seconds": _round_optional(timings["first_reasoning_seconds"]),
        "first_tool_call_seconds": _round_optional(timings["first_tool_call_seconds"]),
        "first_user_visible_text_seconds": _round_optional(timings["first_user_visible_text_seconds"]),
        # This is the time the current frontend can truthfully remain in its
        # fallback "preparing" state before reasoning, a tool call, or visible
        # assistant text appears.
        "preparing_duration_seconds": _round_optional(first_status_signal),
        "event_counts": event_counts,
        "status": run.get("status"),
        "error": run.get("error"),
        "model_name": run.get("model_name") or model_name,
        "llm_call_count": int(run.get("llm_call_count") or 0),
        "total_tokens": int(run.get("total_tokens") or 0),
        "total_input_tokens": int(run.get("total_input_tokens") or 0),
        "total_output_tokens": int(run.get("total_output_tokens") or 0),
        "tool_names": tools,
        "subagent_sequence": specialists,
        "task_result_statuses": [result.split(". Result:", 1)[0] for result in task_results],
        "artifact_names": sorted(artifact_names),
        "pack_complete": checks["seven_artifacts_delivered"],
        "preflight_passed": checks["preflight_passed"],
        "checks": checks,
        "quality_gate_passed": all(checks.values()),
    }


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def percentile(values: list[float], percentile_value: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        rank = (len(ordered) - 1) * percentile_value
        lower = int(rank)
        upper = min(lower + 1, len(ordered) - 1)
        fraction = rank - lower
        return round(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction, 3)

    def timing_summary(key: str) -> dict[str, float | None]:
        values = [float(row[key]) for row in rows if row.get(key) is not None]
        return {
            "min": round(min(values), 3) if values else None,
            "max": round(max(values), 3) if values else None,
            "mean": round(statistics.mean(values), 3) if values else None,
            "p50": percentile(values, 0.5) if values else None,
            "p95": percentile(values, 0.95) if values else None,
        }

    return {
        "runs": len(rows),
        "timings": {key: timing_summary(key) for key in TIMING_METRICS},
        # Kept for compatibility with older local reports.
        "elapsed_seconds": timing_summary("elapsed_seconds"),
        "llm_call_count": {
            "min": min(int(row["llm_call_count"]) for row in rows) if rows else 0,
            "max": max(int(row["llm_call_count"]) for row in rows) if rows else 0,
        },
        "total_tokens": {
            "min": min(int(row["total_tokens"]) for row in rows) if rows else 0,
            "max": max(int(row["total_tokens"]) for row in rows) if rows else 0,
        },
        "pack_success_rate": round(sum(bool(row["pack_complete"]) for row in rows) / len(rows), 3) if rows else 0.0,
        "preflight_success_rate": round(sum(bool(row["preflight_passed"]) for row in rows) / len(rows), 3) if rows else 0.0,
        "run_success_rate": round(sum(row.get("status") == "success" for row in rows) / len(rows), 3) if rows else 0.0,
        "quality_gate_pass_rate": round(sum(bool(row.get("quality_gate_passed")) for row in rows) / len(rows), 3) if rows else 0.0,
        "models": sorted({str(row["model_name"]) for row in rows if row.get("model_name")}),
    }


def _read_report(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _live_evidence_issues(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    *,
    minimum_repeats: int,
) -> list[str]:
    issues: list[str] = []
    for label, report in (("baseline", baseline), ("candidate", candidate)):
        if report.get("replay") is not False:
            issues.append(f"{label} is not explicitly marked replay=false")
        if report.get("measurement_type") != "live_llm_product_path":
            issues.append(f"{label} is not a live_llm_product_path report")
        if int(report.get("repeats") or 0) < minimum_repeats:
            issues.append(f"{label} has fewer than {minimum_repeats} repeats")
    if baseline.get("prompt_id") != candidate.get("prompt_id"):
        issues.append("prompt_id differs")
    if baseline.get("requested_model_name") != candidate.get("requested_model_name"):
        issues.append("requested_model_name differs")
    if set(baseline.get("summary", {})) != set(candidate.get("summary", {})):
        issues.append("scenario modes differ")
    for mode in sorted(set(baseline.get("summary", {})) & set(candidate.get("summary", {}))):
        baseline_models = baseline["summary"][mode].get("models") or []
        candidate_models = candidate["summary"][mode].get("models") or []
        if not baseline_models or not candidate_models:
            issues.append(f"{mode} does not record the resolved live model")
        elif baseline_models != candidate_models:
            issues.append(f"{mode} resolved models differ")
    return issues


def compare_live_reports(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    *,
    minimum_repeats: int = 3,
    latency_threshold_pct: float = 5.0,
    latency_threshold_seconds: float = 1.0,
) -> dict[str, Any]:
    """Compare only repeated real-LLM reports with quality-first gates."""

    issues = _live_evidence_issues(baseline, candidate, minimum_repeats=minimum_repeats)
    changes: dict[str, dict[str, Any]] = {}
    quality_regressions: dict[str, dict[str, float]] = {}
    baseline_summary = baseline.get("summary", {})
    candidate_summary = candidate.get("summary", {})
    for mode in sorted(set(baseline_summary) & set(candidate_summary)):
        baseline_mode = baseline_summary[mode]
        candidate_mode = candidate_summary[mode]
        baseline_quality = float(baseline_mode.get("quality_gate_pass_rate") or 0)
        candidate_quality = float(candidate_mode.get("quality_gate_pass_rate") or 0)
        if candidate_quality < baseline_quality:
            quality_regressions[mode] = {
                "baseline": baseline_quality,
                "candidate": candidate_quality,
            }
        for metric in TIMING_METRICS:
            baseline_p50 = baseline_mode.get("timings", {}).get(metric, {}).get("p50")
            candidate_p50 = candidate_mode.get("timings", {}).get(metric, {}).get("p50")
            if baseline_p50 is None or candidate_p50 is None or float(baseline_p50) <= 0:
                continue
            delta_seconds = float(candidate_p50) - float(baseline_p50)
            delta_pct = delta_seconds / float(baseline_p50) * 100
            changes[f"{mode}.{metric}"] = {
                "baseline_p50_seconds": round(float(baseline_p50), 3),
                "candidate_p50_seconds": round(float(candidate_p50), 3),
                "delta_seconds": round(delta_seconds, 3),
                "delta_pct": round(delta_pct, 2),
                "material_faster": delta_pct <= -latency_threshold_pct and delta_seconds <= -latency_threshold_seconds,
                "material_slower": delta_pct >= latency_threshold_pct and delta_seconds >= latency_threshold_seconds,
            }

    all_quality_passed = all(float(mode_summary.get("quality_gate_pass_rate") or 0) == 1.0 for report in (baseline, candidate) for mode_summary in report.get("summary", {}).values())
    materially_faster = sorted(key for key, value in changes.items() if value["material_faster"])
    materially_slower = sorted(key for key, value in changes.items() if value["material_slower"])
    if issues:
        verdict = "insufficient_live_evidence"
    elif quality_regressions:
        verdict = "reject_quality_regression"
    elif not all_quality_passed:
        verdict = "insufficient_live_evidence"
        issues.append("every baseline and candidate run must pass the full quality gate")
    elif materially_slower:
        verdict = "reject_latency_regression"
    elif materially_faster:
        verdict = "candidate_faster"
    else:
        verdict = "no_material_improvement"

    return {
        "verdict": verdict,
        "performance_claim_eligible": all_quality_passed and not issues and not quality_regressions and not materially_slower,
        "evidence_issues": sorted(set(issues)),
        "quality_regressions": quality_regressions,
        "timing_changes": changes,
        "materially_faster_metrics": materially_faster,
        "materially_slower_metrics": materially_slower,
        "minimum_repeats": minimum_repeats,
        "latency_threshold_pct": latency_threshold_pct,
        "latency_threshold_seconds": latency_threshold_seconds,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.environ.get("OPENSKU_BENCHMARK_BASE_URL", "http://127.0.0.1:8001"))
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--modes", default="flash,ultra", help="Comma-separated subset of flash,ultra")
    parser.add_argument("--timeout", type=float, default=420.0)
    parser.add_argument("--output", default="benchmark-results/opensku-benchmark.json")
    parser.add_argument("--model-name", default=os.environ.get("OPENSKU_BENCHMARK_MODEL_NAME"))
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--minimum-claim-repeats", type=int, default=3)
    parser.add_argument("--latency-threshold-pct", type=float, default=5.0)
    parser.add_argument("--latency-threshold-seconds", type=float, default=1.0)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")
    if args.minimum_claim_repeats < 1:
        parser.error("--minimum-claim-repeats must be at least 1")
    if args.latency_threshold_pct < 0 or args.latency_threshold_seconds < 0:
        parser.error("latency thresholds must be non-negative")
    modes = [value.strip() for value in args.modes.split(",") if value.strip()]
    if not modes or len(set(modes)) != len(modes) or any(mode not in {"flash", "ultra"} for mode in modes):
        parser.error("--modes must be a comma-separated subset of flash,ultra without duplicates")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows: dict[str, list[dict[str, Any]]] = {mode: [] for mode in modes}
    started = time.perf_counter()
    limits = httpx.Limits(max_connections=1, max_keepalive_connections=1)
    with httpx.Client(base_url=args.base_url.rstrip("/"), limits=limits, timeout=args.timeout) as client:
        csrf = _register(client)
        for mode in modes:
            for index in range(1, args.repeats + 1):
                print(f"[{mode} {index}/{args.repeats}] starting", flush=True)
                result = _run_once(
                    client,
                    csrf=csrf,
                    mode=mode,
                    index=index,
                    timeout_seconds=args.timeout,
                    model_name=args.model_name,
                )
                rows[mode].append(result)
                print(
                    f"[{mode} {index}/{args.repeats}] {result['elapsed_seconds']:.3f}s "
                    f"calls={result['llm_call_count']} tokens={result['total_tokens']} "
                    f"pack={'ok' if result['pack_complete'] else 'FAIL'} "
                    f"preparing={result['preparing_duration_seconds']}s "
                    f"preflight={'ok' if result['preflight_passed'] else 'FAIL'} "
                    f"quality={'ok' if result['quality_gate_passed'] else 'FAIL'}",
                    flush=True,
                )

    report = {
        "report_version": 2,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "base_url_host": args.base_url.split("//", 1)[-1].split("/", 1)[0],
        "measurement_type": "live_llm_product_path",
        "replay": False,
        "prompt_id": PROMPT_ID,
        "requested_model_name": args.model_name,
        "repeats": args.repeats,
        "total_elapsed_seconds": round(time.perf_counter() - started, 3),
        "summary": {mode: _summary(mode_rows) for mode, mode_rows in rows.items()},
        "runs": rows,
    }
    report["quality_gate_passed"] = all(bool(row.get("quality_gate_passed")) for mode_rows in rows.values() for row in mode_rows)
    report["optimization_claim_supported"] = False
    if args.baseline:
        report["comparison"] = compare_live_reports(
            _read_report(args.baseline),
            report,
            minimum_repeats=args.minimum_claim_repeats,
            latency_threshold_pct=args.latency_threshold_pct,
            latency_threshold_seconds=args.latency_threshold_seconds,
        )
        report["optimization_claim_supported"] = report["comparison"]["verdict"] == "candidate_faster" and report["comparison"]["performance_claim_eligible"] is True
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output_path}")
    comparison = report.get("comparison")
    if not report["quality_gate_passed"]:
        return 1
    if isinstance(comparison, dict) and comparison.get("verdict") in {
        "insufficient_live_evidence",
        "reject_quality_regression",
        "reject_latency_regression",
    }:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
