"""Deterministic evidence-chain contracts."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.commerce.domain.enums import SemanticStatus
from app.commerce.domain.ids import CaseId, DatasetId, DataSourceId, FactId, WorkspaceId
from app.commerce.domain.models import Evidence, EvidenceRelation, Fact, MetricObservation, SourceRef


def _source() -> SourceRef:
    return SourceRef(
        source_id=DataSourceId.new(),
        dataset_id=DatasetId.new(),
        table_name="orders",
        record_locator="order_id=order-001",
        column_name="order_delivered_customer_date",
    )


def test_observed_fact_requires_a_traceable_source():
    with pytest.raises(ValidationError, match="Observed Fact requires source"):
        Fact(
            workspace_id=WorkspaceId.new(),
            name="delivered_at",
            semantic_status=SemanticStatus.OBSERVED,
            value="2018-01-10T12:00:00Z",
        )


def test_observed_fact_accepts_source_and_value():
    fact = Fact(
        workspace_id=WorkspaceId.new(),
        name="delivered_at",
        semantic_status=SemanticStatus.OBSERVED,
        value="2018-01-10T12:00:00Z",
        source=_source(),
    )

    assert isinstance(fact.id, FactId)
    assert fact.source is not None


def test_unknown_fact_cannot_carry_a_fabricated_value():
    with pytest.raises(ValidationError, match="Unknown or blocked Fact cannot carry a value"):
        Fact(
            workspace_id=WorkspaceId.new(),
            name="ad_spend",
            semantic_status=SemanticStatus.UNKNOWN,
            value=Decimal("123.45"),
            unknown_reason="Field was not uploaded",
        )


def test_unknown_fact_requires_an_explicit_reason():
    with pytest.raises(ValidationError, match="requires unknown_reason"):
        Fact(
            workspace_id=WorkspaceId.new(),
            name="ad_spend",
            semantic_status=SemanticStatus.UNKNOWN,
            value=None,
        )


def test_derived_metric_requires_formula_version_and_source_facts():
    with pytest.raises(ValidationError, match="Derived MetricObservation requires formula_version"):
        MetricObservation(
            workspace_id=WorkspaceId.new(),
            metric_name="late_delivery_rate",
            semantic_status=SemanticStatus.DERIVED,
            value=Decimal("0.351"),
            source_fact_ids=(FactId.new(),),
        )

    with pytest.raises(ValidationError, match="requires source_fact_ids"):
        MetricObservation(
            workspace_id=WorkspaceId.new(),
            metric_name="late_delivery_rate",
            semantic_status=SemanticStatus.DERIVED,
            value=Decimal("0.351"),
            formula_version="late_delivery_rate@1.0.0",
        )


def test_unknown_metric_cannot_carry_a_value():
    with pytest.raises(ValidationError, match="Unknown or blocked MetricObservation cannot carry a value"):
        MetricObservation(
            workspace_id=WorkspaceId.new(),
            metric_name="profit_margin",
            semantic_status=SemanticStatus.UNKNOWN,
            value=Decimal("0.20"),
            unknown_reason="Profit was not uploaded",
        )


def test_evidence_must_reference_fact_or_metric():
    with pytest.raises(ValidationError, match="Evidence must reference at least one Fact or MetricObservation"):
        Evidence(
            workspace_id=WorkspaceId.new(),
            case_id=CaseId.new(),
            summary="Carrier transit time worsened",
            relation=EvidenceRelation.SUPPORTS,
            semantic_status=SemanticStatus.DERIVED,
            confidence=0.95,
        )


def test_evidence_serializes_typed_references_as_strings():
    fact_id = FactId.new()
    evidence = Evidence(
        workspace_id=WorkspaceId.new(),
        case_id=CaseId.new(),
        summary="Carrier transit time worsened",
        relation=EvidenceRelation.SUPPORTS,
        semantic_status=SemanticStatus.DERIVED,
        confidence=0.95,
        fact_ids=(fact_id,),
    )

    payload = evidence.model_dump(mode="json")

    assert payload["fact_ids"] == [str(fact_id)]
