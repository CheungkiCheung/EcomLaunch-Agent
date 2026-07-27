"""Fresh DeepSeek V4 Action Planner over fresh persisted verified context."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.commerce.actions.contracts import ActionKind
from app.commerce.actions.planner import FreshActionPlanner
from app.commerce.agents.context_loader import ContextPacketLoader
from app.commerce.agents.contracts import AgentBudgetLimit
from app.commerce.agents.verification import (
    ClaimVerdict,
    VerificationAuditStore,
    VerificationEngine,
)
from app.commerce.api.action_service import CommerceActionService
from app.commerce.api.analysis_service import CommerceAnalysisService
from app.commerce.api.data_service import CommerceDataService
from app.commerce.api.dependencies import get_commerce_action_service
from app.commerce.api.router import router
from app.commerce.api.run_service import CommerceRunService
from app.commerce.data.gold_cases import load_evaluation_case
from app.commerce.domain.enums import HypothesisStatus
from app.commerce.domain.events import DomainEventActor
from app.commerce.domain.ids import (
    CorrelationId,
    HypothesisId,
    TraceId,
    WorkspaceId,
)
from app.commerce.domain.models import Hypothesis
from app.commerce.metrics.registry import MetricName, MetricWindow
from app.commerce.persistence.repositories import SqlCaseRepository
from app.commerce.persistence.runs import SqlRunLeaseRepository
from app.commerce.persistence.schema import create_commerce_schema
from app.commerce.persistence.unit_of_work import SqlCommerceUnitOfWork

REPO_ROOT = Path(__file__).parents[4]
CASE_ROOT = REPO_ROOT / "evals" / "commerce" / "cases" / "GC-FULFILLMENT-001"
SELLER_ID = "4869f7a5dfa277a7dca6462dcf3b52b2"


@pytest.mark.real_model
@pytest.mark.anyio
async def test_fresh_action_planner_proposes_internal_action_and_replay_is_free(
    tmp_path,
):
    evaluation_case = load_evaluation_case(CASE_ROOT)
    workspace_id = WorkspaceId.new()
    data_service = CommerceDataService(storage_root=tmp_path / "commerce-storage")
    view = data_service.ingest_uploads(
        workspace_id,
        tuple(
            (
                Path(file.relative_path).name,
                (CASE_ROOT / file.relative_path).read_bytes(),
            )
            for file in evaluation_case.input_bundle.files
        ),
    )
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'action-planner.db'}")
    await create_commerce_schema(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        analysis = await CommerceAnalysisService(
            data_service=data_service,
            session_factory=factory,
        ).analyze(
            workspace_id,
            view.manifest.dataset_id,
            baseline_window=MetricWindow(
                start=datetime(2017, 12, 2),
                end=datetime(2018, 1, 31),
            ),
            current_window=MetricWindow(
                start=datetime(2018, 1, 31),
                end=datetime(2018, 4, 1),
            ),
            seller_id=SELLER_ID,
        )
        case = analysis.cases[0]
        started = await CommerceRunService(factory).start_investigation(
            workspace_id,
            case.id,
            goal="Verify a bounded monitor hypothesis before Action planning",
            idempotency_key="fresh-action-planner-context",
        )
        acquired_at = datetime.now(UTC) + timedelta(seconds=1)
        await SqlRunLeaseRepository(factory).acquire(
            workspace_id,
            started.run.id,
            worker_id="fresh-action-planner-context-worker",
            ttl=timedelta(minutes=5),
            acquired_at=acquired_at,
            trace_id=TraceId.new(),
            correlation_id=CorrelationId.new(),
        )
        loader = ContextPacketLoader(
            data_service=data_service,
            session_factory=factory,
        )
        initial = await loader.load_initial(
            workspace_id,
            started.run.id,
            budget=AgentBudgetLimit(max_tokens=16_000),
        )
        current_late = next(item for item in initial.packet.analysis.current_metrics if item.metric_name == MetricName.LATE_DELIVERY_RATE.value)
        evidence = next(item for item in initial.packet.evidence if current_late.metric_observation_id in item.metric_observation_ids)
        claim = "The persisted late-delivery signal is elevated relative to baseline and should be monitored without claiming a causal Action effect."
        verification = await VerificationEngine(audit_store=VerificationAuditStore(tmp_path / "verification")).verify(initial.packet, claims=(claim,))
        assert verification.result.claims[0].verdict is ClaimVerdict.PASS

        persisted_case = await SqlCaseRepository(factory).get(
            workspace_id,
            case.id,
        )
        assert persisted_case is not None
        hypothesis = Hypothesis(
            id=HypothesisId.new(),
            workspace_id=workspace_id,
            case_id=case.id,
            statement=claim,
            status=HypothesisStatus.SUPPORTED,
            confidence=0.9,
            supporting_evidence_ids=(evidence.evidence_id,),
        )
        updated_case = persisted_case.model_copy(
            update={
                "hypothesis_ids": (
                    *persisted_case.hypothesis_ids,
                    hypothesis.id,
                ),
                "updated_at": datetime.now(UTC),
                "version": persisted_case.version + 1,
            }
        )
        await SqlCommerceUnitOfWork(factory).append_hypothesis_version(
            updated_case,
            hypothesis,
            expected_version=persisted_case.version,
            trace_id=TraceId.new(),
            correlation_id=CorrelationId.new(),
            actor=DomainEventActor.AGENT,
        )

        service = CommerceActionService(
            factory,
            data_service=data_service,
            planner=FreshActionPlanner(audit_root=tmp_path / "action-planning"),
        )
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_commerce_action_service] = lambda: service
        headers = {
            "X-Commerce-Workspace-Id": str(workspace_id),
            "X-Commerce-Actor-Id": "operator-a",
        }
        body = {"idempotency_key": "fresh-action-plan-live"}
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            first = await client.post(
                f"/api/commerce/cases/{case.id}/action-plans",
                headers=headers,
                json=body,
            )
            replay = await client.post(
                f"/api/commerce/cases/{case.id}/action-plans",
                headers=headers,
                json=body,
            )

        assert first.status_code == 201, first.text
        assert replay.status_code == 201, replay.text
        first_body = first.json()
        replay_body = replay.json()
        assert first_body["created"] is True
        assert first_body["planning"] is not None
        assert first_body["planning"]["telemetry"]["actual_model_identity"].startswith("deepseek-v4")
        assert first_body["planning"]["telemetry"]["provider_request_id"]
        assert first_body["planning"]["telemetry"]["retry_count"] == 0
        assert first_body["record"]["action"]["status"] in {
            "policy_checked",
            "awaiting_approval",
        }
        assert first_body["record"]["decision"]["validated"]["draft"]["parameters"]["kind"] in {
            ActionKind.NO_OP.value,
            ActionKind.EXPORT_AUDIT_COHORT.value,
            ActionKind.CREATE_INTERNAL_TASK.value,
            ActionKind.CREATE_METRIC_MONITOR.value,
            ActionKind.REQUEST_MISSING_DATA.value,
        }
        rendered_model_output = first_body["planning"]["model_output"]
        for forbidden in (
            "risk_level",
            "policy_level",
            "execution_tool",
            "connector_id",
            "rollback_plan",
        ):
            assert forbidden not in rendered_model_output
        assert replay_body["created"] is False
        assert replay_body["planning"] is None
        assert replay_body["record"]["action"]["id"] == first_body["record"]["action"]["id"]
        assert len(tuple((tmp_path / "action-planning").glob("*.json"))) == 1
    finally:
        await engine.dispose()
