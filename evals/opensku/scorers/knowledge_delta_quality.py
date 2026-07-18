#!/usr/bin/env python3
"""Deterministic quality checks for the OpenSKU knowledge base."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from evals.opensku.scoring import CheckResult, ScoreResult
from scripts.opensku.ingest_knowledge_deltas import (
    PRIVATE_METRICS,
    SAFE_BOUNDARY_WORDS,
    VALID_MATURITIES,
    VALID_TYPES,
)


REQUIRED_RECORD_FIELDS = {
    "id",
    "type",
    "maturity",
    "scope",
    "statement",
    "source_case_id",
    "source_run_id",
    "source_run_dir",
    "evidence_ids",
}


def score_knowledge_base(
    knowledge_dir: Path,
    *,
    min_records: int = 20,
    min_reused_patterns: int = 5,
) -> ScoreResult:
    records, parse_errors = load_records(knowledge_dir / "knowledge-deltas.jsonl")
    patterns_payload, pattern_errors = load_patterns(knowledge_dir / "patterns.json")
    patterns = patterns_payload.get("patterns", []) if isinstance(patterns_payload, dict) else []

    field_errors = validate_required_fields(records)
    source_errors = validate_sources(records)
    private_metric_errors = validate_private_metric_boundary(records)
    reused_patterns = [
        pattern
        for pattern in patterns
        if isinstance(pattern, dict) and int(pattern.get("occurrence_count") or 0) > 1
    ]
    min_record_errors = (
        []
        if len(records) >= min_records
        else [f"record_count={len(records)} below min_records={min_records}"]
    )
    reuse_errors = (
        []
        if len(reused_patterns) >= min_reused_patterns
        else [
            f"reused_pattern_count={len(reused_patterns)} below min_reused_patterns={min_reused_patterns}"
        ]
    )

    checks = [
        CheckResult(
            "parseability",
            not parse_errors and not pattern_errors,
            10 if not parse_errors and not pattern_errors else 0,
            10,
            [*parse_errors, *pattern_errors],
        ),
        CheckResult(
            "record_count",
            not min_record_errors,
            10 if not min_record_errors else 0,
            10,
            [f"record_count={len(records)}", *min_record_errors],
        ),
        CheckResult(
            "required_fields",
            not field_errors,
            10 if not field_errors else 0,
            10,
            field_errors,
        ),
        CheckResult(
            "source_links",
            not source_errors,
            10 if not source_errors else 0,
            10,
            source_errors,
        ),
        CheckResult(
            "private_metric_boundary",
            not private_metric_errors,
            10 if not private_metric_errors else 0,
            10,
            private_metric_errors,
        ),
        CheckResult(
            "reuse_patterns",
            not reuse_errors,
            10 if not reuse_errors else 0,
            10,
            [
                f"reused_pattern_count={len(reused_patterns)}",
                f"pattern_count={len(patterns)}",
                *reuse_errors,
            ],
        ),
    ]
    return ScoreResult("knowledge-delta-quality", str(knowledge_dir), checks)


def load_records(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return [], [f"{path}: missing knowledge-deltas.jsonl"]
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{path}:{line_number}: JSON parse error: {exc}")
            continue
        if not isinstance(record, dict):
            errors.append(f"{path}:{line_number}: record must be a JSON object")
            continue
        records.append(record)
    return records, errors


def load_patterns(path: Path) -> tuple[dict[str, Any], list[str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}, [f"{path}: missing patterns.json"]
    except json.JSONDecodeError as exc:
        return {}, [f"{path}: JSON parse error: {exc}"]
    if not isinstance(payload, dict):
        return {}, [f"{path}: patterns.json must be a JSON object"]
    if not isinstance(payload.get("patterns"), list):
        return {}, [f"{path}: patterns must be a JSON array"]
    return payload, []


def validate_required_fields(records: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for record in records:
        missing = sorted(field for field in REQUIRED_RECORD_FIELDS if not record.get(field))
        if missing:
            errors.append(f"{record.get('id') or '<missing id>'}: missing fields {missing}")
        if record.get("type") not in VALID_TYPES:
            errors.append(f"{record.get('id')}: invalid type {record.get('type')}")
        if record.get("maturity") not in VALID_MATURITIES:
            errors.append(f"{record.get('id')}: invalid maturity {record.get('maturity')}")
        if not isinstance(record.get("evidence_ids"), list):
            errors.append(f"{record.get('id')}: evidence_ids must be an array")
    return errors


def validate_sources(records: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for record in records:
        if not str(record.get("source_case_id") or "").strip():
            errors.append(f"{record.get('id')}: source_case_id is required")
        if not str(record.get("source_run_id") or "").strip():
            errors.append(f"{record.get('id')}: source_run_id is required")
        if not str(record.get("source_run_dir") or "").strip():
            errors.append(f"{record.get('id')}: source_run_dir is required")
    return errors


def validate_private_metric_boundary(records: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for record in records:
        statement = str(record.get("statement") or "")
        lower = statement.lower()
        metric = next((metric for metric in PRIVATE_METRICS if metric in lower), None)
        if metric and not any(word in lower for word in SAFE_BOUNDARY_WORDS):
            errors.append(
                f"{record.get('id')}: private metric '{metric.upper()}' is not framed as unavailable or future data"
            )
    return errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--knowledge", type=Path, required=True)
    parser.add_argument("--min-records", type=int, default=20)
    parser.add_argument("--min-reused-patterns", type=int, default=5)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = score_knowledge_base(
        args.knowledge,
        min_records=args.min_records,
        min_reused_patterns=args.min_reused_patterns,
    )
    print(f"subject={result.subject}")
    print(f"status={result.status}")
    print(f"score={result.score}/{result.max_score}")
    for check in result.checks:
        print(
            f"{check.name}: {'PASS' if check.passed else 'FAIL'} "
            f"{check.score}/{check.max_score}"
        )
        for detail in check.details:
            print(f"  - {detail}")
    return 0 if result.status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
