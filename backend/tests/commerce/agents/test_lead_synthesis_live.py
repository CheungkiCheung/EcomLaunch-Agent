"""Real Lead synthesis over freshly persisted Fulfillment Path Evidence."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.commerce.agents.context_loader import ContextPacketLoader
from app.commerce.agents.contracts import AgentBudgetLimit
from app.commerce.agents.fulfillment import FulfillmentPathAgent, PathAgentAuditStore
from app.commerce.agents.lead import LeadAuditStore, LeadSynthesisAgent, LeadSynthesisStatus
from app.commerce.agents.worker import CommerceInvestigationWorker
from app.commerce.api.analysis_service import CommerceAnalysisService
from app.commerce.api.data_service import CommerceDataService
from app.commerce.api.run_service import CommerceRunService
from app.commerce.data.gold_cases import load_evaluation_case
from app.commerce.domain.ids import WorkspaceId
from app.commerce.metrics.registry import MetricWindow
from app.commerce.persistence.schema import create_commerce_schema

REPO_ROOT = Path(__file__).parents[4]
CASE_ROOT = REPO_ROOT / "evals" / "commerce" / "cases" / "GC-FULFILLMENT-001"
SELLER_ID = "4869f7a5dfa277a7dca6462dcf3b52b2"


@pytest.mark.real_model
@pytest.mark.anyio
async def test_real_lead_synthesizes_traceable_claims_from_path_evidence(tmp_path):
    evaluation_case = load_evaluation_case(CASE_ROOT)
    workspace_id = WorkspaceId.new()
    data_service = CommerceDataService(storage_root=tmp_path / "commerce-storage")
    view = data_service.ingest_uploads(
        workspace_id,
        tuple(
            (Path(file.relative_path).name, (CASE_ROOT / file.relative_path).read_bytes())
            for file in evaluation_case.input_bundle.files
        ),
    )
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'lead.db'}")
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
                start=datetime(2017, 12, 2), end=datetime(2018, 1, 31)
            ),
            current_window=MetricWindow(
                start=datetime(2018, 1, 31), end=datetime(2018, 4, 1)
            ),
            seller_id=SELLER_ID,
        )
        started = await CommerceRunService(factory).start_investigation(
            workspace_id,
            analysis.cases[0].id,
            goal=evaluation_case.input_bundle.user_prompt,
            idempotency_key="live-lead-synthesis",
        )
        path_step = await CommerceInvestigationWorker(
            data_service=data_service,
            session_factory=factory,
            fulfillment_agent=FulfillmentPathAgent(
                audit_store=PathAgentAuditStore(
                    REPO_ROOT / ".deer-flow/commerce/evaluation/path-agents"
                )
            ),
        ).execute_fulfillment_step(
            workspace_id,
            started.run.id,
            worker_id="live-lead-path-worker",
            budget=AgentBudgetLimit(max_tokens=16_000),
        )
        refreshed = await ContextPacketLoader(
            data_service=data_service,
            session_factory=factory,
        ).load_case_packet(
            workspace_id,
            analysis.cases[0].id,
            goal=evaluation_case.input_bundle.user_prompt,
            budget=AgentBudgetLimit(max_tokens=16_000),
        )
        lead = await LeadSynthesisAgent(
            audit_store=LeadAuditStore(
                REPO_ROOT / ".deer-flow/commerce/evaluation/lead-synthesis"
            )
        ).synthesize(refreshed)

        assert lead.telemetry.status is LeadSynthesisStatus.PASSED
        assert lead.telemetry.actual_model_identity is not None
        assert lead.telemetry.actual_model_identity.startswith("deepseek-v4")
        assert lead.telemetry.provider_request_id
        assert lead.telemetry.token_usage is not None
        assert Path(lead.audit_path).is_file()
        assert lead.result.claims
        path_evidence_ids = {item.id for item in path_step.evidence}
        assert any(
            path_evidence_ids & set(claim.evidence_ids)
            for claim in lead.result.claims
        )
        rendered = lead.result.model_dump_json().casefold()
        assert "transit" in rendered
        assert "handling" in rendered
        assert any(
            term in rendered
            for term in (
                "did not worsen",
                "decreased",
                "not worsened",
                "lower",
                "improved",
                "shorter",
                "no deterioration",
            )
        )
        assert "caused the delay" not in rendered
    finally:
        await engine.dispose()
