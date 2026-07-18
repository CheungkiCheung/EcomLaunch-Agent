from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.opensku.ingest_knowledge_deltas import (  # noqa: E402
    KnowledgeIngestConfig,
    ingest_knowledge_deltas,
)


def _write_run(
    root: Path,
    *,
    run_name: str,
    run_id: str,
    status: str,
    deltas: list[dict[str, object]],
) -> Path:
    run_dir = root / run_name
    outputs_dir = run_dir / "outputs"
    outputs_dir.mkdir(parents=True)
    (outputs_dir / "knowledge-deltas.json").write_text(
        json.dumps(deltas, ensure_ascii=False),
        encoding="utf-8",
    )
    (run_dir / "artifacts-manifest.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "case_id": run_name,
                "outputs_dir": str(outputs_dir),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (run_dir / "run-log.md").write_text(
        f"# Run\n\nStatus: {status}\n",
        encoding="utf-8",
    )
    return run_dir


def test_ingest_knowledge_deltas_filters_failed_runs_and_writes_outputs(tmp_path):
    runs_root = tmp_path / "runs"
    output_dir = tmp_path / "knowledge"
    _write_run(
        runs_root,
        run_name="accepted-run",
        run_id="run-001",
        status="PASS",
        deltas=[
            {
                "type": "pitfall",
                "maturity": "draft",
                "scope": "metric",
                "summary": "Do not convert public fixtures into private commerce metrics.",
                "source_case_id": "opensku-idea-001",
                "evidence_ids": ["EVID-004"],
            },
            {
                "type": "process",
                "maturity": "verified",
                "statement": "Run artifact validators before presenting files.",
                "source_run_id": "run-001",
                "evidence_ids": ["EVID-005"],
            },
        ],
    )
    _write_run(
        runs_root,
        run_name="failed-run",
        run_id="run-002",
        status="FAIL",
        deltas=[
            {
                "type": "guideline",
                "maturity": "draft",
                "summary": "This failed run should not be ingested.",
                "source_case_id": "opensku-bad-001",
            },
        ],
    )

    report = ingest_knowledge_deltas(
        KnowledgeIngestConfig(runs_root=runs_root, output_dir=output_dir)
    )

    records = [
        json.loads(line)
        for line in (output_dir / "knowledge-deltas.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]
    patterns = json.loads((output_dir / "patterns.json").read_text(encoding="utf-8"))
    report_json = json.loads(
        (output_dir / "ingest-report.json").read_text(encoding="utf-8")
    )

    assert report.accepted_run_count == 1
    assert report.record_count == 2
    assert report_json["record_count"] == 2
    assert {record["source_run_id"] for record in records} == {"run-001"}
    assert records[0]["statement"] == (
        "Do not convert public fixtures into private commerce metrics."
    )
    assert records[0]["source_run_dir"].endswith("accepted-run")
    assert patterns["pattern_count"] == 2
    assert "failed-run" not in (output_dir / "knowledge-deltas.jsonl").read_text(
        encoding="utf-8"
    )
