from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from evals.opensku.run_live_agent_validation import (
    EXTERNAL_SEARCH_TOOLS,
    final_response_consistency_errors,
    missing_final_response_requirements,
)
from evals.opensku.validate_cases import MIN_TAG_COUNTS, TARGET_STAGE_COUNTS, validate_cases
from evals.opensku.validators.core import REQUIRED_ARTIFACTS, validate_artifact_bundle


REQUIRED_ECOM_ROLES = {
    "market-voc-researcher",
    "offer-architect",
    "growth-analyst",
    "asset-studio",
    "evidence-checker",
}
ARTIFACT_WRITER_TOOL = "write_opensku_artifact_bundle"


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    score: int
    max_score: int
    details: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "score": self.score,
            "max_score": self.max_score,
            "details": self.details,
        }


@dataclass(frozen=True)
class ScoreResult:
    name: str
    subject: str
    checks: list[CheckResult]

    @property
    def score(self) -> int:
        return sum(check.score for check in self.checks)

    @property
    def max_score(self) -> int:
        return sum(check.max_score for check in self.checks)

    @property
    def status(self) -> str:
        return "PASS" if all(check.passed for check in self.checks) else "FAIL"

    @property
    def score_ratio(self) -> float:
        return self.score / self.max_score if self.max_score else 0.0

    def check(self, name: str) -> CheckResult:
        for check in self.checks:
            if check.name == name:
                return check
        raise KeyError(name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "subject": self.subject,
            "status": self.status,
            "score": self.score,
            "max_score": self.max_score,
            "score_ratio": round(self.score_ratio, 4),
            "checks": [check.to_dict() for check in self.checks],
        }


def score_case_suite(cases_dir: Path) -> ScoreResult:
    validation = validate_cases(cases_dir)
    case_validation_passed = not validation.errors
    case_count_passed = validation.case_count == 30
    stage_coverage_passed = validation.stage_counts == TARGET_STAGE_COUNTS
    tag_traps_passed = all(validation.tag_counts.get(tag, 0) >= minimum for tag, minimum in MIN_TAG_COUNTS.items())
    source_reference_errors = [
        error
        for error in validation.errors
        if "referenced sample file" in error or "source_dataset" in error or "source_type" in error
    ]
    source_references_passed = not source_reference_errors

    checks = [
        CheckResult(
            "case_validation",
            case_validation_passed,
            8 if case_validation_passed else 0,
            8,
            validation.errors,
        ),
        CheckResult(
            "case_count",
            case_count_passed,
            3 if case_count_passed else 0,
            3,
            [f"case_count={validation.case_count}"],
        ),
        CheckResult(
            "stage_coverage",
            stage_coverage_passed,
            3 if stage_coverage_passed else 0,
            3,
            [f"stage_counts={validation.stage_counts}", f"target={TARGET_STAGE_COUNTS}"],
        ),
        CheckResult(
            "tag_traps",
            tag_traps_passed,
            4 if tag_traps_passed else 0,
            4,
            [f"tag_counts={validation.tag_counts}", f"minimums={MIN_TAG_COUNTS}"],
        ),
        CheckResult(
            "source_references",
            source_references_passed,
            2 if source_references_passed else 0,
            2,
            source_reference_errors,
        ),
    ]
    return ScoreResult("case-suite", str(cases_dir), checks)


