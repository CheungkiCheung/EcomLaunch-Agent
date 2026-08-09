"""Run an evidence-gated Launch + Growth benchmark on the real Gateway.

The benchmark uses the committed hash-keyed replay model, but it still drives
the real Gateway, authentication, thread state, uploads, agent graph, tools,
run budget, Launch Pack preflight, and artifact APIs. It intentionally reports
contract and determinism metrics separately from live-model quality metrics.

Examples::

    # Write a local report (ignored by Git)
    PYTHONPATH=. uv run python scripts/run_opensku_replay_benchmark.py

    # Write a shareable baseline under the repository's benchmarks directory
    PYTHONPATH=. uv run python scripts/run_opensku_replay_benchmark.py \
      --output-dir ../benchmarks/opensku-replay --repeats 3

    # Compare a candidate report against a previously published baseline
    PYTHONPATH=. uv run python scripts/run_opensku_replay_benchmark.py \
      --baseline ../benchmarks/opensku-replay/latest-summary.json
"""

from __future__ import annotations

import argparse
import html
import json
import os
import platform
import statistics
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND.parent
TESTS = BACKEND / "tests"
FIXTURE_PATH = TESTS / "fixtures" / "replay" / "opensku_product_flows.json"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(TESTS))

PACK_FILES = {
    "launch-war-room.html",
    "evidence-ledger.json",
    "competitor-table.csv",
    "positioning-brief.md",
    "listing-pack.md",
    "content-pack.md",
    "launch-calendar.csv",
}

LAUNCH_PREFLIGHT_MARKERS = (
    "evidence-ledger.json is not valid readable JSON",
    "launch-calendar.csv must contain a header and at least one non-empty data row",
)

GROWTH_MARKERS = (
    "SHIP WITH MONITORING",
    "p = 0.0477",
    "+10.00 pp",
    "+0.20 to +19.80 pp",
    "SRM is not detected",
)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (len(ordered) - 1) * percentile_value
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = rank - lower
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction, 3)


def _latency_summary(rows: list[dict[str, Any]]) -> dict[str, float]:
    elapsed = [float(row["elapsed_seconds"]) for row in rows]
    return {
        "min": round(min(elapsed), 3) if elapsed else 0.0,
        "p50": _percentile(elapsed, 0.5),
        "p95": _percentile(elapsed, 0.95),
        "max": round(max(elapsed), 3) if elapsed else 0.0,
        "mean": round(statistics.mean(elapsed), 3) if elapsed else 0.0,
    }


def _rate(rows: list[dict[str, Any]], key: str) -> float:
    if not rows:
        return 0.0
    return round(sum(bool(row.get(key)) for row in rows) / len(rows), 3)


def _check_rate(rows: list[dict[str, Any]]) -> float:
    checks = [passed for row in rows for passed in (row.get("checks") or {}).values()]
    return round(sum(bool(value) for value in checks) / len(checks), 3) if checks else 0.0


def _metrics_summary(rows: list[dict[str, Any]], key: str) -> dict[str, int | float | None]:
    values = [int(row[key]) for row in rows if row.get(key) is not None]
    if not values:
        return {"min": None, "max": None, "mean": None}
    return {
        "min": min(values),
        "max": max(values),
        "mean": round(statistics.mean(values), 1),
    }


def _summarize_scenario(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "runs": len(rows),
        "run_success_rate": _rate(rows, "run_succeeded"),
        "contract_pass_rate": _rate(rows, "contract_passed"),
        "check_pass_rate": _check_rate(rows),
        "latency_seconds": _latency_summary(rows),
        "llm_call_count": _metrics_summary(rows, "llm_call_count"),
        "total_tokens": _metrics_summary(rows, "total_tokens"),
        "token_metrics_available": all(bool(row.get("token_metrics_available")) for row in rows) if rows else False,
    }


