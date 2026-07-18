#!/usr/bin/env python3
"""Ingest OpenSKU knowledge deltas from live run evidence.

The ingester reads accepted run directories, follows each
``artifacts-manifest.json`` to the real output bundle, and extracts
``knowledge-deltas.json`` into a durable local knowledge base.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_RUNS_ROOT = Path("docs/progress/runs")
DEFAULT_OUTPUT_DIR = Path("docs/knowledge/opensku")
VALID_TYPES = {"decision", "guideline", "pitfall", "process", "model"}
VALID_MATURITIES = {"draft", "verified", "proven"}
PRIVATE_METRICS = {
    "gmv",
    "ctr",
    "cvr",
    "roi",
    "cac",
    "ad spend",
    "sales volume",
    "refund rate",
    "repeat purchase",
    "margin",
    "verified uplift",
    "广告花费",
    "销售额",
    "退款率",
    "复购率",
    "真实提升",
}
SAFE_BOUNDARY_WORDS = {
    "unavailable",
    "missing",
    "not available",
    "do not",
    "cannot",
    "without",
    "until uploaded",
    "to collect",
    "不可用",
    "缺失",
    "不要",
    "不能",
    "未上传",
    "待收集",
}


@dataclass(frozen=True)
class KnowledgeIngestConfig:
    runs_root: Path = DEFAULT_RUNS_ROOT
    output_dir: Path = DEFAULT_OUTPUT_DIR
    require_pass: bool = True
    min_records: int = 0


@dataclass(frozen=True)
class KnowledgeIngestReport:
    status: str
    runs_root: str
    output_dir: str
    discovered_run_count: int
    accepted_run_count: int
    skipped_run_count: int
    record_count: int
    pattern_count: int
    errors: list[str]


def ingest_knowledge_deltas(config: KnowledgeIngestConfig) -> KnowledgeIngestReport:
    run_dirs = discover_run_dirs(config.runs_root)
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    accepted_run_count = 0
    skipped_run_count = 0

    for run_dir in run_dirs:
        if config.require_pass and not run_passed(run_dir):
            skipped_run_count += 1
            continue
        manifest = read_json(run_dir / "artifacts-manifest.json")
        if not isinstance(manifest, dict):
            skipped_run_count += 1
            errors.append(f"{run_dir}: artifacts-manifest.json is not a JSON object")
            continue
        deltas_path = knowledge_deltas_path(run_dir, manifest)
        if deltas_path is None:
            skipped_run_count += 1
            continue
        deltas = read_json(deltas_path)
        if not isinstance(deltas, list):
            skipped_run_count += 1
            errors.append(f"{deltas_path}: knowledge-deltas.json must be a JSON array")
            continue

        accepted_run_count += 1
        for index, item in enumerate(deltas, start=1):
            if not isinstance(item, dict):
                errors.append(f"{deltas_path}: item {index} must be a JSON object")
                continue
            normalized = normalize_delta(
                item,
                index=index,
                run_dir=run_dir,
                deltas_path=deltas_path,
                manifest=manifest,
            )
            item_errors = validate_record(normalized)
            if item_errors:
                errors.extend(f"{deltas_path}: item {index}: {error}" for error in item_errors)
                continue
            records.append(normalized)

    records = assign_ids(records)
    patterns = build_patterns(records)
    if config.min_records and len(records) < config.min_records:
        errors.append(
            f"record_count={len(records)} is below required minimum {config.min_records}"
        )

    status = "PASS" if not errors else "FAIL"
    report = KnowledgeIngestReport(
        status=status,
        runs_root=str(config.runs_root),
        output_dir=str(config.output_dir),
        discovered_run_count=len(run_dirs),
        accepted_run_count=accepted_run_count,
        skipped_run_count=skipped_run_count,
        record_count=len(records),
        pattern_count=len(patterns),
        errors=errors,
    )
    write_outputs(config.output_dir, records, patterns, report)
    return report


def discover_run_dirs(runs_root: Path) -> list[Path]:
    if not runs_root.exists():
        return []
    return sorted(path.parent for path in runs_root.rglob("artifacts-manifest.json"))


def run_passed(run_dir: Path) -> bool:
    run_log = run_dir / "run-log.md"
    if not run_log.exists():
        return False
    return bool(re.search(r"^Status:\s*PASS\s*$", run_log.read_text(encoding="utf-8"), re.M))


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def knowledge_deltas_path(run_dir: Path, manifest: dict[str, Any]) -> Path | None:
    outputs_dir = manifest.get("outputs_dir")
    if isinstance(outputs_dir, str):
        path = Path(outputs_dir) / "knowledge-deltas.json"
        if path.exists():
            return path
    local_path = run_dir / "knowledge-deltas.json"
    return local_path if local_path.exists() else None


def normalize_delta(
    item: dict[str, Any],
    *,
    index: int,
    run_dir: Path,
    deltas_path: Path,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    statement = str(item.get("statement") or item.get("summary") or "").strip()
    source_run_id = str(item.get("source_run_id") or manifest.get("run_id") or "").strip()
    source_case_id = str(
        item.get("source_case_id") or manifest.get("case_id") or run_dir.name
    ).strip()
    evidence_ids = item.get("evidence_ids")
    if not isinstance(evidence_ids, list):
        evidence_ids = []
    return {
        "id": "",
        "type": str(item.get("type") or "").strip(),
        "maturity": str(item.get("maturity") or "draft").strip(),
        "scope": str(item.get("scope") or infer_scope(statement, item)).strip(),
        "statement": statement,
        "summary": str(item.get("summary") or statement).strip(),
        "source_case_id": source_case_id,
        "source_run_id": source_run_id,
        "source_run_dir": str(run_dir),
        "artifact_path": str(deltas_path),
        "evidence_ids": [str(value) for value in evidence_ids if isinstance(value, str)],
        "decay_check": str(
            item.get("decay_check")
            or "Recheck when new private merchant telemetry or newer benchmark cases are added."
        ).strip(),
        "raw_index": index,
    }


def infer_scope(statement: str, item: dict[str, Any]) -> str:
    explicit_type = str(item.get("type") or "").lower()
    lower = statement.lower()
    if explicit_type == "pitfall" and any(metric in lower for metric in PRIVATE_METRICS):
        return "metric"
    if "claim" in lower or "口径" in statement:
        return "claim"
    if "artifact" in lower or "validator" in lower:
        return "workflow"
    return "workflow"


def validate_record(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if record["type"] not in VALID_TYPES:
        errors.append(f"type must be one of {sorted(VALID_TYPES)}")
    if record["maturity"] not in VALID_MATURITIES:
        errors.append(f"maturity must be one of {sorted(VALID_MATURITIES)}")
    if not record["statement"]:
        errors.append("statement is required")
    if not record["source_case_id"] and not record["source_run_id"]:
        errors.append("source_case_id or source_run_id is required")
    if private_metric_claim_without_boundary(record["statement"]):
        errors.append("private metric mention must be framed as unavailable or future data")
    return errors


def private_metric_claim_without_boundary(statement: str) -> bool:
    lower = statement.lower()
    if not any(metric in lower for metric in PRIVATE_METRICS):
        return False
    return not any(word in lower for word in SAFE_BOUNDARY_WORDS)


def assign_ids(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    assigned: list[dict[str, Any]] = []
    for index, record in enumerate(
        sorted(records, key=lambda item: (item["source_run_dir"], item["raw_index"])),
        start=1,
    ):
        assigned.append({**record, "id": f"kd_{index:04d}"})
    return assigned


def build_patterns(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        key = pattern_key(record)
        grouped[key].append(record)

    patterns: list[dict[str, Any]] = []
    for index, (key, items) in enumerate(sorted(grouped.items()), start=1):
        first = items[0]
        patterns.append(
            {
                "id": f"kp_{index:04d}",
                "reuse_key": key,
                "type": first["type"],
                "scope": first["scope"],
                "statement": first["statement"],
                "occurrence_count": len(items),
                "maturities": sorted({item["maturity"] for item in items}),
                "source_case_ids": sorted({item["source_case_id"] for item in items}),
                "source_run_ids": sorted({item["source_run_id"] for item in items}),
                "evidence_ids": sorted(
                    {evidence_id for item in items for evidence_id in item["evidence_ids"]}
                ),
            }
        )
    return patterns


def pattern_key(record: dict[str, Any]) -> str:
    normalized_statement = re.sub(r"\s+", " ", record["statement"].lower()).strip()
    return f"{record['type']}|{record['scope']}|{normalized_statement}"


def write_outputs(
    output_dir: Path,
    records: list[dict[str, Any]],
    patterns: list[dict[str, Any]],
    report: KnowledgeIngestReport,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl = "\n".join(
        json.dumps(record, ensure_ascii=False, sort_keys=True) for record in records
    )
    (output_dir / "knowledge-deltas.jsonl").write_text(
        jsonl + ("\n" if jsonl else ""),
        encoding="utf-8",
    )
    (output_dir / "patterns.json").write_text(
        json.dumps(
            {"pattern_count": len(patterns), "patterns": patterns},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "ingest-report.json").write_text(
        json.dumps(asdict(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "README.md").write_text(render_readme(report), encoding="utf-8")


def render_readme(report: KnowledgeIngestReport) -> str:
    return f"""# OpenSKU Knowledge Base

