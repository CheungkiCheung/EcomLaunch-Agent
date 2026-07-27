"""Fresh real-model fenced persistence for the DeerFlow Fulfillment Subagent."""

from __future__ import annotations

import asyncio
import importlib
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.commerce.agents.budget import BudgetSnapshot, BudgetUsage
from app.commerce.agents.context_loader import ContextPacketLoader
from app.commerce.agents.contracts import AgentBudgetLimit
from app.commerce.agents.fulfillment import FulfillmentPathAgent
from app.commerce.agents.fulfillment_subagent import (
    FulfillmentSubagentSpec,
    build_fulfillment_read_tools,
)
from app.commerce.agents.goal_loop import SkillVersionRef
from app.commerce.agents.subagent_adapter import CommerceSubagentStatus
from app.commerce.agents.subagent_committer import CommerceSubagentCommitter
from app.commerce.agents.subagent_supervisor import CommerceSubagentSupervisor
from app.commerce.api.analysis_service import CommerceAnalysisService
from app.commerce.api.data_service import CommerceDataService
from app.commerce.api.run_service import CommerceRunService
from app.commerce.data.gold_cases import load_evaluation_case
from app.commerce.domain.ids import CorrelationId, TraceId, WorkspaceId
from app.commerce.evaluation.real_model_preflight import (
    PreflightStatus,
    run_real_model_preflight,
)
from app.commerce.metrics.registry import MetricWindow
from app.commerce.persistence.events import SqlDomainEventStore
from app.commerce.persistence.repositories import SqlCaseRepository
from app.commerce.persistence.runs import (
    SqlRunCheckpointRepository,
    SqlRunLeaseRepository,
)
from app.commerce.persistence.schema import create_commerce_schema
from app.commerce.persistence.unit_of_work import SqlCommerceUnitOfWork
from app.commerce.persistence.work_records import SqlEvidenceRepository

REPO_ROOT = Path(__file__).parents[4]
CASE_ROOT = REPO_ROOT / "evals" / "commerce" / "cases" / "GC-FULFILLMENT-001"
SELLER_ID = "4869f7a5dfa277a7dca6462dcf3b52b2"


@pytest.fixture
def real_deerflow_subagent_executor():
    """Replace the suite-wide circular-import mock with the real executor."""

    __import__("deerflow.agents")
    module_name = "deerflow.subagents.executor"
    package = sys.modules["deerflow.subagents"]
    original_module = sys.modules.get(module_name)
    original_attribute = getattr(package, "executor", None)
    sys.modules.pop(module_name, None)
    if hasattr(package, "executor"):
        delattr(package, "executor")
    module = importlib.import_module(module_name)
    try:
        yield module
    finally:
        sys.modules.pop(module_name, None)
        if original_module is not None:
            sys.modules[module_name] = original_module
        if original_attribute is not None:
            setattr(package, "executor", original_attribute)


