from __future__ import annotations

from scripts.run_opensku_benchmark import (
    _record_stream_event,
    _summary,
    compare_live_reports,
)


def test_benchmark_summary_reports_repeatability_and_success_rates() -> None:
    rows = [
        {
            "elapsed_seconds": 10.0,
            "preparing_duration_seconds": 2.0,
            "first_tool_call_seconds": 2.0,
            "first_user_visible_text_seconds": 9.0,
            "llm_call_count": 4,
            "total_tokens": 100,
            "pack_complete": True,
            "preflight_passed": True,
        },
        {
            "elapsed_seconds": 20.0,
            "preparing_duration_seconds": 4.0,
            "first_tool_call_seconds": 4.0,
            "first_user_visible_text_seconds": 18.0,
            "llm_call_count": 5,
            "total_tokens": 200,
            "pack_complete": True,
            "preflight_passed": False,
        },
        {
            "elapsed_seconds": 30.0,
            "preparing_duration_seconds": 6.0,
            "first_tool_call_seconds": 6.0,
            "first_user_visible_text_seconds": 27.0,
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
    assert summary["timings"]["preparing_duration_seconds"]["p50"] == 4.0


def test_stream_event_timing_detects_reasoning_tool_and_visible_text() -> None:
    timings = {
        "first_sse_event_seconds": None,
        "first_state_event_seconds": None,
        "first_ai_message_seconds": None,
        "first_reasoning_seconds": None,
        "first_tool_call_seconds": None,
        "first_user_visible_text_seconds": None,
    }
    counts: dict[str, int] = {}

    _record_stream_event(
        timings,
        counts,
        event="metadata",
        data={"run_id": "run-1"},
        elapsed=0.1,
    )
    _record_stream_event(
        timings,
        counts,
        event="updates",
        data={
            "agent": {
                "messages": [
                    {
                        "type": "ai",
                        "content": "",
                        "additional_kwargs": {"reasoning_content": "分析依赖"},
                        "tool_calls": [{"name": "task", "args": {}}],
                    }
                ]
            }
        },
        elapsed=7.5,
    )
    _record_stream_event(
        timings,
        counts,
        event="values",
        data={"messages": [{"type": "ai", "content": "最终答案"}]},
        elapsed=40.0,
    )

    assert timings == {
        "first_sse_event_seconds": 0.1,
        "first_state_event_seconds": 7.5,
        "first_ai_message_seconds": 7.5,
        "first_reasoning_seconds": 7.5,
        "first_tool_call_seconds": 7.5,
        "first_user_visible_text_seconds": 40.0,
    }
    assert counts == {"metadata": 1, "updates": 1, "values": 1}


def _live_report(
    *,
    elapsed: float,
    preparing: float,
    repeats: int = 3,
    replay: bool = False,
    quality: float = 1.0,
    model: str = "deepseek-reasoner",
) -> dict:
    timings = {
        "preparing_duration_seconds": {"p50": preparing},
        "first_tool_call_seconds": {"p50": preparing},
        "first_user_visible_text_seconds": {"p50": elapsed},
        "elapsed_seconds": {"p50": elapsed},
    }
    mode = {
        "quality_gate_pass_rate": quality,
        "models": [model],
        "timings": timings,
    }
    return {
        "measurement_type": "live_llm_product_path",
        "replay": replay,
        "prompt_id": "prompt-v1",
        "requested_model_name": model,
        "repeats": repeats,
        "summary": {"flash": mode, "ultra": mode},
    }


def test_live_comparison_rejects_replay_even_when_timing_is_faster() -> None:
    comparison = compare_live_reports(
        _live_report(elapsed=100.0, preparing=10.0),
        _live_report(elapsed=50.0, preparing=5.0, replay=True),
    )

    assert comparison["verdict"] == "insufficient_live_evidence"
    assert comparison["performance_claim_eligible"] is False
    assert any("replay=false" in issue for issue in comparison["evidence_issues"])


def test_live_comparison_requires_repeats_and_full_quality_gate() -> None:
    comparison = compare_live_reports(
        _live_report(elapsed=100.0, preparing=10.0, repeats=1),
        _live_report(elapsed=50.0, preparing=5.0, repeats=1, quality=0.667),
    )

    assert comparison["verdict"] == "insufficient_live_evidence"
    assert comparison["performance_claim_eligible"] is False
    assert any("fewer than 3 repeats" in issue for issue in comparison["evidence_issues"])


def test_live_comparison_can_claim_only_quality_preserving_live_improvement() -> None:
    comparison = compare_live_reports(
        _live_report(elapsed=100.0, preparing=10.0),
        _live_report(elapsed=80.0, preparing=7.0),
    )

    assert comparison["verdict"] == "candidate_faster"
    assert comparison["performance_claim_eligible"] is True
    assert "ultra.elapsed_seconds" in comparison["materially_faster_metrics"]
    assert "ultra.preparing_duration_seconds" in comparison["materially_faster_metrics"]
