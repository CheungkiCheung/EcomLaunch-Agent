"""Fresh real-model E2E for one fenced Commerce Worker Path step."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.commerce.agents.contracts import AgentBudgetLimit
from app.commerce.agents.fulfillment import FulfillmentPathAgent, PathAgentAuditStore
from app.commerce.agents.worker import CommerceInvestigationWorker
from app.commerce.api.analysis_service import CommerceAnalysisService
from app.commerce.api.data_service import CommerceDataService
from app.commerce.api.run_service import CommerceRunService
from app.commerce.data.gold_cases import load_evaluation_case
from app.commerce.domain.enums import RunPhase, RunStatus
from app.commerce.domain.ids import WorkspaceId
from app.commerce.metrics.registry import MetricName, MetricWindow
from app.commerce.persistence.events import SqlDomainEventStore
from app.commerce.persistence.repositories import SqlCaseRepository
from app.commerce.persistence.runs import SqlRunCheckpointRepository
from app.commerce.persistence.schema import create_commerce_schema
from app.commerce.persistence.work_records import SqlEvidenceRepository

REPO_ROOT = Path(__file__).parents[4]
CASE_ROOT = REPO_ROOT / "evals" / "commerce" / "cases" / "GC-FULFILLMENT-001"
SELLER_ID = "4869f7a5dfa277a7dca6462dcf3b52b2"


@pytest.mark.real_model
@pytest.mark.anyio
async def test_worker_persists_real_fulfillment_path_under_fenced_lease(tmp_path):
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
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'worker.db'}")
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
            goal=evaluation_case.input_bundle.user_prompt,
            idempotency_key="live-worker-fulfillment-step",
        )
        agent = FulfillmentPathAgent(
            audit_store=PathAgentAuditStore(
                REPO_ROOT
                / ".deer-flow"
                / "commerce"
                / "evaluation"
                / "path-agents"
            )
        )

        step = await CommerceInvestigationWorker(
            data_service=data_service,
            session_factory=factory,
            fulfillment_agent=agent,
        ).execute_fulfillment_step(
            workspace_id,
            started.run.id,
            worker_id="live-worker-fulfillment",
            budget=AgentBudgetLimit(max_tokens=16_000),
        )

        assert step.run.status is RunStatus.RUNNING
        assert step.run.phase is RunPhase.INVESTIGATING
        assert step.pre_call_checkpoint.sequence == 1
        assert step.post_call_checkpoint.sequence == 2
        pre = step.pre_call_checkpoint.checkpoint
        post = step.post_call_checkpoint.checkpoint
        assert pre.loop_iteration == 0
        assert pre.active_path_task_ids == (step.task_id,)
        assert len(pre.model_assignments) == 1
        assert post.loop_iteration == 1
        assert post.active_path_task_ids == ()
        assert post.budget_snapshot.usage.path_agents == 1
        assert post.budget_snapshot.usage.tokens == (
            step.path_run.telemetry.token_usage.total_tokens
        )
        assert post.budget_snapshot.usage.wall_time_seconds > 0
        assert set(item.id for item in step.evidence).issubset(set(post.evidence_ids))
        assert len(step.evidence) == len(step.path_run.result.evidence) > 0

        persisted_case = await SqlCaseRepository(factory).get(workspace_id, case.id)
        assert persisted_case is not None
        assert set(item.id for item in step.evidence).issubset(
            set(persisted_case.evidence_ids)
        )
        persisted_evidence = await SqlEvidenceRepository(factory).list_case(
            workspace_id,
            case.id,
        )
        assert set(item.id for item in step.evidence).issubset(
            {item.id for item in persisted_evidence}
        )
        checkpoints = await SqlRunCheckpointRepository(factory).list_run(
            workspace_id,
            started.run.id,
        )
        assert checkpoints == (
            step.pre_call_checkpoint,
            step.post_call_checkpoint,
        )

        run_events = await SqlDomainEventStore(factory).list_run(
            workspace_id,
            started.run.id,
        )
        event_types = [event.event_type for event in run_events]
        assert event_types[:6] == [
            "run.created",
            "run.status_changed",
            "run.phase_changed",
            "model.assigned",
            "path.started",
            "run.checkpoint_saved",
        ]
        assert event_types.count("evidence.appended") == len(step.evidence)
        assert event_types[-2:] == ["path.completed", "run.checkpoint_saved"]
        completed = next(
            event for event in run_events if event.event_type == "path.completed"
        )
        assert completed.payload["provider_request_id"] == (
            step.path_run.telemetry.provider_request_id
        )
        assert completed.payload["actual_model_identity"].startswith("deepseek-v4")
        assert completed.payload["total_tokens"] == (
            step.path_run.telemetry.token_usage.total_tokens
        )

        baseline_by_name = {
            item.metric_name: item.metric_observation_id
            for item in step.path_run.context.analysis.baseline_metrics
        }
        current_by_name = {
            item.metric_name: item.metric_observation_id
            for item in step.path_run.context.analysis.current_metrics
        }
        handling_ids = {
            baseline_by_name[MetricName.HANDLING_TIME_HOURS.value],
            current_by_name[MetricName.HANDLING_TIME_HOURS.value],
        }
        transit_ids = {
            baseline_by_name[MetricName.TRANSIT_TIME_HOURS.value],
            current_by_name[MetricName.TRANSIT_TIME_HOURS.value],
        }
        handling = next(
            item
            for item in step.path_run.result.observations
            if handling_ids.issubset(set(item.metric_observation_ids))
        )
        transit = next(
            item
            for item in step.path_run.result.observations
            if transit_ids.issubset(set(item.metric_observation_ids))
        )
        assert any(
            term in handling.summary.casefold()
            for term in ("did not worsen", "decreased", "lower", "improved")
        )
        assert any(
            term in transit.summary.casefold()
            for term in ("increased", "higher", "worsened", "deteriorated")
        )
        serialized = "".join(
            record.checkpoint.model_dump_json() for record in checkpoints
        )
        assert step.lease.lease_token.get_secret_value() not in serialized
    finally:
        await engine.dispose()
