"""Deterministic HTTP contracts for the Commerce read workspace."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.commerce.api.analysis_service import CommerceAnalysisService
from app.commerce.api.data_service import CommerceDataService
from app.commerce.api.dependencies import get_commerce_read_service
from app.commerce.api.router import router
from app.commerce.api.service import CommerceReadService
from app.commerce.data.gold_cases import load_evaluation_case
from app.commerce.domain.enums import CaseSeverity, HypothesisStatus, SemanticStatus
from app.commerce.domain.events import DomainEventActor
from app.commerce.domain.ids import (
    AnomalyId,
    CaseId,
    CorrelationId,
    DatasetId,
    EntityId,
    FactId,
    MetricObservationId,
    TraceId,
    WorkspaceId,
)
from app.commerce.domain.lineage import CaseLineage
from app.commerce.domain.models import Case, Evidence, EvidenceRelation, Hypothesis
from app.commerce.metrics.registry import MetricWindow
from app.commerce.persistence.schema import create_commerce_schema
from app.commerce.persistence.unit_of_work import SqlCommerceUnitOfWork

REPO_ROOT = Path(__file__).parents[4]
CASE_ROOT = REPO_ROOT / "evals" / "commerce" / "cases" / "GC-FULFILLMENT-001"


async def _app(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'commerce-api.db'}")
    await create_commerce_schema(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_commerce_read_service] = lambda: CommerceReadService(factory)
    return app, engine, factory


async def _seed(factory, workspace_id: WorkspaceId) -> tuple[Case, Evidence, Hypothesis]:
    now = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
    case = Case(
        workspace_id=workspace_id,
        title="Delivery anomaly",
        severity=CaseSeverity.HIGH,
        opened_at=now,
        updated_at=now,
    )
    evidence = Evidence(
        workspace_id=workspace_id,
        case_id=case.id,
        summary="Transit time increased",
        relation=EvidenceRelation.SUPPORTS,
        semantic_status=SemanticStatus.DERIVED,
        confidence=0.9,
        fact_ids=(FactId.new(),),
        metric_observation_ids=(MetricObservationId.new(),),
    )
    hypothesis = Hypothesis(
        workspace_id=workspace_id,
        case_id=case.id,
        statement="Carrier transit degradation is likely",
        status=HypothesisStatus.PROPOSED,
        confidence=0.7,
        supporting_evidence_ids=(evidence.id,),
    )
    trace_id = TraceId.new()
    correlation_id = CorrelationId.new()
    uow = SqlCommerceUnitOfWork(factory)
    await uow.create_case(
        case,
        trace_id=trace_id,
        correlation_id=correlation_id,
        actor=DomainEventActor.SYSTEM,
    )
    await uow.attach_case_lineage(
        CaseLineage(
            workspace_id=workspace_id,
            case_id=case.id,
            dataset_id=DatasetId.new(),
            seller_entity_id=EntityId.new(),
            seller_external_key="seller-1",
            baseline_start=now,
            baseline_end=datetime(2026, 7, 18, 13, 0, tzinfo=UTC),
            current_start=datetime(2026, 7, 18, 13, 0, tzinfo=UTC),
            current_end=datetime(2026, 7, 18, 14, 0, tzinfo=UTC),
            anomaly_ids=(AnomalyId.new(),),
            metric_observation_ids=(MetricObservationId.new(),),
            analysis_artifact_relative_path="derived/case-context-a.json",
            analysis_artifact_sha256="a" * 64,
            created_at=now,
        ),
        trace_id=trace_id,
        correlation_id=correlation_id,
        actor=DomainEventActor.SYSTEM,
    )
    case_with_evidence = case.model_copy(update={"evidence_ids": (evidence.id,), "version": 2})
    await uow.append_evidence(
        case_with_evidence,
        evidence,
        expected_version=1,
        trace_id=trace_id,
        correlation_id=correlation_id,
        actor=DomainEventActor.AGENT,
    )
    case_with_hypothesis = case_with_evidence.model_copy(update={"hypothesis_ids": (hypothesis.id,), "version": 3})
    await uow.append_hypothesis_version(
        case_with_hypothesis,
        hypothesis,
        expected_version=2,
        trace_id=trace_id,
        correlation_id=correlation_id,
        actor=DomainEventActor.AGENT,
    )
    return case_with_hypothesis, evidence, hypothesis


@pytest.mark.anyio
async def test_read_workspace_returns_case_evidence_hypothesis_and_events(tmp_path):
    app, engine, factory = await _app(tmp_path)
    workspace_id = WorkspaceId.new()
    case, evidence, hypothesis = await _seed(factory, workspace_id)
    headers = {"X-Commerce-Workspace-Id": str(workspace_id)}

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        cases = await client.get("/api/commerce/cases", headers=headers)
        detail = await client.get(f"/api/commerce/cases/{case.id}", headers=headers)
        lineage_response = await client.get(
            f"/api/commerce/cases/{case.id}/lineage",
            headers=headers,
        )
        evidence_response = await client.get(
            f"/api/commerce/cases/{case.id}/evidence/{evidence.id}",
            headers=headers,
        )
        hypotheses = await client.get(
            f"/api/commerce/cases/{case.id}/hypotheses",
            headers=headers,
        )
        events = await client.get(
            f"/api/commerce/cases/{case.id}/events",
            headers=headers,
        )

    assert cases.status_code == 200
    assert cases.json()["items"][0]["id"] == str(case.id)
    assert detail.status_code == 200
    assert detail.json()["case"]["version"] == 3
    assert detail.json()["evidence"][0]["id"] == str(evidence.id)
    assert detail.json()["hypotheses"][0]["id"] == str(hypothesis.id)
    assert detail.json()["lineage"]["seller_external_key"] == "seller-1"
    assert detail.json()["analysis"] == {
        "status": "unavailable",
        "unavailable_reason": "analysis_reader_unconfigured",
        "baseline_metrics": [],
        "current_metrics": [],
        "anomalies": [],
    }
    assert detail.json()["actions"] == []
    assert lineage_response.status_code == 200
    assert lineage_response.json()["case_id"] == str(case.id)
    assert evidence_response.status_code == 200
    assert evidence_response.json()["fact_ids"] == [str(evidence.fact_ids[0])]
    assert hypotheses.status_code == 200
    assert hypotheses.json()["items"][0]["version"] == 1
    assert events.status_code == 200
    assert [item["event_type"] for item in events.json()["items"]] == [
        "case.created",
        "case.lineage_attached",
        "evidence.appended",
        "hypothesis.version_appended",
    ]
    await engine.dispose()


@pytest.mark.anyio
async def test_case_detail_returns_verified_deterministic_analysis(tmp_path):
    app, engine, factory = await _app(tmp_path)
    workspace_id = WorkspaceId.new()
    evaluation_case = load_evaluation_case(CASE_ROOT)
    uploads = tuple(
        (
            Path(file.relative_path).name,
            (CASE_ROOT / file.relative_path).read_bytes(),
        )
        for file in evaluation_case.input_bundle.files
    )
    data_service = CommerceDataService(storage_root=tmp_path / "commerce-storage")
    view = data_service.ingest_uploads(workspace_id, uploads)
    request = evaluation_case.input_bundle.analysis_request
    assert request is not None
    analyzed = await CommerceAnalysisService(
        data_service=data_service,
        session_factory=factory,
    ).analyze(
        workspace_id,
        view.manifest.dataset_id,
        baseline_window=MetricWindow(
            start=request.baseline_window.start,
            end=request.baseline_window.end,
        ),
        current_window=MetricWindow(
            start=request.anomaly_window.start,
            end=request.anomaly_window.end,
        ),
        seller_id=request.seller_id,
    )
    case = analyzed.cases[0]
    app.dependency_overrides[get_commerce_read_service] = lambda: CommerceReadService(
        factory,
        data_service=data_service,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            f"/api/commerce/cases/{case.id}",
            headers={"X-Commerce-Workspace-Id": str(workspace_id)},
        )

    assert response.status_code == 200
    analysis = response.json()["analysis"]
    assert analysis["status"] == "available"
    assert analysis["unavailable_reason"] is None
    assert analysis["baseline_metrics"]
    assert analysis["current_metrics"]
    assert analysis["anomalies"]
    signal = analysis["anomalies"][0]
    baseline = {item["id"]: item for item in analysis["baseline_metrics"]}[signal["baseline_observation_id"]]
    current = {item["id"]: item for item in analysis["current_metrics"]}[signal["current_observation_id"]]
    assert signal["baseline_value"] == baseline["value"]
    assert signal["current_value"] == current["value"]
    await engine.dispose()


@pytest.mark.anyio
async def test_read_workspace_enforces_workspace_and_case_boundaries(tmp_path):
    app, engine, factory = await _app(tmp_path)
    workspace_id = WorkspaceId.new()
    case, evidence, _ = await _seed(factory, workspace_id)
    other_workspace = WorkspaceId.new()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        hidden_list = await client.get(
            "/api/commerce/cases",
            headers={"X-Commerce-Workspace-Id": str(other_workspace)},
        )
        hidden_detail = await client.get(
            f"/api/commerce/cases/{case.id}",
            headers={"X-Commerce-Workspace-Id": str(other_workspace)},
        )
        hidden_lineage = await client.get(
            f"/api/commerce/cases/{case.id}/lineage",
            headers={"X-Commerce-Workspace-Id": str(other_workspace)},
        )
        missing_evidence = await client.get(
            f"/api/commerce/cases/{CaseId.new()}/evidence/{evidence.id}",
            headers={"X-Commerce-Workspace-Id": str(workspace_id)},
        )

    assert hidden_list.status_code == 200
    assert hidden_list.json()["items"] == []
    assert hidden_detail.status_code == 404
    assert hidden_lineage.status_code == 404
    assert missing_evidence.status_code == 404
    await engine.dispose()
