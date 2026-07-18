"""Explicit state transitions for long-lived Commerce cases."""

from __future__ import annotations

from app.commerce.domain.enums import CaseStatus


class InvalidStateTransition(ValueError):
    """Raised when a domain object attempts an undeclared state change."""


_CASE_STATUS_TRANSITIONS: dict[CaseStatus, frozenset[CaseStatus]] = {
    CaseStatus.NEW: frozenset({CaseStatus.TRIAGED, CaseStatus.BLOCKED, CaseStatus.CANCELLED}),
    CaseStatus.TRIAGED: frozenset(
        {
            CaseStatus.INVESTIGATING,
            CaseStatus.AWAITING_DATA,
            CaseStatus.BLOCKED,
            CaseStatus.CANCELLED,
        }
    ),
    CaseStatus.INVESTIGATING: frozenset(
        {
            CaseStatus.AWAITING_DATA,
            CaseStatus.AWAITING_APPROVAL,
            CaseStatus.ACTION_IN_PROGRESS,
            CaseStatus.MONITORING,
            CaseStatus.RESOLVED,
            CaseStatus.INCONCLUSIVE,
            CaseStatus.BLOCKED,
            CaseStatus.CANCELLED,
        }
    ),
    CaseStatus.AWAITING_DATA: frozenset(
        {
            CaseStatus.INVESTIGATING,
            CaseStatus.BLOCKED,
            CaseStatus.CANCELLED,
        }
    ),
    CaseStatus.AWAITING_APPROVAL: frozenset(
        {
            CaseStatus.ACTION_IN_PROGRESS,
            CaseStatus.INVESTIGATING,
            CaseStatus.BLOCKED,
            CaseStatus.CANCELLED,
        }
    ),
    CaseStatus.ACTION_IN_PROGRESS: frozenset(
        {
            CaseStatus.MONITORING,
            CaseStatus.INVESTIGATING,
            CaseStatus.BLOCKED,
            CaseStatus.CANCELLED,
        }
    ),
    CaseStatus.MONITORING: frozenset(
        {
            CaseStatus.RESOLVED,
            CaseStatus.REOPENED,
            CaseStatus.INCONCLUSIVE,
            CaseStatus.BLOCKED,
            CaseStatus.CANCELLED,
        }
    ),
    CaseStatus.RESOLVED: frozenset({CaseStatus.REOPENED}),
    CaseStatus.REOPENED: frozenset(
        {
            CaseStatus.INVESTIGATING,
            CaseStatus.AWAITING_DATA,
            CaseStatus.BLOCKED,
            CaseStatus.CANCELLED,
        }
    ),
    CaseStatus.INCONCLUSIVE: frozenset(
        {
            CaseStatus.REOPENED,
            CaseStatus.AWAITING_DATA,
            CaseStatus.CANCELLED,
        }
    ),
    CaseStatus.BLOCKED: frozenset(
        {
            CaseStatus.REOPENED,
            CaseStatus.AWAITING_DATA,
            CaseStatus.CANCELLED,
        }
    ),
    CaseStatus.CANCELLED: frozenset(),
}


def transition_case_status(current: CaseStatus, target: CaseStatus) -> CaseStatus:
    """Validate and return a declared Case status transition."""

    if target not in _CASE_STATUS_TRANSITIONS[current]:
        raise InvalidStateTransition(f"Case cannot transition from {current.value} to {target.value}")
    return target
