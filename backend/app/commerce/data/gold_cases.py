"""Load and verify disk-isolated Commerce Gold Case bundles."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from app.commerce.domain.evaluation import EvaluationCase, ExpectedBehavior, InputBundle


class GoldCaseIntegrityError(ValueError):
    """Raised when an evaluation fixture no longer matches its manifest."""


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GoldCaseIntegrityError(f"Cannot load Gold Case file: {path}") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_input_files(case_dir: Path, input_bundle: InputBundle) -> None:
    resolved_root = case_dir.resolve()
    for file in input_bundle.files:
        path = (case_dir / file.relative_path).resolve()
        if not path.is_relative_to(resolved_root):
            raise GoldCaseIntegrityError(f"Input file escapes case directory: {file.relative_path}")
        if not path.is_file():
            raise GoldCaseIntegrityError(f"Missing Gold Case input file: {file.relative_path}")
        if _sha256(path) != file.sha256:
            raise GoldCaseIntegrityError(f"SHA-256 mismatch for {file.relative_path}")

        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = sum(1 for _ in reader)
            columns = tuple(reader.fieldnames or ())
        if rows != file.row_count:
            raise GoldCaseIntegrityError(f"Row-count mismatch for {file.relative_path}: {rows} != {file.row_count}")
        if columns != file.columns:
            raise GoldCaseIntegrityError(f"Column mismatch for {file.relative_path}: {columns} != {file.columns}")


def load_evaluation_case(case_dir: Path, *, verify_files: bool = True) -> EvaluationCase:
    """Load metadata, Agent-visible input, and evaluator-only labels separately."""

    metadata = _load_json(case_dir / "case-metadata.json")
    input_bundle = InputBundle.model_validate(_load_json(case_dir / "input-bundle.json"))
    expected_behavior = ExpectedBehavior.model_validate(_load_json(case_dir / "expected-behavior.json"))

    if verify_files:
        _verify_input_files(case_dir, input_bundle)

    return EvaluationCase.model_validate(
        {
            **metadata,
            "input_bundle": input_bundle,
            "expected_behavior": expected_behavior,
        }
    )