def _summary_for_report(report: dict[str, Any]) -> dict[str, Any]:
    scenario_summaries = report.get("summary", {}).get("scenarios", {})
    scenario_rows = report.get("runs", {})
    all_rows = [row for rows in scenario_rows.values() for row in rows]
    return {
        "scenario_count": len(scenario_summaries),
        "runs": len(all_rows),
        "run_success_rate": _rate(all_rows, "run_succeeded"),
        "contract_pass_rate": _rate(all_rows, "contract_passed"),
        "check_pass_rate": _check_rate(all_rows),
    }


def compare_reports(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    *,
    latency_threshold_pct: float = 5.0,
    latency_threshold_seconds: float = 0.05,
) -> dict[str, Any]:
    """Compare reports using quality-first relative and absolute latency gates."""

    baseline_summary = _summary_for_report(baseline)
    candidate_summary = _summary_for_report(candidate)
    quality_regressions = {
        key: {
            "baseline": baseline_summary[key],
            "candidate": candidate_summary[key],
        }
        for key in ("run_success_rate", "contract_pass_rate", "check_pass_rate")
        if candidate_summary[key] < baseline_summary[key]
    }

    quality_improvements = {
        key: {
            "baseline": baseline_summary[key],
            "candidate": candidate_summary[key],
        }
        for key in ("run_success_rate", "contract_pass_rate", "check_pass_rate")
        if candidate_summary[key] > baseline_summary[key]
    }
    latency_changes_pct: dict[str, float] = {}
    latency_changes_seconds: dict[str, float] = {}
    baseline_p50_seconds: dict[str, float] = {}
    candidate_p50_seconds: dict[str, float] = {}
    raw_latency_changes_seconds: dict[str, float] = {}
    baseline_scenarios = baseline.get("summary", {}).get("scenarios", {})
    candidate_scenarios = candidate.get("summary", {}).get("scenarios", {})
    for scenario_name in sorted(set(baseline_scenarios) & set(candidate_scenarios)):
        baseline_p50 = float(baseline_scenarios[scenario_name].get("latency_seconds", {}).get("p50") or 0)
        candidate_p50 = float(candidate_scenarios[scenario_name].get("latency_seconds", {}).get("p50") or 0)
        if baseline_p50 > 0:
            raw_delta_seconds = candidate_p50 - baseline_p50
            baseline_p50_seconds[scenario_name] = round(baseline_p50, 3)
            candidate_p50_seconds[scenario_name] = round(candidate_p50, 3)
            raw_latency_changes_seconds[scenario_name] = raw_delta_seconds
            latency_changes_seconds[scenario_name] = round(raw_delta_seconds, 3)
            latency_changes_pct[scenario_name] = round(raw_delta_seconds / baseline_p50 * 100, 2)

    faster_scenarios = sorted(name for name, change in latency_changes_pct.items() if change <= -latency_threshold_pct and raw_latency_changes_seconds[name] <= -latency_threshold_seconds)
    slower_scenarios = sorted(name for name, change in latency_changes_pct.items() if change >= latency_threshold_pct and raw_latency_changes_seconds[name] >= latency_threshold_seconds)

    if quality_regressions:
        verdict = "reject_quality_regression"
    elif quality_improvements and slower_scenarios:
        verdict = "candidate_quality_better_with_latency_cost"
    elif quality_improvements:
        verdict = "candidate_quality_better"
    elif slower_scenarios:
        verdict = "reject_efficiency_regression"
    elif faster_scenarios:
        verdict = "candidate_faster"
    else:
        verdict = "no_material_improvement"

    return {
        "verdict": verdict,
        "baseline_p50_seconds": baseline_p50_seconds,
        "candidate_p50_seconds": candidate_p50_seconds,
        "latency_changes_pct": latency_changes_pct,
        "latency_changes_seconds": latency_changes_seconds,
        "latency_threshold_pct": latency_threshold_pct,
        "latency_threshold_seconds": latency_threshold_seconds,
        "faster_scenarios": faster_scenarios,
        "slower_scenarios": slower_scenarios,
        "quality_regressions": quality_regressions,
        "quality_improvements": quality_improvements,
        "baseline": baseline_summary,
        "candidate": candidate_summary,
    }


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


