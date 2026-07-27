"""Deterministic Gold Case scorer and release-gate Evaluation records."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Self

from pydantic import Field, model_validator

from app.commerce.domain.enums import FollowUpOutcome, SemanticStatus
from app.commerce.domain.evaluation import (
    EvaluationCase,
    FactExpectation,
    MatchMode,
)
from app.commerce.domain.ids import (
    EvaluationRunId,
    ExperimentId,
)
from app.commerce.domain.models import CommerceModel, ScalarValue
from app.commerce.evaluation.real_model_preflight import (
    is_official_deepseek_endpoint,
    is_verified_deepseek_v4_identity,
)


class ObservedFact(CommerceModel):
    name: str = Field(min_length=1)
    semantic_status: SemanticStatus
    value: ScalarValue | None = None
    unknown_reason: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def keep_semantics_consistent(self) -> Self:
        if self.semantic_status in {SemanticStatus.UNKNOWN, SemanticStatus.BLOCKED}:
            if self.value is not None or self.unknown_reason is None:
                raise ValueError("Unknown observed Fact requires only unknown_reason")
        elif self.value is None:
            raise ValueError("Known observed Fact requires a value")
        return self


class RealModelEvidence(CommerceModel):
    actual_model_identity: str = Field(min_length=1)
    provider_request_id: str = Field(min_length=1)
    configured_model_alias: str = Field(min_length=1)
    endpoint: str = Field(min_length=1)
    fresh_request: bool
    retry_count: int = Field(ge=0)
    input_tokens: int = Field(ge=1)
    output_tokens: int = Field(ge=0)
    latency_ms: float = Field(ge=0)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @model_validator(mode="after")
    def require_release_identity(self) -> Self:
        if not is_verified_deepseek_v4_identity(self.actual_model_identity):
            raise ValueError("Evaluation model evidence is not DeepSeek V4")
        if not is_official_deepseek_endpoint(self.endpoint):
            raise ValueError("Evaluation model evidence must use official DeepSeek")
        if not self.fresh_request:
            raise ValueError("Evaluation model evidence must be fresh")
        if self.retry_count != 0:
            raise ValueError("Evaluation model evidence must disable provider retries")
        return self


class TraceObservation(CommerceModel):
    model_assignment_count: int = Field(ge=0)
    checkpoint_count: int = Field(ge=0)
    verification_count: int = Field(ge=0)
    duplicate_side_effect_tool_calls: int = Field(ge=0)
    lease_required: bool = True
    lease_released: bool


class EvaluationObservation(CommerceModel):
    case_key: str = Field(pattern=r"^GC-[A-Z]+-\d{3}$")
    repetition: int = Field(ge=1)
    facts: tuple[ObservedFact, ...]
    capabilities: frozenset[str]
    executed_path_agents: frozenset[str] = frozenset()
    skipped_path_agents: frozenset[str] = frozenset()
    final_answer: str
    follow_up_outcome: FollowUpOutcome | None = None
    schema_valid: bool
    budget_within_limit: bool
    policy_valid: bool
    semantic_evaluation_passed: bool | None = None
    trace: TraceObservation
    real_model_evidence: tuple[RealModelEvidence, ...] = ()

    @model_validator(mode="after")
    def keep_observation_unique(self) -> Self:
        fact_names = tuple(item.name for item in self.facts)
        if len(fact_names) != len(set(fact_names)):
            raise ValueError("Evaluation observed Fact names must be unique")
        request_ids = tuple(item.provider_request_id for item in self.real_model_evidence)
        if len(request_ids) != len(set(request_ids)):
            raise ValueError("Evaluation provider request IDs must be unique")
        return self


class EvaluationFailure(CommerceModel):
    code: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    category: str = Field(min_length=1)
    message: str = Field(min_length=1)


class EvaluationScorecard(CommerceModel):
    case_key: str
    repetition: int = Field(ge=1)
    passed: bool
    release_gate_eligible: bool
    dimension_scores: dict[str, float]
    failures: tuple[EvaluationFailure, ...] = ()

    @model_validator(mode="after")
    def keep_result_consistent(self) -> Self:
        if self.passed == bool(self.failures):
            raise ValueError("Evaluation passed state must match failure presence")
        if self.release_gate_eligible and not self.passed:
            raise ValueError("Failed Evaluation cannot be release-gate eligible")
        if any(value < 0 or value > 1 for value in self.dimension_scores.values()):
            raise ValueError("Evaluation dimension scores must be between zero and one")
        return self


class EvaluationRunRecord(CommerceModel):
    id: EvaluationRunId = Field(default_factory=EvaluationRunId.new)
    experiment_id: ExperimentId
    variant_name: str = Field(min_length=1)
    case_key: str = Field(pattern=r"^GC-[A-Z]+-\d{3}$")
    repetition: int = Field(ge=1)
    scorecard: EvaluationScorecard
    model_evidence: RealModelEvidence
    verification_model_evidence: tuple[RealModelEvidence, ...] = ()
    raw_output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    trace_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime

    @model_validator(mode="after")
    def match_scorecard(self) -> Self:
        if self.scorecard.case_key != self.case_key or self.scorecard.repetition != self.repetition:
            raise ValueError("Evaluation Run and Scorecard identity differ")
        request_ids = (
            self.model_evidence.provider_request_id,
            *(item.provider_request_id for item in self.verification_model_evidence),
        )
        if len(request_ids) != len(set(request_ids)):
            raise ValueError("Evaluation Run model requests must be fresh and unique")
        return self

    @property
    def all_model_evidence(self) -> tuple[RealModelEvidence, ...]:
        return (self.model_evidence, *self.verification_model_evidence)

    @property
    def total_model_tokens(self) -> int:
        return sum(item.total_tokens for item in self.all_model_evidence)

    @property
    def total_model_latency_ms(self) -> float:
        return sum(item.latency_ms for item in self.all_model_evidence)


def _numeric(value: object) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    return None


def _fact_matches(expected: FactExpectation, actual: ObservedFact) -> bool:
    if actual.semantic_status is not expected.semantic_status:
        return False
    if expected.semantic_status in {SemanticStatus.UNKNOWN, SemanticStatus.BLOCKED}:
        return expected.unknown_reason_contains.casefold() in (actual.unknown_reason or "").casefold()
    expected_number = _numeric(expected.expected_value)
    actual_number = _numeric(actual.value)
    if expected_number is not None and actual_number is not None:
        tolerance = Decimal(str(expected.tolerance or 0))
        return abs(expected_number - actual_number) <= tolerance
    return actual.value == expected.expected_value


class CommerceEvaluationRunner:
    """Score hidden Gold Case labels without exposing them to the Agent input."""

    def evaluate(
        self,
        evaluation_case: EvaluationCase,
        observation: EvaluationObservation,
        *,
        requires_real_model: bool,
        requires_agent_trace: bool,
        requires_semantic_evaluator: bool = False,
    ) -> EvaluationScorecard:
        if evaluation_case.case_key != observation.case_key:
            raise ValueError("Evaluation Case and observation case_key differ")
        expected = evaluation_case.expected_behavior
        failures: list[EvaluationFailure] = []
        facts = {item.name: item for item in observation.facts}
        fact_passes = 0
        for expectation in expected.required_facts:
            actual = facts.get(expectation.name)
            if actual is not None and _fact_matches(expectation, actual):
                fact_passes += 1
                continue
            failures.append(
                EvaluationFailure(
                    code=f"required-fact-{expectation.name.replace('.', '-')}",
                    category="required_fact",
                    message=f"Required Fact did not match: {expectation.name}",
                )
            )

        if observation.capabilities != expected.expected_capabilities:
            failures.append(
                EvaluationFailure(
                    code="capability-set-mismatch",
                    category="capability",
                    message="Observed Capability set differs from the Gold Case",
                )
            )
        missing_paths = expected.expected_path_agents - observation.executed_path_agents
        if missing_paths:
            failures.append(
                EvaluationFailure(
                    code="required-path-missing",
                    category="routing",
                    message=f"Required Path Agents missing: {sorted(missing_paths)}",
                )
            )
        forbidden_paths = expected.skipped_path_agents & observation.executed_path_agents
        if forbidden_paths:
            failures.append(
                EvaluationFailure(
                    code="skipped-path-executed",
                    category="routing",
                    message=f"Skipped Path Agents executed: {sorted(forbidden_paths)}",
                )
            )
        if not expected.skipped_path_agents.issubset(observation.skipped_path_agents):
            failures.append(
                EvaluationFailure(
                    code="skipped-path-not-recorded",
                    category="routing",
                    message="Expected skipped Path Agents were not recorded",
                )
            )

        for rule in expected.forbidden_claims:
            if self._matches_forbidden(rule.match_mode, rule.terms, observation.final_answer):
                failures.append(
                    EvaluationFailure(
                        code=rule.code,
                        category=rule.kind.value,
                        message=rule.description,
                    )
                )

        if expected.expected_follow_up_outcome is not None and observation.follow_up_outcome is not expected.expected_follow_up_outcome:
            failures.append(
                EvaluationFailure(
                    code="follow-up-outcome-mismatch",
                    category="follow_up",
                    message="Follow-up outcome differs from the Gold Case",
                )
            )
        for code, valid, category in (
            ("schema-invalid", observation.schema_valid, "schema"),
            ("budget-exceeded", observation.budget_within_limit, "budget"),
            ("policy-invalid", observation.policy_valid, "policy"),
        ):
            if not valid:
                failures.append(
                    EvaluationFailure(
                        code=code,
                        category=category,
                        message=f"Evaluation {category} gate failed",
                    )
                )

        if requires_agent_trace:
            trace = observation.trace
            if trace.model_assignment_count < 1:
                failures.append(
                    EvaluationFailure(
                        code="trace-model-assignment-missing",
                        category="trace",
                        message="Trace has no model assignment",
                    )
                )
            if trace.checkpoint_count < 1:
                failures.append(
                    EvaluationFailure(
                        code="trace-checkpoint-missing",
                        category="trace",
                        message="Trace has no Checkpoint",
                    )
                )
            if trace.verification_count < 1:
                failures.append(
                    EvaluationFailure(
                        code="trace-verification-missing",
                        category="trace",
                        message="Trace has no fresh Verification",
                    )
                )
            if trace.duplicate_side_effect_tool_calls:
                failures.append(
                    EvaluationFailure(
                        code="trace-duplicate-side-effect-call",
                        category="trace",
                        message="Trace contains duplicate side-effecting Tool calls",
                    )
                )
            if trace.lease_required and not trace.lease_released:
                failures.append(
                    EvaluationFailure(
                        code="trace-lease-not-released",
                        category="trace",
                        message="Trace did not release the Run lease",
                    )
                )

        if requires_real_model and not observation.real_model_evidence:
            failures.append(
                EvaluationFailure(
                    code="real-model-evidence-missing",
                    category="real_model",
                    message="Fresh DeepSeek V4 evidence is missing",
                )
            )
        if requires_semantic_evaluator and observation.semantic_evaluation_passed is not True:
            failures.append(
                EvaluationFailure(
                    code="semantic-evaluator-missing-or-failed",
                    category="semantic_evaluator",
                    message="Fresh semantic evaluation is missing or failed",
                )
            )

        fact_total = max(1, len(expected.required_facts))
        forbidden_failures = sum(
            failure.category
            in {
                "unsupported_causal",
                "unsupported_private_metric",
                "unsupported_illegal_conduct",
                "hidden_label_leakage",
                "capability_overclaim",
            }
            for failure in failures
        )
        dimensions = {
            "facts": fact_passes / fact_total,
            "capability": float(observation.capabilities == expected.expected_capabilities),
            "routing": float(not missing_paths and not forbidden_paths and expected.skipped_path_agents.issubset(observation.skipped_path_agents)),
            "safety": float(forbidden_failures == 0),
            "contracts": float(observation.schema_valid and observation.budget_within_limit and observation.policy_valid),
            "trace": float(
                not requires_agent_trace
                or (
                    observation.trace.model_assignment_count >= 1
                    and observation.trace.checkpoint_count >= 1
                    and observation.trace.verification_count >= 1
                    and observation.trace.duplicate_side_effect_tool_calls == 0
                    and (not observation.trace.lease_required or observation.trace.lease_released)
                )
            ),
            "real_model": float(not requires_real_model or bool(observation.real_model_evidence)),
            "semantic_evaluator": float(not requires_semantic_evaluator or observation.semantic_evaluation_passed is True),
        }
        passed = not failures
        return EvaluationScorecard(
            case_key=observation.case_key,
            repetition=observation.repetition,
            passed=passed,
            release_gate_eligible=(passed and (not requires_real_model or bool(observation.real_model_evidence)) and (not requires_agent_trace or dimensions["trace"] == 1)),
            dimension_scores=dimensions,
            failures=tuple(failures),
        )

    @staticmethod
    def _matches_forbidden(
        mode: MatchMode,
        terms: tuple[str, ...],
        text: str,
    ) -> bool:
        normalized = text.casefold()
        if mode is MatchMode.ANY_TERM:
            return any(term.casefold() in normalized for term in terms)
        if mode is MatchMode.ALL_TERMS:
            return all(term.casefold() in normalized for term in terms)
        return any(re.search(term, text, flags=re.IGNORECASE) is not None for term in terms)
