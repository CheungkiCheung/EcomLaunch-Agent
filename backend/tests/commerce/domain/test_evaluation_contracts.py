"""Deterministic contracts that keep Gold Case inputs and labels isolated."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from app.commerce.domain.enums import SemanticStatus
from app.commerce.domain.evaluation import (
    CapabilityAblation,
    EvaluationAnalysisRequest,
    EvaluationCase,
    EvaluationWindow,
    ExpectedBehavior,
    FactExpectation,
    ForbiddenClaim,
    ForbiddenClaimKind,
    InputBundle,
    InputFile,
    MatchMode,
)


def _input_file() -> InputFile:
    return InputFile(
        name="orders",
        relative_path="data/orders.csv",
        table_name="orders",
        sha256="0" * 64,
        row_count=10,
        columns=("order_id", "seller_id"),
    )


def _required_fact() -> FactExpectation:
    return FactExpectation(
        name="late_delivery_rate",
        semantic_status=SemanticStatus.DERIVED,
        expected_value=0.351,
        tolerance=0.001,
    )


def _forbidden_claim() -> ForbiddenClaim:
    return ForbiddenClaim(
        code="no-seller-handling-blame",
        kind=ForbiddenClaimKind.UNSUPPORTED_CAUSAL,
        description="Do not blame seller handling when handling time did not worsen",
        match_mode=MatchMode.ANY_TERM,
        terms=("seller handling caused", "seller dispatch capacity caused"),
    )


def test_expected_behavior_requires_at_least_one_required_fact():
    with pytest.raises(ValidationError, match="required_facts"):
        ExpectedBehavior(
            required_facts=(),
            forbidden_claims=(_forbidden_claim(),),
            expected_capabilities=frozenset({"fulfillment_diagnosis"}),
        )


def test_hidden_labels_cannot_be_added_to_input_bundle():
    with pytest.raises(ValidationError, match="hidden_labels"):
        InputBundle(
            files=(_input_file(),),
            user_prompt="Investigate the delivery anomaly",
            hidden_labels={"root_cause": "carrier_transit"},
        )


def test_agent_visible_analysis_request_requires_ordered_non_overlapping_windows():
    with pytest.raises(ValidationError, match="Baseline window must end"):
        EvaluationAnalysisRequest(
            seller_id="seller-1",
            baseline_window=EvaluationWindow(
                start=datetime(2018, 1, 1),
                end=datetime(2018, 3, 1),
            ),
            anomaly_window=EvaluationWindow(
                start=datetime(2018, 2, 1),
                end=datetime(2018, 4, 1),
            ),
        )


def test_agent_visible_analysis_request_is_input_not_hidden_label():
    request = EvaluationAnalysisRequest(
        seller_id="seller-1",
        baseline_window=EvaluationWindow(
            start=datetime(2018, 1, 1),
            end=datetime(2018, 2, 1),
        ),
        anomaly_window=EvaluationWindow(
            start=datetime(2018, 2, 1),
            end=datetime(2018, 3, 1),
        ),
        follow_up_window=EvaluationWindow(
            start=datetime(2018, 3, 1),
            end=datetime(2018, 4, 1),
        ),
        controlled_intervention_observed=False,
        comparison_group_observed=False,
    )
    bundle = InputBundle(
        schema_version="1.1",
        files=(_input_file(),),
        user_prompt="Investigate the delivery anomaly",
        analysis_request=request,
    )

    payload = bundle.model_dump(mode="json")

    assert payload["analysis_request"]["seller_id"] == "seller-1"
    assert "expected_behavior" not in payload
    assert "forbidden_claims" not in payload


def test_forbidden_claim_requires_machine_readable_terms():
    with pytest.raises(ValidationError, match="terms"):
        ForbiddenClaim(
            code="no-confirmed-fraud",
            kind=ForbiddenClaimKind.UNSUPPORTED_ILLEGAL_CONDUCT,
            description="Do not confirm fraud from review text",
            match_mode=MatchMode.ANY_TERM,
            terms=(),
        )


def test_capability_ablation_must_change_capabilities():
    with pytest.raises(ValidationError, match="must change the capability set"):
        CapabilityAblation(
            removed_files=("reviews",),
            baseline_capabilities=frozenset({"fulfillment_diagnosis"}),
            expected_capabilities=frozenset({"fulfillment_diagnosis"}),
        )


def test_capability_ablation_records_removed_capability():
    ablation = CapabilityAblation(
        removed_files=("reviews",),
        baseline_capabilities=frozenset({"fulfillment_diagnosis", "review_experience"}),
        expected_capabilities=frozenset({"fulfillment_diagnosis"}),
    )

    assert ablation.removed_capabilities == frozenset({"review_experience"})


def test_input_payload_is_structurally_isolated_from_expected_behavior():
    evaluation_case = EvaluationCase(
        case_key="GC-FULFILLMENT-001",
        title="Carrier transit degradation",
        input_bundle=InputBundle(
            files=(_input_file(),),
            user_prompt="Investigate the delivery anomaly",
        ),
        expected_behavior=ExpectedBehavior(
            required_facts=(_required_fact(),),
            forbidden_claims=(_forbidden_claim(),),
            expected_capabilities=frozenset({"fulfillment_diagnosis"}),
        ),
    )

    agent_input = evaluation_case.input_bundle.model_dump(mode="json")

    assert "expected_behavior" not in agent_input
    assert "required_facts" not in agent_input
    assert "forbidden_claims" not in agent_input
