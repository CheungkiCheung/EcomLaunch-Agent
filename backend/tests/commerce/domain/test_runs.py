"""Bounded Commerce Run lifecycle contracts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.commerce.domain.enums import RunPhase, RunStatus, RunType
from app.commerce.domain.ids import CaseId, WorkspaceId
from app.commerce.domain.runs import CommerceRun, InvalidRunTransitionError


def _run(now: datetime) -> CommerceRun:
    return CommerceRun(
        workspace_id=WorkspaceId.new(),
        case_id=CaseId.new(),
        run_type=RunType.CASE_INVESTIGATION,
        goal="Explain the delivery anomaly with traceable evidence",
        phase=RunPhase.PLANNING,
        idempotency_key_sha256="a" * 64,
        created_at=now,
        updated_at=now,
    )


def test_new_investigation_run_is_honestly_queued():
    now = datetime(2026, 7, 19, 10, 0, tzinfo=UTC)
    run = _run(now)

    assert run.status is RunStatus.QUEUED
    assert run.started_at is None
    assert run.ended_at is None
    assert run.stop_reason is None
    assert run.version == 1


def test_run_transitions_start_wait_resume_and_complete_with_timestamps():
    now = datetime(2026, 7, 19, 10, 0, tzinfo=UTC)
    queued = _run(now)
    running = queued.transition_to(
        RunStatus.RUNNING,
        phase=RunPhase.INVESTIGATING,
        occurred_at=now + timedelta(minutes=1),
    )
    waiting = running.transition_to(
        RunStatus.WAITING,
        wait_reason="awaiting_user_input",
        occurred_at=now + timedelta(minutes=2),
    )
    resumed = waiting.transition_to(
        RunStatus.RUNNING,
        occurred_at=now + timedelta(minutes=3),
    )
    completed = resumed.transition_to(
        RunStatus.COMPLETED,
        phase=RunPhase.VERIFYING,
        stop_reason="goal_achieved",
        occurred_at=now + timedelta(minutes=4),
    )

    assert running.started_at == now + timedelta(minutes=1)
    assert waiting.wait_reason == "awaiting_user_input"
    assert resumed.wait_reason is None
    assert completed.ended_at == now + timedelta(minutes=4)
    assert completed.stop_reason == "goal_achieved"
    assert completed.version == 5


def test_running_run_can_advance_phase_without_faking_a_status_transition():
    now = datetime(2026, 7, 19, 10, 0, tzinfo=UTC)
    running = _run(now).transition_to(
        RunStatus.RUNNING,
        occurred_at=now + timedelta(minutes=1),
    )

    investigating = running.advance_phase(
        RunPhase.INVESTIGATING,
        occurred_at=now + timedelta(minutes=2),
    )

    assert investigating.status is RunStatus.RUNNING
    assert investigating.phase is RunPhase.INVESTIGATING
    assert investigating.version == running.version + 1
    assert investigating.started_at == running.started_at
    with pytest.raises(InvalidRunTransitionError, match="phase"):
        investigating.advance_phase(
            RunPhase.PLANNING,
            occurred_at=now + timedelta(minutes=3),
        )


def test_run_rejects_invalid_transition_and_inconsistent_terminal_fields():
    now = datetime(2026, 7, 19, 10, 0, tzinfo=UTC)
    queued = _run(now)

    with pytest.raises(InvalidRunTransitionError):
        queued.transition_to(
            RunStatus.COMPLETED,
            stop_reason="goal_achieved",
            occurred_at=now + timedelta(minutes=1),
        )

    with pytest.raises(ValidationError, match="terminal Run requires stop_reason"):
        CommerceRun(
            workspace_id=WorkspaceId.new(),
            case_id=CaseId.new(),
            run_type=RunType.CASE_INVESTIGATION,
            status=RunStatus.FAILED,
            phase=RunPhase.INVESTIGATING,
            goal="Investigate",
            idempotency_key_sha256="b" * 64,
            created_at=now,
            started_at=now,
            ended_at=now,
            updated_at=now,
        )
