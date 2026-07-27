"""Fresh V4 E2E for independent Replan -> SellerPeer -> Verification."""

from __future__ import annotations

import importlib
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.commerce.agents.contracts import AgentBudgetLimit, PathType
from app.commerce.agents.lead_execution import CommerceLeadTurnService
from app.commerce.agents.lead_loop import (
    LeadAction,
    LeadTurnIntent,
    LeadTurnRequest,
)
from app.commerce.agents.subagent_adapter import CommerceSubagentStatus
from app.commerce.agents.verification import ClaimVerdict
from app.commerce.agents.verification_execution import (
    CommerceVerificationTurnService,
)
from app.commerce.api.analysis_service import CommerceAnalysisService
from app.commerce.api.data_service import CommerceDataService
from app.commerce.api.run_service import CommerceRunService
from app.commerce.data.gold_cases import load_evaluation_case
from app.commerce.domain.enums import RunPhase, RunStatus, RunType
from app.commerce.domain.events import DomainEventActor
from app.commerce.domain.ids import CorrelationId, TraceId, WorkspaceId
from app.commerce.metrics.registry import MetricWindow, PeerCohortPolicy
from app.commerce.persistence.events import SqlDomainEventStore
from app.commerce.persistence.runs import SqlRunLeaseRepository
from app.commerce.persistence.schema import create_commerce_schema
from app.commerce.persistence.unit_of_work import SqlCommerceUnitOfWork