def _subagent_sequence(state: dict[str, Any]) -> list[str]:
    sequence: list[str] = []
    for call in _tool_calls(state):
        if call.get("name") != "task":
            continue
        args = call.get("args")
        if isinstance(args, dict) and isinstance(args.get("subagent_type"), str):
            sequence.append(args["subagent_type"])
    return sequence


def _state_text(state: dict[str, Any]) -> str:
    return json.dumps(state, ensure_ascii=False, default=str)


def _artifact_names(state: dict[str, Any]) -> set[str]:
    return {Path(str(path)).name for path in state.get("artifacts") or []}


def _run_record(client: Any, thread_id: str) -> dict[str, Any]:
    response = client.get(f"/api/threads/{thread_id}/runs")
    if response.status_code != 200 or not response.json():
        raise RuntimeError(f"run record missing for {thread_id}: {response.text[:500]}")
    record = response.json()[0]
    if not isinstance(record, dict):
        raise RuntimeError(f"invalid run record for {thread_id}")
    return record


def _register(client: Any) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"opensku-replay-benchmark-{uuid.uuid4().hex[:12]}@example.com",
            "password": "benchmark-local-password-123",
        },
    )
    if response.status_code != 201:
        raise RuntimeError(f"register failed: {response.status_code} {response.text[:500]}")
    csrf = client.cookies.get("csrf_token")
    if not csrf:
        raise RuntimeError("register did not set csrf_token")
    return csrf


def _create_thread(client: Any, csrf: str, agent_name: str, index: int) -> str:
    thread_id = f"opensku-replay-benchmark-{agent_name}-{index}-{uuid.uuid4().hex[:10]}"
    response = client.post(
        "/api/threads",
        json={"thread_id": thread_id, "metadata": {"agent_name": agent_name}},
        headers={"X-CSRF-Token": csrf},
    )
    if response.status_code != 200:
        raise RuntimeError(f"create thread failed: {response.status_code} {response.text[:500]}")
    return thread_id


def _upload_growth_files(client: Any, csrf: str, thread_id: str) -> list[dict[str, Any]]:
    from _replay_fixture import opensku_growth_csvs

    response = client.post(
        f"/api/threads/{thread_id}/uploads",
        files=[("files", (name, content.encode("utf-8"), "text/csv")) for name, content in opensku_growth_csvs().items()],
        headers={"X-CSRF-Token": csrf},
    )
    if response.status_code != 200:
        raise RuntimeError(f"growth upload failed: {response.status_code} {response.text[:500]}")
    items = response.json().get("files")
    if not isinstance(items, list):
        raise RuntimeError("growth upload response did not contain files")
    return [item for item in items if isinstance(item, dict)]


def _run_wait(
    client: Any,
    *,
    csrf: str,
    thread_id: str,
    scenario: dict[str, Any],
    files: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], float]:
    message: dict[str, Any] = {"role": "user", "content": scenario["prompt"]}
    if files:
        message = {
            "type": "human",
            "content": [{"type": "text", "text": scenario["prompt"]}],
            "additional_kwargs": {
                "files": [
                    {
                        "filename": item["filename"],
                        "size": item["size"],
                        "path": item["virtual_path"],
                        "status": "uploaded",
                    }
                    for item in files
                ]
            },
        }
    started = time.perf_counter()
    response = client.post(
        f"/api/threads/{thread_id}/runs/wait",
        json={
            "assistant_id": scenario["assistant_id"],
            "input": {"messages": [message]},
            "config": {"recursion_limit": 100},
            "context": scenario["context"],
            "stream_mode": ["values"],
        },
        headers={"X-CSRF-Token": csrf},
    )
    elapsed = time.perf_counter() - started
    if response.status_code != 200:
        raise RuntimeError(f"run failed: {response.status_code} {response.text[:1000]}")
    state = response.json()
    if not isinstance(state, dict):
        raise RuntimeError("run response did not contain a state object")
    return state, _run_record(client, thread_id), elapsed


