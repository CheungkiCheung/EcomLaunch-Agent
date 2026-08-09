from __future__ import annotations

from scripts.run_opensku_replay_benchmark import (
    _build_report,
    _evaluate_growth,
    _render_html,
    _render_markdown,
    compare_reports,
)


def _row(
    *,
    elapsed: float = 10.0,
    contract_passed: bool = True,
    check_values: dict[str, bool] | None = None,
) -> dict:
    checks = check_values or {"run_succeeded": contract_passed}
    return {
        "scenario": "launch",
        "elapsed_seconds": elapsed,
        "run_succeeded": contract_passed,
        "contract_passed": contract_passed,
        "checks": checks,
        "llm_call_count": 4,
        "total_tokens": None,
        "token_metrics_available": False,
    }


def test_growth_evaluator_checks_tool_contract_and_numeric_decision() -> None:
    state = {
        "messages": [
            {
                "type": "ai",
                "tool_calls": [
                    {"name": "inspect_data"},
                    {"name": "query_data"},
                    {"name": "analyze_ab_test"},
                ],
            },
            {
                "type": "ai",
                "content": ("SHIP WITH MONITORING; p = 0.0477; +10.00 pp; +0.20 to +19.80 pp; SRM is not detected"),
            },
        ]
    }
    result = _evaluate_growth(
        state,
        {"status": "success", "total_tokens": None},
        {"customers.csv", "assignments.csv", "outcomes.csv"},
    )

    assert result["contract_passed"] is True
    assert all(result["checks"].values())


def test_comparison_rejects_quality_regression_even_when_candidate_is_faster() -> None:
    baseline = _build_report(
        {"launch": [_row(elapsed=20.0)], "growth": [_row(elapsed=10.0)]},
        repeats=1,
        replay_misses=0,
    )
    candidate = _build_report(
        {
            "launch": [_row(elapsed=10.0, contract_passed=False)],
            "growth": [_row(elapsed=5.0)],
        },
        repeats=1,
        replay_misses=0,
    )

    comparison = compare_reports(baseline, candidate)

    assert comparison["verdict"] == "replay_contract_regression"
    assert "contract_pass_rate" in comparison["quality_regressions"]
    assert comparison["faster_scenarios"] == []
    assert comparison["performance_claim_eligible"] is False


def test_replay_comparison_never_claims_candidate_is_faster() -> None:
    baseline = _build_report(
        {"launch": [_row(elapsed=20.0)], "growth": [_row(elapsed=10.0)]},
        repeats=1,
        replay_misses=0,
    )
    candidate = _build_report(
        {"launch": [_row(elapsed=1.0)], "growth": [_row(elapsed=1.0)]},
        repeats=1,
        replay_misses=0,
    )

    comparison = compare_reports(baseline, candidate)

    assert comparison["verdict"] == "replay_contract_only"
    assert comparison["latency_changes_pct"] == {"growth": -90.0, "launch": -95.0}
    assert comparison["faster_scenarios"] == []
    assert comparison["slower_scenarios"] == []
    assert comparison["performance_claim_eligible"] is False
    assert "diagnostic only" in comparison["performance_claim_reason"]


def test_only_live_reports_are_eligible_for_latency_verdict() -> None:
    baseline = _build_report(
        {"launch": [_row(elapsed=20.0)], "growth": [_row(elapsed=10.0)]},
        repeats=3,
        replay_misses=0,
    )
    candidate = _build_report(
        {"launch": [_row(elapsed=10.0)], "growth": [_row(elapsed=5.0)]},
        repeats=3,
        replay_misses=0,
    )
    baseline["replay"] = False
    candidate["replay"] = False

    comparison = compare_reports(baseline, candidate)

    assert comparison["verdict"] == "candidate_faster"
    assert comparison["faster_scenarios"] == ["growth", "launch"]
    assert comparison["performance_claim_eligible"] is True


def test_missing_replay_metadata_is_not_eligible_for_latency_verdict() -> None:
    baseline = _build_report({"launch": [_row(elapsed=20.0)]}, repeats=3, replay_misses=0)
    candidate = _build_report({"launch": [_row(elapsed=1.0)]}, repeats=3, replay_misses=0)
    baseline.pop("replay")
    candidate.pop("replay")

    comparison = compare_reports(baseline, candidate)

    assert comparison["verdict"] == "replay_contract_only"
    assert comparison["performance_claim_eligible"] is False


def test_comparison_marks_small_latency_changes_as_no_material_improvement() -> None:
    baseline = _build_report(
        {"launch": [_row(elapsed=20.0)], "growth": [_row(elapsed=10.0)]},
        repeats=1,
        replay_misses=0,
    )
    candidate = _build_report(
        {"launch": [_row(elapsed=19.5)], "growth": [_row(elapsed=9.8)]},
        repeats=1,
        replay_misses=0,
    )

    comparison = compare_reports(baseline, candidate)

    assert comparison["verdict"] == "replay_contract_only"
    assert comparison["quality_regressions"] == {}
    assert comparison["faster_scenarios"] == []


def test_comparison_ignores_large_percentage_on_tiny_absolute_latency_change() -> None:
    baseline = _build_report(
        {"launch": [_row(elapsed=20.0)], "growth": [_row(elapsed=0.057)]},
        repeats=1,
        replay_misses=0,
    )
    candidate = _build_report(
        {"launch": [_row(elapsed=20.0)], "growth": [_row(elapsed=0.05)]},
        repeats=1,
        replay_misses=0,
    )

    comparison = compare_reports(baseline, candidate)

    assert comparison["baseline_p50_seconds"]["growth"] == 0.057
    assert comparison["candidate_p50_seconds"]["growth"] == 0.05
    assert comparison["latency_changes_pct"]["growth"] < -5.0
    assert comparison["latency_changes_seconds"]["growth"] == -0.007
    assert comparison["verdict"] == "replay_contract_only"
    assert comparison["faster_scenarios"] == []


def test_report_is_sanitized_and_explains_baseline_scope() -> None:
    report = _build_report(
        {"launch": [_row()], "growth": [_row()]},
        repeats=1,
        replay_misses=0,
    )
    report["runs"]["launch"][0]["private_prompt"] = "do not publish this"

    markdown = _render_markdown(report)
    page = _render_html(report)

    assert "deterministic product contracts" in markdown
    assert "makes no optimization claim" in markdown
    assert "do not publish this" not in markdown
    assert "OpenSKU Replay Benchmark" in page
    assert "baseline_only" in page