This directory is generated from accepted OpenSKU live run artifacts.

The records come from `knowledge-deltas.json` files produced by the agent and
are tied back to source run directories, run IDs, case IDs, and evidence IDs.
Public benchmark fixtures remain benchmark evidence; this knowledge base does
not claim private merchant GMV, CTR, CVR, ROI, ad spend, sales, refund, repeat
purchase, or verified uplift.

## Current Snapshot

```text
status={report.status}
accepted_run_count={report.accepted_run_count}
record_count={report.record_count}
pattern_count={report.pattern_count}
```

## Files

```text
knowledge-deltas.jsonl
patterns.json
ingest-report.json
```
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--include-failed", action="store_true")
    parser.add_argument("--min-records", type=int, default=0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = ingest_knowledge_deltas(
        KnowledgeIngestConfig(
            runs_root=args.runs,
            output_dir=args.output,
            require_pass=not args.include_failed,
            min_records=args.min_records,
        )
    )
    print(f"output_dir={report.output_dir}")
    print(f"status={report.status}")
    print(f"accepted_run_count={report.accepted_run_count}")
    print(f"record_count={report.record_count}")
    print(f"pattern_count={report.pattern_count}")
    for error in report.errors:
        print(f"ERROR: {error}")
    return 0 if report.status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
