"""Versioned structured contracts for proposed and validated Commerce Actions."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from app.commerce.domain.ids import (
    ActionId,
    CaseId,
    EvidenceId,
    HypothesisId,
    MetricObservationId,
    WorkspaceId,
)
from app.commerce.domain.models import CommerceModel, RollbackPlan


class ActionKind(StrEnum):
    NO_OP = "no_op"
    EXPORT_AUDIT_COHORT = "export_audit_cohort"
    CREATE_INTERNAL_TASK = "create_internal_task"
    CREATE_METRIC_MONITOR = "create_metric_monitor"
    REQUEST_MISSING_DATA = "request_missing_data"
    EXTERNAL_MUTATION = "external_mutation"


class MetricComparison(StrEnum):
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"


class ExternalOperation(StrEnum):
    SEND_MERCHANT_MESSAGE = "send_merchant_message"
    UPDATE_CAMPAIGN_BUDGET = "update_campaign_budget"
    UPDATE_PRICE = "update_price"
    UPDATE_INVENTORY = "update_inventory"
    PAUSE_LISTING = "pause_listing"
    DELETE_LISTING = "delete_listing"
    ISSUE_REFUND = "issue_refund"
    SUSPEND_SELLER = "suspend_seller"


class NoOpParameters(CommerceModel):
    kind: Literal[ActionKind.NO_OP] = ActionKind.NO_OP
    reason: str = Field(min_length=1)


class AuditExportParameters(CommerceModel):
    kind: Literal[ActionKind.EXPORT_AUDIT_COHORT] = (
        ActionKind.EXPORT_AUDIT_COHORT
    )
    format: Literal["csv", "jsonl"] = "csv"
    max_rows: int = Field(default=1_000, ge=1, le=5_000)
    include_direct_identifiers: Literal[False] = False


class InternalTaskParameters(CommerceModel):
    kind: Literal[ActionKind.CREATE_INTERNAL_TASK] = ActionKind.CREATE_INTERNAL_TASK
    owner_role: str = Field(min_length=1, max_length=64)
    due_days: int = Field(ge=1, le=30)
    checklist: tuple[str, ...] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def keep_checklist_unique(self) -> Self:
        if len(self.checklist) != len(set(self.checklist)):
            raise ValueError("Internal task checklist items must be unique")
        return self


class MetricMonitorParameters(CommerceModel):
    kind: Literal[ActionKind.CREATE_METRIC_MONITOR] = (
        ActionKind.CREATE_METRIC_MONITOR
    )
    metric_name: str = Field(min_length=1)
    metric_observation_ids: tuple[MetricObservationId, ...] = Field(min_length=1)
    comparison: MetricComparison
    threshold: Decimal
    cadence_hours: int = Field(ge=1, le=168)
    follow_up_after_days: int = Field(ge=1, le=365)

    @model_validator(mode="after")
    def keep_metric_ids_unique(self) -> Self:
        if len(self.metric_observation_ids) != len(
            set(self.metric_observation_ids)
        ):
            raise ValueError("Metric monitor references must be unique")
        return self


class DataRequestParameters(CommerceModel):
    kind: Literal[ActionKind.REQUEST_MISSING_DATA] = ActionKind.REQUEST_MISSING_DATA
    missing_fields: tuple[str, ...] = Field(min_length=1, max_length=20)
    due_days: int = Field(ge=1, le=30)

    @model_validator(mode="after")
    def keep_fields_unique(self) -> Self:
        if len(self.missing_fields) != len(set(self.missing_fields)):
            raise ValueError("Requested data fields must be unique")
        return self


class ExternalMutationParameters(CommerceModel):
    kind: Literal[ActionKind.EXTERNAL_MUTATION] = ActionKind.EXTERNAL_MUTATION
    connector_id: str = Field(min_length=1, max_length=128)
    operation: ExternalOperation
    target_ref_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reversible: bool
    dry_run: bool


ActionParameters = Annotated[
    NoOpParameters
    | AuditExportParameters
    | InternalTaskParameters
    | MetricMonitorParameters
    | DataRequestParameters
    | ExternalMutationParameters,
    Field(discriminator="kind"),
]


class ActionDraft(CommerceModel):
    schema_version: str = "commerce.action-draft@1.0.0"
    id: ActionId = Field(default_factory=ActionId.new)
    workspace_id: WorkspaceId
    case_id: CaseId
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2_000)
    evidence_ids: tuple[EvidenceId, ...] = Field(min_length=1)
    hypothesis_ids: tuple[HypothesisId, ...] = Field(min_length=1)
    expected_signal_metric_ids: tuple[MetricObservationId, ...] = Field(
        min_length=1
    )
    parameters: ActionParameters
    rollback_plan: RollbackPlan

    @property
    def kind(self) -> ActionKind:
        return self.parameters.kind

    @model_validator(mode="after")
    def keep_references_unique(self) -> Self:
        for label, values in (
            ("Evidence", self.evidence_ids),
            ("Hypothesis", self.hypothesis_ids),
            ("expected MetricObservation", self.expected_signal_metric_ids),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"Action Draft {label} references must be unique")
        return self


class ValidatedActionDraft(CommerceModel):
    schema_version: str = "commerce.validated-action@1.0.0"
    draft: ActionDraft
    validation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
