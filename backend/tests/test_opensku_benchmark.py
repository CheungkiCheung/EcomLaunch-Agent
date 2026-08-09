from __future__ import annotations

from scripts.run_opensku_benchmark import _summary


def test_benchmark_summary_reports_repeatability_and_success_rates() -> None:
    rows = [
        {
            "elapsed_seconds": 10.0,
            "llm_call_count": 4,
            "total_tokens": 100,
            "pack_complete": True,
            "preflight_passed": True,
        },
        {
            "elapsed_seconds": 20.0,
            "llm_call_count": 5,
            "total_tokens": 200,
            "pack_complete": True,
            "preflight_passed": False,
        },
        {
            "elapsed_seconds": 30.0,
            "llm_call_count": 4,
            "total_tokens": 150,
            "pack_complete": False,
            "preflight_passed": False,
        },
    ]

    summary = _summary(rows)

    assert summary["elapsed_seconds"] == {
        "min": 10.0,
        "max": 30.0,
        "mean": 20.0,
        "p50": 20.0,
        "p95": 29.0,
    }
    assert summary["llm_call_count"] == {"min": 4, "max": 5}
    assert summary["total_tokens"] == {"min": 100, "max": 200}
    assert summary["pack_success_rate"] == 0.667
    assert summary["preflight_success_rate"] == 0.333
