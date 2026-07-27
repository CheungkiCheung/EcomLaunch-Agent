"""Deterministic eval scoring, Pareto experiments, and gated Skill evolution."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.commerce.data.gold_cases import load_evaluation_case
from app.commerce.domain.ids import ExperimentId
from app.commerce.evaluation.experiment import (
    ExperimentComparator,
    ExperimentDecision,
    ExperimentDefinition,
    ExperimentRegistry,
    ExperimentVariant,
)
from app.commerce.evaluation.runner import (
    CommerceEvaluationRunner,
    EvaluationObservation,
    EvaluationRunRecord,
    ObservedFact,
    RealModelEvidence,
    TraceObservation,
)
from app.commerce.evaluation.skill_evolution import (
    SkillCandidateRegistry,
    SkillCandidateStatus,
    SkillEvolutionError,
)

REPO_ROOT = Path(__file__).parents[4]
CASES_ROOT = REPO_ROOT / "evals" / "commerce" / "cases"
CONTRACT_EXPERIMENT_ID = ExperimentId("exp_00000000000000000000000000000001")


def _model_evidence(request_id: str) -> RealModelEvidence:
    return RealModelEvidence(
        actual_model_identity="deepseek-v4-flash",
        provider_request_id=request_id,
        configured_model_alias="deepseek-reasoner",
        endpoint="https://api.deepseek.com/v1",
        fresh_request=True,
        retry_count=0,
        input_tokens=1_000,
        output_tokens=300,
        latency_ms=800,
    )


def _passing_observation(case_key: str = "GC-FULFILLMENT-001"):
    evaluation_case = load_evaluation_case(CASES_ROOT / case_key)
    facts = tuple(
        ObservedFact(
            name=item.name,
            semantic_status=item.semantic_status,
            value=item.expected_value,
            unknown_reason=(f"Unavailable because {item.unknown_reason_contains} is missing" if item.unknown_reason_contains else None),
        )
        for item in evaluation_case.expected_behavior.required_facts
    )
    return evaluation_case, EvaluationObservation(
        case_key=case_key,
        repetition=1,
        facts=facts,
        capabilities=evaluation_case.expected_behavior.expected_capabilities,
        executed_path_agents=evaluation_case.expected_behavior.expected_path_agents,
        skipped_path_agents=evaluation_case.expected_behavior.skipped_path_agents,
        final_answer=("The observed delivery signal recovered, but no controlled intervention exists, so Action effectiveness remains inconclusive."),
        follow_up_outcome=evaluation_case.expected_behavior.expected_follow_up_outcome,
        schema_valid=True,
        budget_within_limit=True,
        policy_valid=True,
        trace=TraceObservation(
            model_assignment_count=3,
            checkpoint_count=4,
            verification_count=1,
            duplicate_side_effect_tool_calls=0,
            lease_released=True,
        ),
        real_model_evidence=(_model_evidence(f"req-{case_key}-1"),),
    )


def test_evaluation_runner_passes_exact_gold_behavior_and_blocks_causal_overclaim():
    evaluation_case, observation = _passing_observation()
    runner = CommerceEvaluationRunner()

    passed = runner.evaluate(
        evaluation_case,
        observation,
        requires_real_model=True,
        requires_agent_trace=True,
    )
    causal = runner.evaluate(
        evaluation_case,
        observation.model_copy(update={"final_answer": "The action caused the recovery."}),
        requires_real_model=True,
        requires_agent_trace=True,
    )

    assert passed.passed is True
    assert passed.release_gate_eligible is True
    assert passed.failures == ()
    assert causal.passed is False
    assert "no-causal-action-effect" in {failure.code for failure in causal.failures}


def test_evaluation_runner_blocks_transit_correlation_written_as_root_cause():
    evaluation_case, observation = _passing_observation()

    result = CommerceEvaluationRunner().evaluate(
        evaluation_case,
        observation.model_copy(update={"final_answer": ("Transit time was the dominant driver and the recovery window further confirmed transit was the root cause.")}),
        requires_real_model=True,
        requires_agent_trace=True,
    )

    assert result.passed is False
    assert "no-transit-causal-certainty" in {failure.code for failure in result.failures}


def test_evaluation_runner_fails_closed_on_missing_fresh_model_or_trace_evidence():
    evaluation_case, observation = _passing_observation()
    result = CommerceEvaluationRunner().evaluate(
        evaluation_case,
        observation.model_copy(
            update={
                "real_model_evidence": (),
                "trace": observation.trace.model_copy(
                    update={
                        "checkpoint_count": 0,
                        "lease_released": False,
                    }
                ),
            }
        ),
        requires_real_model=True,
        requires_agent_trace=True,
    )

    assert result.passed is False
    assert result.release_gate_eligible is False
    assert {failure.code for failure in result.failures} >= {
        "real-model-evidence-missing",
        "trace-checkpoint-missing",
        "trace-lease-not-released",
    }


def test_evaluation_trace_does_not_require_a_runtime_lease_for_offline_experiments():
    evaluation_case, observation = _passing_observation()
    offline_trace = observation.trace.model_copy(
        update={
            "lease_required": False,
            "lease_released": False,
        }
    )

    result = CommerceEvaluationRunner().evaluate(
        evaluation_case,
        observation.model_copy(update={"trace": offline_trace}),
        requires_real_model=True,
        requires_agent_trace=True,
    )

    assert result.passed is True
    assert result.release_gate_eligible is True


def test_evaluation_runner_requires_fresh_semantic_gate_when_requested():
    evaluation_case, observation = _passing_observation()

    missing = CommerceEvaluationRunner().evaluate(
        evaluation_case,
        observation,
        requires_real_model=True,
        requires_agent_trace=True,
        requires_semantic_evaluator=True,
    )
    passed = CommerceEvaluationRunner().evaluate(
        evaluation_case,
        observation.model_copy(update={"semantic_evaluation_passed": True}),
        requires_real_model=True,
        requires_agent_trace=True,
        requires_semantic_evaluator=True,
    )

    assert "semantic-evaluator-missing-or-failed" in {failure.code for failure in missing.failures}
    assert passed.passed is True


def _run_record(
    *,
    variant: str,
    repetition: int,
    request_id: str,
    passed: bool = True,
    release_gate_eligible: bool = True,
    tokens: int = 1_000,
    latency_ms: float = 1_000,
) -> EvaluationRunRecord:
    evaluation_case, observation = _passing_observation()
    evaluated_observation = observation.model_copy(
        update={
            "repetition": repetition,
            "real_model_evidence": (_model_evidence(request_id),),
            "final_answer": (observation.final_answer if passed else "The action caused the recovery."),
        }
    )
    scorecard = CommerceEvaluationRunner().evaluate(
        evaluation_case,
        evaluated_observation,
        requires_real_model=True,
        requires_agent_trace=True,
    )
    if passed and not release_gate_eligible:
        scorecard = scorecard.model_copy(
            update={
                "release_gate_eligible": release_gate_eligible,
            }
        )
    return EvaluationRunRecord(
        experiment_id=CONTRACT_EXPERIMENT_ID,
        variant_name=variant,
        case_key=evaluation_case.case_key,
        repetition=repetition,
        scorecard=scorecard,
        model_evidence=_model_evidence(request_id).model_copy(
            update={
                "input_tokens": tokens - 300,
                "output_tokens": 300,
                "latency_ms": latency_ms,
            }
        ),
        raw_output_sha256="a" * 64,
        trace_sha256="b" * 64,
        created_at=datetime(2026, 7, 19, 19, repetition, tzinfo=UTC),
    )


def _experiment() -> ExperimentDefinition:
    return ExperimentDefinition(
        id=CONTRACT_EXPERIMENT_ID,
        title="Prompt-only versus explicit fulfillment Skill contract",
        hypothesis=("The candidate Skill preserves safety and Gold Case quality while reducing token cost."),
        control=ExperimentVariant(
            name="control",
            prompt_version="lead@1.0.0",
            context_version="commerce-context@1.0.0",
            router_version="commerce-model-router@1.0.0",
            skill_version="fulfillment@1.0.0",
        ),
        candidate=ExperimentVariant(
            name="candidate",
            prompt_version="lead@1.0.0",
            context_version="commerce-context@1.0.0",
            router_version="commerce-model-router@1.0.0",
            skill_version="fulfillment@1.1.0-candidate",
        ),
        case_keys=("GC-FULFILLMENT-001",),
        repetitions=2,
        controlled_variables=(
            "model_alias=deepseek-reasoner",
            "effort=high",
            "temperature=0",
        ),
        reproduction_command=("PYTHONPATH=. .venv/bin/python -m app.commerce.evaluation.run_experiment"),
    )


def test_experiment_comparator_uses_hard_gates_then_pareto_and_registry_is_immutable(
    tmp_path,
):
    definition = _experiment()
    records = (
        _run_record(
            variant="control",
            repetition=1,
            request_id="req-control-1",
            tokens=1_200,
            latency_ms=1_000,
        ),
        _run_record(
            variant="control",
            repetition=2,
            request_id="req-control-2",
            tokens=1_180,
            latency_ms=980,
        ),
        _run_record(
            variant="candidate",
            repetition=1,
            request_id="req-candidate-1",
            tokens=900,
            latency_ms=970,
        ),
        _run_record(
            variant="candidate",
            repetition=2,
            request_id="req-candidate-2",
            tokens=880,
            latency_ms=960,
        ),
    )

    report = ExperimentComparator().compare(definition, records)
    registry = ExperimentRegistry(tmp_path / "experiments")
    definition_path = registry.register(definition)
    report_path = registry.record_report(report)

    assert report.decision is ExperimentDecision.PROMOTE_CANDIDATE
    assert report.candidate.hard_gate_failures == 0
    assert report.candidate.mean_total_tokens < report.control.mean_total_tokens
    assert definition_path.is_file()
    assert report_path.is_file()
    with pytest.raises(FileExistsError):
        registry.register(definition)


def test_experiment_rejects_candidate_on_any_release_gate_regression():
    definition = _experiment()
    records = (
        _run_record(variant="control", repetition=1, request_id="req-control-1"),
        _run_record(variant="control", repetition=2, request_id="req-control-2"),
        _run_record(
            variant="candidate",
            repetition=1,
            request_id="req-candidate-1",
            passed=False,
            release_gate_eligible=False,
        ),
        _run_record(variant="candidate", repetition=2, request_id="req-candidate-2"),
    )

    report = ExperimentComparator().compare(definition, records)

    assert report.decision is ExperimentDecision.REJECT_CANDIDATE
    assert report.candidate.hard_gate_failures == 1


def test_skill_candidate_cannot_become_active_without_scan_eval_shadow_and_review(
    tmp_path,
):
    definition = _experiment()
    report = ExperimentComparator().compare(
        definition,
        (
            _run_record(variant="control", repetition=1, request_id="req-control-1"),
            _run_record(variant="control", repetition=2, request_id="req-control-2"),
            _run_record(
                variant="candidate",
                repetition=1,
                request_id="req-candidate-1",
                tokens=800,
            ),
            _run_record(
                variant="candidate",
                repetition=2,
                request_id="req-candidate-2",
                tokens=790,
            ),
        ),
    )
    registry = SkillCandidateRegistry(tmp_path / "skills")
    candidate = registry.propose(
        skill_name="commerce-fulfillment-diagnosis",
        base_version="1.0.0",
        candidate_version="1.1.0",
        content=("# Fulfillment Diagnosis\n\nUse deterministic metrics, cite Evidence IDs, and preserve unknowns.\n"),
        source_failure_codes=("causal-overclaim",),
    )

    assert candidate.status is SkillCandidateStatus.CANDIDATE
    with pytest.raises(SkillEvolutionError, match="offline evaluation"):
        registry.promote(candidate.id, reviewer_id="reviewer-a")

    evaluated = registry.record_offline_evaluation(
        candidate.id,
        experiment_report=report,
        regression_passed=True,
        holdout_passed=True,
    )
    assert evaluated.status is SkillCandidateStatus.OFFLINE_EVALUATED
    with pytest.raises(SkillEvolutionError, match="shadow"):
        registry.promote(candidate.id, reviewer_id="reviewer-a")

    shadowed = registry.record_shadow_result(
        candidate.id,
        passed=True,
        live_run_ids=("run-shadow-001", "run-shadow-002"),
    )
    active = registry.promote(shadowed.id, reviewer_id="reviewer-a")

    assert active.status is SkillCandidateStatus.ACTIVE
    assert registry.active_version(candidate.skill_name) == "1.1.0"
    rolled_back = registry.rollback(
        candidate.skill_name,
        reviewer_id="reviewer-b",
        reason="Holdout regression observed after promotion",
    )
    assert rolled_back.status is SkillCandidateStatus.ROLLED_BACK
    assert registry.active_version(candidate.skill_name) == "1.0.0"


def test_skill_candidate_registry_rejects_blank_rollback_review_and_fails_closed_on_pointer_tampering(
    tmp_path,
):
    definition = _experiment()
    report = ExperimentComparator().compare(
        definition,
        (
            _run_record(variant="control", repetition=1, request_id="req-control-1"),
            _run_record(variant="control", repetition=2, request_id="req-control-2"),
            _run_record(
                variant="candidate",
                repetition=1,
                request_id="req-candidate-1",
                tokens=800,
            ),
            _run_record(
                variant="candidate",
                repetition=2,
                request_id="req-candidate-2",
                tokens=790,
            ),
        ),
    )
    registry = SkillCandidateRegistry(tmp_path / "skills")
    candidate = registry.propose(
        skill_name="commerce-fulfillment-diagnosis",
        base_version="1.0.0",
        candidate_version="1.1.0",
        content="# Fulfillment Diagnosis\n\nPreserve deterministic Evidence lineage.\n",
        source_failure_codes=("causal-overclaim",),
    )
    registry.record_offline_evaluation(
        candidate.id,
        experiment_report=report,
        regression_passed=True,
        holdout_passed=True,
    )
    registry.record_shadow_result(
        candidate.id,
        passed=True,
        live_run_ids=("run-shadow-001", "run-shadow-002"),
    )
    registry.promote(candidate.id, reviewer_id="reviewer-a")

    with pytest.raises(SkillEvolutionError, match="human reviewer"):
        registry.rollback(candidate.skill_name, reviewer_id="   ", reason="regression")
    with pytest.raises(SkillEvolutionError, match="reason"):
        registry.rollback(candidate.skill_name, reviewer_id="reviewer-b", reason="   ")

    pointer_path = tmp_path / "skills" / "active" / f"{candidate.skill_name}.json"
    pointer_path.write_text('{"skill_name":"commerce-fulfillment-diagnosis"}\n', encoding="utf-8")

    with pytest.raises(SkillEvolutionError, match="pointer is invalid"):
        registry.active_pointer(candidate.skill_name)
