from __future__ import annotations

import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "backend" / "tests"))

from evals.opensku.release_candidate_gate import (  # noqa: E402
    load_release_candidate_config,
    score_release_candidate,
    score_release_candidate_config,
    write_release_candidate_report,
)
from test_opensku_scoring import (  # noqa: E402
    _complete_final_response,
    _write_launch_state,
    _write_minimal_outputs,
    _write_run_evidence,
)


def test_release_candidate_config_requires_declared_stage_coverage(tmp_path):
    run_dirs = _make_run_dirs(tmp_path, count=10)
    candidate_path = tmp_path / "rc.json"
    candidate_path.write_text(
        json.dumps(
            {
                "name": "test-rc",
                "cases_dir": str(REPO_ROOT / "evals/opensku/cases"),
                "decision_gate": True,
                "acceptance": {
                    "min_live_runs": 10,
                    "required_stage_counts": {
                        "idea_only": 2,
                        "supplier_sample": 2,
                        "pre_launch_test": 2,
                        "soft_launch": 2,
                        "scale_iterate": 2,
                    },
                },
                "live_runs": [
                    {"case_id": "opensku-idea-001", "stage": "idea_only", "run_dir": str(run_dirs[0])},
                    {"case_id": "opensku-idea-002", "stage": "idea_only", "run_dir": str(run_dirs[1])},
                    {"case_id": "opensku-supplier-001", "stage": "supplier_sample", "run_dir": str(run_dirs[2])},
                    {"case_id": "opensku-supplier-002", "stage": "supplier_sample", "run_dir": str(run_dirs[3])},
                    {"case_id": "opensku-prelaunch-001", "stage": "pre_launch_test", "run_dir": str(run_dirs[4])},
                    {"case_id": "opensku-prelaunch-002", "stage": "pre_launch_test", "run_dir": str(run_dirs[5])},
                    {"case_id": "opensku-softlaunch-001", "stage": "soft_launch", "run_dir": str(run_dirs[6])},
                    {"case_id": "opensku-softlaunch-002", "stage": "soft_launch", "run_dir": str(run_dirs[7])},
                    {"case_id": "opensku-scale-001", "stage": "scale_iterate", "run_dir": str(run_dirs[8])},
                    {"case_id": "opensku-scale-002", "stage": "scale_iterate", "run_dir": str(run_dirs[9])},
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    config = load_release_candidate_config(candidate_path)
    result = score_release_candidate_config(config)

    assert result.status == "PASS"
    assert result.score == result.max_score == 10
    assert result.check("live_run_count").passed is True
    assert result.check("stage_coverage").passed is True
    assert result.check("run_paths").passed is True
    assert result.check("case_files").passed is True


def test_release_candidate_scoring_adds_expected_decision_gate_for_each_live_run(tmp_path):
    outputs_dir = _write_minimal_outputs(tmp_path / "outputs")
    _write_launch_state(outputs_dir, decision="Pivot")
    run_dir = _write_run_evidence(
        tmp_path / "live-decision-taxonomy-prelaunch-002",
        outputs_dir=outputs_dir,
        tool_call_names=["read_file", "task", "write_opensku_artifact_bundle", "present_files"],
        present_files_called=True,
        status="PASS",
        run_status="success",
        final_response=_complete_final_response(evidence_count=5).replace(
            "当前决策 Decision: Hold",
            "当前决策 Decision: Pivot",
        ),
    )
    candidate_path = tmp_path / "rc.json"
    candidate_path.write_text(
        json.dumps(
            {
                "name": "single-prelaunch-rc",
                "cases_dir": str(REPO_ROOT / "evals/opensku/cases"),
                "decision_gate": True,
                "acceptance": {
                    "min_live_runs": 1,
                    "required_stage_counts": {"pre_launch_test": 1},
                },
                "live_runs": [
                    {
                        "case_id": "opensku-prelaunch-002",
                        "stage": "pre_launch_test",
                        "run_dir": str(run_dir),
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    config = load_release_candidate_config(candidate_path)
    results = score_release_candidate(config)
    report_dir = write_release_candidate_report(
        output_root=tmp_path / "reports",
        results=results,
        report_name="single-prelaunch-rc",
    )

    assert [result.name for result in results] == [
        "release-candidate-config",
        "case-suite",
        "live-run",
        "expected-decision",
    ]
    assert all(result.status == "PASS" for result in results)
    scores = json.loads((report_dir / "scores.json").read_text(encoding="utf-8"))
    assert scores["status"] == "PASS"
    assert scores["score"] == scores["max_score"] == 80


def _make_run_dirs(tmp_path: Path, *, count: int) -> list[Path]:
    run_dirs = []
    for index in range(count):
        run_dir = tmp_path / f"run-{index:02d}"
        run_dir.mkdir()
        run_dirs.append(run_dir)
    return run_dirs
