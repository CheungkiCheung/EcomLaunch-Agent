"""Measure repeatability of the real OpenSKU Flash and Ultra launch flows.

This is intentionally an HTTP-level benchmark: it exercises the same Gateway
contract used by the browser while keeping each run in a fresh thread. The
output contains only timings, counts, tool names, and artifact filenames; user
prompts and model responses are never written to the report.

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

PROMPT = (
    "我想做一个 99-199 元的通勤咖啡杯，但没有任何店铺后台数据。"
    "请用公开信号帮我判断是否值得做 7 天轻量验证，并输出 Launch Validation Pack。"
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


def _artifact_names(state: dict[str, Any]) -> set[str]:
    return {Path(str(path)).name for path in state.get("artifacts") or []}


def _run_once(
    client: httpx.Client,
    *,
    csrf: str,
    mode: str,
    index: int,
    timeout_seconds: float,
) -> dict[str, Any]:
    thread_id = _create_thread(client, csrf, index)
    context = {
        "mode": mode,
        "thinking_enabled": mode == "ultra",
        "is_plan_mode": mode == "ultra",
        "subagent_enabled": mode == "ultra",
    }
    body = {
        "assistant_id": "ecom-launch",
        "input": {"messages": [{"role": "user", "content": PROMPT}]},
        "config": {"recursion_limit": 100},
        "context": context,
        "stream_mode": ["values"],
    }
    started = time.perf_counter()
    response = client.post(
        f"/api/threads/{thread_id}/runs/wait",
        json=body,
        headers={"X-CSRF-Token": csrf},
        timeout=timeout_seconds,
    )
    elapsed = time.perf_counter() - started
    state = _json_response(response, f"{mode} run {index}")
    runs = _json_response(client.get(f"/api/threads/{thread_id}/runs"), "list runs")
    run = runs[0] if runs else {}
    artifact_names = _artifact_names(state)
    tools = _tool_names(state)
    return {
        "index": index,
        "mode": mode,
        "elapsed_seconds": round(elapsed, 3),
        "status": run.get("status"),
        "llm_call_count": int(run.get("llm_call_count") or 0),
        "total_tokens": int(run.get("total_tokens") or 0),
        "total_input_tokens": int(run.get("total_input_tokens") or 0),
        "total_output_tokens": int(run.get("total_output_tokens") or 0),
        "tool_names": tools,
        "artifact_names": sorted(artifact_names),
        "pack_complete": artifact_names == PACK_FILES,
        "preflight_passed": any(
            "Successfully presented files" in str(message.get("content", ""))
            for message in state.get("messages", [])
            if isinstance(message, dict) and message.get("type") == "tool"
        ),
    }


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    elapsed = [float(row["elapsed_seconds"]) for row in rows]

    def percentile(values: list[float], percentile_value: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        rank = (len(ordered) - 1) * percentile_value
        lower = int(rank)
        upper = min(lower + 1, len(ordered) - 1)
        fraction = rank - lower
        return round(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction, 3)

    return {
        "runs": len(rows),
        "elapsed_seconds": {
            "min": round(min(elapsed), 3) if elapsed else 0.0,
            "max": round(max(elapsed), 3) if elapsed else 0.0,
            "mean": round(statistics.mean(elapsed), 3) if elapsed else 0.0,
            "p50": percentile(elapsed, 0.5),
            "p95": percentile(elapsed, 0.95),
        },
        "llm_call_count": {
            "min": min(int(row["llm_call_count"]) for row in rows) if rows else 0,
            "max": max(int(row["llm_call_count"]) for row in rows) if rows else 0,
        },
        "total_tokens": {
            "min": min(int(row["total_tokens"]) for row in rows) if rows else 0,
            "max": max(int(row["total_tokens"]) for row in rows) if rows else 0,
        },
        "pack_success_rate": round(
            sum(bool(row["pack_complete"]) for row in rows) / len(rows), 3
        )
        if rows
        else 0.0,
        "preflight_success_rate": round(
            sum(bool(row["preflight_passed"]) for row in rows) / len(rows), 3
        )
        if rows
        else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.environ.get("OPENSKU_BENCHMARK_BASE_URL", "http://127.0.0.1:8001"))
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=420.0)
    parser.add_argument("--output", default="benchmark-results/opensku-benchmark.json")
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows: dict[str, list[dict[str, Any]]] = {"flash": [], "ultra": []}
    started = time.perf_counter()
    limits = httpx.Limits(max_connections=1, max_keepalive_connections=1)
    with httpx.Client(base_url=args.base_url.rstrip("/"), limits=limits, timeout=args.timeout) as client:
        csrf = _register(client)
        for mode in ("flash", "ultra"):
            for index in range(1, args.repeats + 1):
                print(f"[{mode} {index}/{args.repeats}] starting", flush=True)
                result = _run_once(
                    client,
                    csrf=csrf,
                    mode=mode,
                    index=index,
                    timeout_seconds=args.timeout,
                )
                rows[mode].append(result)
                print(
                    f"[{mode} {index}/{args.repeats}] {result['elapsed_seconds']:.3f}s "
                    f"calls={result['llm_call_count']} tokens={result['total_tokens']} "
                    f"pack={'ok' if result['pack_complete'] else 'FAIL'} "
                    f"preflight={'ok' if result['preflight_passed'] else 'FAIL'}",
                    flush=True,
                )

    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "base_url_host": args.base_url.split("//", 1)[-1].split("/", 1)[0],
        "repeats": args.repeats,
        "total_elapsed_seconds": round(time.perf_counter() - started, 3),
        "summary": {mode: _summary(mode_rows) for mode, mode_rows in rows.items()},
        "runs": rows,
    }
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