REPO_ROOT = Path(__file__).parents[4]
CASE_ROOT = REPO_ROOT / "evals" / "commerce" / "cases" / "GC-PEER-004"
TARGET_SELLER_ID = "e5a3438891c0bfdb9394643f95273d8e"


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
async def test_independent_replan_runs_seller_peer_and_fresh_verification(
    tmp_path,
    real_deerflow_subagent_executor,
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
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'replan.db'}")
    await create_commerce_schema(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    lease_ttl = timedelta(minutes=5)
    try:
        outcome = await CommerceAnalysisService(
            data_service=data_service,
            session_factory=factory,
        ).open_explicit_case(
            workspace_id,
            view.manifest.dataset_id,
            seller_id=TARGET_SELLER_ID,
            baseline_window=MetricWindow(
                start=datetime(2017, 7, 1),
                end=datetime(2018, 1, 1),
            ),
            current_window=MetricWindow(
                start=datetime(2018, 1, 1),
                end=datetime(2018, 7, 1),
            ),
            requested_paths=(PathType.FULFILLMENT, PathType.SELLER_PEER),
            peer_policy=PeerCohortPolicy(
                product_category="fashion_bolsas_e_acessorios",
                min_orders_per_seller=20,
            ),
        )
        case = outcome.cases[0]
        run_service = CommerceRunService(factory)
        parent = await run_service.start_investigation(
            workspace_id,
            case.id,
            goal="Preserve the first bounded investigation before replanning",
            idempotency_key="replan-live-parent",
        )
        leases = SqlRunLeaseRepository(factory)
        parent_grant = await leases.acquire(
            workspace_id,
            parent.run.id,
            worker_id="replan-live-parent-worker",
            ttl=lease_ttl,
            acquired_at=datetime.now(UTC),
            trace_id=TraceId.new(),
            correlation_id=CorrelationId.new(),
        )
        terminal_at = max(datetime.now(UTC), parent_grant.run.updated_at)
        blocked_parent = parent_grant.run.transition_to(
            RunStatus.BLOCKED,
            phase=RunPhase.VERIFYING,
            stop_reason="verification_replan_required",
            occurred_at=terminal_at,
        )
        correlation_id = CorrelationId.new()
        trace_id = TraceId.new()
        await SqlCommerceUnitOfWork(factory).save_run(
            blocked_parent,
            expected_version=parent_grant.run.version,
            trace_id=trace_id,
            correlation_id=correlation_id,
            actor=DomainEventActor.AGENT,
            lease=parent_grant.credentials,
            lease_checked_at=terminal_at,
        )
        await leases.release(
            workspace_id,
            blocked_parent.id,
            parent_grant.credentials,
            released_at=max(datetime.now(UTC), terminal_at),
            trace_id=trace_id,
            correlation_id=correlation_id,
        )

        child = await run_service.start_replan(
            workspace_id,
            blocked_parent.id,
            goal=evaluation_case.input_bundle.user_prompt,
            requested_paths=(PathType.SELLER_PEER,),
            idempotency_key="replan-live-child",
        )
        child_grant = await leases.acquire(
            workspace_id,
            child.run.id,
            worker_id="replan-live-child-worker",
            ttl=lease_ttl,
            acquired_at=max(datetime.now(UTC), child.run.updated_at),
            trace_id=TraceId.new(),
            correlation_id=CorrelationId.new(),
        )
        budget = AgentBudgetLimit(
            max_iterations=5,
            max_tokens=30_000,
            max_wall_time_seconds=600,
            max_model_escalations=2,
        )
        turn = await CommerceLeadTurnService(
            data_service=data_service,
            session_factory=factory,
            lease_ttl=lease_ttl,
        ).execute(
            workspace_id,
            child.run.id,
            request=LeadTurnRequest(
                intent=LeadTurnIntent.NEW_INVESTIGATION_ANGLE,
                question=child.run.goal,
                requested_paths=child.run.requested_paths,
            ),
            budget=budget,
            lease=child_grant.credentials,
            correlation_id=CorrelationId.new(),
        )

        assert turn.run.run_type is RunType.REPLAN
        assert turn.run.parent_run_id == blocked_parent.id
        assert turn.decision.action is LeadAction.REPLAN
        assert turn.decision.selected_paths == (PathType.SELLER_PEER,)
        assert turn.fanout is not None
        assert len(turn.fanout.outcomes) == 1
        outcome = turn.fanout.outcomes[0]
        assert outcome.status is CommerceSubagentStatus.COMPLETED
        assert outcome.result is not None
        assert outcome.result.path_type is PathType.SELLER_PEER
        assert outcome.result.model_execution.actual_model_identity.startswith(
            "deepseek-v4"
        )
        assert outcome.result.model_execution.provider_request_id
        assert outcome.result.model_execution.retry_count == 0
        assert turn.lead_run is not None
        assert turn.lead_run.telemetry.actual_model_identity is not None
        assert turn.lead_run.telemetry.actual_model_identity.startswith(
            "deepseek-v4"
        )
        assert turn.lead_run.telemetry.provider_request_id
        assert turn.lead_run.telemetry.retry_count == 0
        assert turn.proposed_hypothesis_ids

        verification = await CommerceVerificationTurnService(
            data_service=data_service,
            session_factory=factory,
            lease_ttl=lease_ttl,
        ).verify(
            workspace_id,
            child.run.id,
            hypothesis_ids=turn.proposed_hypothesis_ids,
            budget=budget,
            lease=child_grant.credentials,
            correlation_id=CorrelationId.new(),
        )

        assert verification.verification.actual_model_identity.startswith(
            "deepseek-v4"
        )
        assert verification.verification.provider_request_id
        assert verification.verification.retry_count == 0
        assert verification.verification.context.analysis.supplemental_metrics
        assert verification.goal_decision.stop_reason is not None
        if verification.verification.result.overall_verdict is ClaimVerdict.PASS:
            assert verification.run.status is RunStatus.COMPLETED
        else:
            assert verification.run.status is RunStatus.BLOCKED
        events = await SqlDomainEventStore(factory).list_run(
            workspace_id,
            child.run.id,
        )
        event_types = [event.event_type for event in events]
        assert event_types.count("path.started") == 1
        assert event_types.count("path.completed") == 1
        assert "lead.completed" in event_types
        assert "verification.completed" in event_types
        assert "goal_loop.stopped" in event_types
        assert event_types[-1] == "run.lease_released"
    finally:
        await engine.dispose()