def _evaluate_launch(
    state: dict[str, Any],
    run: dict[str, Any],
    artifact_evidence_label: str | None,
) -> dict[str, Any]:
    text = _state_text(state)
    tool_names = _tool_names(state)
    artifacts = _artifact_names(state)
    checks = {
        "run_succeeded": run.get("status") == "success",
        "specialists_in_dependency_order": _subagent_sequence(state) == ["market-voc-researcher", "offer-architect", "asset-studio"],
        "seven_artifacts_delivered": artifacts == PACK_FILES,
        "seven_file_writes": tool_names.count("write_file") == 7,
        "two_preflight_attempts": tool_names.count("present_files") == 2,
        "two_bounded_repairs": tool_names.count("str_replace") == 2,
        "failed_observations_recorded": all(marker in text for marker in LAUNCH_PREFLIGHT_MARKERS),
        "evidence_ledger_observed_public": artifact_evidence_label == "observed_public",
    }
    return {
        "scenario": "launch",
        "tool_names": tool_names,
        "artifact_names": sorted(artifacts),
        "subagent_sequence": _subagent_sequence(state),
        "checks": checks,
        "run_succeeded": bool(checks["run_succeeded"]),
        "contract_passed": all(checks.values()),
        # The replay config disables token accounting. Do not turn its
        # placeholder zeroes into a false performance metric.
        "llm_call_count": None,
        "total_tokens": None,
        "token_metrics_available": False,
    }


def _evaluate_growth(state: dict[str, Any], run: dict[str, Any], uploaded_names: set[str]) -> dict[str, Any]:
    text = _state_text(state)
    tool_names = _tool_names(state)
    checks = {
        "run_succeeded": run.get("status") == "success",
        "three_csv_files_uploaded": uploaded_names == {"customers.csv", "assignments.csv", "outcomes.csv"},
        "deterministic_tool_chain": tool_names == ["inspect_data", "query_data", "analyze_ab_test"],
        "ship_decision_present": GROWTH_MARKERS[0] in text,
        "p_value_present": GROWTH_MARKERS[1] in text,
        "uplift_present": GROWTH_MARKERS[2] in text,
        "confidence_interval_present": GROWTH_MARKERS[3] in text,
        "srm_check_present": GROWTH_MARKERS[4] in text,
    }
    return {
        "scenario": "growth",
        "tool_names": tool_names,
        "artifact_names": sorted(_artifact_names(state)),
        "checks": checks,
        "run_succeeded": bool(checks["run_succeeded"]),
        "contract_passed": all(checks.values()),
        "llm_call_count": None,
        "total_tokens": None,
        "token_metrics_available": False,
    }


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# OpenSKU Replay Benchmark",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Provider: `{report['provider']}`",
        f"Repeats per scenario: `{report['repeats']}`",
        "",
        "> This report measures the real Gateway and deterministic product contracts. It is not a live-model quality score. No prompts, model responses, uploaded rows, or artifact contents are stored in the report.",
        "",
        "## Overall",
        "",
        "| Metric | Result |",
        "| --- | ---: |",
        f"| Scenarios | {summary['scenario_count']} |",
        f"| Runs | {summary['runs']} |",
        f"| Run success rate | {_pct(summary['run_success_rate'])} |",
        f"| Contract-complete run rate | {_pct(summary['contract_pass_rate'])} |",
        f"| Contract check pass rate | {_pct(summary['check_pass_rate'])} |",
        f"| Replay misses | {report['replay_misses']} |",
        "",
        "## Scenario summary",
        "",
        "| Scenario | Runs | Run success | Contract-complete | Checks | P50 | P95 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, item in report["summary"]["scenarios"].items():
        latency = item["latency_seconds"]
        lines.append(f"| {name} | {item['runs']} | {_pct(item['run_success_rate'])} | {_pct(item['contract_pass_rate'])} | {_pct(item['check_pass_rate'])} | {latency['p50']:.3f}s | {latency['p95']:.3f}s |")
    lines.extend(["", "## Evidence-gated optimization verdict", ""])
    comparison = report.get("comparison")
    if comparison is None:
        lines.append("No candidate/baseline comparison was supplied. This run establishes a measured baseline; it makes no optimization claim.")
    else:
        lines.append(f"**Verdict:** `{comparison['verdict']}`")
        if comparison["latency_changes_pct"]:
            lines.append(f"\nP50 latency changes (negative means faster; material only when both `{comparison['latency_threshold_pct']:.1f}%` and `{comparison['latency_threshold_seconds']:.3f}s` thresholds are met):")
            for name, change in comparison["latency_changes_pct"].items():
                baseline_p50 = comparison["baseline_p50_seconds"][name]
                candidate_p50 = comparison["candidate_p50_seconds"][name]
                delta_seconds = comparison["latency_changes_seconds"][name]
                material = name in comparison["faster_scenarios"] or name in comparison["slower_scenarios"]
                lines.append(f"- `{name}`: `{baseline_p50:.3f}s -> {candidate_p50:.3f}s`; `{change:.2f}%` / `{delta_seconds:+.3f}s` ({'material' if material else 'below gate'})")
        if comparison["quality_regressions"]:
            lines.append("\nQuality regressions were detected and speed changes are rejected:")
            for key, values in comparison["quality_regressions"].items():
                lines.append(f"- `{key}`: baseline `{values['baseline']}`, candidate `{values['candidate']}`")
    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "- The replay provider is deterministic and does not represent live provider quality.",
            "- Token metrics are reported only when the runtime records them; replay runs may disable token tracking.",
            "- The current golden suite covers one Launch workflow and one Growth workflow; expand the case manifest before treating this as a broad benchmark.",
        ]
    )
    return "\n".join(lines) + "\n"


