from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REQUIRED_ARTIFACTS = [
    "launch-war-room.html",
    "evidence-ledger.json",
    "competitor-table.csv",
    "positioning-brief.md",
    "listing-pack.md",
    "content-pack.md",
    "launch-calendar.csv",
    "launch-state.json",
    "promotion-replan.md",
    "knowledge-deltas.json",
]

EVIDENCE_TYPES = {
    "observed_public",
    "uploaded_real",
    "estimated",
    "unavailable",
    "assumption",
}

KNOWLEDGE_TYPES = {
    "decision",
    "guideline",
    "pitfall",
    "process",
    "model",
}

KNOWLEDGE_MATURITY = {
    "draft",
    "verified",
    "proven",
}

PRIVATE_METRICS = {
    "gmv",
    "ctr",
    "cvr",
    "roi",
    "cac",
    "ad spend",
    "margin",
    "refund rate",
    "repeat purchase rate",
    "verified uplift",
    "live inventory",
    "live ranking",
}

UNSUPPORTED_CLAIM_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\bFDA approved\b",
        r"\bclinically proven\b",
        r"\b100% safe\b",
        r"\bcertified organic\b",
        r"\blifetime warranty\b",
        r"\bguaranteed (?:results|conversion|sales|ranking)\b",
    ]
]

EVIDENCE_ID_RE = re.compile(r"\bEVID-[A-Z0-9-]+\b")


@dataclass
class ArtifactBundleResult:
    bundle_path: Path
    artifact_count: int
    errors: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass
class FixtureCollectionResult:
    root: Path
    bundle_count: int
    passed_count: int
    failed_count: int
    results: list[ArtifactBundleResult]


def validate_artifact_bundle(bundle_path: Path) -> ArtifactBundleResult:
    errors: list[str] = []
    if not bundle_path.exists():
        return ArtifactBundleResult(bundle_path, 0, [f"{bundle_path}: fixture directory does not exist"])
    if not bundle_path.is_dir():
        return ArtifactBundleResult(bundle_path, 0, [f"{bundle_path}: expected a directory"])

    artifact_count = len([path for path in bundle_path.iterdir() if path.is_file()])
    for artifact in REQUIRED_ARTIFACTS:
        if not (bundle_path / artifact).exists():
            errors.append(f"{bundle_path}: missing required artifact {artifact}")

    ledger_items, ledger_ids, has_uploaded_real, ledger_errors = validate_evidence_ledger(
        bundle_path / "evidence-ledger.json"
    )
    errors.extend(ledger_errors)

    validators = [
        validate_competitor_table,
        validate_positioning_brief,
        validate_listing_pack,
        validate_content_pack,
        validate_launch_calendar,
        validate_launch_state,
        validate_promotion_replan,
        validate_knowledge_deltas,
        validate_launch_war_room,
    ]
    for validator in validators:
        errors.extend(validator(bundle_path, ledger_ids, has_uploaded_real))

    errors.extend(validate_evidence_references(bundle_path, ledger_ids))
    return ArtifactBundleResult(bundle_path, artifact_count, errors)


def validate_fixture_collection(root: Path) -> FixtureCollectionResult:
    bundle_paths = sorted(path for path in root.iterdir() if path.is_dir()) if root.exists() else []
    results = [validate_artifact_bundle(path) for path in bundle_paths]
    passed_count = sum(1 for result in results if result.ok)
    failed_count = len(results) - passed_count
    return FixtureCollectionResult(root, len(results), passed_count, failed_count, results)


