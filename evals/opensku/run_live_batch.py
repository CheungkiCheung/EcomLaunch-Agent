#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Any


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from evals.opensku.scoring import CheckResult, ScoreResult, score_case_suite, score_live_run, write_benchmark_report
from evals.opensku.validate_cases import load_cases


STAGE_ORDER = [
    "idea_only",
    "supplier_sample",
    "pre_launch_test",
    "soft_launch",
    "scale_iterate",
]


Executor = Callable[[list[str]], int]


@dataclass(frozen=True)
class BatchConfig:
    cases_dir: Path
    date: str
    case_ids: list[str]
    stages: list[str]
    max_cases: int | None
    timeout_seconds: float
    reasoning_effort: str
    case_id_prefix: str
    report_name: str
    reports_root: Path
    runs_root: Path
    plan_only: bool = False
    score_existing: bool = False
    knowledge_dir: Path | None = None


@dataclass(frozen=True)
class BatchRunRecord:
    case_id: str
    live_case_id: str
    stage: str
    command: list[str]
    exit_code: int | None
    run_dir: Path
    score_status: str
    score: int
    max_score: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "live_case_id": self.live_case_id,
            "stage": self.stage,
            "command": self.command,
            "exit_code": self.exit_code,
            "run_dir": str(self.run_dir),
            "score_status": self.score_status,
            "score": self.score,
            "max_score": self.max_score,
        }


@dataclass(frozen=True)
class BatchResult:
    status: str
    planned_case_ids: list[str]
    report_dir: Path
    records: list[BatchRunRecord]


def plan_batch_cases(
    *,
    cases_dir: Path,
    case_ids: list[str],
    stages: list[str],
    max_cases: int | None,
) -> list[dict[str, Any]]:
    loaded = [(path, case) for path, case in load_cases(cases_dir) if isinstance(case.get("case_id"), str)]
    by_id = {case["case_id"]: (path, case) for path, case in loaded}

    selected: list[tuple[Path, dict[str, Any]]] = []
    if case_ids:
        missing = [case_id for case_id in case_ids if case_id not in by_id]
        if missing:
            raise ValueError(f"unknown case ids: {', '.join(missing)}")
        selected = [by_id[case_id] for case_id in case_ids]
    elif stages:
        for stage in stages:
            first = next(((path, case) for path, case in loaded if case.get("stage") == stage), None)
            if first is None:
                raise ValueError(f"no case found for stage: {stage}")
            selected.append(first)
    else:
        selected = sorted(loaded, key=lambda item: (_stage_sort_key(item[1]), item[1]["case_id"]))

    if max_cases is not None:
        selected = selected[:max_cases]

    planned: list[dict[str, Any]] = []
    for path, case in selected:
        planned_case = dict(case)
        planned_case["__case_path__"] = str(path)
        planned.append(planned_case)
    return planned


def build_live_command(
    *,
    case: dict[str, Any],
    case_path: Path,
    date: str,
    timeout_seconds: float,
    reasoning_effort: str,
    case_id_prefix: str,
    knowledge_dir: Path | None = None,
) -> list[str]:
    live_case_id = f"{case_id_prefix}-{case['case_id']}" if case_id_prefix else str(case["case_id"])
    command = [
        "uv",
        "run",
        "--project",
        "backend",
        "python",
        "evals/opensku/run_live_agent_validation.py",
        "--case-id",
        live_case_id,
        "--case-file",
        str(case_path),
        "--date",
        date,
        "--timeout-seconds",
        _format_seconds(timeout_seconds),
        "--reasoning-effort",
        reasoning_effort,
    ]
    if knowledge_dir is not None:
        command.extend(["--knowledge-dir", str(knowledge_dir)])
    return command


