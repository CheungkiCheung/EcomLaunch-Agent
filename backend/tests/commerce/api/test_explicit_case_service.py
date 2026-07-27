"""Deterministic explicit-user Case trigger contracts."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.commerce.agents.context_loader import (
    CaseAnalysisArtifact,
    ContextPacketLoader,
)
from app.commerce.agents.contracts import AgentBudgetLimit, CaseTriggerType, PathType
from app.commerce.agents.fulfillment import FulfillmentPathAgent
from app.commerce.api.analysis_service import CommerceAnalysisService
from app.commerce.api.data_service import CommerceDataService
from app.commerce.api.dependencies import get_commerce_analysis_service
from app.commerce.api.router import router
from app.commerce.data.gold_cases import load_evaluation_case
from app.commerce.domain.ids import WorkspaceId
from app.commerce.metrics.registry import MetricWindow, PeerCohortPolicy
from app.commerce.persistence.events import SqlDomainEventStore
from app.commerce.persistence.lineage import SqlCaseLineageRepository
from app.commerce.persistence.repositories import SqlCaseRepository
from app.commerce.persistence.schema import create_commerce_schema

REPO_ROOT = Path(__file__).parents[4]
CASE_ROOT = REPO_ROOT / "evals" / "commerce" / "cases" / "GC-REVIEW-002"
PEER_CASE_ROOT = REPO_ROOT / "evals" / "commerce" / "cases" / "GC-PEER-004"
TARGET_SELLER_ID = "0b90b6df587eb83608a64ea8b390cf07"


async def _fixture(tmp_path):
    workspace_id = WorkspaceId.new()
    evaluation_case = load_evaluation_case(CASE_ROOT)
    data_service = CommerceDataService(storage_root=tmp_path / "commerce-storage")
    view = data_service.ingest_uploads(
        workspace_id,
        tuple((Path(file.relative_path).name, (CASE_ROOT / file.relative_path).read_bytes()) for file in evaluation_case.input_bundle.files),
    )
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'explicit.db'}")
    await create_commerce_schema(engine)
    return (
        engine,
        async_sessionmaker(engine, expire_on_commit=False),
        data_service,
        workspace_id,
        view.manifest.dataset_id,
    )


@pytest.mark.anyio
async def test_explicit_case_persists_user_paths_without_fabricating_anomaly(
    tmp_path,
):
    engine, factory, data_service, workspace_id, dataset_id = await _fixture(tmp_path)
    service = CommerceAnalysisService(
        data_service=data_service,
        session_factory=factory,
    )

    outcome = await service.open_explicit_case(
        workspace_id,
        dataset_id,
        seller_id=TARGET_SELLER_ID,
        baseline_window=MetricWindow(start=datetime(2018, 3, 1), end=datetime(2018, 4, 1)),
        current_window=MetricWindow(start=datetime(2018, 4, 1), end=datetime(2018, 5, 1)),
        requested_paths=(PathType.REVIEW_EXPERIENCE,),
        peer_policy=None,
    )

    assert len(outcome.cases) == 1
    case = outcome.cases[0]
    assert outcome.signals == ()
    assert case.evidence_ids == ()
    lineage = await SqlCaseLineageRepository(factory).get(workspace_id, case.id)
    assert lineage is not None
    assert lineage.anomaly_ids == ()
    assert lineage.metric_observation_ids == ()
    artifact_path = data_service.storage_root / str(workspace_id) / str(dataset_id) / lineage.analysis_artifact_relative_path
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["trigger"]["trigger_type"] == CaseTriggerType.EXPLICIT_USER.value
    assert artifact["trigger"]["requested_paths"] == [PathType.REVIEW_EXPERIENCE.value]
    assert artifact["signals"] == []
    parsed = CaseAnalysisArtifact.model_validate_json(artifact_path.read_bytes())
    assert parsed.trigger.requested_paths == (PathType.REVIEW_EXPERIENCE,)
    assert parsed.signals == ()
    persisted = await SqlCaseRepository(factory).get(workspace_id, case.id)
    assert persisted is not None
    assert persisted.id == case.id
    assert persisted.version == case.version
    assert persisted.evidence_ids == ()
    events = await SqlDomainEventStore(factory).list_case(workspace_id, case.id)
    assert events[0].payload["trigger"]["trigger_type"] == "explicit_user_request"
    await engine.dispose()


@pytest.mark.anyio
async def test_explicit_case_replays_the_same_content_addressed_case(tmp_path):
    engine, factory, data_service, workspace_id, dataset_id = await _fixture(tmp_path)
    service = CommerceAnalysisService(
        data_service=data_service,
        session_factory=factory,
    )
    request = {
        "seller_id": TARGET_SELLER_ID,
        "baseline_window": MetricWindow(start=datetime(2018, 3, 1), end=datetime(2018, 4, 1)),
        "current_window": MetricWindow(start=datetime(2018, 4, 1), end=datetime(2018, 5, 1)),
        "requested_paths": (PathType.REVIEW_EXPERIENCE,),
        "peer_policy": None,
    }

    first = await service.open_explicit_case(
        workspace_id,
        dataset_id,
        **request,
    )
    replay = await service.open_explicit_case(
        workspace_id,
        dataset_id,
        **request,
    )

    assert replay.cases[0].id == first.cases[0].id
    persisted = await SqlCaseRepository(factory).list(workspace_id)
    assert [item.id for item in persisted] == [first.cases[0].id]
    events = await SqlDomainEventStore(factory).list_case(
        workspace_id,
        first.cases[0].id,
    )
    assert [event.event_type for event in events].count("case.created") == 1
    await engine.dispose()


@pytest.mark.anyio
async def test_peer_gold_case_prepares_explicit_fulfillment_without_anomaly(
    tmp_path,
):
    evaluation_case = load_evaluation_case(PEER_CASE_ROOT)
    request = evaluation_case.input_bundle.peer_analysis_request
    assert request is not None
    workspace_id = WorkspaceId.new()
    data_service = CommerceDataService(storage_root=tmp_path / "peer-storage")
    view = data_service.ingest_uploads(
        workspace_id,
        tuple(
            (
                Path(item.relative_path).name,
                (PEER_CASE_ROOT / item.relative_path).read_bytes(),
            )
            for item in evaluation_case.input_bundle.files
        ),
    )
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'peer.db'}")
    await create_commerce_schema(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        outcome = await CommerceAnalysisService(
            data_service=data_service,
            session_factory=factory,
        ).open_explicit_case(
            workspace_id,
            view.manifest.dataset_id,
            seller_id=request.seller_id,
            baseline_window=MetricWindow(
                start=request.baseline_window.start,
                end=request.baseline_window.end,
            ),
            current_window=MetricWindow(
                start=request.window.start,
                end=request.window.end,
            ),
            requested_paths=request.requested_paths,
            peer_policy=PeerCohortPolicy(
                product_category=request.product_category,
                min_orders_per_seller=request.min_orders_per_seller,
                match_seller_state=request.match_seller_state,
            ),
        )
        packet = await ContextPacketLoader(
            data_service=data_service,
            session_factory=factory,
        ).load_case_packet(
            workspace_id,
            outcome.cases[0].id,
            goal=evaluation_case.input_bundle.user_prompt,
            budget=AgentBudgetLimit(max_tokens=16_000),
        )

        plan = await FulfillmentPathAgent().prepare(packet)

        assert plan.context.analysis.anomalies == ()
        assert plan.context.analysis.trigger.trigger_type is CaseTriggerType.EXPLICIT_USER
        assert plan.context.analysis.trigger.requested_paths == (
            PathType.FULFILLMENT,
            PathType.SELLER_PEER,
        )
        assert plan.context.manifest.included_anomaly_ids == ()
        assert "without claiming that an anomaly was detected" in plan.context.goal
    finally:
        await engine.dispose()


def test_explicit_peer_path_requires_outcome_agnostic_policy():
    with pytest.raises(ValueError, match="peer_policy"):
        from app.commerce.agents.contracts import CaseTriggerDigest

        CaseTriggerDigest(
            trigger_type=CaseTriggerType.EXPLICIT_USER,
            requested_paths=(PathType.SELLER_PEER,),
        )

    trigger = CaseTriggerDigest(
        trigger_type=CaseTriggerType.EXPLICIT_USER,
        requested_paths=(PathType.SELLER_PEER,),
        peer_policy=PeerCohortPolicy(
            product_category="fashion_bolsas_e_acessorios",
            min_orders_per_seller=20,
        ),
    )
    assert trigger.requested_paths == (PathType.SELLER_PEER,)


@pytest.mark.anyio
async def test_explicit_case_api_exposes_structured_trigger(tmp_path):
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
            f"/api/commerce/datasets/{dataset_id}/cases",
            headers={"X-Commerce-Workspace-Id": str(workspace_id)},
            json={
                "seller_id": TARGET_SELLER_ID,
                "baseline_window": {
                    "start": "2018-03-01T00:00:00",
                    "end": "2018-04-01T00:00:00",
                },
                "current_window": {
                    "start": "2018-04-01T00:00:00",
                    "end": "2018-05-01T00:00:00",
                },
                "requested_paths": ["review_experience"],
            },
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["case"]["evidence_ids"] == []
    assert payload["trigger"] == {
        "trigger_type": "explicit_user_request",
        "requested_paths": ["review_experience"],
        "peer_policy": None,
    }
    await engine.dispose()
