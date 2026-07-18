#!/usr/bin/env python3
"""Validate OpenSKU-Bench cases."""

from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CASES_DIR = REPO_ROOT / "evals/opensku/cases"

ALLOWED_STAGES = {
    "idea_only",
    "supplier_sample",
    "pre_launch_test",
    "soft_launch",
    "scale_iterate",
}
ALLOWED_DECISIONS = {"Go", "Pivot", "Hold", "Kill", "Scale"}
REQUIRED_FIELDS = {
    "case_id",
    "stage",
    "category",
    "brief",
    "public_context",
    "uploaded_real",
    "expected_decision",
    "expected_decision_rationale",
    "required_artifacts",
    "required_claims",
    "forbidden_claims",
    "scoring_notes",
    "source_dataset",
    "evaluation_tags",
}
TARGET_STAGE_COUNTS = {
    "idea_only": 6,
    "supplier_sample": 6,
    "pre_launch_test": 6,
    "soft_launch": 8,
    "scale_iterate": 4,
}
MIN_TAG_COUNTS = {
    "uploaded_data_simulation": 10,
    "public_signal_context": 10,
    "forbidden_metric_trap": 5,
    "unsupported_claim_trap": 5,
}
ALLOWED_SOURCE_TYPES = {
    "public_benchmark_fixture",
    "public_fixture_as_uploaded_simulation",
}


@dataclass
class ValidationResult:
    case_count: int
    stage_counts: dict[str, int]
    tag_counts: dict[str, int]
    errors: list[str]


def load_cases(cases_dir: Path = DEFAULT_CASES_DIR) -> list[tuple[Path, dict[str, Any]]]:
    if not cases_dir.exists():
        return []
    cases = []
    for path in sorted(cases_dir.glob("*.json")):
        try:
            cases.append((path, json.loads(path.read_text(encoding="utf-8"))))
        except json.JSONDecodeError as exc:
            cases.append((path, {"__json_error__": str(exc)}))
    return cases


def validate_case(case: dict[str, Any], path: Path) -> list[str]:
    errors: list[str] = []
    if "__json_error__" in case:
        return [f"{path}: invalid JSON: {case['__json_error__']}"]

    missing = sorted(REQUIRED_FIELDS - set(case))
    if missing:
        errors.append(f"{path}: missing required fields: {', '.join(missing)}")
        return errors

    if case["stage"] not in ALLOWED_STAGES:
        errors.append(f"{path}: invalid stage {case['stage']!r}")
    if case["expected_decision"] not in ALLOWED_DECISIONS:
        errors.append(f"{path}: invalid expected_decision {case['expected_decision']!r}")

    for field in ["case_id", "category", "brief", "expected_decision_rationale"]:
        if not isinstance(case[field], str) or not case[field].strip():
            errors.append(f"{path}: {field} must be a non-empty string")

    if len(case["expected_decision_rationale"].strip()) < 20:
        errors.append(f"{path}: expected_decision_rationale is too short")

    for field in [
        "public_context",
        "uploaded_real",
        "required_artifacts",
        "required_claims",
        "forbidden_claims",
        "source_dataset",
        "evaluation_tags",
    ]:
        if not isinstance(case[field], list):
            errors.append(f"{path}: {field} must be a list")

    if isinstance(case["source_dataset"], list) and not case["source_dataset"]:
        errors.append(f"{path}: source_dataset must not be empty")
    if isinstance(case["required_artifacts"], list) and not case["required_artifacts"]:
        errors.append(f"{path}: required_artifacts must not be empty")
    if not isinstance(case["scoring_notes"], dict):
        errors.append(f"{path}: scoring_notes must be an object")

    for context_field in ["public_context", "uploaded_real"]:
        contexts = case[context_field]
        if not isinstance(contexts, list):
            continue
        for index, context in enumerate(contexts):
            if not isinstance(context, dict):
                errors.append(f"{path}: {context_field}[{index}] must be an object")
                continue
            for required in ["source_type", "dataset", "component", "sample_file", "row_index", "fields"]:
                if required not in context:
                    errors.append(f"{path}: {context_field}[{index}] missing {required}")
            if context.get("source_type") not in ALLOWED_SOURCE_TYPES:
                errors.append(
                    f"{path}: {context_field}[{index}] has invalid source_type {context.get('source_type')!r}"
                )
            sample_file = context.get("sample_file")
            if isinstance(sample_file, str) and not (REPO_ROOT / sample_file).exists():
                errors.append(f"{path}: referenced sample file does not exist: {sample_file}")

    if case["stage"] in {"soft_launch", "scale_iterate"}:
        artifacts = set(case["required_artifacts"])
        for artifact in ["launch-state.json", "promotion-replan.md", "knowledge-deltas.json"]:
            if artifact not in artifacts:
                errors.append(f"{path}: {case['stage']} case must require {artifact}")

    return errors


def validate_cases(cases_dir: Path = DEFAULT_CASES_DIR) -> ValidationResult:
    loaded_cases = load_cases(cases_dir)
    errors: list[str] = []
    stage_counter: Counter[str] = Counter()
    tag_counter: Counter[str] = Counter()
    seen_case_ids: set[str] = set()

    for path, case in loaded_cases:
        errors.extend(validate_case(case, path))
        case_id = case.get("case_id")
        if isinstance(case_id, str):
            if case_id in seen_case_ids:
                errors.append(f"{path}: duplicate case_id {case_id}")
            seen_case_ids.add(case_id)
        if isinstance(case.get("stage"), str):
            stage_counter[case["stage"]] += 1
        if isinstance(case.get("evaluation_tags"), list):
            tag_counter.update(str(tag) for tag in case["evaluation_tags"])

    if len(loaded_cases) != 30:
        errors.append(f"suite: expected 30 cases, found {len(loaded_cases)}")
    if dict(stage_counter) != TARGET_STAGE_COUNTS:
        errors.append(f"suite: expected stage counts {TARGET_STAGE_COUNTS}, found {dict(stage_counter)}")
    for tag, minimum in MIN_TAG_COUNTS.items():
        if tag_counter[tag] < minimum:
            errors.append(f"suite: expected at least {minimum} cases tagged {tag}, found {tag_counter[tag]}")

    return ValidationResult(
        case_count=len(loaded_cases),
        stage_counts={stage: stage_counter.get(stage, 0) for stage in TARGET_STAGE_COUNTS},
        tag_counts=dict(tag_counter),
        errors=errors,
    )


def main() -> int:
    result = validate_cases()
    print(f"case_count={result.case_count}")
    print(f"stage_counts={result.stage_counts}")
    print(f"tag_counts={result.tag_counts}")
    if result.errors:
        print("VALIDATION FAILED")
        for error in result.errors:
            print(f"- {error}")
        return 1
    print("VALIDATION PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

