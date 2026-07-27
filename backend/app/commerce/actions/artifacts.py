"""Versioned internal Action artifacts and connector verification receipts."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from app.commerce.actions.contracts import MetricComparison
from app.commerce.domain.ids import (
    ActionId,
    CaseId,
    EvidenceId,
    MetricObservationId,
    WorkspaceId,
)
from app.commerce.domain.models import CommerceModel


class ActionArtifactKind(StrEnum):
    NO_OP_RECEIPT = "no_op_receipt"
    AUDIT_EXPORT = "audit_export"
    INTERNAL_TASK = "internal_task"
    METRIC_MONITOR = "metric_monitor"
    DATA_REQUEST = "data_request"


class ActionArtifactStatus(StrEnum):
    COMPLETED = "completed"
    AVAILABLE = "available"
    OPEN = "open"
    ACTIVE = "active"
    CANCELLED = "cancelled"
    DISABLED = "disabled"
    ARCHIVED = "archived"


class AuditCohortRow(CommerceModel):
    evidence_id: EvidenceId
    summary: str = Field(min_length=1, max_length=2_000)
    confidence: float = Field(ge=0.0, le=1.0)
    metric_observation_ids: tuple[MetricObservationId, ...] = ()


class NoOpReceiptArtifact(CommerceModel):
    kind: Literal[ActionArtifactKind.NO_OP_RECEIPT] = ActionArtifactKind.NO_OP_RECEIPT
    reason: str = Field(min_length=1)


class AuditExportArtifact(CommerceModel):
    kind: Literal[ActionArtifactKind.AUDIT_EXPORT] = ActionArtifactKind.AUDIT_EXPORT
    format: Literal["csv", "jsonl"]
    relative_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    row_count: int = Field(ge=0)
    include_direct_identifiers: Literal[False] = False

    @model_validator(mode="after")
    def require_safe_relative_path(self) -> Self:
        path = PurePosixPath(self.relative_path)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Audit export path must remain relative and traversal-free")
        return self


class InternalTaskArtifact(CommerceModel):
    kind: Literal[ActionArtifactKind.INTERNAL_TASK] = ActionArtifactKind.INTERNAL_TASK
    owner_role: str = Field(min_length=1, max_length=64)
    due_at: datetime
    checklist: tuple[str, ...] = Field(min_length=1, max_length=10)


class MetricMonitorArtifact(CommerceModel):
    kind: Literal[ActionArtifactKind.METRIC_MONITOR] = ActionArtifactKind.METRIC_MONITOR
    metric_name: str = Field(min_length=1)
    metric_observation_ids: tuple[MetricObservationId, ...] = Field(min_length=1)
    comparison: MetricComparison
    threshold: Decimal
    cadence_hours: int = Field(ge=1, le=168)
    follow_up_after_days: int = Field(ge=1, le=365)
    next_evaluation_at: datetime


class DataRequestArtifact(CommerceModel):
    kind: Literal[ActionArtifactKind.DATA_REQUEST] = ActionArtifactKind.DATA_REQUEST
    missing_fields: tuple[str, ...] = Field(min_length=1, max_length=20)
    due_at: datetime


ActionArtifactPayload = Annotated[
    NoOpReceiptArtifact | AuditExportArtifact | InternalTaskArtifact | MetricMonitorArtifact | DataRequestArtifact,
    Field(discriminator="kind"),
]


_INITIAL_STATUS = {
    ActionArtifactKind.NO_OP_RECEIPT: ActionArtifactStatus.COMPLETED,
    ActionArtifactKind.AUDIT_EXPORT: ActionArtifactStatus.AVAILABLE,
    ActionArtifactKind.INTERNAL_TASK: ActionArtifactStatus.OPEN,
    ActionArtifactKind.METRIC_MONITOR: ActionArtifactStatus.ACTIVE,
    ActionArtifactKind.DATA_REQUEST: ActionArtifactStatus.OPEN,
}

_ROLLBACK_STATUS = {
    ActionArtifactKind.NO_OP_RECEIPT: ActionArtifactStatus.ARCHIVED,
    ActionArtifactKind.AUDIT_EXPORT: ActionArtifactStatus.ARCHIVED,
    ActionArtifactKind.INTERNAL_TASK: ActionArtifactStatus.CANCELLED,
    ActionArtifactKind.METRIC_MONITOR: ActionArtifactStatus.DISABLED,
    ActionArtifactKind.DATA_REQUEST: ActionArtifactStatus.CANCELLED,
}


class ActionExecutionArtifact(CommerceModel):
    schema_version: str = "commerce.action-execution-artifact@1.0.0"
    workspace_id: WorkspaceId
    case_id: CaseId
    action_id: ActionId
    execution_tool: str = Field(min_length=1)
    payload: ActionArtifactPayload
    status: ActionArtifactStatus
    execution_input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    verification_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    version: int = Field(default=1, ge=1)

    @property
    def kind(self) -> ActionArtifactKind:
        return self.payload.kind

    @model_validator(mode="after")
    def keep_status_consistent(self) -> Self:
        allowed = {_INITIAL_STATUS[self.kind], _ROLLBACK_STATUS[self.kind]}
        if self.status not in allowed:
            raise ValueError(f"Artifact {self.kind.value} cannot use status {self.status.value}")
        if self.updated_at < self.created_at:
            raise ValueError("Artifact updated_at cannot precede created_at")
        return self

    def rolled_back(
        self,
        *,
        payload: ActionArtifactPayload | None = None,
        verification_sha256: str,
        occurred_at: datetime,
    ) -> Self:
        if self.status is _ROLLBACK_STATUS[self.kind]:
            return self
        if self.status is not _INITIAL_STATUS[self.kind]:
            raise ValueError("Artifact is not in a rollback-eligible state")
        return ActionExecutionArtifact.model_validate(
            {
                **self.model_dump(mode="python"),
                "payload": payload or self.payload,
                "status": _ROLLBACK_STATUS[self.kind],
                "verification_sha256": verification_sha256,
                "updated_at": max(occurred_at, self.updated_at),
                "version": self.version + 1,
            }
        )


class ConnectorVerification(CommerceModel):
    schema_version: str = "commerce.connector-verification@1.0.0"
    passed: bool
    checks: tuple[str, ...] = Field(min_length=1)
    verification_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class InternalConnectorResult(CommerceModel):
    artifact: ActionExecutionArtifact
    verification: ConnectorVerification

    @model_validator(mode="after")
    def match_verification(self) -> Self:
        if self.artifact.verification_sha256 != self.verification.verification_sha256:
            raise ValueError("Artifact and connector verification hashes differ")
        return self