def score_artifact_bundle(bundle_path: Path) -> ScoreResult:
    validation = validate_artifact_bundle(bundle_path)
    existing_artifacts = {path.name for path in bundle_path.iterdir() if path.is_file()} if bundle_path.exists() else set()
    required_present = sorted(set(REQUIRED_ARTIFACTS) & existing_artifacts)
    missing_required = sorted(set(REQUIRED_ARTIFACTS) - existing_artifacts)
    loop_artifacts = {"launch-state.json", "promotion-replan.md", "knowledge-deltas.json"}
    missing_loop_artifacts = sorted(loop_artifacts - existing_artifacts)
    private_metric_errors = [error for error in validation.errors if "private metric" in error.lower()]
    ledger_errors = [error for error in validation.errors if "evidence-ledger.json" in error]
    evidence_boundary_errors = _dedupe([*private_metric_errors, *ledger_errors])

    artifact_coverage_score = int(5 * len(required_present) / len(REQUIRED_ARTIFACTS))
    checks = [
        CheckResult(
            "artifact_validator",
            validation.ok,
            25 if validation.ok else 0,
            25,
            validation.errors,
        ),
        CheckResult(
            "required_artifacts",
            not missing_required,
            5 if not missing_required else artifact_coverage_score,
            5,
            [f"present={required_present}", f"missing={missing_required}"],
        ),
        CheckResult(
            "evidence_boundary",
            not evidence_boundary_errors,
            5 if not evidence_boundary_errors else 0,
            5,
            evidence_boundary_errors,
        ),
        CheckResult(
            "loop_artifacts",
            not missing_loop_artifacts,
            5 if not missing_loop_artifacts else int(5 * (len(loop_artifacts) - len(missing_loop_artifacts)) / len(loop_artifacts)),
            5,
            [f"missing={missing_loop_artifacts}"],
        ),
    ]
    return ScoreResult("artifact-bundle", str(bundle_path), checks)


