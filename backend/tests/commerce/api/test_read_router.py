"""Deterministic HTTP contracts for the Commerce read workspace."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.commerce.api.dependencies import get_commerce_read_service
from app.commerce.api.router import router
from app.commerce.api.service import CommerceReadService
from app.commerce.domain.enums import CaseSeverity, HypothesisStatus, SemanticStatus
from app.commerce.domain.events import DomainEventActor
from app.commerce.domain.ids import (
    CaseId,
    CorrelationId,
    FactId,
    MetricObservationId,
    TraceId,
    WorkspaceId,
)
from app.commerce.domain.models import Case, Evidence, EvidenceRelation, Hypothesis
from app.commerce.persistence.schema import create_commerce_schema
from app.commerce.persistence.unit_of_work import SqlCommerceUnitOfWork


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
    case_with_evidence = case.model_copy(
        update={"evidence_ids": (evidence.id,), "version": 2}
    )
    await uow.append_evidence(
        case_with_evidence,
        evidence,
        expected_version=1,
        trace_id=trace_id,
        correlation_id=correlation_id,
        actor=DomainEventActor.AGENT,
    )
    case_with_hypothesis = case_with_evidence.model_copy(
        update={"hypothesis_ids": (hypothesis.id,), "version": 3}
    )
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
    assert evidence_response.status_code == 200
    assert evidence_response.json()["fact_ids"] == [str(evidence.fact_ids[0])]
    assert hypotheses.status_code == 200
    assert hypotheses.json()["items"][0]["version"] == 1
    assert events.status_code == 200
    assert [item["event_type"] for item in events.json()["items"]] == [
        "case.created",
        "evidence.appended",
        "hypothesis.version_appended",
    ]
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
        missing_evidence = await client.get(
            f"/api/commerce/cases/{CaseId.new()}/evidence/{evidence.id}",
            headers={"X-Commerce-Workspace-Id": str(workspace_id)},
        )

    assert hidden_list.status_code == 200
    assert hidden_list.json()["items"] == []
    assert hidden_detail.status_code == 404
    assert missing_evidence.status_code == 404
    await engine.dispose()
