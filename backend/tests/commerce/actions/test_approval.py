"""Deterministic multi-actor Approval state transitions."""

from datetime import UTC, datetime, timedelta

import pytest

from app.commerce.actions.approval import ApprovalRequest, ApprovalStateError
from app.commerce.actions.contracts import (
    ActionDraft,
    ActionKind,
    ExternalMutationParameters,
    ExternalOperation,
    ValidatedActionDraft,
)
from app.commerce.actions.policy import (
    ActionPolicyGate,
    ConnectorPolicy,
)
from app.commerce.domain.enums import ApprovalStatus
from app.commerce.domain.ids import (
    CaseId,
    EvidenceId,
    HypothesisId,
    MetricObservationId,
    WorkspaceId,
)
from app.commerce.domain.models import RollbackPlan


def _request() -> ApprovalRequest:
    draft = ActionDraft(
        workspace_id=WorkspaceId.new(),
        case_id=CaseId.new(),
        title="Adjust campaign budget",
        description="A reversible connector write that needs two approvals.",
        evidence_ids=(EvidenceId.new(),),
        hypothesis_ids=(HypothesisId.new(),),
        expected_signal_metric_ids=(MetricObservationId.new(),),
        parameters=ExternalMutationParameters(
            kind=ActionKind.EXTERNAL_MUTATION,
            connector_id="merchant_ads",
            operation=ExternalOperation.UPDATE_CAMPAIGN_BUDGET,
            target_ref_sha256="a" * 64,
            reversible=True,
            dry_run=False,
        ),
        rollback_plan=RollbackPlan(
            strategy="Restore the prior campaign budget",
            trigger="Approval is revoked or a guardrail fires",
            verification="Read the connector value after rollback",
        ),
    )
    validated = ValidatedActionDraft(
        draft=draft,
        validation_sha256="c" * 64,
    )
    decision = ActionPolicyGate(
        connector_policy=ConnectorPolicy(
            allowed_operations={
                "merchant_ads": frozenset(
                    {ExternalOperation.UPDATE_CAMPAIGN_BUDGET}
                )
            }
        )
    ).evaluate(validated)
    return ApprovalRequest.from_policy(
        decision,
        occurred_at=datetime(2026, 7, 19, 12, 0, tzinfo=UTC),
    )


def test_two_distinct_approvers_are_required_for_l4():
    request = _request()
    first = request.approve(
        "operator-a",
        occurred_at=request.updated_at + timedelta(minutes=1),
    )
    assert first.status is ApprovalStatus.PENDING
    assert first.approved_actor_ids == ("operator-a",)

    with pytest.raises(ApprovalStateError, match="already approved"):
        first.approve(
            "operator-a",
            occurred_at=first.updated_at + timedelta(minutes=1),
        )

    second = first.approve(
        "operator-b",
        occurred_at=first.updated_at + timedelta(minutes=2),
    )
    assert second.status is ApprovalStatus.APPROVED
    assert second.approved_actor_ids == ("operator-a", "operator-b")
    assert second.version == request.version + 2


def test_reject_and_modify_are_terminal_and_auditable():
    request = _request()
    rejected = request.reject(
        "operator-a",
        occurred_at=request.updated_at + timedelta(minutes=1),
    )
    assert rejected.status is ApprovalStatus.REJECTED
    assert rejected.rejected_actor_id == "operator-a"
    with pytest.raises(ApprovalStateError, match="terminal"):
        rejected.approve(
            "operator-b",
            occurred_at=rejected.updated_at + timedelta(minutes=1),
        )

    modified = _request().modify(
        "operator-c",
        replacement_draft_sha256="b" * 64,
        occurred_at=request.updated_at + timedelta(minutes=2),
    )
    assert modified.status is ApprovalStatus.REVOKED
    assert modified.modified_by_actor_id == "operator-c"
    assert modified.replacement_draft_sha256 == "b" * 64
