from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from evals.opensku.scorers.knowledge_delta_quality import (  # noqa: E402
    score_knowledge_base,
)


def _write_knowledge_base(
    root: Path,
    *,
    records: list[dict[str, object]],
    patterns: list[dict[str, object]],
) -> Path:
    root.mkdir(parents=True)
    (root / "knowledge-deltas.jsonl").write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
        encoding="utf-8",
    )
    (root / "patterns.json").write_text(
        json.dumps({"pattern_count": len(patterns), "patterns": patterns}),
        encoding="utf-8",
    )
    return root


def test_score_knowledge_base_accepts_sourced_reused_records(tmp_path):
    knowledge = _write_knowledge_base(
        tmp_path / "knowledge",
        records=[
            {
                "id": "kd_0001",
                "type": "pitfall",
                "maturity": "draft",
                "scope": "metric",
                "statement": "Do not convert public fixtures into private commerce metrics.",
                "source_case_id": "opensku-idea-001",
                "source_run_id": "run-001",
                "source_run_dir": "runs/accepted",
                "evidence_ids": ["EVID-004"],
            },
            {
                "id": "kd_0002",
                "type": "process",
                "maturity": "verified",
                "scope": "workflow",
                "statement": "Run artifact validators before presenting files.",
                "source_case_id": "opensku-idea-002",
                "source_run_id": "run-002",
                "source_run_dir": "runs/accepted-2",
                "evidence_ids": ["EVID-005"],
            },
        ],
        patterns=[
            {
                "id": "kp_0001",
                "statement": "Run artifact validators before presenting files.",
                "occurrence_count": 2,
                "source_run_ids": ["run-001", "run-002"],
            }
        ],
    )

    result = score_knowledge_base(knowledge, min_records=2, min_reused_patterns=1)

    assert result.status == "PASS"
    assert result.score == result.max_score
    assert result.check("reuse_patterns").passed is True


def test_score_knowledge_base_rejects_private_metric_claims(tmp_path):
    knowledge = _write_knowledge_base(
        tmp_path / "knowledge",
        records=[
            {
                "id": "kd_0001",
                "type": "decision",
                "maturity": "draft",
                "scope": "metric",
                "statement": "This category has a GMV baseline above target.",
                "source_case_id": "opensku-bad-001",
                "source_run_id": "run-bad",
                "source_run_dir": "runs/bad",
                "evidence_ids": ["EVID-001"],
            }
        ],
        patterns=[],
    )

    result = score_knowledge_base(knowledge, min_records=1, min_reused_patterns=0)

    assert result.status == "FAIL"
    assert result.check("private_metric_boundary").passed is False
    assert any("GMV" in detail for detail in result.check("private_metric_boundary").details)
