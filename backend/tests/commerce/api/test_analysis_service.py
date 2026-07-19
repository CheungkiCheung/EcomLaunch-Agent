"""Deterministic anomaly-to-Case application contracts."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.commerce.api.analysis_service import CommerceAnalysisService
from app.commerce.api.data_service import CommerceDataService
from app.commerce.api.dependencies import get_commerce_analysis_service
from app.commerce.api.router import router
from app.commerce.data.gold_cases import load_evaluation_case
from app.commerce.domain.events import replay_case_projection
from app.commerce.domain.ids import WorkspaceId
from app.commerce.metrics.registry import MetricName, MetricWindow
from app.commerce.persistence.events import SqlDomainEventStore
from app.commerce.persistence.lineage import SqlCaseLineageRepository
from app.commerce.persistence.repositories import SqlCaseRepository
from app.commerce.persistence.schema import create_commerce_schema

REPO_ROOT = Path(__file__).parents[4]
CASE_ROOT = REPO_ROOT / "evals" / "commerce" / "cases" / "GC-FULFILLMENT-001"
SELLER_ID = "4869f7a5dfa277a7dca6462dcf3b52b2"


async def _fixture(tmp_path):
    storage_root = tmp_path / "commerce-storage"
    workspace_id = WorkspaceId.new()
    evaluation_case = load_evaluation_case(CASE_ROOT)
    uploads = tuple(
        (
            Path(file.relative_path).name,
            (CASE_ROOT / file.relative_path).read_bytes(),
        )
        for file in evaluation_case.input_bundle.files
    )
    data_service = CommerceDataService(storage_root=storage_root)
    view = data_service.ingest_uploads(workspace_id, uploads)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'analysis.db'}")
    await create_commerce_schema(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, factory, data_service, workspace_id, view.manifest.dataset_id


@pytest.mark.anyio
async def test_analysis_persists_deterministic_case_evidence_and_artifact(tmp_path):
    engine, factory, data_service, workspace_id, dataset_id = await _fixture(tmp_path)
    service = CommerceAnalysisService(
        data_service=data_service,
        session_factory=factory,
    )
    baseline = MetricWindow(
        start=datetime(2017, 12, 2),
        end=datetime(2018, 1, 31),
    )
    current = MetricWindow(
        start=datetime(2018, 1, 31),
        end=datetime(2018, 4, 1),
    )

    outcome = await service.analyze(
        workspace_id,
        dataset_id,
        baseline_window=baseline,
        current_window=current,
        seller_id=SELLER_ID,
    )

    metrics = {signal.metric_name for signal in outcome.signals}
    assert MetricName.LATE_DELIVERY_RATE.value in metrics
    assert MetricName.TRANSIT_TIME_HOURS.value in metrics
    assert MetricName.AVERAGE_REVIEW_SCORE.value in metrics
    assert len(outcome.cases) == 1
    case = outcome.cases[0]
    assert case.version == 1 + len(outcome.signals)

    events = await SqlDomainEventStore(factory).list_case(workspace_id, case.id)
    assert events[0].event_type == "case.created"
    assert sum(event.event_type == "evidence.appended" for event in events) == len(outcome.signals)
    assert replay_case_projection(events).version == case.version
    persisted_case = await SqlCaseRepository(factory).get(workspace_id, case.id)
    assert persisted_case is not None
    assert persisted_case.id == case.id
    assert len(case.evidence_ids) == len(outcome.signals)
    lineage = await SqlCaseLineageRepository(factory).get(workspace_id, case.id)
    assert lineage is not None
    assert lineage.dataset_id == dataset_id
    assert lineage.seller_external_key == SELLER_ID
    assert lineage.analysis_artifact_relative_path.startswith("derived/case-context-")
    context_path = (
        data_service.storage_root
        / str(workspace_id)
        / str(dataset_id)
        / lineage.analysis_artifact_relative_path
    )
    assert context_path.is_file()
    assert list((data_service.storage_root / str(workspace_id) / str(dataset_id) / "derived").glob("analysis-*.json"))

    repeated = await service.analyze(
        workspace_id,
        dataset_id,
        baseline_window=baseline,
        current_window=current,
        seller_id=SELLER_ID,
    )
    assert repeated.cases[0].id == case.id
    assert len(await SqlDomainEventStore(factory).list_case(workspace_id, case.id)) == len(events)
    await engine.dispose()


@pytest.mark.anyio
async def test_analysis_api_returns_persisted_case_contract(tmp_path):
    engine, factory, data_service, workspace_id, dataset_id = await _fixture(tmp_path)
    service = CommerceAnalysisService(
        data_service=data_service,
        session_factory=factory,
    )
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_commerce_analysis_service] = lambda: service

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"/api/commerce/datasets/{dataset_id}/analyze",
            headers={"X-Commerce-Workspace-Id": str(workspace_id)},
            json={
                "baseline_window": {
                    "start": "2017-12-02T00:00:00",
                    "end": "2018-01-31T00:00:00",
                },
                "current_window": {
                    "start": "2018-01-31T00:00:00",
                    "end": "2018-04-01T00:00:00",
                },
                "seller_id": SELLER_ID,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset_id"] == str(dataset_id)
    assert payload["cases"]
    assert payload["signals"]
    await engine.dispose()