@pytest.mark.real_model
@pytest.mark.anyio
async def test_supervisor_commits_real_subagent_evidence_events_and_budget(
    tmp_path,
    real_deerflow_subagent_executor,
):
    """Persist runtime telemetry and Evidence under the active fencing token."""

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
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'supervisor.db'}")
    await create_commerce_schema(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    adapter = None
    task = None
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
            idempotency_key="live-fulfillment-subagent-supervisor",
        )
        leases = SqlRunLeaseRepository(factory)
        grant = await leases.acquire(
            workspace_id,
            started.run.id,
            worker_id="live-fulfillment-subagent-supervisor-worker",
            ttl=timedelta(minutes=5),
            acquired_at=datetime.now(UTC),
            trace_id=TraceId.new(),
            correlation_id=CorrelationId.new(),
        )
        run_budget = AgentBudgetLimit(
            max_iterations=4,
            max_tokens=16_000,
            max_wall_time_seconds=300,
        )
        initial = await ContextPacketLoader(
            data_service=data_service,
            session_factory=factory,
        ).load_initial(
            workspace_id,
            started.run.id,
            budget=run_budget,
        )
        plan = await FulfillmentPathAgent().prepare(initial.packet)
        spec = FulfillmentSubagentSpec(plan)
        task = spec.build_task(
            run_id=started.run.id,
            lease_worker_id=grant.credentials.worker_id,
            fencing_token=grant.credentials.fencing_token,
            trace_id=TraceId.new(),
            correlation_id=CorrelationId.new(),
        )
        skill = SkillVersionRef(skill_id=task.skill_id, version=task.skill_version)
        pre_checkpoint = initial.checkpoint.model_copy(
            update={
                "active_path_task_ids": (task.task_id,),
                "model_assignments": (task.model_assignment,),
                "skill_versions": (skill,),
                "context_sha256": task.context_sha256,
            }
        )
        adapter = spec.build_adapter(tools=build_fulfillment_read_tools(plan.context))
        committer = CommerceSubagentCommitter(
            uow=SqlCommerceUnitOfWork(factory),
            cases=SqlCaseRepository(factory),
            evidence=SqlEvidenceRepository(factory),
        )

        def build_post_checkpoint(outcome):
            tokens = 0
            wall_time_seconds = 0.0
            if outcome.result is not None:
                tokens = (
                    outcome.result.cost.input_tokens
                    + outcome.result.cost.output_tokens
                )
                wall_time_seconds = outcome.result.cost.latency_ms / 1000
            prior = pre_checkpoint.budget_snapshot.usage
            usage = BudgetUsage(
                **{
                    **prior.model_dump(),
                    "path_agents": prior.path_agents + 1,
                    "tool_calls": prior.tool_calls + len(outcome.tool_events),
                    "tokens": prior.tokens + tokens,
                    "wall_time_seconds": (
                        prior.wall_time_seconds + wall_time_seconds
                    ),
                }
            )
            return pre_checkpoint.model_copy(
                update={
                    "budget_snapshot": BudgetSnapshot(
                        limit=pre_checkpoint.budget_snapshot.limit,
                        usage=usage,
                    ),
                    "active_path_task_ids": (),
                }
            )

        preflight = await asyncio.to_thread(run_real_model_preflight)
        assert preflight.status is PreflightStatus.PASSED, preflight.model_dump_json()
        supervised = await CommerceSubagentSupervisor(
            adapter=adapter,
            committer=committer,
            leases=leases,
            lease_ttl=timedelta(minutes=5),
            poll_interval_seconds=0.25,
            max_polls=240,
        ).run(
            task,
            context=plan.context,
            manifest=plan.context.manifest,
            pre_checkpoint=pre_checkpoint,
            post_checkpoint_builder=build_post_checkpoint,
            lease=grant.credentials,
        )

        assert supervised.outcome.status is CommerceSubagentStatus.COMPLETED
        assert supervised.terminal_commit.status is CommerceSubagentStatus.COMPLETED
        assert supervised.terminal_commit.evidence_ids
        assert supervised.outcome.result is not None
        result = supervised.outcome.result

        persisted_case = await SqlCaseRepository(factory).get(
            workspace_id,
            started.run.case_id,
        )
        assert persisted_case is not None
        assert set(supervised.terminal_commit.evidence_ids).issubset(
            persisted_case.evidence_ids
        )
        persisted_evidence = await SqlEvidenceRepository(factory).list_case(
            workspace_id,
            started.run.case_id,
        )
        persisted_evidence_ids = {item.id for item in persisted_evidence}
        assert set(supervised.terminal_commit.evidence_ids).issubset(
            persisted_evidence_ids
        )
        assert len(supervised.terminal_commit.evidence_ids) == len(
            set(supervised.terminal_commit.evidence_ids)
        )

        checkpoints = await SqlRunCheckpointRepository(factory).list_run(
            workspace_id,
            started.run.id,
        )
        assert tuple(item.sequence for item in checkpoints) == (1, 2)
        post = checkpoints[-1].checkpoint
        assert post.active_path_task_ids == ()
        assert post.budget_snapshot.usage.path_agents == 1
        assert post.budget_snapshot.usage.tool_calls == len(
            supervised.outcome.tool_events
        )
        assert post.budget_snapshot.usage.tokens == (
            result.cost.input_tokens + result.cost.output_tokens
        )
        assert post.budget_snapshot.usage.wall_time_seconds == pytest.approx(
            result.cost.latency_ms / 1000
        )

        events = await SqlDomainEventStore(factory).list_run(
            workspace_id,
            started.run.id,
        )
        path_completed = next(
            event for event in events if event.event_type == "path.completed"
        )
        assert path_completed.payload["provider_request_id"] == (
            result.model_execution.provider_request_id
        )
        assert path_completed.payload["actual_model_identity"] == (
            result.model_execution.actual_model_identity
        )
        assert path_completed.payload["total_tokens"] == (
            result.cost.input_tokens + result.cost.output_tokens
        )
        assert path_completed.payload["latency_ms"] == result.cost.latency_ms
        assert path_completed.payload["tool_call_count"] == len(
            supervised.outcome.tool_events
        )
    finally:
        if adapter is not None and task is not None:
            adapter.cleanup(task)
        await engine.dispose()
