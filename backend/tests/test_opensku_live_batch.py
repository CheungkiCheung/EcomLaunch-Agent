from __future__ import annotations

import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from evals.opensku.run_live_batch import (  # noqa: E402
    BatchConfig,
    build_live_command,
    plan_batch_cases,
    run_batch,
)
from evals.opensku.run_live_agent_validation import build_live_prompt, copy_upload_fixtures  # noqa: E402


def test_case_aware_live_prompt_uses_case_without_revealing_expected_decision():
    case_path = REPO_ROOT / "evals/opensku/cases/opensku-softlaunch-001.json"
    case = json.loads(case_path.read_text(encoding="utf-8"))

    prompt = build_live_prompt(case["case_id"], case=case)

    assert "Case id: opensku-softlaunch-001" in prompt
    assert "Benchmark case file: /mnt/user-data/uploads/opensku-case.json" in prompt
    assert "Case launch stage: soft_launch" in prompt
    assert "Diagnose the decision from the case evidence" in prompt
    assert "expected_decision" not in prompt
    assert "expected_decision_rationale" not in prompt
    assert "scoring_notes" not in prompt
    assert f"Expected decision: {case['expected_decision']}" not in prompt
    assert "The expected benchmark decision is intentionally not provided" in prompt
    assert "GMV, CTR, CVR, ROI" in prompt


def test_copy_upload_fixtures_writes_case_file_and_referenced_samples(tmp_path):
    case_path = REPO_ROOT / "evals/opensku/cases/opensku-softlaunch-001.json"
    case = json.loads(case_path.read_text(encoding="utf-8"))

    uploaded = copy_upload_fixtures(tmp_path, case=case)
    uploaded_names = {item["name"] for item in uploaded}

    assert "opensku-case.json" in uploaded_names
    assert "opensku-case-brief.json" in uploaded_names
    assert "olist.jsonl" in uploaded_names
    assert (tmp_path / "opensku-case.json").exists()
    assert "expected_decision" not in (tmp_path / "opensku-case.json").read_text(encoding="utf-8")


def test_plan_batch_cases_selects_one_case_per_stage():
    planned = plan_batch_cases(
        cases_dir=REPO_ROOT / "evals/opensku/cases",
        case_ids=[],
        stages=["idea_only", "supplier_sample", "pre_launch_test", "soft_launch", "scale_iterate"],
        max_cases=5,
    )

    assert [case["stage"] for case in planned] == [
        "idea_only",
        "supplier_sample",
        "pre_launch_test",
        "soft_launch",
        "scale_iterate",
    ]
    assert [case["case_id"] for case in planned] == [
        "opensku-idea-001",
        "opensku-supplier-001",
        "opensku-prelaunch-001",
        "opensku-softlaunch-001",
        "opensku-scale-001",
    ]


def test_build_live_command_includes_case_file_and_batch_case_id():
    case_path = REPO_ROOT / "evals/opensku/cases/opensku-idea-001.json"
    case = json.loads(case_path.read_text(encoding="utf-8"))
    command = build_live_command(
        case=case,
        case_path=case_path,
        date="2026-06-27",
        timeout_seconds=123,
        reasoning_effort="low",
        case_id_prefix="batch",
        knowledge_dir=None,
    )

    assert command[:5] == ["uv", "run", "--project", "backend", "python"]
    assert "--case-id" in command
    assert "batch-opensku-idea-001" in command
    assert "--case-file" in command
    assert str(case_path) in command
    assert "--timeout-seconds" in command
    assert "123" in command


def test_build_live_command_passes_knowledge_dir_when_enabled():
    case_path = REPO_ROOT / "evals/opensku/cases/opensku-idea-001.json"
    case = json.loads(case_path.read_text(encoding="utf-8"))
    command = build_live_command(
        case=case,
        case_path=case_path,
        date="2026-06-27",
        timeout_seconds=123,
        reasoning_effort="low",
        case_id_prefix="batch",
        knowledge_dir=Path("docs/knowledge/opensku"),
    )

    assert "--knowledge-dir" in command
    assert command[command.index("--knowledge-dir") + 1] == "docs/knowledge/opensku"


