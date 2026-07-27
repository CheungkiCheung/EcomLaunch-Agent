"""SQLite/PostgreSQL-compatible Commerce ORM rows."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.commerce.persistence.base import CommerceBase


class CaseRow(CommerceBase):
    __tablename__ = "commerce_cases"

    case_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    summary: Mapped[str | None] = mapped_column(Text)
    evidence_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    hypothesis_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    action_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint("version >= 1", name="ck_commerce_cases_version_positive"),
        Index(
            "ix_commerce_cases_workspace_status_updated",
            "workspace_id",
            "status",
            "updated_at",
        ),
    )


class DomainEventRow(CommerceBase):
    __tablename__ = "commerce_domain_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    case_id: Mapped[str | None] = mapped_column(String(64), index=True)
    run_id: Mapped[str | None] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    case_sequence: Mapped[int | None] = mapped_column(Integer)
    run_sequence: Mapped[int | None] = mapped_column(Integer)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    causation_event_id: Mapped[str | None] = mapped_column(String(64))
    actor: Mapped[str] = mapped_column(String(20), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "case_id",
            "case_sequence",
            name="uq_commerce_event_case_sequence",
        ),
        UniqueConstraint(
            "run_id",
            "run_sequence",
            name="uq_commerce_event_run_sequence",
        ),
        CheckConstraint(
            "(case_id IS NOT NULL AND case_sequence IS NOT NULL) OR (case_id IS NULL AND case_sequence IS NULL)",
            name="ck_commerce_event_case_sequence_presence",
        ),
        CheckConstraint(
            "(run_id IS NOT NULL AND run_sequence IS NOT NULL) OR (run_id IS NULL AND run_sequence IS NULL)",
            name="ck_commerce_event_run_sequence_presence",
        ),
        CheckConstraint(
            "case_id IS NOT NULL OR run_id IS NOT NULL",
            name="ck_commerce_event_has_aggregate",
        ),
        Index(
            "ix_commerce_events_workspace_case_sequence",
            "workspace_id",
            "case_id",
            "case_sequence",
        ),
        Index(
            "ix_commerce_events_workspace_run_sequence",
            "workspace_id",
            "run_id",
            "run_sequence",
        ),
    )


class EvidenceRow(CommerceBase):
    """Append-only, Case-scoped evidence record."""

    __tablename__ = "commerce_evidence"

    evidence_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    relation: Mapped[str] = mapped_column(String(20), nullable=False)
    semantic_status: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    fact_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    metric_observation_ids_json: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_commerce_evidence_confidence_range",
        ),
        Index(
            "ix_commerce_evidence_workspace_case",
            "workspace_id",
            "case_id",
        ),
    )


class HypothesisRow(CommerceBase):
    """Immutable version of a Case-scoped hypothesis."""

    __tablename__ = "commerce_hypotheses"

    hypothesis_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    supporting_evidence_ids_json: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    contradicting_evidence_ids_json: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint("version >= 1", name="ck_commerce_hypotheses_version_positive"),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_commerce_hypotheses_confidence_range",
        ),
        Index(
            "ix_commerce_hypotheses_workspace_case",
            "workspace_id",
            "case_id",
        ),
        Index(
            "ix_commerce_hypotheses_workspace_case_status",
            "workspace_id",
            "case_id",
            "status",
        ),
    )


class RunRow(CommerceBase):
    """Mutable projection for one bounded Commerce execution."""

    __tablename__ = "commerce_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    run_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    phase: Mapped[str] = mapped_column(String(32), nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_run_id: Mapped[str | None] = mapped_column(String(64), index=True)
    subject_action_id: Mapped[str | None] = mapped_column(String(64), index=True)
    action_operation: Mapped[str | None] = mapped_column(String(16))
    requested_paths_json: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    wait_reason: Mapped[str | None] = mapped_column(Text)
    stop_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "case_id",
            "idempotency_key_sha256",
            name="uq_commerce_runs_workspace_case_idempotency",
        ),
        CheckConstraint("version >= 1", name="ck_commerce_runs_version_positive"),
        Index(
            "ix_commerce_runs_workspace_case_updated",
            "workspace_id",
            "case_id",
            "updated_at",
        ),
        Index(
            "ix_commerce_runs_workspace_status_updated",
            "workspace_id",
            "status",
            "updated_at",
        ),
    )


class RunCheckpointRow(CommerceBase):
    """Append-only serialized Goal Loop checkpoint."""

    __tablename__ = "commerce_run_checkpoints"

    checkpoint_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    checkpoint_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "sequence",
            name="uq_commerce_run_checkpoint_sequence",
        ),
        CheckConstraint(
            "sequence >= 1",
            name="ck_commerce_run_checkpoint_sequence_positive",
        ),
        Index(
            "ix_commerce_run_checkpoints_workspace_run_sequence",
            "workspace_id",
            "run_id",
            "sequence",
        ),
    )


class ActionRow(CommerceBase):
    """Versioned Action projection plus its validated policy decision."""

    __tablename__ = "commerce_actions"

    action_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    policy_level: Mapped[str] = mapped_column(String(4), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    decision_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint("version >= 1", name="ck_commerce_actions_version_positive"),
        Index(
            "ix_commerce_actions_workspace_case_created",
            "workspace_id",
            "case_id",
            "created_at",
        ),
    )


class ApprovalRequestRow(CommerceBase):
    """Mutable projection for one policy-required human Approval."""

    __tablename__ = "commerce_approval_requests"

    approval_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    action_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    request_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "version >= 1",
            name="ck_commerce_approval_requests_version_positive",
        ),
        Index(
            "ix_commerce_approval_requests_workspace_case_updated",
            "workspace_id",
            "case_id",
            "updated_at",
        ),
    )


class ApprovalDecisionRow(CommerceBase):
    """Append-only idempotent human Approval decision."""

    __tablename__ = "commerce_approval_decisions"

    decision_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    approval_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    action_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_key_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    decision_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "action_id",
            "idempotency_key_sha256",
            name="uq_commerce_approval_decision_idempotency",
        ),
        Index(
            "ix_commerce_approval_decisions_approval_created",
            "approval_id",
            "created_at",
        ),
    )


class ActionArtifactRow(CommerceBase):
    """Versioned real internal artifact created by one Action Connector."""

    __tablename__ = "commerce_action_artifacts"

    action_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    artifact_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "version >= 1",
            name="ck_commerce_action_artifacts_version_positive",
        ),
        Index(
            "ix_commerce_action_artifacts_workspace_case_updated",
            "workspace_id",
            "case_id",
            "updated_at",
        ),
    )


class FollowUpRow(CommerceBase):
    """Versioned Follow-up request and deterministic evaluation projection."""

    __tablename__ = "commerce_follow_ups"

    follow_up_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    action_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    dataset_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    outcome: Mapped[str | None] = mapped_column(String(32), index=True)
    follow_up_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "version >= 1",
            name="ck_commerce_follow_ups_version_positive",
        ),
        Index(
            "ix_commerce_follow_ups_workspace_action_created",
            "workspace_id",
            "action_id",
            "created_at",
        ),
    )


class RunLeaseRow(CommerceBase):
    """Current fenced execution ownership for one Commerce Run."""

    __tablename__ = "commerce_run_leases"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    worker_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    lease_token_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    fencing_token: Mapped[int] = mapped_column(Integer, nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "fencing_token >= 1",
            name="ck_commerce_run_lease_fencing_positive",
        ),
        Index(
            "ix_commerce_run_leases_workspace_expiry",
            "workspace_id",
            "expires_at",
        ),
    )


class CaseLineageRow(CommerceBase):
    """One immutable deterministic data lineage record per Case."""

    __tablename__ = "commerce_case_lineage"

    case_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    dataset_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    seller_entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    seller_external_key: Mapped[str] = mapped_column(String(256), nullable=False)
    baseline_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    baseline_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    anomaly_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    metric_observation_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    analysis_artifact_relative_path: Mapped[str] = mapped_column(Text, nullable=False)
    analysis_artifact_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index(
            "ix_commerce_case_lineage_workspace_dataset",
            "workspace_id",
            "dataset_id",
        ),
    )
