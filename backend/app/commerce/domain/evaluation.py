"""Gold Case contracts with structural separation between input and labels."""

from __future__ import annotations

from enum import StrEnum
from pathlib import PurePosixPath
from typing import Literal, Self

from pydantic import Field, model_validator

from app.commerce.domain.enums import FollowUpOutcome, SemanticStatus
from app.commerce.domain.ids import EvaluationCaseId
from app.commerce.domain.models import CommerceModel, ScalarValue


class InputFile(CommerceModel):
    """Immutable manifest entry for one small evaluation input table."""

    name: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    table_name: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    row_count: int = Field(ge=1)
    columns: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def require_safe_relative_path(self) -> Self:
        path = PurePosixPath(self.relative_path)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("InputFile relative_path must stay inside the input bundle")
        return self


class InputBundle(CommerceModel):
    """The only evaluation payload that may be exposed to an Agent run."""

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    source_type: Literal["public_benchmark_fixture"] = "public_benchmark_fixture"
    not_a_live_merchant_integration: Literal[True] = True
    files: tuple[InputFile, ...] = Field(min_length=1)
    user_prompt: str = Field(min_length=1)
    declared_missing_fields: tuple[str, ...] = Field(default_factory=tuple)


class FactExpectation(CommerceModel):
    """Hidden machine-readable fact assertion used by deterministic scorers."""

    name: str = Field(min_length=1)
    semantic_status: SemanticStatus
    expected_value: ScalarValue | None = None
    tolerance: float | None = Field(default=None, ge=0.0)
    unknown_reason_contains: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def keep_unknown_expectation_value_free(self) -> Self:
        if self.semantic_status in {SemanticStatus.UNKNOWN, SemanticStatus.BLOCKED}:
            if self.expected_value is not None:
                raise ValueError("Unknown FactExpectation cannot carry expected_value")
            if self.unknown_reason_contains is None:
                raise ValueError("Unknown FactExpectation requires unknown_reason_contains")
        elif self.expected_value is None:
            raise ValueError("Known FactExpectation requires expected_value")
        return self


class ForbiddenClaimKind(StrEnum):
    UNSUPPORTED_CAUSAL = "unsupported_causal"
    UNSUPPORTED_PRIVATE_METRIC = "unsupported_private_metric"
    UNSUPPORTED_ILLEGAL_CONDUCT = "unsupported_illegal_conduct"
    HIDDEN_LABEL_LEAKAGE = "hidden_label_leakage"
    CAPABILITY_OVERCLAIM = "capability_overclaim"


class MatchMode(StrEnum):
    ANY_TERM = "any_term"
    ALL_TERMS = "all_terms"
    REGEX = "regex"


class ForbiddenClaim(CommerceModel):
    """Machine-readable rule for claims that must fail an evaluation."""

    code: str = Field(min_length=1, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    kind: ForbiddenClaimKind
    description: str = Field(min_length=1)
    match_mode: MatchMode
    terms: tuple[str, ...] = Field(min_length=1)


class CapabilityAblation(CommerceModel):
    """Expected capability change after removing one or more inputs."""

    removed_files: tuple[str, ...] = Field(min_length=1)
    baseline_capabilities: frozenset[str] = Field(min_length=1)
    expected_capabilities: frozenset[str]

    @model_validator(mode="after")
    def require_changed_capabilities(self) -> Self:
        if self.baseline_capabilities == self.expected_capabilities:
            raise ValueError("Capability ablation must change the capability set")
        return self

    @property
    def removed_capabilities(self) -> frozenset[str]:
        return self.baseline_capabilities - self.expected_capabilities


class ExpectedBehavior(CommerceModel):
    """Hidden labels and gates that never enter an Agent InputBundle."""

    required_facts: tuple[FactExpectation, ...] = Field(min_length=1)
    forbidden_claims: tuple[ForbiddenClaim, ...] = Field(min_length=1)
    expected_capabilities: frozenset[str] = Field(min_length=1)
    expected_path_agents: frozenset[str] = Field(default_factory=frozenset)
    skipped_path_agents: frozenset[str] = Field(default_factory=frozenset)
    capability_ablation: CapabilityAblation | None = None
    expected_follow_up_outcome: FollowUpOutcome | None = None


class EvaluationCase(CommerceModel):
    """Versioned Gold Case containing isolated input and expected behavior."""

    id: EvaluationCaseId = Field(default_factory=EvaluationCaseId.new)
    case_key: str = Field(pattern=r"^GC-[A-Z]+-\d{3}$")
    version: str = Field(default="1.0.0", pattern=r"^\d+\.\d+\.\d+$")
    title: str = Field(min_length=1)
    input_bundle: InputBundle
    expected_behavior: ExpectedBehavior
