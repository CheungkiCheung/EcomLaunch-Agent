"""Stable string enums shared by Commerce domain contracts."""

from enum import StrEnum


class SemanticStatus(StrEnum):
    OBSERVED = "observed"
    DERIVED = "derived"
    ESTIMATED = "estimated"
    HYPOTHESIS = "hypothesis"
    UNKNOWN = "unknown"
    BLOCKED = "blocked"


class CaseStatus(StrEnum):
    NEW = "new"
    TRIAGED = "triaged"
    INVESTIGATING = "investigating"
    AWAITING_DATA = "awaiting_data"
    AWAITING_APPROVAL = "awaiting_approval"
    ACTION_IN_PROGRESS = "action_in_progress"
    MONITORING = "monitoring"
    RESOLVED = "resolved"
    REOPENED = "reopened"
    INCONCLUSIVE = "inconclusive"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class CaseSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class HypothesisStatus(StrEnum):
    PROPOSED = "proposed"
    INVESTIGATING = "investigating"
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    REJECTED = "rejected"
    UNKNOWN = "unknown"
    BLOCKED = "blocked"


class RunType(StrEnum):
    DATA_INTAKE = "data_intake"
    CASE_INVESTIGATION = "case_investigation"
    ACTION_EXECUTION = "action_execution"
    FOLLOW_UP = "follow_up"
    REPLAN = "replan"
    EVALUATION = "evaluation"


class RunPhase(StrEnum):
    PROFILING = "profiling"
    MAPPING = "mapping"
    PLANNING = "planning"
    INVESTIGATING = "investigating"
    SYNTHESIZING = "synthesizing"
    VERIFYING = "verifying"
    VALIDATING_ACTION = "validating_action"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    EVALUATING_FOLLOW_UP = "evaluating_follow_up"


class ActionStatus(StrEnum):
    DRAFT = "draft"
    VALIDATING = "validating"
    POLICY_CHECKED = "policy_checked"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    MONITORING = "monitoring"
    EFFECTIVE = "effective"
    INEFFECTIVE = "ineffective"
    INCONCLUSIVE = "inconclusive"
    ROLLED_BACK = "rolled_back"


class ActionRiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ApprovalStatus(StrEnum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    REVOKED = "revoked"


class FollowUpOutcome(StrEnum):
    EFFECTIVE = "effective"
    INEFFECTIVE = "ineffective"
    INCONCLUSIVE = "inconclusive"
    RESOLVED = "resolved"
    REOPENED = "reopened"
    BLOCKED = "blocked"
