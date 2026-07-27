"""Deterministic contracts for the fresh-model Experiment harness."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.commerce.data.gold_cases import load_evaluation_case
from app.commerce.evaluation.run_experiment import (
    GoldCaseExperimentInputBuilder,
    SynthesisExperimentParseError,
    build_experiment_suite,
    parse_synthesis_output,
)
from app.commerce.evaluation.semantic import DeepSeekSemanticEvaluator

REPO_ROOT = Path(__file__).parents[4]
CASE_ROOT = REPO_ROOT / "evals" / "commerce" / "cases" / "GC-FULFILLMENT-001"
PEER_CASE_ROOT = REPO_ROOT / "evals" / "commerce" / "cases" / "GC-PEER-004"


def test_experiment_input_is_recomputed_from_visible_fixture_without_hidden_labels(
    tmp_path,
):
    evaluation_case = load_evaluation_case(CASE_ROOT)

    packet = GoldCaseExperimentInputBuilder().build(
        evaluation_case,
        case_root=CASE_ROOT,
        storage_root=tmp_path / "storage",
    )

    facts = {item.name: item.value for item in packet.facts}
    assert facts["baseline.order_count"] == 141
    assert facts["anomaly.order_count"] == 202
    assert facts["recovery.order_count"] == 211
    assert packet.capabilities == frozenset({"fulfillment_diagnosis", "review_experience"})
    assert packet.executed_path_agents == frozenset({"FulfillmentPathAgent", "ReviewExperiencePathAgent"})
    assert packet.skipped_path_agents == frozenset({"SellerPeerPathAgent"})
    rendered = packet.model_dump_json()
    assert "expected_behavior" not in rendered
    assert "forbidden_claims" not in rendered
    assert "expected_value" not in rendered


@pytest.mark.parametrize(
    ("case_key", "expected_capabilities", "expected_paths", "skipped_paths"),
    (
        (
            "GC-REVIEW-002",
            frozenset({"fulfillment_diagnosis", "review_experience"}),
            frozenset({"ReviewExperiencePathAgent"}),
            frozenset({"FulfillmentPathAgent", "SellerPeerPathAgent"}),
        ),
        (
            "GC-CAPABILITY-003",
            frozenset({"fulfillment_diagnosis"}),
            frozenset({"FulfillmentPathAgent"}),
            frozenset({"ReviewExperiencePathAgent", "SellerPeerPathAgent"}),
        ),
    ),
)
def test_experiment_input_routes_holdouts_from_visible_anomaly_signals(
    tmp_path,
    case_key,
    expected_capabilities,
    expected_paths,
    skipped_paths,
):
    case_root = REPO_ROOT / "evals" / "commerce" / "cases" / case_key
    evaluation_case = load_evaluation_case(case_root)

    packet = GoldCaseExperimentInputBuilder().build(
        evaluation_case,
        case_root=case_root,
        storage_root=tmp_path / case_key,
    )

    assert packet.capabilities == expected_capabilities
    assert packet.executed_path_agents == expected_paths
    assert packet.skipped_path_agents == skipped_paths
    if case_key == "GC-REVIEW-002":
        facts = {item.name: item.value for item in packet.facts}
        assert float(facts["baseline.low_rating_rate"]) == pytest.approx(0.23529411764705882)
        assert float(facts["anomaly.low_rating_rate"]) == pytest.approx(0.4444444444444444)
    else:
        facts = {item.name: item for item in packet.facts}
        review = facts["anomaly.average_review_score"]
        assert review.value is None
        assert "order_reviews" in (review.unknown_reason or "")


def test_experiment_input_recomputes_peer_and_geography_from_visible_request(
    tmp_path,
):
    evaluation_case = load_evaluation_case(PEER_CASE_ROOT)

    packet = GoldCaseExperimentInputBuilder().build(
        evaluation_case,
        case_root=PEER_CASE_ROOT,
        storage_root=tmp_path / "peer-storage",
    )

    facts = {item.name: item.value for item in packet.facts}
    assert packet.analysis_request is None
    assert packet.peer_analysis_request is not None
    assert packet.capabilities == frozenset(
        {
            "fulfillment_diagnosis",
            "review_experience",
            "seller_peer_comparison",
        }
    )
    assert packet.executed_path_agents == frozenset({"FulfillmentPathAgent", "SellerPeerPathAgent"})
    assert packet.skipped_path_agents == frozenset({"ReviewExperiencePathAgent"})
    assert facts["peer.target_order_count"] == 59
    assert float(facts["peer.target_late_delivery_rate"]) == pytest.approx(0.2711864406779661)
    assert facts["peer.peer_seller_count"] == 5
    assert facts["peer.peer_order_count"] == 257
    assert float(facts["peer.peer_late_delivery_rate"]) == pytest.approx(0.07392996108949416)
    assert float(facts["peer.late_delivery_rate_gap"]) == pytest.approx(0.19725647958847192)
    assert facts["geography.SP.order_count"] == 26
    assert facts["geography.MG.order_count"] == 8
    assert facts["geography.RJ.order_count"] == 7
    rendered = packet.model_dump_json()
    assert "expected_behavior" not in rendered
    assert "expected_value" not in rendered
    assert packet.peer_analysis_request.eligibility_uses_late_delivery_result is False
    assert '"eligibility_uses_late_delivery_result":false' in rendered


def test_synthesis_output_parser_accepts_one_json_object_and_rejects_free_text():
    parsed = parse_synthesis_output('{"final_answer":"Transit increased while handling did not worsen."}')

    assert parsed.final_answer.startswith("Transit increased")
    with pytest.raises(SynthesisExperimentParseError):
        parse_synthesis_output("Transit increased without a JSON envelope")


def test_semantic_reason_codes_remove_contradictory_success_marker():
    judgment = DeepSeekSemanticEvaluator._parse(
        """{
          "useful": true,
          "action_guidance_is_bounded": true,
          "unknowns_preserved": true,
          "unsupported_causal_claim": true,
          "unsupported_private_metric_claim": false,
          "reason_codes": ["no-transit-causal-certainty", "all-gates-passed"],
          "explanation": "The answer turns correlation into a root-cause claim."
        }"""
    )

    assert "all-gates-passed" not in judgment.reason_codes
    assert "inconsistent-success-code-removed" in judgment.reason_codes


def test_semantic_parser_discards_overlong_free_form_explanation_without_losing_verdict():
    judgment = DeepSeekSemanticEvaluator._parse(
        json.dumps(
            {
                "useful": True,
                "action_guidance_is_bounded": False,
                "unknowns_preserved": True,
                "unsupported_causal_claim": False,
                "unsupported_private_metric_claim": False,
                "reason_codes": ["unsupported-action-threshold"],
                "explanation": "internal revision commentary " * 200,
            }
        )
    )

    assert judgment.action_guidance_is_bounded is False
    assert judgment.explanation == ("模型返回了超长自由文本说明；系统已丢弃该说明，仅保留结构化判定与审计码。")
    assert "explanation-overlong-discarded" in judgment.reason_codes


@pytest.mark.parametrize(
    "answer",
    (
        "建议监控未来30天延迟率，若仍超15%则触发人工审核。",
        "若持续高于对标均值2倍则触发人工审核。",
        "Monitor for 30 days and trigger review if the rate remains above 15%.",
    ),
)
def test_semantic_guard_rejects_model_authored_numeric_action_threshold(answer):
    judgment = DeepSeekSemanticEvaluator._parse(
        """{
          "useful": true,
          "action_guidance_is_bounded": true,
          "unknowns_preserved": true,
          "unsupported_causal_claim": false,
          "unsupported_private_metric_claim": false,
          "reason_codes": ["all-gates-passed"],
          "explanation": "The answer is otherwise calibrated."
        }"""
    )

    guarded = DeepSeekSemanticEvaluator._apply_deterministic_guards(
        judgment,
        answer,
    )

    assert guarded.action_guidance_is_bounded is False
    assert "unsupported-action-threshold" in guarded.reason_codes
    assert "all-gates-passed" not in guarded.reason_codes


@pytest.mark.parametrize(
    "answer",
    (
        "该卖家延迟率高出对标19.7个百分点，建议持续监控并由服务端策略确定阈值。",
        "Keep monitoring late_delivery_rate and reopen the Case if the configured threshold is breached.",
    ),
)
def test_semantic_guard_allows_observed_numbers_without_invented_policy(answer):
    judgment = DeepSeekSemanticEvaluator._parse(
        """{
          "useful": true,
          "action_guidance_is_bounded": true,
          "unknowns_preserved": true,
          "unsupported_causal_claim": false,
          "unsupported_private_metric_claim": false,
          "reason_codes": ["all-gates-passed"],
          "explanation": "The answer is calibrated."
        }"""
    )

    guarded = DeepSeekSemanticEvaluator._apply_deterministic_guards(
        judgment,
        answer,
    )

    assert guarded.action_guidance_is_bounded is True
    assert guarded.reason_codes == ("all-gates-passed",)


def test_experiment_suite_versions_all_regression_and_holdout_cases():
    cases = tuple(
        load_evaluation_case(REPO_ROOT / "evals" / "commerce" / "cases" / key)
        for key in (
            "GC-FULFILLMENT-001",
            "GC-REVIEW-002",
            "GC-CAPABILITY-003",
            "GC-PEER-004",
        )
    )

    definition = build_experiment_suite(cases, repetitions=2)

    assert definition.case_keys == tuple(item.case_key for item in cases)
    assert definition.repetitions == 2
    assert definition.candidate.skill_content_sha256
    assert any(item.startswith("suite_context_sha256=") for item in definition.controlled_variables)
