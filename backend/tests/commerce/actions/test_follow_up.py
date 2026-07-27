"""Deterministic post-Action Follow-up without causal overclaiming."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.commerce.actions.contracts import (
    ActionDraft,
    ActionKind,
    MetricComparison,
    MetricMonitorParameters,
    ValidatedActionDraft,
)
from app.commerce.actions.follow_up import (
    FollowUpService,
    FollowUpStatus,
)
from app.commerce.actions.follow_up_contracts import FollowUpSignalStatus
from app.commerce.actions.internal_connectors import InternalConnectorRegistry
from app.commerce.actions.policy import ActionPolicyGate
from app.commerce.api.data_service import CommerceDataService
from app.commerce.api.dependencies import get_commerce_follow_up_service
from app.commerce.api.router import router
from app.commerce.data.gold_cases import load_evaluation_case
from app.commerce.domain.enums import (
    ActionStatus,
    CaseSeverity,
    CaseStatus,
    FollowUpOutcome,
    RunStatus,
)
from app.commerce.domain.events import DomainEventActor
from app.commerce.domain.ids import (
    CorrelationId,
    EvidenceId,
    HypothesisId,
    MetricObservationId,
    TraceId,
    WorkspaceId,
)
from app.commerce.domain.lineage import CaseLineage
from app.commerce.domain.models import Action, Case, RollbackPlan
from app.commerce.metrics.registry import MetricWindow
from app.commerce.persistence.action_artifacts import SqlActionArtifactRepository
from app.commerce.persistence.actions import ActionRecord, SqlActionRepository
from app.commerce.persistence.follow_ups import SqlFollowUpRepository
from app.commerce.persistence.lineage import SqlCaseLineageRepository
from app.commerce.persistence.repositories import SqlCaseRepository
from app.commerce.persistence.schema import create_commerce_schema
from app.commerce.persistence.unit_of_work import SqlCommerceUnitOfWork

REPO_ROOT = Path(__file__).parents[4]
CASES_ROOT = REPO_ROOT / "evals" / "commerce" / "cases"
SELLER_ID = "4869f7a5dfa277a7dca6462dcf3b52b2"


def _rollback() -> RollbackPlan:
    return RollbackPlan(
        strategy="Disable the metric monitor",
        trigger="The monitor contract is invalidated",
        verification="Read back the disabled monitor state",
    )


async def _seed_monitor(tmp_path: Path, *, threshold: str):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'follow-up.db'}")
    await create_commerce_schema(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    workspace_id = WorkspaceId.new()
    data_service = CommerceDataService(storage_root=tmp_path / "data")
    case_dir = CASES_ROOT / "GC-FULFILLMENT-001"
    evaluation_case = load_evaluation_case(case_dir)
    uploads = tuple(
        (
            Path(file.relative_path).name,
            (case_dir / file.relative_path).read_bytes(),
        )
        for file in evaluation_case.input_bundle.files
    )
    view = data_service.ingest_uploads(workspace_id, uploads)
    normalized = data_service.normalize(workspace_id, view.manifest.dataset_id)
    seller_entity = next(entity for entity in normalized.entities if entity.external_key == SELLER_ID)
    now = datetime(2026, 7, 19, 18, 0, tzinfo=UTC)
    evidence_id = EvidenceId.new()
    metric_id = MetricObservationId.new()
    case = Case(
        workspace_id=workspace_id,
        title="Late-delivery anomaly",
        severity=CaseSeverity.HIGH,
        status=CaseStatus.MONITORING,
        evidence_ids=(evidence_id,),
        opened_at=now,
        updated_at=now,
    )
    draft = ActionDraft(
        workspace_id=workspace_id,
        case_id=case.id,
        title="Monitor late-delivery recovery",
        description="Track the deterministic late-delivery rate target.",
        evidence_ids=(evidence_id,),
        hypothesis_ids=(HypothesisId.new(),),
        expected_signal_metric_ids=(metric_id,),
        parameters=MetricMonitorParameters(
            kind=ActionKind.CREATE_METRIC_MONITOR,
            metric_name="late_delivery_rate",
            metric_observation_ids=(metric_id,),
            comparison=MetricComparison.LESS_THAN_OR_EQUAL,
            threshold=threshold,
            cadence_hours=24,
            follow_up_after_days=7,
        ),
        rollback_plan=_rollback(),
    )
    decision = ActionPolicyGate().evaluate(
        ValidatedActionDraft(
            draft=draft,
            validation_sha256="a" * 64,
        )
    )
    policy_record = ActionRecord.from_policy(decision, occurred_at=now)
    artifact = (
        InternalConnectorRegistry()
        .execute(
            policy_record,
            storage_root=tmp_path / "artifacts",
            occurred_at=now,
        )
        .artifact
    )
    monitoring_action = Action.model_validate(
        {
            **policy_record.action.model_dump(mode="python"),
            "status": ActionStatus.MONITORING,
        }
    )
    monitoring_decision = decision.model_copy(update={"action": monitoring_action})
    record = ActionRecord.from_policy(monitoring_decision, occurred_at=now)
    uow = SqlCommerceUnitOfWork(factory)
    await uow.create_case(
        case,
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
        actor=DomainEventActor.SYSTEM,
    )
    updated_case = case.model_copy(
        update={
            "action_ids": (record.action.id,),
            "version": case.version + 1,
        }
    )
    await uow.create_action(
        updated_case,
        record,
        approval=None,
        expected_case_version=case.version,
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
        actor=DomainEventActor.AGENT,
    )
    await SqlActionArtifactRepository(factory).create(artifact)
    await SqlCaseLineageRepository(factory).create(
        CaseLineage(
            workspace_id=workspace_id,
            case_id=case.id,
            dataset_id=view.manifest.dataset_id,
            seller_entity_id=seller_entity.id,
            seller_external_key=SELLER_ID,
            baseline_start=datetime(2017, 12, 2),
            baseline_end=datetime(2018, 1, 31),
            current_start=datetime(2018, 1, 31),
            current_end=datetime(2018, 4, 1),
            analysis_artifact_relative_path="derived/case-context.json",
            analysis_artifact_sha256="b" * 64,
            created_at=now,
        )
    )
    return engine, factory, data_service, record, view.manifest.dataset_id


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("threshold", "window", "expected_signal", "expected_case"),
    (
        (
            "0.15",
            MetricWindow(
                start=datetime(2018, 4, 1),
                end=datetime(2018, 5, 1),
            ),
            FollowUpSignalStatus.TARGET_MET,
            CaseStatus.RESOLVED,
        ),
        (
            "0.01",
            MetricWindow(
                start=datetime(2018, 4, 1),
                end=datetime(2018, 5, 1),
            ),
            FollowUpSignalStatus.TARGET_MISSED,
            CaseStatus.REOPENED,
        ),
        (
            "0.15",
            MetricWindow(
                start=datetime(2018, 4, 1),
                end=datetime(2018, 4, 2),
            ),
            FollowUpSignalStatus.UNAVAILABLE,
            CaseStatus.INCONCLUSIVE,
        ),
    ),
)
async def test_follow_up_recomputes_signal_and_updates_action_case_without_causality(
    tmp_path,
    threshold,
    window,
    expected_signal,
    expected_case,
):
    root = tmp_path / expected_signal.value
    root.mkdir()
    engine, factory, data_service, record, dataset_id = await _seed_monitor(
        root,
        threshold=threshold,
    )
    times = iter(
        (
            datetime(2026, 7, 19, 18, 1, tzinfo=UTC),
            datetime(2026, 7, 19, 18, 2, tzinfo=UTC),
        )
    )
    service = FollowUpService(
        factory,
        data_service=data_service,
        clock=lambda: next(times),
        minimum_sample_size=20,
    )
    started = await service.start(
        record.action.workspace_id,
        record.action.id,
        dataset_id=dataset_id,
        evaluation_window=window,
        idempotency_key=f"follow-up-{expected_signal.value}-001",
        actor_id="operator-a",
    )
    start_replay = await service.start(
        record.action.workspace_id,
        record.action.id,
        dataset_id=dataset_id,
        evaluation_window=window,
        idempotency_key=f"follow-up-{expected_signal.value}-001",
        actor_id="operator-a",
    )
    result = await service.evaluate(
        record.action.workspace_id,
        started.run.id,
        worker_id="follow-up-worker-1",
    )
    evaluation_replay = await service.evaluate(
        record.action.workspace_id,
        started.run.id,
        worker_id="follow-up-worker-2",
    )

    assert started.created is True
    assert start_replay.created is False
    assert result.run.status is RunStatus.COMPLETED
    assert result.follow_up.status is FollowUpStatus.COMPLETED
    assert result.follow_up.outcome is FollowUpOutcome.INCONCLUSIVE
    assert result.follow_up.signal_status is expected_signal
    assert result.follow_up.causal_claim is False
    assert "causal" in result.follow_up.assessment.lower()
    assert result.record.action.status is ActionStatus.INCONCLUSIVE
    assert result.case.status is expected_case
    assert evaluation_replay.replayed is True
    persisted = await SqlFollowUpRepository(factory).get(
        record.action.workspace_id,
        result.follow_up.id,
    )
    assert persisted == result.follow_up
    assert (
        await SqlActionRepository(factory).get(
            record.action.workspace_id,
            record.action.id,
        )
    ).action.status is ActionStatus.INCONCLUSIVE
    assert (
        await SqlCaseRepository(factory).get(
            record.action.workspace_id,
            record.action.case_id,
        )
    ).status is expected_case
    if expected_signal is FollowUpSignalStatus.UNAVAILABLE:
        assert "sample" in " ".join(result.follow_up.limitations).lower()
    else:
        assert result.follow_up.metric_observation is not None
        assert result.follow_up.metric_observation.sample_size >= 20
    await engine.dispose()


@pytest.mark.anyio
async def test_follow_up_http_endpoint_executes_and_lists_persisted_assessment(tmp_path):
    root = tmp_path / "follow-up-api"
    root.mkdir()
    engine, factory, data_service, record, dataset_id = await _seed_monitor(
        root,
        threshold="0.15",
    )
    times = iter(
        (
            datetime(2026, 7, 19, 18, 1, tzinfo=UTC),
            datetime(2026, 7, 19, 18, 2, tzinfo=UTC),
        )
    )
    service = FollowUpService(
        factory,
        data_service=data_service,
        clock=lambda: next(times),
        minimum_sample_size=20,
    )
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_commerce_follow_up_service] = lambda: service
    headers = {
        "X-Commerce-Workspace-Id": str(record.action.workspace_id),
        "X-Commerce-Actor-Id": "operator-a",
    }
    body = {
        "dataset_id": str(dataset_id),
        "evaluation_window": {
            "start": "2018-04-01T00:00:00",
            "end": "2018-05-01T00:00:00",
        },
        "idempotency_key": "follow-up-api-effective-001",
    }
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        evaluated = await client.post(
            f"/api/commerce/actions/{record.action.id}/follow-ups",
            headers=headers,
            json=body,
        )
        replay = await client.post(
            f"/api/commerce/actions/{record.action.id}/follow-ups",
            headers=headers,
            json=body,
        )
        listed = await client.get(
            f"/api/commerce/actions/{record.action.id}/follow-ups",
            headers=headers,
        )

    assert evaluated.status_code == 201
    assert evaluated.json()["created"] is True
    assert evaluated.json()["run"]["run_type"] == "follow_up"
    assert evaluated.json()["run"]["status"] == "completed"
    assert evaluated.json()["follow_up"]["outcome"] == "inconclusive"
    assert evaluated.json()["follow_up"]["signal_status"] == "target_met"
    assert evaluated.json()["follow_up"]["causal_claim"] is False
    assert evaluated.json()["case"]["status"] == "resolved"
    assert replay.status_code == 201
    assert replay.json()["created"] is False
    assert replay.json()["replayed"] is True
    assert listed.status_code == 200
    assert [item["outcome"] for item in listed.json()["items"]] == ["inconclusive"]
    await engine.dispose()
