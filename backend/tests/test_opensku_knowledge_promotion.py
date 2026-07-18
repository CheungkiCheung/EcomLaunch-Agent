from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.opensku.promote_knowledge_maturity import (  # noqa: E402
    KnowledgePromotionConfig,
    promote_knowledge_maturity,
)


def test_promote_knowledge_maturity_verifies_injected_pattern_from_passing_run(tmp_path):
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()
    (knowledge / "patterns.json").write_text(
        json.dumps(
            {
                "pattern_count": 1,
                "patterns": [
                    {
                        "id": "kp_0008",
                        "type": "pitfall",
                        "scope": "workflow",
                        "statement": "Do not convert public fixtures into private commerce metrics.",
                        "maturities": ["draft"],
                        "occurrence_count": 3,
                        "source_case_ids": ["opensku-idea-001"],
                        "source_run_ids": ["source-run-1"],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    run_dir = tmp_path / "runs" / "accepted"
    run_dir.mkdir(parents=True)
    (run_dir / "run-log.md").write_text("# Run\n\nStatus: PASS\n", encoding="utf-8")
    (run_dir / "artifacts-manifest.json").write_text(
        json.dumps(
            {
                "case_id": "live-knowledge-injection-opensku-idea-002",
                "run_id": "run-verified-1",
                "injected_knowledge_patterns": [
                    {
                        "id": "kp_0008",
                        "type": "pitfall",
                        "maturity": "draft",
                        "statement": "Do not convert public fixtures into private commerce metrics.",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = promote_knowledge_maturity(
        KnowledgePromotionConfig(knowledge_dir=knowledge, runs_root=tmp_path / "runs")
    )
    promoted = json.loads((knowledge / "patterns.json").read_text(encoding="utf-8"))["patterns"][0]
    promotion_report = json.loads((knowledge / "promotion-report.json").read_text(encoding="utf-8"))

    assert report.status == "PASS"
    assert report.promoted_count == 1
    assert report.verified_reuse_pattern_count == 1
    assert promoted["maturity"] == "verified"
    assert "verified" in promoted["maturities"]
    assert promoted["reuse_evidence"][0]["run_id"] == "run-verified-1"
    assert promotion_report["promoted_count"] == 1

    second_report = promote_knowledge_maturity(
        KnowledgePromotionConfig(knowledge_dir=knowledge, runs_root=tmp_path / "runs", min_promotions=1)
    )

    assert second_report.status == "PASS"
    assert second_report.promoted_count == 0
    assert second_report.verified_reuse_pattern_count == 1


def test_promote_knowledge_maturity_ignores_failed_runs(tmp_path):
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()
    (knowledge / "patterns.json").write_text(
        json.dumps(
            {
                "pattern_count": 1,
                "patterns": [
                    {
                        "id": "kp_0008",
                        "type": "pitfall",
                        "statement": "Do not convert public fixtures into private commerce metrics.",
                        "maturities": ["draft"],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    run_dir = tmp_path / "runs" / "failed"
    run_dir.mkdir(parents=True)
    (run_dir / "run-log.md").write_text("# Run\n\nStatus: FAIL\n", encoding="utf-8")
    (run_dir / "artifacts-manifest.json").write_text(
        json.dumps(
            {
                "run_id": "run-failed",
                "injected_knowledge_patterns": [{"id": "kp_0008"}],
            }
        ),
        encoding="utf-8",
    )

    report = promote_knowledge_maturity(
        KnowledgePromotionConfig(knowledge_dir=knowledge, runs_root=tmp_path / "runs")
    )
    pattern = json.loads((knowledge / "patterns.json").read_text(encoding="utf-8"))["patterns"][0]

    assert report.promoted_count == 0
    assert pattern.get("maturity") != "verified"
    assert pattern["maturities"] == ["draft"]


def test_promote_knowledge_maturity_matches_reuse_key_when_pattern_ids_drift(tmp_path):
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()
    (knowledge / "patterns.json").write_text(
        json.dumps(
            {
                "pattern_count": 2,
                "patterns": [
                    {
                        "id": "kp_0006",
                        "reuse_key": "decision|workflow|current loop state is kill at stage pre_launch_test.",
                        "type": "decision",
                        "scope": "workflow",
                        "statement": "Current loop state is Kill at stage pre_launch_test.",
                        "maturities": ["draft"],
                    },
                    {
                        "id": "kp_0011",
                        "reuse_key": "decision|workflow|current loop state is pivot at stage pre_launch_test.",
                        "type": "decision",
                        "scope": "workflow",
                        "statement": "Current loop state is Pivot at stage pre_launch_test.",
                        "maturities": ["draft"],
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    run_dir = tmp_path / "runs" / "live-knowledge-injection-prelaunch-002"
    outputs_dir = run_dir / "outputs"
    run_dir.mkdir(parents=True)
    outputs_dir.mkdir()
    (outputs_dir / "launch-state.json").write_text(
        json.dumps({"stage": "pre_launch_test", "decision": "Pivot"}),
        encoding="utf-8",
    )
    (run_dir / "run-log.md").write_text("# Run\n\nStatus: PASS\n", encoding="utf-8")
    (run_dir / "artifacts-manifest.json").write_text(
        json.dumps(
            {
                "case_id": "live-knowledge-injection-prelaunch-002",
                "run_id": "run-reuse-key-1",
                "outputs_dir": str(outputs_dir),
                "injected_knowledge_patterns": [
                    {
                        "id": "kp_0006",
                        "type": "decision",
                        "scope": "workflow",
                        "statement": "Current loop state is Pivot at stage pre_launch_test.",
                        "stage_matches": ["pre_launch_test"],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = promote_knowledge_maturity(
        KnowledgePromotionConfig(knowledge_dir=knowledge, runs_root=tmp_path / "runs")
    )
    patterns = {
        pattern["statement"]: pattern
        for pattern in json.loads((knowledge / "patterns.json").read_text(encoding="utf-8"))["patterns"]
    }

    assert report.status == "PASS"
    assert report.promoted_count == 1
    assert patterns["Current loop state is Kill at stage pre_launch_test."].get("maturity") != "verified"
    assert patterns["Current loop state is Pivot at stage pre_launch_test."]["maturity"] == "verified"
    assert patterns["Current loop state is Pivot at stage pre_launch_test."]["reuse_evidence"][0]["run_id"] == "run-reuse-key-1"


def test_promote_decision_pattern_requires_matching_final_decision(tmp_path):
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()
    (knowledge / "patterns.json").write_text(
        json.dumps(
            {
                "pattern_count": 2,
                "patterns": [
                    {
                        "id": "kp_hold",
                        "reuse_key": "decision|workflow|current loop state is hold at stage pre_launch_test.",
                        "type": "decision",
                        "scope": "workflow",
                        "statement": "Current loop state is Hold at stage pre_launch_test.",
                        "maturities": ["draft"],
                    },
                    {
                        "id": "kp_pivot",
                        "reuse_key": "decision|workflow|current loop state is pivot at stage pre_launch_test.",
                        "type": "decision",
                        "scope": "workflow",
                        "statement": "Current loop state is Pivot at stage pre_launch_test.",
                        "maturities": ["draft"],
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    run_dir = tmp_path / "runs" / "live-knowledge-injection-prelaunch-002"
    outputs_dir = run_dir / "outputs"
    outputs_dir.mkdir(parents=True)
    (outputs_dir / "launch-state.json").write_text(
        json.dumps({"stage": "pre_launch_test", "decision": "Pivot"}),
        encoding="utf-8",
    )
    (run_dir / "run-log.md").write_text("# Run\n\nStatus: PASS\n", encoding="utf-8")
    (run_dir / "artifacts-manifest.json").write_text(
        json.dumps(
            {
                "case_id": "live-knowledge-injection-prelaunch-002",
                "run_id": "run-decision-match-1",
                "outputs_dir": str(outputs_dir),
                "injected_knowledge_patterns": [
                    {
                        "id": "kp_hold",
                        "type": "decision",
                        "scope": "workflow",
                        "statement": "Current loop state is Hold at stage pre_launch_test.",
                        "stage_matches": ["pre_launch_test"],
                    },
                    {
                        "id": "kp_pivot",
                        "type": "decision",
                        "scope": "workflow",
                        "statement": "Current loop state is Pivot at stage pre_launch_test.",
                        "stage_matches": ["pre_launch_test"],
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = promote_knowledge_maturity(
        KnowledgePromotionConfig(knowledge_dir=knowledge, runs_root=tmp_path / "runs")
    )
    patterns = {
        pattern["id"]: pattern
        for pattern in json.loads((knowledge / "patterns.json").read_text(encoding="utf-8"))["patterns"]
    }

    assert report.status == "PASS"
    assert report.promoted_count == 1
    assert patterns["kp_hold"].get("maturity") != "verified"
    assert patterns["kp_pivot"]["maturity"] == "verified"