def run_batch(config: BatchConfig, *, executor: Executor | None = None) -> BatchResult:
    executor = executor or _default_executor
    planned_cases = plan_batch_cases(
        cases_dir=config.cases_dir,
        case_ids=config.case_ids,
        stages=config.stages,
        max_cases=config.max_cases,
    )
    records: list[BatchRunRecord] = []
    score_results: list[ScoreResult] = [score_case_suite(config.cases_dir)]

    for case in planned_cases:
        case_path = Path(str(case["__case_path__"]))
        command = build_live_command(
            case=case,
            case_path=case_path,
            date=config.date,
            timeout_seconds=config.timeout_seconds,
            reasoning_effort=config.reasoning_effort,
            case_id_prefix=config.case_id_prefix,
            knowledge_dir=config.knowledge_dir,
        )
        live_case_id = command[command.index("--case-id") + 1]
        run_dir = config.runs_root / config.date / live_case_id
        exit_code: int | None = None
        if config.plan_only:
            live_score_status = "PLAN"
            live_score = 0
            live_max_score = 0
        elif config.score_existing:
            if run_dir.exists():
                scored_live_run = score_live_run(run_dir)
            else:
                scored_live_run = _missing_run_score(run_dir)
            score_results.append(scored_live_run)
            live_score_status = scored_live_run.status
            live_score = scored_live_run.score
            live_max_score = scored_live_run.max_score
        else:
            exit_code = executor(command)
            if run_dir.exists():
                scored_live_run = score_live_run(run_dir)
            else:
                scored_live_run = _missing_run_score(run_dir)
            score_results.append(scored_live_run)
            live_score_status = scored_live_run.status
            live_score = scored_live_run.score
            live_max_score = scored_live_run.max_score

        records.append(
            BatchRunRecord(
                case_id=str(case["case_id"]),
                live_case_id=live_case_id,
                stage=str(case.get("stage", "")),
                command=command,
                exit_code=exit_code,
                run_dir=run_dir,
                score_status=live_score_status,
                score=live_score,
                max_score=live_max_score,
            )
        )

    report_dir = write_benchmark_report(
        output_root=config.reports_root,
        results=score_results,
        report_name=config.report_name,
    )
    _write_batch_summary(report_dir, config, records)
    status = "PASS" if records and all(record.exit_code in {0, None} for record in records) and all(record.score_status == "PASS" for record in records) else "FAIL"
    if config.plan_only:
        status = "PLAN"
    return BatchResult(
        status=status,
        planned_case_ids=[str(case["case_id"]) for case in planned_cases],
        report_dir=report_dir,
        records=records,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run OpenSKU live validations across benchmark cases.")
    parser.add_argument("--cases-dir", type=Path, default=Path("evals/opensku/cases"))
    parser.add_argument("--case-id", action="append", dest="case_ids", default=[])
    parser.add_argument("--stage", action="append", dest="stages", default=[])
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument("--date", default="2026-06-27")
    parser.add_argument("--timeout-seconds", type=float, default=600.0)
    parser.add_argument("--reasoning-effort", choices=["low", "medium", "high"], default="medium")
    parser.add_argument("--case-id-prefix", default="batch")
    parser.add_argument("--report-name", default="opensku-live-batch")
    parser.add_argument("--reports-root", type=Path, default=Path("evals/opensku/reports"))
    parser.add_argument("--runs-root", type=Path, default=Path("docs/progress/runs"))
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--score-existing", action="store_true", help="Do not execute live runs; score existing run evidence for the selected cases and prefix.")
    parser.add_argument("--knowledge-dir", type=Path, default=None, help="Optional OpenSKU knowledge directory to pass through to live validation.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = BatchConfig(
        cases_dir=args.cases_dir,
        date=args.date,
        case_ids=args.case_ids,
        stages=args.stages,
        max_cases=args.max_cases,
        timeout_seconds=args.timeout_seconds,
        reasoning_effort=args.reasoning_effort,
        case_id_prefix=args.case_id_prefix,
        report_name=args.report_name,
        reports_root=args.reports_root,
        runs_root=args.runs_root,
        plan_only=args.plan_only,
        score_existing=args.score_existing,
        knowledge_dir=args.knowledge_dir,
    )
    result = run_batch(config)
    print(f"report_dir={result.report_dir}")
    print(f"status={result.status}")
    print(f"planned_case_ids={result.planned_case_ids}")
    return 0 if result.status in {"PASS", "PLAN"} else 1


def _default_executor(command: list[str]) -> int:
    completed = subprocess.run(command, cwd=REPO_ROOT, check=False)
    return completed.returncode


def _stage_sort_key(case: dict[str, Any]) -> tuple[int, str]:
    stage = str(case.get("stage", ""))
    try:
        stage_index = STAGE_ORDER.index(stage)
    except ValueError:
        stage_index = len(STAGE_ORDER)
    return stage_index, str(case.get("case_id", ""))


def _format_seconds(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


def _missing_run_score(run_dir: Path) -> ScoreResult:
    return ScoreResult(
        "live-run",
        str(run_dir),
        [
            CheckResult(
                "run_evidence_exists",
                False,
                0,
                40,
                [f"run directory does not exist: {run_dir}"],
            )
        ],
    )


def _write_batch_summary(report_dir: Path, config: BatchConfig, records: list[BatchRunRecord]) -> None:
    payload = {
        "status": "PLAN" if config.plan_only else ("PASS" if all(record.score_status == "PASS" and record.exit_code in {0, None} for record in records) else "FAIL"),
        "date": config.date,
        "case_id_prefix": config.case_id_prefix,
        "timeout_seconds": config.timeout_seconds,
        "reasoning_effort": config.reasoning_effort,
        "plan_only": config.plan_only,
        "score_existing": config.score_existing,
        "records": [record.to_dict() for record in records],
    }
    (report_dir / "batch-records.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# OpenSKU Live Batch Summary",
        "",
        f"Status: {payload['status']}",
        f"Cases: {len(records)}",
        "",
        "| Case | Live Case | Stage | Exit | Score | Status |",
        "|---|---|---|---:|---:|---|",
    ]
    for record in records:
        if config.plan_only:
            exit_text = "plan"
        elif config.score_existing and record.exit_code is None:
            exit_text = "existing"
        else:
            exit_text = str(record.exit_code)
        lines.append(
            f"| `{record.case_id}` | `{record.live_case_id}` | {record.stage} | {exit_text} | {record.score}/{record.max_score} | {record.score_status} |"
        )
    if records and all(record.score_status == "PASS" and record.exit_code in {0, None} for record in records):
        lines.append("")
        lines.append("LIVE_VALIDATION_PASSED")
    elif config.plan_only:
        lines.append("")
        lines.append("LIVE_BATCH_PLAN_READY")
    else:
        lines.append("")
        lines.append("LIVE_VALIDATION_FAILED")
    lines.append("")
    (report_dir / "batch-summary.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
