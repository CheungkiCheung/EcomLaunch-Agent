from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evals.opensku.scoring import (
    CheckResult,
    ScoreResult,
    score_case_suite,
    score_expected_decision,
    score_live_run,
    write_benchmark_report,
)


DEFAULT_REQUIRED_STAGE_COUNTS = {
    "idea_only": 1,
    "supplier_sample": 1,
    "pre_launch_test": 1,
    "soft_launch": 1,
    "scale_iterate": 1,
}


@dataclass(frozen=True)
class ReleaseCandidateRun:
    case_id: str
    stage: str
    run_dir: Path
    note: str = ""


@dataclass(frozen=True)
class ReleaseCandidateConfig:
    name: str
    cases_dir: Path
    live_runs: list[ReleaseCandidateRun]
    decision_gate: bool
    min_live_runs: int
    required_stage_counts: dict[str, int]
    source_path: Path
    description: str = ""


def load_release_candidate_config(path: Path) -> ReleaseCandidateConfig:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"release candidate config must be a JSON object: {path}")

    acceptance = payload.get("acceptance") if isinstance(payload.get("acceptance"), dict) else {}
    required_stage_counts = acceptance.get("required_stage_counts", DEFAULT_REQUIRED_STAGE_COUNTS)
    if not isinstance(required_stage_counts, dict):
        raise ValueError("acceptance.required_stage_counts must be an object")

    live_runs_payload = payload.get("live_runs")
    if not isinstance(live_runs_payload, list):
        raise ValueError("live_runs must be a list")

    live_runs = []
    for index, item in enumerate(live_runs_payload):
        if not isinstance(item, dict):
            raise ValueError(f"live_runs[{index}] must be an object")
        live_runs.append(
            ReleaseCandidateRun(
                case_id=str(item.get("case_id") or ""),
                stage=str(item.get("stage") or ""),
                run_dir=Path(str(item.get("run_dir") or "")),
                note=str(item.get("note") or ""),
            )
        )

    min_live_runs = acceptance.get("min_live_runs", sum(int(value) for value in required_stage_counts.values()))
    return ReleaseCandidateConfig(
        name=str(payload.get("name") or path.stem),
        description=str(payload.get("description") or ""),
        cases_dir=Path(str(payload.get("cases_dir") or "evals/opensku/cases")),
        live_runs=live_runs,
        decision_gate=bool(payload.get("decision_gate", True)),
        min_live_runs=int(min_live_runs),
        required_stage_counts={str(stage): int(count) for stage, count in required_stage_counts.items()},
        source_path=path,
    )


def score_release_candidate_config(config: ReleaseCandidateConfig) -> ScoreResult:
    stage_counts = Counter(run.stage for run in config.live_runs)
    missing_or_extra_stage_counts = []
    for stage, required_count in config.required_stage_counts.items():
        observed_count = stage_counts.get(stage, 0)
        if observed_count != required_count:
            missing_or_extra_stage_counts.append(f"{stage}: expected={required_count} observed={observed_count}")
    unexpected_stages = sorted(stage for stage in stage_counts if stage not in config.required_stage_counts)
    missing_run_paths = [str(run.run_dir) for run in config.live_runs if not run.run_dir.exists()]
    missing_case_files = [
        str(config.cases_dir / f"{run.case_id}.json")
        for run in config.live_runs
        if not (config.cases_dir / f"{run.case_id}.json").exists()
    ]
    duplicate_case_ids = sorted(
        case_id
        for case_id, count in Counter(run.case_id for run in config.live_runs).items()
        if case_id and count > 1
    )

    live_run_count_passed = len(config.live_runs) >= config.min_live_runs
    stage_coverage_passed = not missing_or_extra_stage_counts and not unexpected_stages
    run_paths_passed = not missing_run_paths
    case_files_passed = not missing_case_files
    unique_cases_passed = not duplicate_case_ids

    return ScoreResult(
        "release-candidate-config",
        str(config.source_path),
        [
            CheckResult(
                "live_run_count",
                live_run_count_passed,
                2 if live_run_count_passed else 0,
                2,
                [f"observed={len(config.live_runs)}", f"minimum={config.min_live_runs}"],
            ),
            CheckResult(
                "stage_coverage",
                stage_coverage_passed,
                3 if stage_coverage_passed else 0,
                3,
                [
                    f"observed={dict(stage_counts)}",
                    f"required={config.required_stage_counts}",
                    f"mismatches={missing_or_extra_stage_counts}",
                    f"unexpected={unexpected_stages}",
                ],
            ),
            CheckResult(
                "run_paths",
                run_paths_passed,
                2 if run_paths_passed else 0,
                2,
                [f"missing={missing_run_paths}"],
            ),
            CheckResult(
                "case_files",
                case_files_passed,
                2 if case_files_passed else 0,
                2,
                [f"missing={missing_case_files}"],
            ),
            CheckResult(
                "unique_cases",
                unique_cases_passed,
                1 if unique_cases_passed else 0,
                1,
                [f"duplicates={duplicate_case_ids}"],
            ),
        ],
    )


def score_release_candidate(
    config: ReleaseCandidateConfig,
    *,
    decision_gate: bool | None = None,
) -> list[ScoreResult]:
    use_decision_gate = config.decision_gate if decision_gate is None else decision_gate
    results = [
        score_release_candidate_config(config),
        score_case_suite(config.cases_dir),
    ]
    for run in config.live_runs:
        results.append(score_live_run(run.run_dir))
        if use_decision_gate:
            results.append(score_expected_decision(run.run_dir, cases_dir=config.cases_dir))
    return results


def write_release_candidate_report(
    *,
    output_root: Path,
    results: list[ScoreResult],
    report_name: str,
) -> Path:
    return write_benchmark_report(output_root=output_root, results=results, report_name=report_name)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run an OpenSKU release-candidate gate over selected live-run evidence.")
    parser.add_argument(
        "--candidate-file",
        type=Path,
        default=Path("evals/opensku/release_candidates/2026-06-27-rc1-five-stage.json"),
    )
    parser.add_argument("--output-root", type=Path, default=Path("evals/opensku/reports"))
    parser.add_argument("--report-name", default=None)
    parser.add_argument(
        "--no-decision-gate",
        action="store_true",
        help="Score runtime integrity only. Release-candidate checks should normally keep the decision gate enabled.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = load_release_candidate_config(args.candidate_file)
    results = score_release_candidate(config, decision_gate=False if args.no_decision_gate else None)
    report_name = args.report_name or config.name
    report_dir = write_release_candidate_report(
        output_root=args.output_root,
        results=results,
        report_name=report_name,
    )
    overall_status = "PASS" if all(result.status == "PASS" for result in results) else "FAIL"
    total_score = sum(result.score for result in results)
    total_max = sum(result.max_score for result in results)
    print(f"candidate={config.name}")
    print(f"candidate_file={config.source_path}")
    print(f"live_run_count={len(config.live_runs)}")
    print(f"decision_gate={config.decision_gate and not args.no_decision_gate}")
    print(f"report_dir={report_dir}")
    print(f"status={overall_status}")
    print(f"score={total_score}/{total_max}")
    return 0 if overall_status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
