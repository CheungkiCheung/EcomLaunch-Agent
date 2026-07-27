"""Deterministic L0-L5 policy gate for validated Commerce Actions."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from app.commerce.actions.contracts import (
    ActionKind,
    ExternalMutationParameters,
    ExternalOperation,
    ValidatedActionDraft,
)
from app.commerce.domain.enums import (
    ActionRiskLevel,
    ActionStatus,
    ApprovalStatus,
)
from app.commerce.domain.models import (
    Action,
    ApprovalRequirement,
    CommerceModel,
)


class ActionPolicyLevel(StrEnum):
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"
    L5 = "L5"


class ActionPolicyDisposition(StrEnum):
    AUTO_EXECUTE = "auto_execute"
    APPROVAL_REQUIRED = "approval_required"
    BLOCKED = "blocked"


class PolicyReasonCode(StrEnum):
    READ_ONLY = "read_only"
    REVERSIBLE_INTERNAL_ARTIFACT = "reversible_internal_artifact"
    REVERSIBLE_INTERNAL_OPERATION = "reversible_internal_operation"
    EXTERNAL_DRY_RUN = "external_dry_run"
    REVERSIBLE_EXTERNAL_WRITE = "reversible_external_write"
    CONNECTOR_NOT_ALLOWED = "connector_not_allowed"
    IRREVERSIBLE_OR_FINANCIAL = "irreversible_or_financial"


class ConnectorPolicy(CommerceModel):
    allowed_operations: dict[str, frozenset[ExternalOperation]] = Field(
        default_factory=dict
    )

    def allows(self, connector_id: str, operation: ExternalOperation) -> bool:
        return operation in self.allowed_operations.get(connector_id, frozenset())


class ActionPolicyDecision(CommerceModel):
    schema_version: str = "commerce.action-policy-decision@1.0.0"
    validated: ValidatedActionDraft
    level: ActionPolicyLevel
    disposition: ActionPolicyDisposition
    reason_codes: frozenset[PolicyReasonCode] = Field(min_length=1)
    required_approvals: int = Field(ge=0, le=2)
    execution_tool: str | None = Field(default=None, min_length=1)
    action: Action


_IRREVERSIBLE_OR_FINANCIAL = frozenset(
    {
        ExternalOperation.DELETE_LISTING,
        ExternalOperation.ISSUE_REFUND,
        ExternalOperation.SUSPEND_SELLER,
    }
)


class ActionPolicyGate:
    """Assign policy level independently from model-supplied risk language."""

    def __init__(
        self,
        *,
        connector_policy: ConnectorPolicy | None = None,
    ) -> None:
        self._connectors = connector_policy or ConnectorPolicy()

    def evaluate(self, validated: ValidatedActionDraft) -> ActionPolicyDecision:
        draft = validated.draft
        if isinstance(draft.parameters, ExternalMutationParameters):
            return self._external(validated)
        mapping = {
            ActionKind.NO_OP: (
                ActionPolicyLevel.L0,
                PolicyReasonCode.READ_ONLY,
                None,
                ActionRiskLevel.LOW,
            ),
            ActionKind.EXPORT_AUDIT_COHORT: (
                ActionPolicyLevel.L1,
                PolicyReasonCode.REVERSIBLE_INTERNAL_ARTIFACT,
                "internal_audit_export.create",
                ActionRiskLevel.LOW,
            ),
            ActionKind.CREATE_INTERNAL_TASK: (
                ActionPolicyLevel.L2,
                PolicyReasonCode.REVERSIBLE_INTERNAL_OPERATION,
                "internal_ops_task.create",
                ActionRiskLevel.MEDIUM,
            ),
            ActionKind.CREATE_METRIC_MONITOR: (
                ActionPolicyLevel.L2,
                PolicyReasonCode.REVERSIBLE_INTERNAL_OPERATION,
                "internal_metric_monitor.create",
                ActionRiskLevel.MEDIUM,
            ),
            ActionKind.REQUEST_MISSING_DATA: (
                ActionPolicyLevel.L2,
                PolicyReasonCode.REVERSIBLE_INTERNAL_OPERATION,
                "internal_data_request.create",
                ActionRiskLevel.MEDIUM,
            ),
        }
        level, reason, tool, risk = mapping[draft.kind]
        return self._decision(
            validated,
            level=level,
            disposition=ActionPolicyDisposition.AUTO_EXECUTE,
            reasons=frozenset({reason}),
            required_approvals=0,
            execution_tool=tool,
            risk=risk,
            action_status=ActionStatus.POLICY_CHECKED,
            approval=ApprovalRequirement(
                required=False,
                status=ApprovalStatus.NOT_REQUIRED,
                reason="Internal reversible Action is below the approval threshold",
            ),
        )

    def _external(
        self,
        validated: ValidatedActionDraft,
    ) -> ActionPolicyDecision:
        parameters = validated.draft.parameters
        assert isinstance(parameters, ExternalMutationParameters)
        if parameters.operation in _IRREVERSIBLE_OR_FINANCIAL or not (
            parameters.reversible
        ):
            return self._decision(
                validated,
                level=ActionPolicyLevel.L5,
                disposition=ActionPolicyDisposition.BLOCKED,
                reasons=frozenset(
                    {PolicyReasonCode.IRREVERSIBLE_OR_FINANCIAL}
                ),
                required_approvals=0,
                execution_tool=None,
                risk=ActionRiskLevel.CRITICAL,
                action_status=ActionStatus.REJECTED,
                approval=ApprovalRequirement(
                    required=True,
                    status=ApprovalStatus.REJECTED,
                    reason="Irreversible or financial mutation is forbidden",
                ),
            )
        level = ActionPolicyLevel.L3 if parameters.dry_run else ActionPolicyLevel.L4
        approvals = 1 if parameters.dry_run else 2
        if not self._connectors.allows(
            parameters.connector_id,
            parameters.operation,
        ):
            return self._decision(
                validated,
                level=level,
                disposition=ActionPolicyDisposition.BLOCKED,
                reasons=frozenset({PolicyReasonCode.CONNECTOR_NOT_ALLOWED}),
                required_approvals=0,
                execution_tool=None,
                risk=ActionRiskLevel.HIGH,
                action_status=ActionStatus.REJECTED,
                approval=ApprovalRequirement(
                    required=True,
                    status=ApprovalStatus.REJECTED,
                    reason="Connector or operation is not allowlisted",
                ),
            )
        return self._decision(
            validated,
            level=level,
            disposition=ActionPolicyDisposition.APPROVAL_REQUIRED,
            reasons=frozenset(
                {
                    PolicyReasonCode.EXTERNAL_DRY_RUN
                    if parameters.dry_run
                    else PolicyReasonCode.REVERSIBLE_EXTERNAL_WRITE
                }
            ),
            required_approvals=approvals,
            execution_tool=(
                f"connector:{parameters.connector_id}:{parameters.operation.value}"
            ),
            risk=ActionRiskLevel.HIGH,
            action_status=ActionStatus.AWAITING_APPROVAL,
            approval=ApprovalRequirement(
                required=True,
                status=ApprovalStatus.PENDING,
                reason=f"Policy {level.value} requires human approval",
            ),
        )

    @staticmethod
    def _decision(
        validated: ValidatedActionDraft,
        *,
        level: ActionPolicyLevel,
        disposition: ActionPolicyDisposition,
        reasons: frozenset[PolicyReasonCode],
        required_approvals: int,
        execution_tool: str | None,
        risk: ActionRiskLevel,
        action_status: ActionStatus,
        approval: ApprovalRequirement,
    ) -> ActionPolicyDecision:
        draft = validated.draft
        return ActionPolicyDecision(
            validated=validated,
            level=level,
            disposition=disposition,
            reason_codes=reasons,
            required_approvals=required_approvals,
            execution_tool=execution_tool,
            action=Action(
                id=draft.id,
                workspace_id=draft.workspace_id,
                case_id=draft.case_id,
                title=draft.title,
                description=draft.description,
                status=action_status,
                evidence_ids=draft.evidence_ids,
                risk_level=risk,
                approval=approval,
                rollback_plan=draft.rollback_plan,
            ),
        )
