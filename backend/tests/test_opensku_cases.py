from pathlib import Path
import sys
import json


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from evals.opensku.validate_cases import validate_case, validate_cases  # noqa: E402


def test_validate_cases_accepts_generated_benchmark_suite():
    result = validate_cases(REPO_ROOT / "evals/opensku/cases")

    assert result.case_count == 30
    assert result.stage_counts == {
        "idea_only": 6,
        "supplier_sample": 6,
        "pre_launch_test": 6,
        "soft_launch": 8,
        "scale_iterate": 4,
    }
    assert result.tag_counts["uploaded_data_simulation"] >= 10
    assert result.tag_counts["public_signal_context"] >= 10
    assert result.tag_counts["forbidden_metric_trap"] >= 5
    assert result.tag_counts["unsupported_claim_trap"] >= 5
    assert result.errors == []


def test_validate_case_rejects_missing_expected_decision_rationale():
    bad_case = {
        "case_id": "opensku-bad-001",
        "stage": "idea_only",
        "category": "Beauty",
        "brief": "A case without rationale.",
        "public_context": [],
        "uploaded_real": [],
        "expected_decision": "Hold",
        "required_artifacts": ["evidence-ledger.json"],
        "required_claims": [],
        "forbidden_claims": [],
        "scoring_notes": {},
        "source_dataset": ["amazon_reviews"],
        "evaluation_tags": ["public_signal_context"],
    }

    errors = validate_case(bad_case, Path("bad.json"))

    assert any("expected_decision_rationale" in error for error in errors)


def test_prelaunch_search_mismatch_case_expects_pivot():
    case = json.loads((REPO_ROOT / "evals/opensku/cases/opensku-prelaunch-001.json").read_text(encoding="utf-8"))

    assert case["stage"] == "pre_launch_test"
    assert case["expected_decision"] == "Pivot"
    assert "query/product/category mismatch" in case["expected_decision_rationale"]
