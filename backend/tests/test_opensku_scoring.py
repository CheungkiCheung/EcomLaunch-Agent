from __future__ import annotations

import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from evals.opensku.scoring import (  # noqa: E402
    REQUIRED_ECOM_ROLES,
    score_artifact_bundle,
    score_case_suite,
    score_expected_decision,
    score_live_run,
    write_benchmark_report,
)
from evals.opensku.validators.core import REQUIRED_ARTIFACTS  # noqa: E402


def test_score_case_suite_accepts_generated_benchmark_cases():
    result = score_case_suite(REPO_ROOT / "evals/opensku/cases")

    assert result.status == "PASS"
    assert result.score == result.max_score == 20
    assert result.check("case_validation").passed is True
    assert result.check("stage_coverage").passed is True
    assert result.check("tag_traps").passed is True


def test_score_artifact_bundle_passes_golden_and_fails_broken_fixture():
    golden = score_artifact_bundle(REPO_ROOT / "evals/opensku/fixtures/golden/golden-001")
    broken = score_artifact_bundle(REPO_ROOT / "evals/opensku/fixtures/broken/broken-003")

    assert golden.status == "PASS"
    assert golden.score == golden.max_score == 40
    assert golden.check("artifact_validator").passed is True

    assert broken.status == "FAIL"
    assert broken.score < broken.max_score
    assert broken.check("artifact_validator").passed is False
    assert any("private metric" in detail for detail in broken.check("artifact_validator").details)


def test_score_live_run_accepts_complete_realistic_evidence(tmp_path):
    outputs_dir = _write_minimal_outputs(tmp_path / "outputs")
    run_dir = _write_run_evidence(
        tmp_path / "run",
        outputs_dir=outputs_dir,
        tool_call_names=["read_file", *["task"] * 5, "write_opensku_artifact_bundle", "present_files"],
        present_files_called=True,
        status="PASS",
        run_status="success",
        final_response=_complete_final_response(evidence_count=5),
    )

    result = score_live_run(run_dir)

    assert result.status == "PASS"
    assert result.score == result.max_score == 40
    assert result.check("artifact_writer_called").passed is True
    assert result.check("final_response").passed is True


def test_score_live_run_rejects_missing_writer_tool(tmp_path):
    outputs_dir = _write_minimal_outputs(tmp_path / "outputs")
    run_dir = _write_run_evidence(
        tmp_path / "run",
        outputs_dir=outputs_dir,
        tool_call_names=["read_file", *["task"] * 5, "present_files"],
        present_files_called=True,
        status="PASS",
        run_status="success",
        final_response=_complete_final_response(evidence_count=5),
    )

    result = score_live_run(run_dir)

    assert result.status == "FAIL"
    assert result.check("artifact_writer_called").passed is False
    assert result.score < result.max_score


def test_score_expected_decision_accepts_matching_launch_state(tmp_path):
    outputs_dir = _write_minimal_outputs(tmp_path / "outputs")
    _write_launch_state(outputs_dir, decision="Pivot")
    run_dir = _write_run_evidence(
        tmp_path / "live-knowledge-injection-prelaunch-002",
        outputs_dir=outputs_dir,
        tool_call_names=["write_opensku_artifact_bundle", "present_files"],
        present_files_called=True,
        status="PASS",
        run_status="success",
        final_response=_complete_final_response(evidence_count=5),
    )

    result = score_expected_decision(run_dir, cases_dir=REPO_ROOT / "evals/opensku/cases")

    assert result.status == "PASS"
    assert result.score == result.max_score == 10
    assert result.check("decision_match").passed is True
    assert "expected=Pivot" in result.check("decision_match").details
    assert "actual=Pivot" in result.check("decision_match").details


def test_score_expected_decision_rejects_mismatched_launch_state(tmp_path):
    outputs_dir = _write_minimal_outputs(tmp_path / "outputs")
    _write_launch_state(outputs_dir, decision="Kill")
    run_dir = _write_run_evidence(
        tmp_path / "live-knowledge-injection-prelaunch-002",
        outputs_dir=outputs_dir,
        tool_call_names=["write_opensku_artifact_bundle", "present_files"],
        present_files_called=True,
        status="PASS",
        run_status="success",
        final_response=_complete_final_response(evidence_count=5),
    )

    result = score_expected_decision(run_dir, cases_dir=REPO_ROOT / "evals/opensku/cases")

    assert result.status == "FAIL"
    assert result.score == 5
    assert result.check("decision_match").passed is False
    assert "expected=Pivot" in result.check("decision_match").details
    assert "actual=Kill" in result.check("decision_match").details