def validate_evidence_ledger(path: Path) -> tuple[list[dict[str, Any]], set[str], bool, list[str]]:
    errors: list[str] = []
    ledger_ids: set[str] = set()
    has_uploaded_real = False
    if not path.exists():
        return [], ledger_ids, has_uploaded_real, [f"{path}: missing evidence-ledger.json"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [], ledger_ids, has_uploaded_real, [f"{path}: evidence-ledger.json is not parseable JSON: {exc}"]
    if not isinstance(data, list):
        return [], ledger_ids, has_uploaded_real, [f"{path}: evidence-ledger.json must be a JSON array"]

    for index, item in enumerate(data):
        if not isinstance(item, dict):
            errors.append(f"{path}: evidence item {index} must be an object")
            continue
        evidence_id = item.get("id")
        if not isinstance(evidence_id, str) or not evidence_id.strip():
            errors.append(f"{path}: evidence item {index} missing id")
        elif evidence_id in ledger_ids:
            errors.append(f"{path}: duplicate evidence id {evidence_id}")
        else:
            ledger_ids.add(evidence_id)

        evidence_type = item.get("evidence_type")
        if evidence_type not in EVIDENCE_TYPES:
            errors.append(f"{path}: evidence item {index} invalid evidence_type {evidence_type!r}")
        if "source_type" not in item or not str(item.get("source_type")).strip():
            errors.append(f"{path}: evidence item {index} missing source_type")
        if "confidence" not in item or not str(item.get("confidence")).strip():
            errors.append(f"{path}: evidence item {index} missing confidence")
        if evidence_type == "uploaded_real":
            has_uploaded_real = True

        metric = str(item.get("metric", "")).strip().lower()
        if metric in PRIVATE_METRICS and evidence_type not in {"uploaded_real", "unavailable"}:
            errors.append(
                f"{path}: evidence item {index} treats private metric {metric!r} as {evidence_type}; "
                "private metric must be uploaded_real or unavailable"
            )

    return data, ledger_ids, has_uploaded_real, errors


def validate_competitor_table(bundle_path: Path, ledger_ids: set[str], has_uploaded_real: bool) -> list[str]:
    path = bundle_path / "competitor-table.csv"
    if not path.exists():
        return []
    required = {"competitor", "observed_claim", "evidence_id", "confidence", "limitation"}
    errors, rows = read_csv_with_required_columns(path, required)
    for row_index, row in enumerate(rows, start=2):
        evidence_id = row.get("evidence_id", "")
        if evidence_id and evidence_id not in ledger_ids:
            errors.append(f"{path}: row {row_index} references unknown evidence id {evidence_id}")
    return errors


def validate_launch_calendar(bundle_path: Path, ledger_ids: set[str], has_uploaded_real: bool) -> list[str]:
    path = bundle_path / "launch-calendar.csv"
    if not path.exists():
        return []
    required = {
        "day",
        "objective",
        "experiment",
        "asset",
        "channel",
        "validation_signal_to_collect",
        "decision_rule",
        "owner",
        "expected_output",
    }
    errors, rows = read_csv_with_required_columns(path, required)
    for row_index, row in enumerate(rows, start=2):
        if not row.get("decision_rule", "").strip():
            errors.append(f"{path}: row {row_index} decision_rule must not be empty")
        signal = row.get("validation_signal_to_collect", "")
        if not has_uploaded_real and contains_private_metric(signal):
            errors.append(
                f"{path}: row {row_index} uses private metric validation signal without uploaded_real evidence"
            )
    return errors


def validate_positioning_brief(bundle_path: Path, ledger_ids: set[str], has_uploaded_real: bool) -> list[str]:
    path = bundle_path / "positioning-brief.md"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    if "Decision:" not in text:
        errors.append(f"{path}: positioning brief must include Decision:")
    if "Evidence limitations:" not in text:
        errors.append(f"{path}: positioning brief must include Evidence limitations:")
    errors.extend(validate_markdown_claim_safety(path, text))
    return errors


def validate_listing_pack(bundle_path: Path, ledger_ids: set[str], has_uploaded_real: bool) -> list[str]:
    path = bundle_path / "listing-pack.md"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    if "Claim readiness:" not in text:
        errors.append(f"{path}: listing-pack.md must include Claim readiness labels")
    errors.extend(validate_markdown_claim_safety(path, text))
    return errors


def validate_content_pack(bundle_path: Path, ledger_ids: set[str], has_uploaded_real: bool) -> list[str]:
    path = bundle_path / "content-pack.md"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    if "Claim readiness:" not in text:
        errors.append(f"{path}: content-pack.md must include Claim readiness labels")
    errors.extend(validate_markdown_claim_safety(path, text))
    return errors


def validate_launch_state(bundle_path: Path, ledger_ids: set[str], has_uploaded_real: bool) -> list[str]:
    path = bundle_path / "launch-state.json"
    if not path.exists():
        return []
    errors: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"{path}: launch-state.json is not parseable JSON: {exc}"]
    if not isinstance(data, dict):
        return [f"{path}: launch-state.json must be an object"]
    for field in ["stage", "decision", "evidence_ids"]:
        if field not in data:
            errors.append(f"{path}: launch-state.json missing {field}")
    for evidence_id in data.get("evidence_ids", []):
        if evidence_id not in ledger_ids:
            errors.append(f"{path}: launch-state references unknown evidence id {evidence_id}")
    return errors