def test_run_batch_with_fake_executor_writes_report(tmp_path):
    config = BatchConfig(
        cases_dir=REPO_ROOT / "evals/opensku/cases",
        date="2026-06-27",
        case_ids=["opensku-idea-001"],
        stages=[],
        max_cases=None,
        timeout_seconds=30,
        reasoning_effort="low",
        case_id_prefix="fake-batch",
        report_name="fake-report",
        reports_root=tmp_path / "reports",
        runs_root=tmp_path / "runs",
        plan_only=False,
    )

    def fake_executor(command: list[str]) -> int:
        case_id = command[command.index("--case-id") + 1]
        run_dir = config.runs_root / config.date / case_id
        _write_passing_run(run_dir)
        return 0

    result = run_batch(config, executor=fake_executor)

    assert result.status == "PASS"
    assert result.planned_case_ids == ["opensku-idea-001"]
    assert result.report_dir == tmp_path / "reports/fake-report"
    assert (result.report_dir / "summary.md").exists()
    assert "LIVE_VALIDATION_PASSED" in (result.report_dir / "batch-summary.md").read_text(encoding="utf-8")


def test_plan_only_batch_writes_plan_without_missing_run_failures(tmp_path):
    config = BatchConfig(
        cases_dir=REPO_ROOT / "evals/opensku/cases",
        date="2026-06-27",
        case_ids=["opensku-idea-001"],
        stages=[],
        max_cases=None,
        timeout_seconds=30,
        reasoning_effort="low",
        case_id_prefix="planned",
        report_name="plan-report",
        reports_root=tmp_path / "reports",
        runs_root=tmp_path / "runs",
        plan_only=True,
    )

    def unexpected_executor(command: list[str]) -> int:
        raise AssertionError(f"plan-only batch should not execute: {command}")

    result = run_batch(config, executor=unexpected_executor)

    assert result.status == "PLAN"
    assert result.records[0].score_status == "PLAN"
    assert result.records[0].score == 0
    assert result.records[0].max_score == 0
    assert "LIVE_BATCH_PLAN_READY" in (result.report_dir / "batch-summary.md").read_text(encoding="utf-8")
    scores = json.loads((result.report_dir / "scores.json").read_text(encoding="utf-8"))
    assert scores["status"] == "PASS"
    assert [item["name"] for item in scores["results"]] == ["case-suite"]


def test_score_existing_batch_reuses_run_evidence_without_execution(tmp_path):
    config = BatchConfig(
        cases_dir=REPO_ROOT / "evals/opensku/cases",
        date="2026-06-27",
        case_ids=["opensku-idea-001"],
        stages=[],
        max_cases=None,
        timeout_seconds=30,
        reasoning_effort="low",
        case_id_prefix="existing-batch",
        report_name="existing-report",
        reports_root=tmp_path / "reports",
        runs_root=tmp_path / "runs",
        plan_only=False,
        score_existing=True,
    )
    _write_passing_run(config.runs_root / config.date / "existing-batch-opensku-idea-001")

    def unexpected_executor(command: list[str]) -> int:
        raise AssertionError(f"score-existing batch should not execute: {command}")

    result = run_batch(config, executor=unexpected_executor)

    assert result.status == "PASS"
    assert result.records[0].exit_code is None
    assert result.records[0].score_status == "PASS"
    assert "existing" in (result.report_dir / "batch-summary.md").read_text(encoding="utf-8")
    scores = json.loads((result.report_dir / "scores.json").read_text(encoding="utf-8"))
    assert scores["status"] == "PASS"
    assert [item["name"] for item in scores["results"]] == ["case-suite", "live-run"]


def _write_passing_run(run_dir: Path) -> None:
    from backend.tests.test_opensku_scoring import _complete_final_response, _write_minimal_outputs, _write_run_evidence

    outputs = _write_minimal_outputs(run_dir / "user-data" / "outputs")
    _write_run_evidence(
        run_dir,
        outputs_dir=outputs,
        tool_call_names=["read_file", *["task"] * 5, "write_opensku_artifact_bundle", "present_files"],
        present_files_called=True,
        status="PASS",
        run_status="success",
        final_response=_complete_final_response(evidence_count=5),
    )
