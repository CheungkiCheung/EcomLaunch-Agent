from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from evals.opensku.knowledge_context import (  # noqa: E402
    KnowledgePattern,
    format_knowledge_context,
    load_knowledge_patterns,
    select_knowledge_patterns,
)


def test_select_patterns_prioritizes_metric_boundary_and_artifact_process():
    patterns = load_knowledge_patterns(REPO_ROOT / "docs/knowledge/opensku")
    case = {
        "stage": "pre_launch_test",
        "category": "home and furniture search relevance",
        "forbidden_claims": ["Do not invent GMV, CTR, CVR, ROI, ad spend, or sales volume."],
    }

    selected = select_knowledge_patterns(patterns, case=case, limit=5)

    assert "private commerce metrics" in selected[0].statement
    assert "artifact writer plus validator" in selected[1].statement
    assert 3 <= len(selected) <= 5
    assert all(pattern.statement for pattern in selected)
    assert all(pattern.occurrence_count >= 1 for pattern in selected)
    assert all(
        pattern.type != "decision" or "pre_launch_test" in pattern.stage_matches
        for pattern in selected
    )


def test_format_knowledge_context_is_bounded_and_warns_against_copying_decisions():
    patterns = load_knowledge_patterns(REPO_ROOT / "docs/knowledge/opensku")
    selected = select_knowledge_patterns(patterns, case={"stage": "idea_only"}, limit=3)

    context = format_knowledge_context(selected, knowledge_dir=REPO_ROOT / "docs/knowledge/opensku")

    assert "Relevant OpenSKU reusable knowledge" in context
    assert "Do not convert public fixtures" in context
    assert "Do not copy a previous decision unless the current evidence supports it" in context
    assert context.count("- kp_") == len(selected)
    assert context.count("- kp_") <= 3


def test_decision_statement_stage_is_not_widened_by_source_case_id():
    pattern = KnowledgePattern.from_dict(
        {
            "id": "kp_bug",
            "type": "decision",
            "statement": "Current loop state is Hold at stage pre_launch_test.",
            "maturity": "draft",
            "occurrence_count": 1,
            "source_case_ids": ["batch-live-stage2-opensku-softlaunch-002"],
        }
    )

    assert pattern.stage_matches == ("pre_launch_test",)
    assert select_knowledge_patterns([pattern], case={"stage": "soft_launch"}, limit=5) == []
    assert [item.id for item in select_knowledge_patterns([pattern], case={"stage": "pre_launch_test"}, limit=5)] == ["kp_bug"]
