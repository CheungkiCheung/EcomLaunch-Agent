"""Fresh real-model E2E for the fenced Path → Lead → Verification Loop."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.commerce.agents.contracts import AgentBudgetLimit
from app.commerce.agents.fulfillment import FulfillmentPathAgent, PathAgentAuditStore
from app.commerce.agents.goal_loop import GoalLoopOutcome, GoalStopReason
from app.commerce.agents.lead import LeadAuditStore, LeadSynthesisAgent
from app.commerce.agents.verification import (
    ClaimVerdict,
    VerificationAuditStore,
    VerificationEngine,
)
from app.commerce.agents.worker import CommerceInvestigationWorker
from app.commerce.api.analysis_service import CommerceAnalysisService
from app.commerce.api.data_service import CommerceDataService
from app.commerce.api.run_service import CommerceRunService
from app.commerce.data.gold_cases import load_evaluation_case
from app.commerce.domain.enums import HypothesisStatus, RunPhase, RunStatus
from app.commerce.domain.ids import WorkspaceId
from app.commerce.metrics.registry import MetricWindow
from app.commerce.persistence.events import SqlDomainEventStore
from app.commerce.persistence.runs import SqlRunCheckpointRepository
from app.commerce.persistence.schema import create_commerce_schema
from app.commerce.persistence.work_records import SqlHypothesisRepository

REPO_ROOT = Path(__file__).parents[4]
CASE_ROOT = REPO_ROOT / "evals" / "commerce" / "cases" / "GC-FULFILLMENT-001"
SELLER_ID = "4869f7a5dfa277a7dca6462dcf3b52b2"


@pytest.mark.real_model
@pytest.mark.anyio
async def test_worker_closes_fulfillment_diagnosis_through_fresh_lead_and_verifier(
    tmp_path,
):
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
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'case-loop.db'}")
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
            idempotency_key="live-worker-lead-verification-loop",
        )
        worker = CommerceInvestigationWorker(
            data_service=data_service,
            session_factory=factory,
            fulfillment_agent=FulfillmentPathAgent(
                audit_store=PathAgentAuditStore(
                    REPO_ROOT / ".deer-flow/commerce/evaluation/path-agents"
                )
            ),
            lead_agent=LeadSynthesisAgent(
                audit_store=LeadAuditStore(
                    REPO_ROOT / ".deer-flow/commerce/evaluation/lead-synthesis"
                )
            ),
            verification_engine=VerificationEngine(
                audit_store=VerificationAuditStore(
                    REPO_ROOT / ".deer-flow/commerce/evaluation/verification"
                )
            ),
        )

        loop = await worker.execute_fulfillment_case_loop(
            workspace_id,
            started.run.id,
            worker_id="live-worker-case-loop",
            budget=AgentBudgetLimit(
                max_iterations=4,
                max_tokens=32_000,
                max_wall_time_seconds=600,
                max_model_escalations=2,
                max_verification_repairs=1,
            ),
        )

        assert loop.run.status is RunStatus.COMPLETED
        assert loop.run.phase is RunPhase.VERIFYING
        assert loop.run.stop_reason == GoalStopReason.GOAL_ACHIEVED.value
        assert loop.decision.outcome is GoalLoopOutcome.ACHIEVED
        assert loop.verification_run.result.overall_verdict is ClaimVerdict.PASS

        calls = (
            loop.path_step.path_run.telemetry,
            loop.lead_run.telemetry,
            loop.verification_run.telemetry,
        )
        assert all(
            item.actual_model_identity is not None
            and item.actual_model_identity.startswith("deepseek-v4")
            and item.provider_request_id
            and item.token_usage is not None
            and item.request_attempt_count == 1
            and item.retry_count == 0
            for item in calls
        )
        path_evidence_ids = {item.id for item in loop.path_step.evidence}
        lead_metric_names = {
            item.metric_name
            for item in (
                *loop.lead_run.context.analysis.baseline_metrics,
                *loop.lead_run.context.analysis.current_metrics,
            )
        }
        assert "average_review_score" not in lead_metric_names
        assert "low_rating_rate" not in lead_metric_names
        assert loop.lead_run.context.analysis == loop.path_step.path_run.context.analysis
        assert all(
            set(claim.evidence_ids).issubset(path_evidence_ids)
            for claim in loop.lead_run.result.claims
        )
        rendered_claims = " ".join(
            claim.statement.casefold() for claim in loop.lead_run.result.claims
        )
        assert not any(
            phrase in rendered_claims
            for phrase in (
                "attributable to",
                "because of",
                "caused",
                "driven by",
                "driven primarily by",
                "due to",
                "implying",
                "indicating",
                "responsible for",
                "resulted in",
                "suggesting",
            )
        )
        assert loop.verification_run.context.claims == tuple(
            claim.statement for claim in loop.lead_run.result.claims
        )
        assert "Lead reasoning history excluded" in (
            loop.verification_run.context.manifest.redactions
        )

        checkpoints = await SqlRunCheckpointRepository(factory).list_run(
            workspace_id, started.run.id
        )
        assert tuple(item.sequence for item in checkpoints) == (1, 2, 3, 4, 5)
        final = checkpoints[-1].checkpoint
        expected_tokens = sum(item.token_usage.total_tokens for item in calls)
        assert final.budget_snapshot.usage.tokens == expected_tokens
        assert final.budget_snapshot.usage.path_agents == 1
        assert final.budget_snapshot.usage.model_escalations == 1
        assert final.budget_snapshot.usage.verification_repairs == 0
        assert final.budget_snapshot.usage.iterations == 2
        assert final.budget_snapshot.usage.wall_time_seconds > 0
        assert set(final.hypothesis_ids) == {
            claim.hypothesis_id for claim in loop.lead_run.result.claims
        }

        repository = SqlHypothesisRepository(factory)
        for proposed, verified in zip(
            loop.proposed_hypotheses,
            loop.verified_hypotheses,
            strict=True,
        ):
            assert await repository.list_versions(workspace_id, proposed.id) == (
                proposed,
                verified,
            )
            assert verified.status is HypothesisStatus.SUPPORTED

        events = await SqlDomainEventStore(factory).list_run(
            workspace_id, started.run.id
        )
        event_types = [event.event_type for event in events]
        assert event_types.count("model.assigned") == 3
        assert "lead.started" in event_types
        assert "lead.completed" in event_types
        assert "verification.started" in event_types
        assert "verification.completed" in event_types
        assert "goal_loop.stopped" in event_types
        assert event_types[-1] == "run.status_changed"
        completed = next(
            event for event in events if event.event_type == "verification.completed"
        )
        assert completed.payload["overall_verdict"] == ClaimVerdict.PASS.value
        assert completed.payload["result_sha256"] == (
            loop.verification_run.result_sha256
        )

        serialized = "".join(
            item.checkpoint.model_dump_json() for item in checkpoints
        ) + "".join(event.model_dump_json() for event in events)
        assert loop.path_step.lease.lease_token.get_secret_value() not in serialized
    finally:
        await engine.dispose()
