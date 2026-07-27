"""Deterministic Path metric reconstruction after a process restart."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.commerce.agents.context_loader import ContextPacketLoader
from app.commerce.agents.contracts import (
    AgentBudgetLimit,
    PathEvidenceScope,
    PathType,
)
from app.commerce.agents.lead import build_persisted_lead_context
from app.commerce.agents.lead_execution import CommercePathPreparationService
from app.commerce.agents.lead_loop import (
    CommerceLeadObserver,
    LeadAction,
    LeadActionDecision,
    LeadActionReasonCode,
    LeadLoopPlanner,
    LeadTurnIntent,
    LeadTurnRequest,
)
from app.commerce.agents.router import DynamicPathRouter, summarize_case_signals
from app.commerce.agents.verification_subagent import (
    build_fresh_verification_packet,
)
from app.commerce.api.analysis_service import CommerceAnalysisService
from app.commerce.api.data_service import CommerceDataService
from app.commerce.api.run_service import CommerceRunService
from app.commerce.data.gold_cases import load_evaluation_case
from app.commerce.domain.enums import RunPhase, RunStatus, SemanticStatus
from app.commerce.domain.events import DomainEventActor, NewDomainEvent
from app.commerce.domain.ids import (
    CorrelationId,
    EvidenceId,
    TraceId,
    WorkspaceId,
)
from app.commerce.domain.models import Evidence, EvidenceRelation
from app.commerce.metrics.registry import MetricWindow, PeerCohortPolicy
from app.commerce.persistence.events import SqlDomainEventStore
from app.commerce.persistence.repositories import SqlCaseRepository
from app.commerce.persistence.runs import (
    SqlRunLeaseRepository,
    SqlRunRepository,
)
from app.commerce.persistence.schema import create_commerce_schema
from app.commerce.persistence.unit_of_work import SqlCommerceUnitOfWork

REPO_ROOT = Path(__file__).parents[4]
CASE_ROOT = REPO_ROOT / "evals" / "commerce" / "cases" / "GC-PEER-004"
TARGET_SELLER_ID = "e5a3438891c0bfdb9394643f95273d8e"


@pytest.mark.anyio
async def test_seller_peer_scope_rebuilds_metrics_for_fresh_verification(tmp_path):
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
            seller_id=TARGET_SELLER_ID,
            baseline_window=MetricWindow(
                start=datetime(2017, 7, 1),
                end=datetime(2018, 1, 1),
            ),
            current_window=MetricWindow(
                start=datetime(2018, 1, 1),
                end=datetime(2018, 7, 1),
            ),
            requested_paths=(PathType.SELLER_PEER,),
            peer_policy=PeerCohortPolicy(
                product_category="fashion_bolsas_e_acessorios",
                min_orders_per_seller=20,
            ),
        )
        case = outcome.cases[0]
        started = await CommerceRunService(factory).start_investigation(
            workspace_id,
            case.id,
            goal=evaluation_case.input_bundle.user_prompt,
            idempotency_key="seller-peer-reconstruction",
        )
        grant = await SqlRunLeaseRepository(factory).acquire(
            workspace_id,
            started.run.id,
            worker_id="seller-peer-reconstruction-worker",
            ttl=timedelta(minutes=5),
            acquired_at=datetime.now(UTC),
            trace_id=TraceId.new(),
            correlation_id=CorrelationId.new(),
        )
        budget = AgentBudgetLimit(max_tokens=16_000)
        loader = ContextPacketLoader(
            data_service=data_service,
            session_factory=factory,
        )
        base = await loader.load_case_packet(
            workspace_id,
            case.id,
            goal=started.run.goal,
            budget=budget,
        )
        observation = await CommerceLeadObserver(
            data_service=data_service,
            session_factory=factory,
        ).observe(workspace_id, started.run.id, budget=budget)
        prepared = await CommercePathPreparationService(
            data_service=data_service
        ).prepare(
            observation=observation,
            decision=LeadActionDecision(
                action=LeadAction.INVESTIGATE,
                selected_paths=(PathType.SELLER_PEER,),
                reason_codes=frozenset(
                    {LeadActionReasonCode.MISSING_PATH_EVIDENCE}
                ),
            ),
        )
        peer_context = prepared[0].spec.plan.context

        assert peer_context.manifest.source_artifact_sha256 == (
            base.manifest.source_artifact_sha256
        )
        peer_metric_ids = (
            peer_context.target_rate.metric_observation_id,
            peer_context.peer_rate.metric_observation_id,
        )
        persisted_case = await SqlCaseRepository(factory).get(
            workspace_id,
            case.id,
        )
        assert persisted_case is not None
        evidence = Evidence(
            id=EvidenceId.new(),
            workspace_id=workspace_id,
            case_id=case.id,
            summary=(
                "The target late-delivery rate is above the deterministic "
                "outcome-agnostic matched-peer rate."
            ),
            relation=EvidenceRelation.CONTEXT,
            semantic_status=SemanticStatus.DERIVED,
            confidence=0.9,
            metric_observation_ids=peer_metric_ids,
        )
        updated_case = persisted_case.model_copy(
            update={
                "evidence_ids": (*persisted_case.evidence_ids, evidence.id),
                "updated_at": datetime.now(UTC),
                "version": persisted_case.version + 1,
            }
        )
        trace_id = TraceId.new()
        correlation_id = CorrelationId.new()
        await SqlCommerceUnitOfWork(factory).append_evidence(
            updated_case,
            evidence,
            expected_version=persisted_case.version,
            trace_id=trace_id,
            correlation_id=correlation_id,
            actor=DomainEventActor.AGENT,
        )
        scope = PathEvidenceScope.from_manifest(
            peer_context.manifest,
            run_id=started.run.id,
            task_id=prepared[0].spec.build_task(
                run_id=started.run.id,
                lease_worker_id=grant.credentials.worker_id,
                fencing_token=grant.credentials.fencing_token,
                trace_id=trace_id,
                correlation_id=correlation_id,
            ).task_id,
            path_type=PathType.SELLER_PEER,
            evidence_ids=(evidence.id,),
        )
        await SqlDomainEventStore(factory).append(
            NewDomainEvent(
                workspace_id=workspace_id,
                case_id=case.id,
                run_id=started.run.id,
                event_type="path.completed",
                trace_id=trace_id,
                correlation_id=correlation_id,
                actor=DomainEventActor.AGENT,
                payload={
                    "task_id": str(scope.task_id),
                    "path_type": PathType.SELLER_PEER.value,
                    "evidence_ids": [str(evidence.id)],
                    "evidence_scope": scope.model_dump(mode="json"),
                },
            )
        )

        recovered = await loader.load_case_packet(
            workspace_id,
            case.id,
            goal="Reload after the worker process restarted",
            budget=budget,
        )
        reconstructed = {
            item.metric_observation_id: item
            for item in recovered.analysis.supplemental_metrics
        }
        assert set(reconstructed) == set(
            peer_context.manifest.included_metric_observation_ids
        )
        assert reconstructed[peer_metric_ids[0]].value == (
            peer_context.target_rate.value
        )
        assert reconstructed[peer_metric_ids[1]].value == (
            peer_context.peer_rate.value
        )

        persisted = build_persisted_lead_context(
            recovered,
            path_scopes=(scope,),
        )
        verification = build_fresh_verification_packet(
            base=recovered,
            persisted=persisted,
            claims=(evidence.summary,),
            claim_evidence_ids=((evidence.id,),),
        )
        assert verification.analysis.baseline_metrics == ()
        assert verification.analysis.current_metrics == ()
        assert {
            item.metric_observation_id
            for item in verification.analysis.supplemental_metrics
        } == set(peer_metric_ids)
        assert verification.manifest.included_metric_observation_ids == (
            peer_metric_ids
        )

        parent = await SqlRunRepository(factory).get(
            workspace_id,
            started.run.id,
        )
        assert parent is not None
        terminal_parent = parent.transition_to(
            RunStatus.COMPLETED,
            phase=RunPhase.VERIFYING,
            stop_reason="goal_achieved",
            occurred_at=max(datetime.now(UTC), parent.updated_at),
        )
        await SqlRunRepository(factory).save(
            terminal_parent,
            expected_version=parent.version,
        )
        child = await CommerceRunService(factory).start_replan(
            workspace_id,
            terminal_parent.id,
            goal="Check the remaining fulfillment angle",
            requested_paths=(PathType.SELLER_PEER, PathType.FULFILLMENT),
            idempotency_key="seller-peer-child-replan",
        )
        await SqlRunLeaseRepository(factory).acquire(
            workspace_id,
            child.run.id,
            worker_id="seller-peer-child-worker",
            ttl=timedelta(minutes=5),
            acquired_at=max(datetime.now(UTC), child.run.updated_at),
            trace_id=TraceId.new(),
            correlation_id=CorrelationId.new(),
        )
        child_observation = await CommerceLeadObserver(
            data_service=data_service,
            session_factory=factory,
        ).observe(workspace_id, child.run.id, budget=budget)
        assert child_observation.scope_run_ids == (
            terminal_parent.id,
            child.run.id,
        )
        assert child_observation.planning_state.completed_path_types == (
            PathType.SELLER_PEER,
        )
        route_plan = DynamicPathRouter().route(
            child_observation.context.capability_profile,
            summarize_case_signals(child_observation.context.analysis).model_copy(
                update={
                    "requested_paths": frozenset(
                        {
                            PathType.SELLER_PEER,
                            PathType.FULFILLMENT,
                        }
                    )
                }
            ),
        )
        decision = LeadLoopPlanner().decide(
            request=LeadTurnRequest(
                intent=LeadTurnIntent.NEW_INVESTIGATION_ANGLE,
                question=child.run.goal,
                requested_paths=child.run.requested_paths,
            ),
            state=child_observation.planning_state,
            route_plan=route_plan,
        )
        assert decision.action is LeadAction.REPLAN
        assert decision.selected_paths == (PathType.FULFILLMENT,)
    finally:
        await engine.dispose()
