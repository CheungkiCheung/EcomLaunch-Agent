"""Hard-gated Pareto experiment contracts and immutable file registry."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from statistics import mean
from typing import Self

from pydantic import Field, model_validator

from app.commerce.domain.ids import ExperimentId
from app.commerce.domain.models import CommerceModel
from app.commerce.evaluation.runner import EvaluationObservation, EvaluationRunRecord


class ExperimentDecision(StrEnum):
    PROMOTE_CANDIDATE = "promote_candidate"
    HOLD = "hold"
    REJECT_CANDIDATE = "reject_candidate"


class ExperimentVariant(CommerceModel):
    name: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_-]*$")
    prompt_version: str = Field(min_length=1)
    context_version: str = Field(min_length=1)
    router_version: str = Field(min_length=1)
    skill_version: str = Field(min_length=1)
    skill_content_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )


class ExperimentDefinition(CommerceModel):
    schema_version: str = "commerce.experiment@1.0.0"
    id: ExperimentId = Field(default_factory=ExperimentId.new)
    title: str = Field(min_length=1, max_length=200)
    hypothesis: str = Field(min_length=1, max_length=2_000)
    control: ExperimentVariant
    candidate: ExperimentVariant
    case_keys: tuple[str, ...] = Field(min_length=1)
    repetitions: int = Field(ge=2, le=20)
    controlled_variables: tuple[str, ...] = Field(min_length=1)
    reproduction_command: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def require_distinct_variants(self) -> Self:
        if self.control.name == self.candidate.name:
            raise ValueError("Experiment variants must have distinct names")
        if len(self.case_keys) != len(set(self.case_keys)):
            raise ValueError("Experiment case keys must be unique")
        return self


class VariantAggregate(CommerceModel):
    variant_name: str
    run_count: int = Field(ge=1)
    passed_count: int = Field(ge=0)
    hard_gate_failures: int = Field(ge=0)
    pass_rate: float = Field(ge=0, le=1)
    mean_total_tokens: float = Field(ge=0)
    mean_latency_ms: float = Field(ge=0)


class ExperimentReport(CommerceModel):
    schema_version: str = "commerce.experiment-report@1.0.0"
    experiment_id: ExperimentId
    control: VariantAggregate
    candidate: VariantAggregate
    decision: ExperimentDecision
    reasons: tuple[str, ...] = Field(min_length=1)
    provider_request_ids: tuple[str, ...] = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ExperimentComparator:
    """Apply release hard gates before evaluating the quality/cost Pareto frontier."""

    def compare(
        self,
        definition: ExperimentDefinition,
        records: Sequence[EvaluationRunRecord],
    ) -> ExperimentReport:
        grouped: dict[str, list[EvaluationRunRecord]] = defaultdict(list)
        for record in records:
            if record.experiment_id != definition.id:
                raise ValueError("Evaluation Run belongs to another Experiment")
            grouped[record.variant_name].append(record)
        expected_runs = len(definition.case_keys) * definition.repetitions
        expected_variants = {definition.control.name, definition.candidate.name}
        if set(grouped) != expected_variants:
            raise ValueError("Experiment records do not contain exactly two variants")
        for variant_name, values in grouped.items():
            identities = {(item.case_key, item.repetition) for item in values}
            expected_identities = {(case_key, repetition) for case_key in definition.case_keys for repetition in range(1, definition.repetitions + 1)}
            if len(values) != expected_runs or identities != expected_identities:
                raise ValueError(f"Experiment variant {variant_name} has incomplete repetitions")
        request_ids = tuple(evidence.provider_request_id for record in records for evidence in record.all_model_evidence)
        if len(request_ids) != len(set(request_ids)):
            raise ValueError("Experiment requires a fresh unique Provider request per run")

        control = self._aggregate(definition.control.name, grouped[definition.control.name])
        candidate = self._aggregate(
            definition.candidate.name,
            grouped[definition.candidate.name],
        )
        reasons: list[str] = []
        if candidate.hard_gate_failures:
            decision = ExperimentDecision.REJECT_CANDIDATE
            reasons.append(f"Candidate has {candidate.hard_gate_failures} release hard-gate failures")
        elif candidate.pass_rate < control.pass_rate:
            decision = ExperimentDecision.REJECT_CANDIDATE
            reasons.append("Candidate Gold Case pass rate regressed")
        else:
            token_ratio = candidate.mean_total_tokens / max(
                control.mean_total_tokens,
                1,
            )
            latency_ratio = candidate.mean_latency_ms / max(
                control.mean_latency_ms,
                1,
            )
            if token_ratio > 1.10 or latency_ratio > 1.20:
                decision = ExperimentDecision.HOLD
                reasons.append("Candidate is outside the permitted token or latency Pareto envelope")
            else:
                quality_better = candidate.pass_rate > control.pass_rate
                token_better = token_ratio <= 0.95
                latency_better = latency_ratio <= 0.95
                if quality_better or token_better or latency_better:
                    decision = ExperimentDecision.PROMOTE_CANDIDATE
                    reasons.append("Candidate passes all hard gates and improves the Pareto frontier")
                else:
                    decision = ExperimentDecision.HOLD
                    reasons.append("Candidate is safe but does not materially improve quality, tokens, or latency")
        return ExperimentReport(
            experiment_id=definition.id,
            control=control,
            candidate=candidate,
            decision=decision,
            reasons=tuple(reasons),
            provider_request_ids=request_ids,
        )

    @staticmethod
    def _aggregate(
        variant_name: str,
        records: Sequence[EvaluationRunRecord],
    ) -> VariantAggregate:
        passed = sum(record.scorecard.passed for record in records)
        hard_failures = sum(not record.scorecard.release_gate_eligible for record in records)
        return VariantAggregate(
            variant_name=variant_name,
            run_count=len(records),
            passed_count=passed,
            hard_gate_failures=hard_failures,
            pass_rate=passed / len(records),
            mean_total_tokens=mean(record.total_model_tokens for record in records),
            mean_latency_ms=mean(record.total_model_latency_ms for record in records),
        )


class ExperimentRegistry:
    """Persist definitions and reports immutably; never overwrite evidence."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def register(self, definition: ExperimentDefinition) -> Path:
        return self._write_new(
            self._root / "definitions" / f"{definition.id}.json",
            definition.model_dump(mode="json"),
        )

    def record_report(self, report: ExperimentReport) -> Path:
        return self._write_new(
            self._root / "reports" / f"{report.experiment_id}.json",
            report.model_dump(mode="json"),
        )

    def record_run(
        self,
        record: EvaluationRunRecord,
        *,
        raw_output: str,
        observation: EvaluationObservation,
        trace_payload: dict,
        semantic_evaluation_payload: dict,
    ) -> Path:
        return self._write_new(
            self._root / "runs" / str(record.experiment_id) / record.variant_name / record.case_key / f"{record.repetition:02d}-{record.id}.json",
            {
                "schema_version": "commerce.experiment-run-audit@1.0.0",
                "record": record.model_dump(mode="json"),
                "raw_output": raw_output,
                "observation": observation.model_dump(mode="json"),
                "trace": trace_payload,
                "semantic_evaluation": semantic_evaluation_payload,
            },
        )

    @staticmethod
    def _write_new(path: Path, payload: dict) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        return path
