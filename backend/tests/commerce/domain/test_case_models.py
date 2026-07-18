"""Deterministic Case, Hypothesis, and Action contracts."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.commerce.domain.enums import (
    ActionRiskLevel,
    ActionStatus,
    ApprovalStatus,
    CaseSeverity,
    CaseStatus,
    HypothesisStatus,
)
from app.commerce.domain.ids import CaseId, EvidenceId, WorkspaceId
from app.commerce.domain.models import (
    Action,
    ApprovalRequirement,
    Case,
    Hypothesis,
    RollbackPlan,
)
from app.commerce.domain.transitions import InvalidStateTransition


def _case() -> Case:
    return Case(
        workspace_id=WorkspaceId.new(),
        title="Late delivery rate increased",
        severity=CaseSeverity.HIGH,
        opened_at=datetime.now(UTC),
    )


def _rollback() -> RollbackPlan:
    return RollbackPlan(
        strategy="Close the internal task and restore the previous routing note",
        trigger="The action creates operational regressions",
        verification="Confirm the task is closed and the previous note is active",
    )


def test_hypothesis_requires_explicit_status():
    with pytest.raises(ValidationError, match="status"):
        Hypothesis(
            workspace_id=WorkspaceId.new(),
            case_id=CaseId.new(),
            statement="Carrier transit time is the primary driver",
            confidence=0.7,
        )


def test_supported_hypothesis_requires_supporting_evidence():
    with pytest.raises(ValidationError, match="Supported Hypothesis requires supporting evidence"):
        Hypothesis(
            workspace_id=WorkspaceId.new(),
            case_id=CaseId.new(),
            statement="Carrier transit time is the primary driver",
            status=HypothesisStatus.SUPPORTED,
            confidence=0.9,
        )


def test_action_requires_traceability_risk_approval_and_rollback():
    base = {
        "workspace_id": WorkspaceId.new(),
        "case_id": CaseId.new(),
        "title": "Create a carrier escalation task",
        "description": "Open an internal task for the affected delivery route",
        "status": ActionStatus.DRAFT,
    }

    with pytest.raises(ValidationError):
        Action(**base)

    with pytest.raises(ValidationError, match="at least one Evidence"):
        Action(
            **base,
            risk_level=ActionRiskLevel.LOW,
            approval=ApprovalRequirement(required=False, status=ApprovalStatus.NOT_REQUIRED),
            rollback_plan=_rollback(),
        )


def test_high_risk_action_requires_approval():
    with pytest.raises(ValidationError, match="High-risk Action requires approval"):
        Action(
            workspace_id=WorkspaceId.new(),
            case_id=CaseId.new(),
            title="Change live seller routing",
            description="Apply a production routing change",
            status=ActionStatus.DRAFT,
            evidence_ids=(EvidenceId.new(),),
            risk_level=ActionRiskLevel.HIGH,
            approval=ApprovalRequirement(required=False, status=ApprovalStatus.NOT_REQUIRED),
            rollback_plan=_rollback(),
        )


@pytest.mark.parametrize(
    "status",
    (
        ActionStatus.EXECUTING,
        ActionStatus.SUCCEEDED,
        ActionStatus.MONITORING,
        ActionStatus.EFFECTIVE,
    ),
)
def test_high_risk_action_cannot_advance_without_approved_gate(status: ActionStatus):
    with pytest.raises(ValidationError, match="approved gate"):
        Action(
            workspace_id=WorkspaceId.new(),
            case_id=CaseId.new(),
            title="Change live seller routing",
            description="Apply a production routing change",
            status=status,
            evidence_ids=(EvidenceId.new(),),
            risk_level=ActionRiskLevel.HIGH,
            approval=ApprovalRequirement(required=True, status=ApprovalStatus.PENDING),
            rollback_plan=_rollback(),
        )


def test_high_risk_action_can_execute_after_approval():
    action = Action(
        workspace_id=WorkspaceId.new(),
        case_id=CaseId.new(),
        title="Change live seller routing",
        description="Apply a production routing change",
        status=ActionStatus.EXECUTING,
        evidence_ids=(EvidenceId.new(),),
        risk_level=ActionRiskLevel.HIGH,
        approval=ApprovalRequirement(required=True, status=ApprovalStatus.APPROVED),
        rollback_plan=_rollback(),
    )

    assert action.status is ActionStatus.EXECUTING


def test_case_transition_returns_a_new_versioned_record():
    case = _case()

    triaged = case.transition_to(CaseStatus.TRIAGED)

    assert case.status is CaseStatus.NEW
    assert triaged.status is CaseStatus.TRIAGED
    assert triaged.version == case.version + 1
    assert triaged.updated_at >= case.updated_at


def test_case_transition_cannot_skip_declared_state_machine():
    case = _case()

    with pytest.raises(InvalidStateTransition):
        case.transition_to(CaseStatus.RESOLVED)
