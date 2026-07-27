"""Immutable Approval request and idempotent human decision contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from app.commerce.actions.contracts import ActionDraft
from app.commerce.actions.policy import (
    ActionPolicyDecision,
    ActionPolicyDisposition,
)
from app.commerce.domain.enums import ApprovalStatus
from app.commerce.domain.ids import (
    ActionId,
    ApprovalDecisionId,
    ApprovalId,
    CaseId,
    WorkspaceId,
)
from app.commerce.domain.models import CommerceModel


class ApprovalDecisionType(StrEnum):
    APPROVE = "approve"
    MODIFY = "modify"
    REJECT = "reject"


class ApprovalStateError(ValueError):
    pass


class ApprovalRequest(CommerceModel):
    schema_version: str = "commerce.approval-request@1.0.0"
    id: ApprovalId = Field(default_factory=ApprovalId.new)
    workspace_id: WorkspaceId
    case_id: CaseId
    action_id: ActionId
    required_approvals: int = Field(ge=1, le=2)
    status: ApprovalStatus = ApprovalStatus.PENDING
    approved_actor_ids: tuple[str, ...] = ()
    rejected_actor_id: str | None = Field(default=None, min_length=1)
    modified_by_actor_id: str | None = Field(default=None, min_length=1)
    replacement_draft_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    version: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def keep_projection_consistent(self) -> Self:
        if len(self.approved_actor_ids) != len(set(self.approved_actor_ids)):
            raise ValueError("Approval actors must be unique")
        if len(self.approved_actor_ids) > self.required_approvals:
            raise ValueError("Approval actor count exceeds the requirement")
        if self.status is ApprovalStatus.PENDING:
            if (
                len(self.approved_actor_ids) >= self.required_approvals
                or self.rejected_actor_id is not None
                or self.modified_by_actor_id is not None
            ):
                raise ValueError("Pending Approval projection is inconsistent")
        elif self.status is ApprovalStatus.APPROVED:
            if len(self.approved_actor_ids) != self.required_approvals:
                raise ValueError("Approved request requires all approvals")
        elif self.status is ApprovalStatus.REJECTED:
            if self.rejected_actor_id is None:
                raise ValueError("Rejected request requires an actor")
        elif self.status is ApprovalStatus.REVOKED:
            if (
                self.modified_by_actor_id is None
                or self.replacement_draft_sha256 is None
            ):
                raise ValueError("Modified request requires replacement draft audit")
        return self

    @classmethod
    def from_policy(
        cls,
        decision: ActionPolicyDecision,
        *,
        occurred_at: datetime | None = None,
    ) -> Self:
        if decision.disposition is not ActionPolicyDisposition.APPROVAL_REQUIRED:
            raise ValueError("Only approval-required Actions create requests")
        draft = decision.validated.draft
        now = occurred_at or datetime.now(UTC)
        return cls(
            workspace_id=draft.workspace_id,
            case_id=draft.case_id,
            action_id=draft.id,
            required_approvals=decision.required_approvals,
            created_at=now,
            updated_at=now,
        )

    def approve(self, actor_id: str, *, occurred_at: datetime) -> Self:
        self._require_pending(actor_id)
        actors = (*self.approved_actor_ids, actor_id)
        status = (
            ApprovalStatus.APPROVED
            if len(actors) == self.required_approvals
            else ApprovalStatus.PENDING
        )
        return self.model_copy(
            update={
                "status": status,
                "approved_actor_ids": actors,
                "updated_at": max(occurred_at, self.updated_at),
                "version": self.version + 1,
            }
        )

    def reject(self, actor_id: str, *, occurred_at: datetime) -> Self:
        self._require_pending(actor_id)
        return self.model_copy(
            update={
                "status": ApprovalStatus.REJECTED,
                "rejected_actor_id": actor_id,
                "updated_at": max(occurred_at, self.updated_at),
                "version": self.version + 1,
            }
        )

    def modify(
        self,
        actor_id: str,
        *,
        replacement_draft_sha256: str,
        occurred_at: datetime,
    ) -> Self:
        self._require_pending(actor_id)
        return self.model_copy(
            update={
                "status": ApprovalStatus.REVOKED,
                "modified_by_actor_id": actor_id,
                "replacement_draft_sha256": replacement_draft_sha256,
                "updated_at": max(occurred_at, self.updated_at),
                "version": self.version + 1,
            }
        )

    def _require_pending(self, actor_id: str) -> None:
        if not actor_id.strip():
            raise ApprovalStateError("Approval actor ID cannot be empty")
        if self.status is not ApprovalStatus.PENDING:
            raise ApprovalStateError("Approval request is already terminal")
        if actor_id in self.approved_actor_ids:
            raise ApprovalStateError("Actor has already approved this request")


class ApprovalDecisionCommand(CommerceModel):
    schema_version: str = "commerce.approval-decision@1.0.0"
    id: ApprovalDecisionId = Field(default_factory=ApprovalDecisionId.new)
    workspace_id: WorkspaceId
    case_id: CaseId
    action_id: ActionId
    approval_id: ApprovalId
    decision: ApprovalDecisionType
    actor_id: str = Field(min_length=1, max_length=128)
    idempotency_key_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reason: str | None = Field(default=None, min_length=1, max_length=1_000)
    replacement_draft: ActionDraft | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def keep_decision_payload_consistent(self) -> Self:
        if self.decision is ApprovalDecisionType.MODIFY:
            if self.replacement_draft is None:
                raise ValueError("Modify decision requires a replacement Action Draft")
            if (
                self.replacement_draft.workspace_id != self.workspace_id
                or self.replacement_draft.case_id != self.case_id
            ):
                raise ValueError("Replacement Action Draft must remain in the Case")
        elif self.replacement_draft is not None:
            raise ValueError("Only modify may carry a replacement Action Draft")
        return self