def _render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    rows = []
    for name, item in report["summary"]["scenarios"].items():
        latency = item["latency_seconds"]
        rows.append(
            "<tr>"
            f"<td>{html.escape(name)}</td>"
            f"<td>{item['runs']}</td>"
            f"<td>{_pct(item['run_success_rate'])}</td>"
            f"<td>{_pct(item['contract_pass_rate'])}</td>"
            f"<td>{_pct(item['check_pass_rate'])}</td>"
            f"<td>{latency['p50']:.3f}s</td>"
            f"<td>{latency['p95']:.3f}s</td>"
            "</tr>"
        )
    comparison = report.get("comparison")
    verdict = comparison["verdict"] if comparison else "baseline_only"
    comparison_html = ""
    if comparison:
        change_items = []
        for name, change in comparison["latency_changes_pct"].items():
            baseline_p50 = comparison["baseline_p50_seconds"][name]
            candidate_p50 = comparison["candidate_p50_seconds"][name]
            delta_seconds = comparison["latency_changes_seconds"][name]
            material = name in comparison["faster_scenarios"] or name in comparison["slower_scenarios"]
            change_items.append(
                f"<li><code>{html.escape(name)}</code>: <code>{baseline_p50:.3f}s -&gt; {candidate_p50:.3f}s</code>; <code>{change:.2f}%</code> / <code>{delta_seconds:+.3f}s</code> ({'material' if material else 'below gate'})</li>"
            )
        comparison_html = (
            "<h2>Optimization comparison</h2>"
            f"<p>Verdict: <code>{html.escape(verdict)}</code>. A latency change is material only when it reaches both "
            f"<code>{comparison['latency_threshold_pct']:.1f}%</code> and <code>{comparison['latency_threshold_seconds']:.3f}s</code>.</p>"
            f"<ul>{''.join(change_items)}</ul>"
        )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>OpenSKU Replay Benchmark</title>
