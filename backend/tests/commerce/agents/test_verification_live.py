"""Fresh-context Verification must pass evidence and reject causal overclaim."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.commerce.agents.context_loader import ContextPacketLoader
from app.commerce.agents.contracts import AgentBudgetLimit
from app.commerce.agents.verification import (
    ClaimVerdict,
    VerificationAuditStore,
    VerificationEngine,
    VerificationRunStatus,
)
from app.commerce.api.analysis_service import CommerceAnalysisService
from app.commerce.api.data_service import CommerceDataService
from app.commerce.api.run_service import CommerceRunService
from app.commerce.data.gold_cases import load_evaluation_case
from app.commerce.domain.ids import CorrelationId, TraceId, WorkspaceId
from app.commerce.metrics.registry import MetricWindow
from app.commerce.persistence.runs import SqlRunLeaseRepository
from app.commerce.persistence.schema import create_commerce_schema

REPO_ROOT = Path(__file__).parents[4]
CASE_ROOT = REPO_ROOT / "evals" / "commerce" / "cases" / "GC-FULFILLMENT-001"
SELLER_ID = "4869f7a5dfa277a7dca6462dcf3b52b2"


@pytest.mark.real_model
@pytest.mark.anyio
async def test_fresh_verifier_passes_supported_claim_and_rejects_handling_causality(
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
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'verify.db'}")
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
        started = await CommerceRunService(factory).start_investigation(
            workspace_id,
            analysis.cases[0].id,
            goal=evaluation_case.input_bundle.user_prompt,
            idempotency_key="live-fresh-verification",
        )
        acquired_at = datetime.now(UTC) + timedelta(seconds=1)
        await SqlRunLeaseRepository(factory).acquire(
            workspace_id,
            started.run.id,
            worker_id="live-verifier-context-worker",
            ttl=timedelta(minutes=5),
            acquired_at=acquired_at,
            trace_id=TraceId.new(),
            correlation_id=CorrelationId.new(),
        )
        initial = await ContextPacketLoader(
            data_service=data_service,
            session_factory=factory,
        ).load_initial(
            workspace_id,
            started.run.id,
            budget=AgentBudgetLimit(max_tokens=16_000),
        )
        claims = (
            (
                "Handling time decreased from baseline while transit time increased; "
                "the observed fulfillment deterioration is localized to transit "
                "rather than seller handling."
            ),
            "Seller handling time worsened and caused the delivery delay.",
        )
        run = await VerificationEngine(
            audit_store=VerificationAuditStore(
                REPO_ROOT
                / ".deer-flow"
                / "commerce"
                / "evaluation"
                / "verification"
            )
        ).verify(initial.packet, claims=claims)

        assert run.telemetry.status is VerificationRunStatus.PASSED
        assert run.telemetry.actual_model_identity is not None
        assert run.telemetry.actual_model_identity.startswith("deepseek-v4")
        assert run.telemetry.provider_request_id
        assert run.telemetry.token_usage is not None
        assert run.telemetry.request_attempt_count == 1
        assert run.telemetry.retry_count == 0
        assert run.telemetry.stop_reason == "stop"
        assert Path(run.audit_path).is_file()
        assert run.result.overall_verdict is ClaimVerdict.REJECT
        assert len(run.result.claims) == 2
        assert run.result.claims[0].claim == claims[0]
        assert run.result.claims[0].verdict is ClaimVerdict.PASS
        assert run.result.claims[0].metric_observation_ids
        assert run.result.claims[1].claim == claims[1]
        assert run.result.claims[1].verdict is ClaimVerdict.REJECT
        assert run.result.claims[1].metric_observation_ids
        assert any(
            code.value in {"metric_contradiction", "unsupported_causal_language"}
            for code in run.result.claims[1].issue_codes
        )
        assert run.context.metadata == {
            "parent_context_sha256": initial.packet.manifest.context_sha256
        }
        assert "lead_reasoning" not in run.context.model_dump(mode="json")
    finally:
        await engine.dispose()