def validate_promotion_replan(bundle_path: Path, ledger_ids: set[str], has_uploaded_real: bool) -> list[str]:
    path = bundle_path / "promotion-replan.md"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8").lower()
    errors: list[str] = []
    for section in ["observed signal", "interpretation", "plan change", "next test", "stop/continue rule"]:
        if section not in text:
            errors.append(f"{path}: promotion-replan.md missing section {section!r}")
    return errors


def validate_knowledge_deltas(bundle_path: Path, ledger_ids: set[str], has_uploaded_real: bool) -> list[str]:
    path = bundle_path / "knowledge-deltas.json"
    if not path.exists():
        return []
    errors: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"{path}: knowledge-deltas.json is not parseable JSON: {exc}"]
    if not isinstance(data, list):
        return [f"{path}: knowledge-deltas.json must be a JSON array"]
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            errors.append(f"{path}: knowledge delta {index} must be an object")
            continue
        if item.get("type") not in KNOWLEDGE_TYPES:
            errors.append(f"{path}: knowledge delta {index} invalid type {item.get('type')!r}")
        if item.get("maturity") not in KNOWLEDGE_MATURITY:
            errors.append(f"{path}: knowledge delta {index} invalid maturity {item.get('maturity')!r}")
        if not item.get("source_case_id") and not item.get("source_run_id"):
            errors.append(f"{path}: knowledge delta {index} missing source_case_id or source_run_id")
    return errors


def validate_launch_war_room(bundle_path: Path, ledger_ids: set[str], has_uploaded_real: bool) -> list[str]:
    path = bundle_path / "launch-war-room.html"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    if "<html" not in text.lower() or "</html>" not in text.lower():
        return [f"{path}: launch-war-room.html must be an HTML document"]
    return []


def validate_evidence_references(bundle_path: Path, ledger_ids: set[str]) -> list[str]:
    errors: list[str] = []
    for path in bundle_path.iterdir():
        if not path.is_file() or path.name == "evidence-ledger.json":
            continue
        if path.suffix.lower() not in {".md", ".csv", ".json", ".html"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for evidence_id in EVIDENCE_ID_RE.findall(text):
            if evidence_id not in ledger_ids:
                errors.append(f"{path}: references unknown evidence id {evidence_id}")
    return errors


def validate_markdown_claim_safety(path: Path, text: str) -> list[str]:
    errors: list[str] = []
    for pattern in UNSUPPORTED_CLAIM_PATTERNS:
        if pattern.search(text):
            errors.append(f"{path}: contains unsupported claim pattern {pattern.pattern!r}")
    lower_text = text.lower()
    if contains_private_metric(lower_text) and "unavailable" not in lower_text and "do not" not in lower_text:
        errors.append(f"{path}: contains private metric claim without unavailable/do-not boundary")
    return errors


def contains_private_metric(text: str) -> bool:
    lower_text = text.lower()
    return any(metric in lower_text for metric in PRIVATE_METRICS)


def read_csv_with_required_columns(path: Path, required: set[str]) -> tuple[list[str], list[dict[str, str]]]:
    errors: list[str] = []
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = set(reader.fieldnames or [])
            missing = sorted(required - fieldnames)
            if missing:
                errors.append(f"{path}: missing CSV columns: {', '.join(missing)}")
                return errors, []
            rows = list(reader)
    except csv.Error as exc:
        return [f"{path}: CSV parse error: {exc}"], []
    if not rows:
        errors.append(f"{path}: CSV must contain at least one data row")
    return errors, rows