def test_score_expected_decision_fails_when_case_cannot_be_inferred(tmp_path):
    outputs_dir = _write_minimal_outputs(tmp_path / "outputs")
    _write_launch_state(outputs_dir, decision="Hold")
    run_dir = _write_run_evidence(
        tmp_path / "live-knowledge-injection-unknown",
        outputs_dir=outputs_dir,
        tool_call_names=["write_opensku_artifact_bundle", "present_files"],
        present_files_called=True,
        status="PASS",
        run_status="success",
        final_response=_complete_final_response(evidence_count=5),
    )

    result = score_expected_decision(run_dir, cases_dir=REPO_ROOT / "evals/opensku/cases")

    assert result.status == "FAIL"
    assert result.check("case_resolution").passed is False


def test_write_benchmark_report_creates_summary_scores_and_failures(tmp_path):
    cases = score_case_suite(REPO_ROOT / "evals/opensku/cases")
    golden = score_artifact_bundle(REPO_ROOT / "evals/opensku/fixtures/golden/golden-001")
    broken = score_artifact_bundle(REPO_ROOT / "evals/opensku/fixtures/broken/broken-003")

    report_dir = write_benchmark_report(
        output_root=tmp_path / "reports",
        results=[cases, golden, broken],
        report_name="test-report",
    )

    assert (report_dir / "summary.md").exists()
    assert (report_dir / "scores.json").exists()
    assert (report_dir / "failures.md").exists()

    scores = json.loads((report_dir / "scores.json").read_text(encoding="utf-8"))
    assert scores["status"] == "FAIL"
    assert scores["results"][0]["name"] == "case-suite"
    assert any(result["status"] == "FAIL" for result in scores["results"])
    assert "broken-003" in (report_dir / "failures.md").read_text(encoding="utf-8")


def _write_minimal_outputs(outputs_dir: Path) -> Path:
    from backend.tests.test_opensku_artifact_writer_tool import _runtime_for_thread_data
    from deerflow.tools.builtins.opensku_artifact_writer import write_opensku_artifact_bundle_tool

    uploads_dir = outputs_dir.parent / "uploads"
    runtime = _runtime_for_thread_data(outputs_path=outputs_dir, uploads_path=uploads_dir)
    result = write_opensku_artifact_bundle_tool.func(
        runtime=runtime,
        case_id="opensku-scoring-test-001",
        stage="idea_only",
        decision="Hold",
        product_name="Portable coffee tumbler",
        data_limitations="No merchant backend metrics are available.",
    )
    assert "status=PASS" in result
    return outputs_dir


def _write_launch_state(outputs_dir: Path, *, decision: str) -> None:
    path = outputs_dir / "launch-state.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["decision"] = decision
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_run_evidence(
    run_dir: Path,
    *,
    outputs_dir: Path,
    tool_call_names: list[str],
    present_files_called: bool,
    status: str,
    run_status: str,
    final_response: str,
) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    artifacts = [
        {
            "name": artifact,
            "host_path": str(outputs_dir / artifact),
            "virtual_path": f"/mnt/user-data/outputs/{artifact}",
            "size_bytes": (outputs_dir / artifact).stat().st_size,
            "sha256": "test",
        }
        for artifact in REQUIRED_ARTIFACTS
    ]
    manifest = {
        "present_files_called": present_files_called,
        "tool_call_names": tool_call_names,
        "subagent_types": sorted(REQUIRED_ECOM_ROLES),
        "outputs_dir": str(outputs_dir),
        "artifacts": artifacts,
        "state_artifacts": [artifact["virtual_path"] for artifact in artifacts],
    }
    (run_dir / "artifacts-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (run_dir / "validator-output.txt").write_text(
        f"bundle={outputs_dir}\nartifact_count=10\nstatus=PASS\n",
        encoding="utf-8",
    )
    (run_dir / "final-response.md").write_text(final_response, encoding="utf-8")
    (run_dir / "run-log.md").write_text(
        f"# OpenSKU Live Agent Run\n\nStatus: {status}\n\n- run_status: {run_status}\n- external_search_tool_calls: []\n",
        encoding="utf-8",
    )
    return run_dir


def _complete_final_response(*, evidence_count: int) -> str:
    artifact_lines = "\n".join(f"- `{artifact}`" for artifact in REQUIRED_ARTIFACTS)
    return f"""## 验证完成

上新阶段 Stage: idea_only
当前决策 Decision: Hold
下一循环: 7天验证冲刺，测试两个标题钩子。
推广调整: 暂停放量，先做样本反馈。
数据限制: GMV/CTR/CVR/ROI 不可用。

`evidence-ledger.json` 包含 {evidence_count} 条证据条目。

Artifact list:
{artifact_lines}
"""