<style>
body{{margin:0;background:#f7f3ec;color:#3f342b;font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
main{{max-width:960px;margin:40px auto;padding:0 24px}}
article{{background:#fffdf9;border:1px solid #eadfce;border-radius:18px;padding:28px;box-shadow:0 12px 36px #a1784a18}}
h1{{margin-top:0;color:#8c4e2b}} h2{{margin-top:30px;color:#70432d}}
.note{{background:#fff5dc;border-left:4px solid #e5a33d;padding:12px 16px;border-radius:8px}}
table{{width:100%;border-collapse:collapse;margin-top:12px}} th,td{{padding:10px;border-bottom:1px solid #eee3d6;text-align:left}} th{{color:#8c6d56;font-size:12px;text-transform:uppercase;letter-spacing:.04em}}
.pill{{display:inline-block;border-radius:999px;background:#e7f7ef;color:#23724a;padding:2px 10px;font-weight:600}}
code{{background:#f3eee7;padding:2px 5px;border-radius:5px}}
</style></head><body><main><article>
<h1>OpenSKU Replay Benchmark</h1>
<p>Generated <code>{html.escape(str(report["generated_at"]))}</code> · provider <code>{html.escape(str(report["provider"]))}</code> · repeats <code>{report["repeats"]}</code></p>
<p class="note">This is a deterministic Gateway contract baseline, not a live-model quality score. The report stores no prompts, responses, uploaded rows, or artifact contents.</p>
<h2>Overall</h2><table><tbody>
<tr><th>Scenarios</th><td>{summary["scenario_count"]}</td></tr>
<tr><th>Runs</th><td>{summary["runs"]}</td></tr>
<tr><th>Run success rate</th><td><span class="pill">{_pct(summary["run_success_rate"])}</span></td></tr>
<tr><th>Contract-complete run rate</th><td><span class="pill">{_pct(summary["contract_pass_rate"])}</span></td></tr>
<tr><th>Contract check pass rate</th><td><span class="pill">{_pct(summary["check_pass_rate"])}</span></td></tr>
<tr><th>Optimization verdict</th><td><code>{html.escape(verdict)}</code></td></tr>
</tbody></table>
<h2>Scenario summary</h2><table><thead><tr><th>Scenario</th><th>Runs</th><th>Run success</th><th>Contract-complete</th><th>Checks</th><th>P50</th><th>P95</th></tr></thead><tbody>{"".join(rows)}</tbody></table>
{comparison_html}
<h2>Limitations</h2><ul>
<li>Replay is deterministic and does not represent live provider quality.</li>
<li>Token metrics are available only when runtime token tracking is enabled.</li>
<li>The current suite contains one Launch and one Growth golden workflow.</li>
</ul>
</article></main></body></html>
"""


def _build_report(
    rows: dict[str, list[dict[str, Any]]],
    *,
    repeats: int,
    replay_misses: int,
    comparison: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = {"scenarios": {name: _summarize_scenario(scenario_rows) for name, scenario_rows in rows.items()}}
    report: dict[str, Any] = {
        "report_version": 1,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "provider": "deterministic_replay",
        "replay": True,
        "repeats": repeats,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "summary": summary,
        "runs": rows,
        "replay_misses": replay_misses,
        "comparison": comparison,
    }
    report["summary"].update(_summary_for_report(report))
    return report


def _prepare_runtime() -> tuple[tempfile.TemporaryDirectory[str], Path]:
    from _replay_fixture import build_opensku_config_yaml, prepare_hermetic_extras

    temp_dir = tempfile.TemporaryDirectory(prefix="opensku-replay-benchmark-")
    home = Path(temp_dir.name)
    config_path = home / "config.yaml"
    config_path.write_text(
        build_opensku_config_yaml(
            model_use="replay_provider:ReplayChatModel",
            home=home,
            repo_root=REPO_ROOT,
        ),
        encoding="utf-8",
    )
    os.environ["OPENSKU_HOME"] = str(home)
    os.environ["OPENSKU_CONFIG_PATH"] = str(config_path)
    os.environ["OPENSKU_PROJECT_ROOT"] = str(REPO_ROOT)
    os.environ["OPENSKU_EXTENSIONS_CONFIG_PATH"] = str(prepare_hermetic_extras(home))
    os.environ["OPENSKU_REPLAY_FIXTURE"] = str(FIXTURE_PATH)
    os.environ.setdefault("AUTH_JWT_SECRET", "opensku-replay-benchmark-secret-32-bytes")
    return temp_dir, home


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output-dir", default="benchmark-results/opensku-replay")
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--latency-threshold-pct", type=float, default=5.0)
    parser.add_argument("--latency-threshold-seconds", type=float, default=0.05)
    args = parser.parse_args(argv)
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")
    if args.latency_threshold_pct < 0 or args.latency_threshold_seconds < 0:
        parser.error("latency thresholds must be non-negative")

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    temp_dir, _home = _prepare_runtime()
    try:
        import replay_provider
        from starlette.testclient import TestClient

        from app.gateway.app import create_app

        replay_provider.reset_replay_misses()
        fixture = _read_json(FIXTURE_PATH)
        scenarios = fixture.get("scenarios") or {}
        rows: dict[str, list[dict[str, Any]]] = {"launch": [], "growth": []}
        with TestClient(create_app()) as client:
            csrf = _register(client)
            for repeat in range(1, args.repeats + 1):
                for name in ("launch", "growth"):
                    scenario = scenarios.get(name)
                    if not isinstance(scenario, dict):
                        raise RuntimeError(f"fixture scenario {name!r} is missing")
                    thread_id = _create_thread(client, csrf, str(scenario["assistant_id"]), repeat)
                    uploaded_items: list[dict[str, Any]] = []
                    if name == "growth":
                        uploaded_items = _upload_growth_files(client, csrf, thread_id)
                    print(f"[{name} {repeat}/{args.repeats}] starting", flush=True)
                    state, run, elapsed = _run_wait(
                        client,
                        csrf=csrf,
                        thread_id=thread_id,
                        scenario=scenario,
                        files=uploaded_items or None,
                    )
                    if name == "launch":
                        evidence_label: str | None = None
                        artifact_response = client.get(f"/api/threads/{thread_id}/artifacts/mnt/user-data/outputs/evidence-ledger.json")
                        if artifact_response.status_code == 200:
                            try:
                                evidence_label = artifact_response.json().get("entries", [{}])[0].get("label")
                            except (AttributeError, IndexError, TypeError, ValueError):
                                evidence_label = None
                        result = _evaluate_launch(state, run, evidence_label)
                    else:
                        result = _evaluate_growth(
                            state,
                            run,
                            {str(item.get("filename")) for item in uploaded_items if item.get("filename")},
                        )
                    result.update(
                        {
                            "repeat": repeat,
                            "elapsed_seconds": round(elapsed, 3),
                        }
                    )
                    rows[name].append(result)
                    print(
                        f"[{name} {repeat}/{args.repeats}] {result['elapsed_seconds']:.3f}s run={'ok' if result['run_succeeded'] else 'FAIL'} contract={'ok' if result['contract_passed'] else 'FAIL'}",
                        flush=True,
                    )

        misses = len(replay_provider.replay_misses())
        report = _build_report(rows, repeats=args.repeats, replay_misses=misses)
        if args.baseline:
            report["comparison"] = compare_reports(
                _read_json(args.baseline),
                report,
                latency_threshold_pct=args.latency_threshold_pct,
                latency_threshold_seconds=args.latency_threshold_seconds,
            )
        _write_json(output_dir / "latest-summary.json", report)
        (output_dir / "latest-report.md").write_text(_render_markdown(report), encoding="utf-8")
        (output_dir / "latest-report.html").write_text(_render_html(report), encoding="utf-8")
        print(f"Wrote benchmark reports to {output_dir}")
        if misses:
            print(f"Replay misses detected: {misses}", file=sys.stderr)
            return 1
        comparison = report.get("comparison")
        if isinstance(comparison, dict) and comparison.get("verdict") in {
            "reject_quality_regression",
            "reject_efficiency_regression",
        }:
            return 1
        return 0
    finally:
        temp_dir.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
