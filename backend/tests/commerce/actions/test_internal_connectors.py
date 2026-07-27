"""Real internal Connector artifacts, verification, persistence, and rollback."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.commerce.actions.artifacts import (
    ActionArtifactStatus,
    AuditCohortRow,
    AuditExportArtifact,
    DataRequestArtifact,
    InternalTaskArtifact,
    MetricMonitorArtifact,
)
from app.commerce.actions.contracts import (
    ActionDraft,
    ActionKind,
    AuditExportParameters,
    DataRequestParameters,
    ExternalMutationParameters,
    ExternalOperation,
    InternalTaskParameters,
    MetricComparison,
    MetricMonitorParameters,
    NoOpParameters,
    ValidatedActionDraft,
)
from app.commerce.actions.internal_connectors import (
    InternalConnectorRegistry,
    UnsupportedConnectorError,
)
from app.commerce.actions.policy import (
    ActionPolicyGate,
    ConnectorPolicy,
)
from app.commerce.domain.ids import (
    CaseId,
    EvidenceId,
    HypothesisId,
    MetricObservationId,
    WorkspaceId,
)
from app.commerce.domain.models import RollbackPlan
from app.commerce.persistence.action_artifacts import (
    SqlActionArtifactRepository,
)
from app.commerce.persistence.actions import ActionRecord
from app.commerce.persistence.repositories import (
    DuplicateEntityError,
    OptimisticConcurrencyError,
)
from app.commerce.persistence.schema import create_commerce_schema


def _rollback() -> RollbackPlan:
    return RollbackPlan(
        strategy="Reverse the internal artifact",
        trigger="An operator requests rollback or a guardrail fails",
        verification="Read back the persisted artifact state",
    )


def _record(parameters, *, workspace_id=None, case_id=None) -> ActionRecord:
    workspace_id = workspace_id or WorkspaceId.new()
    case_id = case_id or CaseId.new()
    draft = ActionDraft(
        workspace_id=workspace_id,
        case_id=case_id,
        title=f"Execute {parameters.kind.value}",
        description="Create one bounded and reversible internal artifact.",
        evidence_ids=(EvidenceId.new(),),
        hypothesis_ids=(HypothesisId.new(),),
        expected_signal_metric_ids=(MetricObservationId.new(),),
        parameters=parameters,
        rollback_plan=_rollback(),
    )
    decision = ActionPolicyGate().evaluate(
        ValidatedActionDraft(
            draft=draft,
            validation_sha256="a" * 64,
        )
    )
    return ActionRecord.from_policy(
        decision,
        occurred_at=datetime(2026, 7, 19, 16, 0, tzinfo=UTC),
    )


def test_registry_executes_real_task_monitor_data_request_and_no_op(tmp_path):
    now = datetime(2026, 7, 19, 16, 1, tzinfo=UTC)
    metric_id = MetricObservationId.new()
    records = (
        _record(
            InternalTaskParameters(
                kind=ActionKind.CREATE_INTERNAL_TASK,
                owner_role="seller-operations",
                due_days=3,
                checklist=("Contact carrier", "Attach route evidence"),
            )
        ),
        _record(
            MetricMonitorParameters(
                kind=ActionKind.CREATE_METRIC_MONITOR,
                metric_name="late_delivery_rate",
                metric_observation_ids=(metric_id,),
                comparison=MetricComparison.LESS_THAN_OR_EQUAL,
                threshold="0.15",
                cadence_hours=24,
                follow_up_after_days=7,
            )
        ),
        _record(
            DataRequestParameters(
                kind=ActionKind.REQUEST_MISSING_DATA,
                missing_fields=("ad_spend", "gross_profit"),
                due_days=5,
            )
        ),
        _record(
            NoOpParameters(
                kind=ActionKind.NO_OP,
                reason="No safe mutation is warranted",
            )
        ),
    )
    registry = InternalConnectorRegistry()

    results = [
        registry.execute(
            record,
            storage_root=tmp_path,
            occurred_at=now,
        )
        for record in records
    ]

    assert isinstance(results[0].artifact.payload, InternalTaskArtifact)
    assert results[0].artifact.status is ActionArtifactStatus.OPEN
    assert results[0].artifact.payload.owner_role == "seller-operations"
    assert isinstance(results[1].artifact.payload, MetricMonitorArtifact)
    assert results[1].artifact.status is ActionArtifactStatus.ACTIVE
    assert results[1].artifact.payload.next_evaluation_at > now
    assert isinstance(results[2].artifact.payload, DataRequestArtifact)
    assert results[2].artifact.status is ActionArtifactStatus.OPEN
    assert results[2].artifact.payload.missing_fields == (
        "ad_spend",
        "gross_profit",
    )
    assert results[3].artifact.status is ActionArtifactStatus.COMPLETED
    assert all(result.verification.passed for result in results)
    assert all(result.artifact.verification_sha256 for result in results)


def test_audit_export_writes_hash_verifies_and_physically_archives_on_rollback(
    tmp_path,
):
    record = _record(
        AuditExportParameters(
            kind=ActionKind.EXPORT_AUDIT_COHORT,
            format="jsonl",
            max_rows=10,
            include_direct_identifiers=False,
        )
    )
    rows = (
        AuditCohortRow(
            evidence_id=record.action.evidence_ids[0],
            summary="Late-delivery rate increased in the current window",
            confidence=0.94,
            metric_observation_ids=record.decision.validated.draft.expected_signal_metric_ids,
        ),
    )
    registry = InternalConnectorRegistry()
    executed = registry.execute(
        record,
        storage_root=tmp_path,
        audit_rows=rows,
        occurred_at=datetime(2026, 7, 19, 16, 2, tzinfo=UTC),
    )

    assert isinstance(executed.artifact.payload, AuditExportArtifact)
    path = tmp_path / executed.artifact.payload.relative_path
    assert path.is_file()
    assert executed.artifact.payload.row_count == 1
    assert executed.artifact.payload.sha256
    assert "seller_external_key" not in path.read_text()

    rolled_back = registry.rollback(
        executed.artifact,
        storage_root=tmp_path,
        occurred_at=datetime(2026, 7, 19, 16, 3, tzinfo=UTC),
    )
    archived_path = tmp_path / rolled_back.artifact.payload.relative_path
    assert rolled_back.artifact.status is ActionArtifactStatus.ARCHIVED
    assert not path.exists()
    assert archived_path.is_file()
    assert rolled_back.verification.passed is True


def test_registry_rejects_external_or_unbound_execution_tools(tmp_path):
    draft = ActionDraft(
        workspace_id=WorkspaceId.new(),
        case_id=CaseId.new(),
        title="Adjust campaign budget",
        description="One reversible external write.",
        evidence_ids=(EvidenceId.new(),),
        hypothesis_ids=(HypothesisId.new(),),
        expected_signal_metric_ids=(MetricObservationId.new(),),
        parameters=ExternalMutationParameters(
            kind=ActionKind.EXTERNAL_MUTATION,
            connector_id="merchant_ads",
            operation=ExternalOperation.UPDATE_CAMPAIGN_BUDGET,
            target_ref_sha256="b" * 64,
            reversible=True,
            dry_run=False,
        ),
        rollback_plan=_rollback(),
    )
    decision = ActionPolicyGate(connector_policy=ConnectorPolicy(allowed_operations={"merchant_ads": frozenset({ExternalOperation.UPDATE_CAMPAIGN_BUDGET})})).evaluate(ValidatedActionDraft(draft=draft, validation_sha256="c" * 64))
    record = ActionRecord.from_policy(
        decision,
        occurred_at=datetime(2026, 7, 19, 16, 0, tzinfo=UTC),
    )

    with pytest.raises(UnsupportedConnectorError, match="external"):
        InternalConnectorRegistry().execute(
            record,
            storage_root=tmp_path,
            occurred_at=datetime(2026, 7, 19, 16, 1, tzinfo=UTC),
        )


@pytest.mark.anyio
async def test_artifact_repository_is_idempotency_scoped_and_optimistically_versioned(
    tmp_path,
):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'action-artifacts.db'}")
    await create_commerce_schema(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    record = _record(
        InternalTaskParameters(
            kind=ActionKind.CREATE_INTERNAL_TASK,
            owner_role="seller-operations",
            due_days=3,
            checklist=("Contact carrier",),
        )
    )
    artifact = (
        InternalConnectorRegistry()
        .execute(
            record,
            storage_root=tmp_path,
            occurred_at=datetime(2026, 7, 19, 16, 1, tzinfo=UTC),
        )
        .artifact
    )
    repository = SqlActionArtifactRepository(factory)

    await repository.create(artifact)
    loaded = await repository.get(record.action.workspace_id, record.action.id)
    assert loaded == artifact
    assert await repository.get(WorkspaceId.new(), record.action.id) is None
    with pytest.raises(DuplicateEntityError):
        await repository.create(artifact)

    rolled_back = (
        InternalConnectorRegistry()
        .rollback(
            artifact,
            storage_root=tmp_path,
            occurred_at=datetime(2026, 7, 19, 16, 2, tzinfo=UTC),
        )
        .artifact
    )
    await repository.save(rolled_back, expected_version=artifact.version)
    assert await repository.get(record.action.workspace_id, record.action.id) == rolled_back
    with pytest.raises(OptimisticConcurrencyError):
        await repository.save(rolled_back, expected_version=artifact.version)
    await engine.dispose()