def score_live_run(run_dir: Path, *, outputs_dir: Path | None = None) -> ScoreResult:
    manifest = _load_json(run_dir / "artifacts-manifest.json")
    validator_output = _read_text(run_dir / "validator-output.txt")
    final_response = _read_text(run_dir / "final-response.md")
    run_log = _read_text(run_dir / "run-log.md")

    tool_call_names = _string_list(manifest.get("tool_call_names"))
    subagent_types = set(_string_list(manifest.get("subagent_types")))
    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), list) else []
    artifact_names = {
        item.get("name")
        for item in artifacts
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    state_artifacts = _string_list(manifest.get("state_artifacts"))
    output_path = outputs_dir or _manifest_outputs_dir(manifest)
    if output_path is not None and not output_path.exists():
        output_path = None

    run_status_passed = _run_log_has_pass_status(run_log)
    present_files_passed = bool(manifest.get("present_files_called")) and bool(state_artifacts)
    missing_subagents = sorted(REQUIRED_ECOM_ROLES - subagent_types)
    writer_called = ARTIFACT_WRITER_TOOL in tool_call_names
    external_search_calls = sorted(name for name in tool_call_names if name in EXTERNAL_SEARCH_TOOLS)
    missing_artifacts = sorted(set(REQUIRED_ARTIFACTS) - artifact_names)
    validator_passed = "status=PASS" in validator_output
    final_missing = missing_final_response_requirements(final_response)
    final_errors = final_response_consistency_errors(final_response, output_path) if output_path else []
    final_response_passed = not final_missing and not final_errors

    checks = [
        CheckResult(
            "run_status",
            run_status_passed,
            5 if run_status_passed else 0,
            5,
            [line for line in run_log.splitlines() if "Status:" in line or "run_status:" in line],
        ),
        CheckResult(
            "present_files",
            present_files_passed,
            5 if present_files_passed else 0,
            5,
            [f"present_files_called={manifest.get('present_files_called')}", f"state_artifacts={state_artifacts}"],
        ),
        CheckResult(
            "subagents",
            not missing_subagents,
            5 if not missing_subagents else 0,
            5,
            [f"observed={sorted(subagent_types)}", f"missing={missing_subagents}"],
        ),
        CheckResult(
            "artifact_writer_called",
            writer_called,
            5 if writer_called else 0,
            5,
            [f"tool_call_names={tool_call_names}"],
        ),
        CheckResult(
            "external_search_gate",
            not external_search_calls,
            5 if not external_search_calls else 0,
            5,
            [f"external_search_calls={external_search_calls}"],
        ),
        CheckResult(
            "artifact_manifest",
            not missing_artifacts,
            5 if not missing_artifacts else int(5 * (len(REQUIRED_ARTIFACTS) - len(missing_artifacts)) / len(REQUIRED_ARTIFACTS)),
            5,
            [f"artifacts={sorted(artifact_names)}", f"missing={missing_artifacts}"],
        ),
        CheckResult(
            "validator_output",
            validator_passed,
            5 if validator_passed else 0,
            5,
            validator_output.splitlines(),
        ),
        CheckResult(
            "final_response",
            final_response_passed,
            5 if final_response_passed else 0,
            5,
            [f"missing_requirements={final_missing}", f"consistency_errors={final_errors}"],
        ),
    ]
    return ScoreResult("live-run", str(run_dir), checks)


def score_expected_decision(run_dir: Path, *, cases_dir: Path) -> ScoreResult:
    manifest = _load_json(run_dir / "artifacts-manifest.json")
    case_path, case_payload, case_candidates = _resolve_expected_case(
        run_dir,
        manifest=manifest,
        cases_dir=cases_dir,
    )
    expected_decision = _normalize_decision(str(case_payload.get("expected_decision") or ""))
    actual_decision = _actual_decision_for_run(run_dir, manifest)
    case_resolution_passed = bool(case_path and expected_decision)
    decision_match_passed = bool(
        case_resolution_passed
        and actual_decision
        and actual_decision == expected_decision
    )

    checks = [
        CheckResult(
            "case_resolution",
            case_resolution_passed,
            5 if case_resolution_passed else 0,
            5,
            [
                f"case_path={case_path}" if case_path else "case_path=<unresolved>",
                f"case_candidates={case_candidates}",
                f"expected={_display_decision(expected_decision)}",
            ],
        ),
        CheckResult(
            "decision_match",
            decision_match_passed,
            5 if decision_match_passed else 0,
            5,
            [
                f"expected={_display_decision(expected_decision)}",
                f"actual={_display_decision(actual_decision)}",
            ],
        ),
    ]
    return ScoreResult("expected-decision", str(run_dir), checks)


def write_benchmark_report(
    *,
    output_root: Path,
    results: list[ScoreResult],
    report_name: str | None = None,
) -> Path:
    report_id = report_name or datetime.now().strftime("%Y%m%d-%H%M%S")
    report_dir = output_root / report_id
    report_dir.mkdir(parents=True, exist_ok=True)

    total_score = sum(result.score for result in results)
    total_max_score = sum(result.max_score for result in results)
    status = "PASS" if results and all(result.status == "PASS" for result in results) else "FAIL"
    payload = {
        "status": status,
        "score": total_score,
        "max_score": total_max_score,
        "score_ratio": round(total_score / total_max_score, 4) if total_max_score else 0.0,
        "results": [result.to_dict() for result in results],
    }
    (report_dir / "scores.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (report_dir / "summary.md").write_text(_render_summary(payload), encoding="utf-8")
    (report_dir / "failures.md").write_text(_render_failures(results), encoding="utf-8")
    return report_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Score OpenSKU-Bench cases, artifact bundles, and live-run evidence.")
    parser.add_argument("--cases-dir", type=Path, default=Path("evals/opensku/cases"))
    parser.add_argument("--artifact-bundle", type=Path, action="append", default=[])
    parser.add_argument("--live-run", type=Path, action="append", default=[])
    parser.add_argument(
        "--decision-gate",
        action="store_true",
        help="For each --live-run, add an expected-decision check inferred from --cases-dir.",
    )
    parser.add_argument("--output-root", type=Path, default=Path("evals/opensku/reports"))
    parser.add_argument("--report-name", default=None)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    results = [score_case_suite(args.cases_dir)]
    results.extend(score_artifact_bundle(path) for path in args.artifact_bundle)
    for path in args.live_run:
        results.append(score_live_run(path))
        if args.decision_gate:
            results.append(score_expected_decision(path, cases_dir=args.cases_dir))
    report_dir = write_benchmark_report(output_root=args.output_root, results=results, report_name=args.report_name)
    overall_status = "PASS" if all(result.status == "PASS" for result in results) else "FAIL"
    total_score = sum(result.score for result in results)
    total_max = sum(result.max_score for result in results)
    print(f"report_dir={report_dir}")
    print(f"status={overall_status}")
    print(f"score={total_score}/{total_max}")
    return 0 if overall_status == "PASS" else 1


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _string_list(value: Any) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _manifest_outputs_dir(manifest: dict[str, Any]) -> Path | None:
    raw_outputs_dir = manifest.get("outputs_dir")
    return Path(raw_outputs_dir) if isinstance(raw_outputs_dir, str) and raw_outputs_dir else None


def _run_log_has_pass_status(run_log: str) -> bool:
    return bool(re.search(r"^Status:\s*PASS\b", run_log, re.MULTILINE)) and "run_status: success" in run_log


def _resolve_expected_case(
    run_dir: Path,
    *,
    manifest: dict[str, Any],
    cases_dir: Path,
) -> tuple[Path | None, dict[str, Any], list[str]]:
    candidates = _case_id_candidates(run_dir, manifest)
    for candidate in candidates:
        path = cases_dir / f"{candidate}.json"
        if path.exists():
            return path, _load_json(path), candidates
    return None, {}, candidates


def _case_id_candidates(run_dir: Path, manifest: dict[str, Any]) -> list[str]:
    raw_values = [
        str(manifest.get("benchmark_case_id") or ""),
        str(manifest.get("source_case_id") or ""),
        str(manifest.get("case_id") or ""),
        run_dir.name,
    ]
    candidates: list[str] = []
    for value in raw_values:
        candidates.extend(_case_ids_from_text(value))
    return _dedupe(candidates)


def _case_ids_from_text(text: str) -> list[str]:
    lower = text.lower()
    candidates = re.findall(r"opensku-(?:idea|supplier|prelaunch|softlaunch|scale)-\d+", lower)
    aliases = {
        "idea": "idea",
        "supplier": "supplier",
        "prelaunch": "prelaunch",
        "pre_launch": "prelaunch",
        "softlaunch": "softlaunch",
        "soft_launch": "softlaunch",
        "scale": "scale",
    }
    for alias, case_prefix in aliases.items():
        for match in re.finditer(rf"\b{re.escape(alias)}-(\d+)\b", lower):
            candidates.append(f"opensku-{case_prefix}-{match.group(1)}")
    return candidates


def _actual_decision_for_run(run_dir: Path, manifest: dict[str, Any]) -> str:
    outputs_dir = _manifest_outputs_dir(manifest)
    candidate_paths = []
    if outputs_dir is not None:
        candidate_paths.append(outputs_dir / "launch-state.json")
    candidate_paths.append(run_dir / "launch-state.json")
    for path in candidate_paths:
        state = _load_json(path)
        decision = _normalize_decision(str(state.get("decision") or ""))
        if decision:
            return decision
    return _decision_from_text(_read_text(run_dir / "final-response.md"))


def _decision_from_text(text: str) -> str:
    match = re.search(r"\b(go|pivot|hold|kill|scale)\b", text, re.I)
    return _normalize_decision(match.group(1)) if match else ""


def _normalize_decision(value: str) -> str:
    match = re.search(r"\b(go|pivot|hold|kill|scale)\b", value, re.I)
    return match.group(1).lower() if match else ""


def _display_decision(value: str) -> str:
    return {
        "go": "Go",
        "pivot": "Pivot",
        "hold": "Hold",
        "kill": "Kill",
        "scale": "Scale",
    }.get(value, "<missing>")


def _render_summary(payload: dict[str, Any]) -> str:
    lines = [
        "# OpenSKU-Bench Score Summary",
        "",
        f"Status: {payload['status']}",
        f"Score: {payload['score']}/{payload['max_score']}",
        "",
        "| Result | Subject | Status | Score |",
        "|---|---|---|---|",
    ]
    for result in payload["results"]:
        lines.append(
            f"| {result['name']} | `{result['subject']}` | {result['status']} | {result['score']}/{result['max_score']} |"
        )
    lines.append("")
    return "\n".join(lines)


def _render_failures(results: list[ScoreResult]) -> str:
    lines = ["# OpenSKU-Bench Failures", ""]
    failed_any = False
    for result in results:
        failed_checks = [check for check in result.checks if not check.passed]
        if not failed_checks:
            continue
        failed_any = True
        lines.append(f"## {result.name}: `{result.subject}`")
        lines.append("")
        for check in failed_checks:
            lines.append(f"- `{check.name}` scored {check.score}/{check.max_score}")
            for detail in check.details:
                lines.append(f"  - {detail}")
        lines.append("")
    if not failed_any:
        lines.append("No failures.")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
