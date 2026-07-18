"""Deterministic contracts for Commerce domain foundations."""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from app.commerce.domain.enums import (
    ActionStatus,
    ApprovalStatus,
    CaseStatus,
    FollowUpOutcome,
    RunPhase,
    RunType,
    SemanticStatus,
)
from app.commerce.domain.ids import CaseId, EvidenceId
from app.commerce.domain.transitions import InvalidStateTransition, transition_case_status


@pytest.mark.parametrize(
    "enum_type",
    (
        SemanticStatus,
        CaseStatus,
        RunType,
        RunPhase,
        ActionStatus,
        ApprovalStatus,
        FollowUpOutcome,
    ),
)
def test_domain_enums_reject_unknown_values(enum_type):
    with pytest.raises(ValueError):
        enum_type("invented-status")


def test_typed_ids_are_prefixed_and_not_interchangeable():
    case_id = CaseId.new()
    evidence_id = EvidenceId.new()

    assert case_id.startswith("case_")
    assert evidence_id.startswith("evd_")
    assert case_id != evidence_id

    with pytest.raises(ValueError):
        CaseId(str(evidence_id))


@pytest.mark.parametrize(
    "value",
    (
        "case_",
        "case_not-a-uuid",
        "case_1234",
        "CASE_0123456789abcdef0123456789abcdef",
        "  case_0123456789abcdef0123456789abcdef",
    ),
)
def test_typed_ids_reject_malformed_values(value: str):
    with pytest.raises(ValueError):
        CaseId(value)


def test_typed_ids_validate_inside_pydantic_models():
    adapter = TypeAdapter(CaseId)

    parsed = adapter.validate_python("case_0123456789abcdef0123456789abcdef")

    assert isinstance(parsed, CaseId)
    assert str(parsed) == "case_0123456789abcdef0123456789abcdef"

    with pytest.raises(ValidationError):
        adapter.validate_python("evd_0123456789abcdef0123456789abcdef")


def test_case_transition_requires_explicit_reopen():
    assert transition_case_status(CaseStatus.NEW, CaseStatus.TRIAGED) is CaseStatus.TRIAGED
    assert transition_case_status(CaseStatus.RESOLVED, CaseStatus.REOPENED) is CaseStatus.REOPENED
    assert transition_case_status(CaseStatus.REOPENED, CaseStatus.INVESTIGATING) is CaseStatus.INVESTIGATING

    with pytest.raises(InvalidStateTransition):
        transition_case_status(CaseStatus.RESOLVED, CaseStatus.INVESTIGATING)


def test_cancelled_case_is_terminal():
    with pytest.raises(InvalidStateTransition):
        transition_case_status(CaseStatus.CANCELLED, CaseStatus.REOPENED)
