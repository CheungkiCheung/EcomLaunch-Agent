"""Deterministic, fail-closed initial ContextPacket loading contracts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import SecretStr
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.commerce.agents.context_loader import (
    ContextLoadError,
    ContextLoadReason,
    ContextPacketLoader,
)
from app.commerce.agents.contracts import (
    AgentBudgetLimit,
    PathEvidenceScope,
    PathType,
    canonical_context_sha256,
)
from app.commerce.agents.goal_loop import GoalStopReason
from app.commerce.agents.lead import build_persisted_lead_context
from app.commerce.agents.lead_execution import (
    CommerceLeadTurnService,
    CommercePathPreparationService,
)
from app.commerce.agents.lead_loop import (
    CommerceLeadObserver,
    LeadAction,
    LeadActionDecision,
    LeadActionReasonCode,
    LeadTurnIntent,
    LeadTurnRequest,
)
from app.commerce.agents.verification_subagent import (
    build_fresh_verification_packet,
)
from app.commerce.api.analysis_service import CommerceAnalysisService
from app.commerce.api.data_service import CommerceDataService
from app.commerce.api.run_service import CommerceRunService
from app.commerce.data.gold_cases import load_evaluation_case
from app.commerce.domain.enums import RunStatus, SemanticStatus
from app.commerce.domain.events import (
    DomainEventActor,
    NewDomainEvent,
)
from app.commerce.domain.ids import (
    AgentTaskId,
    CaseId,
    CorrelationId,
    DatasetId,
    EvidenceId,
    MetricObservationId,
    RunId,
    TraceId,
    WorkspaceId,
)
from app.commerce.domain.models import Evidence, EvidenceRelation
from app.commerce.metrics.registry import MetricWindow
from app.commerce.persistence.events import SqlDomainEventStore
from app.commerce.persistence.models import CaseLineageRow, EvidenceRow
from app.commerce.persistence.repositories import SqlCaseRepository
from app.commerce.persistence.runs import (
    RunLeaseLostError,
    SqlRunLeaseRepository,
)
from app.commerce.persistence.schema import create_commerce_schema
from app.commerce.persistence.unit_of_work import SqlCommerceUnitOfWork

REPO_ROOT = Path(__file__).parents[4]
CASE_ROOT = REPO_ROOT / "evals" / "commerce" / "cases" / "GC-FULFILLMENT-001"
SELLER_ID = "4869f7a5dfa277a7dca6462dcf3b52b2"


@dataclass(frozen=True)
class _Seed:
    engine: AsyncEngine
    factory: async_sessionmaker
    data_service: CommerceDataService
    workspace_id: WorkspaceId
    dataset_id: DatasetId
    case_id: CaseId
    run_id: RunId
    grant: object
    artifact_path: Path


async def _seed(tmp_path: Path) -> _Seed:
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
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'context.db'}")
    await create_commerce_schema(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
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
        goal="Find the strongest traceable explanation for this anomaly",
        idempotency_key="context-loader-test",
    )
    acquired_at = datetime.now(UTC) + timedelta(seconds=1)
    grant = await SqlRunLeaseRepository(factory).acquire(
        workspace_id,
        started.run.id,
        worker_id="context-loader-test-worker",
        ttl=timedelta(minutes=5),
        acquired_at=acquired_at,
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
    )
    async with factory() as session:
        lineage = await session.get(CaseLineageRow, str(case.id))
    assert lineage is not None
    artifact_path = storage_root / str(workspace_id) / str(view.manifest.dataset_id) / lineage.analysis_artifact_relative_path
    return _Seed(
        engine=engine,
        factory=factory,
        data_service=data_service,
        workspace_id=workspace_id,
        dataset_id=view.manifest.dataset_id,
        case_id=case.id,
        run_id=started.run.id,
        grant=grant,
        artifact_path=artifact_path,
    )


def _loader(seed: _Seed) -> ContextPacketLoader:
    return ContextPacketLoader(
        data_service=seed.data_service,
        session_factory=seed.factory,
    )


async def _rewrite_artifact(
    seed: _Seed,
    mutate,
    *,
    update_persisted_sha: bool,
) -> None:
    payload = json.loads(seed.artifact_path.read_text(encoding="utf-8"))
    mutate(payload)
    seed.artifact_path.chmod(0o600)
    seed.artifact_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if update_persisted_sha:
        digest = hashlib.sha256(seed.artifact_path.read_bytes()).hexdigest()
        async with seed.factory() as session, session.begin():
            await session.execute(update(CaseLineageRow).where(CaseLineageRow.case_id == str(seed.case_id)).values(analysis_artifact_sha256=digest))


@pytest.mark.anyio
async def test_loader_exposes_verified_case_analysis_without_agent_budget(tmp_path):
    seed = await _seed(tmp_path)

    loaded = await _loader(seed).load_case_analysis(
        seed.workspace_id,
        seed.case_id,
    )

    assert loaded.case.id == seed.case_id
    assert loaded.lineage.dataset_id == seed.dataset_id
    assert loaded.artifact.case_id == seed.case_id
    assert loaded.artifact.baseline.observations
    assert loaded.artifact.current.observations
    assert loaded.artifact_sha256 == hashlib.sha256(seed.artifact_path.read_bytes()).hexdigest()
    await seed.engine.dispose()


@pytest.mark.anyio
async def test_loader_builds_canonical_minimal_context_and_initial_checkpoint(tmp_path):
    seed = await _seed(tmp_path)
    loaded = await _loader(seed).load_initial(
        seed.workspace_id,
        seed.run_id,
        budget=AgentBudgetLimit(max_tokens=16_000),
        resume_token=SecretStr("resume-only-in-worker-memory"),
    )

    assert loaded.packet.case.case_id == seed.case_id
    assert loaded.packet.manifest.workspace_id == seed.workspace_id
    assert loaded.packet.manifest.dataset_id == seed.dataset_id
    assert loaded.packet.manifest.source_artifact_sha256 == hashlib.sha256(seed.artifact_path.read_bytes()).hexdigest()
    assert loaded.packet.manifest.context_sha256 == canonical_context_sha256(loaded.packet)
    assert loaded.packet.manifest.estimated_tokens <= loaded.packet.budget.max_tokens
    assert loaded.packet.analysis.seller_external_key == SELLER_ID
    assert loaded.packet.capabilities
    assert loaded.packet.evidence
    assert set(loaded.packet.manifest.included_evidence_ids) == set(loaded.state.evidence_ids)
    assert loaded.state.loop_iteration == 0
    assert loaded.state.context_sha256 == loaded.packet.manifest.context_sha256
    assert loaded.checkpoint.loop_iteration == 0
    assert loaded.checkpoint.budget_snapshot.usage.iterations == 0
    serialized = loaded.checkpoint.model_dump_json()
    assert "resume-only-in-worker-memory" not in serialized
    assert loaded.state.resume_token_sha256 == hashlib.sha256(b"resume-only-in-worker-memory").hexdigest()

    with pytest.raises(Exception, match="requires a lease"):
        await SqlCommerceUnitOfWork(seed.factory).append_run_checkpoint(
            loaded.checkpoint,
            trace_id=TraceId.new(),
            correlation_id=CorrelationId.new(),
            actor=DomainEventActor.AGENT,
        )
    record, event = await SqlCommerceUnitOfWork(seed.factory).append_run_checkpoint(
        loaded.checkpoint,
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
        actor=DomainEventActor.AGENT,
        lease=seed.grant.credentials,
        lease_checked_at=seed.grant.acquired_at + timedelta(seconds=1),
    )
    assert record.sequence == 1
    assert event.event_type == "run.checkpoint_saved"
    with pytest.raises(ContextLoadError) as duplicate_initialization:
        await _loader(seed).load_initial(
            seed.workspace_id,
            seed.run_id,
            budget=AgentBudgetLimit(max_tokens=16_000),
        )
    assert duplicate_initialization.value.reason is ContextLoadReason.CHECKPOINT_ALREADY_EXISTS
    await seed.engine.dispose()


@pytest.mark.anyio
async def test_loader_rejects_unreconstructable_path_metric_scope(tmp_path):
    seed = await _seed(tmp_path)
    loader = _loader(seed)
    before = await loader.load_case_packet(
        seed.workspace_id,
        seed.case_id,
        goal="Explain the anomaly",
        budget=AgentBudgetLimit(max_tokens=16_000),
    )
    case = await SqlCaseRepository(seed.factory).get(seed.workspace_id, seed.case_id)
    assert case is not None
    peer_metric_id = MetricObservationId.new()
    peer_evidence = Evidence(
        id=EvidenceId.new(),
        workspace_id=seed.workspace_id,
        case_id=seed.case_id,
        summary="The target seller is above its persisted deterministic peer rate",
        relation=EvidenceRelation.CONTEXT,
        semantic_status=SemanticStatus.DERIVED,
        confidence=0.88,
        metric_observation_ids=(peer_metric_id,),
    )
    updated_case = case.model_copy(
        update={
            "evidence_ids": (*case.evidence_ids, peer_evidence.id),
            "updated_at": datetime.now(UTC),
            "version": case.version + 1,
        }
    )
    trace_id = TraceId.new()
    correlation_id = CorrelationId.new()
    await SqlCommerceUnitOfWork(seed.factory).append_evidence(
        updated_case,
        peer_evidence,
        expected_version=case.version,
        trace_id=trace_id,
        correlation_id=correlation_id,
        actor=DomainEventActor.AGENT,
    )
    task_id = AgentTaskId.new()
    scope = PathEvidenceScope(
        workspace_id=seed.workspace_id,
        case_id=seed.case_id,
        run_id=seed.run_id,
        task_id=task_id,
        path_type=PathType.SELLER_PEER,
        dataset_id=seed.dataset_id,
        context_version="commerce-seller-peer-context@1.0.0",
        context_sha256="c" * 64,
        source_artifact_sha256=before.manifest.source_artifact_sha256,
        evidence_ids=(peer_evidence.id,),
        included_metric_observation_ids=(peer_metric_id,),
    )
    await SqlDomainEventStore(seed.factory).append(
        NewDomainEvent(
            workspace_id=seed.workspace_id,
            case_id=seed.case_id,
            run_id=seed.run_id,
            event_type="path.completed",
            trace_id=trace_id,
            correlation_id=correlation_id,
            actor=DomainEventActor.AGENT,
            payload={
                "task_id": str(task_id),
                "path_type": PathType.SELLER_PEER.value,
                "evidence_ids": [str(peer_evidence.id)],
                "evidence_scope": scope.model_dump(mode="json"),
            },
        )
    )

    with pytest.raises(ContextLoadError) as error:
        await loader.load_case_packet(
            seed.workspace_id,
            seed.case_id,
            goal="Explain the anomaly after process restart",
            budget=AgentBudgetLimit(max_tokens=16_000),
        )
    assert error.value.reason is ContextLoadReason.PATH_EVIDENCE_SCOPE_INVALID
    assert "outcome-agnostic policy" in str(error.value)
    await seed.engine.dispose()


@pytest.mark.anyio
async def test_lead_selected_paths_prepare_case_bound_coordinator_entries(tmp_path):
    seed = await _seed(tmp_path)
    observation = await CommerceLeadObserver(
        data_service=seed.data_service,
        session_factory=seed.factory,
    ).observe(
        seed.workspace_id,
        seed.run_id,
        budget=AgentBudgetLimit(max_tokens=16_000),
    )
    decision = LeadActionDecision(
        action=LeadAction.INVESTIGATE,
        selected_paths=(PathType.FULFILLMENT,),
        reason_codes=frozenset({LeadActionReasonCode.MISSING_PATH_EVIDENCE}),
    )

    prepared = await CommercePathPreparationService(data_service=seed.data_service).prepare(observation=observation, decision=decision)

    assert len(prepared) == 1
    context = prepared[0].spec.plan.context
    assert context.case == observation.context.case
    assert context.path_type is PathType.FULFILLMENT
    assert {tool.name for tool in prepared[0].tool_builder(context)} == {
        "metric_query",
        "source_fact_lookup",
    }
    assert prepared[0].spec.plan.assignment.model_alias == "deepseek-reasoner"
    await seed.engine.dispose()


@pytest.mark.anyio
async def test_lead_wait_persists_checkpoint_releases_lease_and_resumes(tmp_path):
    seed = await _seed(tmp_path)
    lease_ttl = timedelta(minutes=5)
    service = CommerceLeadTurnService(
        data_service=seed.data_service,
        session_factory=seed.factory,
        lease_ttl=lease_ttl,
    )
    budget = AgentBudgetLimit(max_tokens=16_000)

    waiting = await service.execute(
        seed.workspace_id,
        seed.run_id,
        request=LeadTurnRequest(
            intent=LeadTurnIntent.WAIT,
            wait_reason=GoalStopReason.AWAITING_USER_INPUT,
        ),
        budget=budget,
        lease=seed.grant.credentials,
        correlation_id=CorrelationId.new(),
    )

    assert waiting.decision.action is LeadAction.WAIT
    assert waiting.run.status is RunStatus.WAITING
    assert waiting.run.wait_reason == GoalStopReason.AWAITING_USER_INPUT.value
    assert waiting.final_checkpoint is not None
    assert waiting.final_checkpoint.checkpoint.wait_reason is (GoalStopReason.AWAITING_USER_INPUT)
    leases = SqlRunLeaseRepository(seed.factory)
    with pytest.raises(RunLeaseLostError):
        await leases.heartbeat(
            seed.workspace_id,
            seed.run_id,
            seed.grant.credentials,
            ttl=lease_ttl,
            heartbeat_at=datetime.now(UTC),
        )

    resumed = await leases.acquire(
        seed.workspace_id,
        seed.run_id,
        worker_id="context-loader-resumed-worker",
        ttl=lease_ttl,
        acquired_at=datetime.now(UTC) + timedelta(seconds=1),
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
    )
    assert resumed.run.status is RunStatus.RUNNING
    assert resumed.run.wait_reason is None
    assert resumed.latest_checkpoint is not None
    assert resumed.latest_checkpoint.checkpoint.wait_reason is (GoalStopReason.AWAITING_USER_INPUT)
    events = await SqlDomainEventStore(seed.factory).list_run(
        seed.workspace_id,
        seed.run_id,
    )
    assert "lead.waiting" in [event.event_type for event in events]
    assert "run.lease_released" in [event.event_type for event in events]
    await seed.engine.dispose()


@pytest.mark.anyio
async def test_lead_cancel_stops_run_and_fences_old_worker(tmp_path):
    seed = await _seed(tmp_path)
    lease_ttl = timedelta(minutes=5)

    stopped = await CommerceLeadTurnService(
        data_service=seed.data_service,
        session_factory=seed.factory,
        lease_ttl=lease_ttl,
    ).execute(
        seed.workspace_id,
        seed.run_id,
        request=LeadTurnRequest(intent=LeadTurnIntent.CANCEL),
        budget=AgentBudgetLimit(max_tokens=16_000),
        lease=seed.grant.credentials,
        correlation_id=CorrelationId.new(),
    )

    assert stopped.decision.action is LeadAction.STOP
    assert stopped.run.status is RunStatus.CANCELLED
    assert stopped.run.stop_reason == GoalStopReason.CANCELLED.value
    assert stopped.final_checkpoint is not None
    assert stopped.final_checkpoint.checkpoint.active_path_task_ids == ()
    leases = SqlRunLeaseRepository(seed.factory)
    with pytest.raises(RunLeaseLostError):
        await leases.heartbeat(
            seed.workspace_id,
            seed.run_id,
            seed.grant.credentials,
            ttl=lease_ttl,
            heartbeat_at=datetime.now(UTC),
        )
    events = await SqlDomainEventStore(seed.factory).list_run(
        seed.workspace_id,
        seed.run_id,
    )
    event_types = [event.event_type for event in events]
    assert "lead.stopped" in event_types
    assert event_types[-1] == "run.lease_released"
    await seed.engine.dispose()


@pytest.mark.anyio
async def test_fresh_verification_packet_rebuilds_from_persisted_evidence_only(tmp_path):
    seed = await _seed(tmp_path)
    base = await _loader(seed).load_case_packet(
        seed.workspace_id,
        seed.case_id,
        goal="Explain the anomaly",
        budget=AgentBudgetLimit(max_tokens=16_000),
    )
    evidence = base.evidence[0]
    scope = PathEvidenceScope(
        workspace_id=seed.workspace_id,
        case_id=seed.case_id,
        run_id=seed.run_id,
        task_id=AgentTaskId.new(),
        path_type=PathType.FULFILLMENT,
        dataset_id=seed.dataset_id,
        context_version="commerce-fulfillment-path-context@1.0.0",
        context_sha256="d" * 64,
        source_artifact_sha256=base.manifest.source_artifact_sha256,
        evidence_ids=(evidence.evidence_id,),
        included_fact_ids=evidence.fact_ids,
        included_metric_observation_ids=evidence.metric_observation_ids,
    )
    persisted = build_persisted_lead_context(base, path_scopes=(scope,))

    packet = build_fresh_verification_packet(
        base=base,
        persisted=persisted,
        claims=("The observed anomaly is localized to the supplied metric Evidence.",),
        claim_evidence_ids=((evidence.evidence_id,),),
    )

    assert packet.evidence == (evidence,)
    assert packet.manifest.included_evidence_ids == (evidence.evidence_id,)
    assert set(packet.manifest.included_metric_observation_ids) == set(evidence.metric_observation_ids)
    assert packet.metadata == {
        "base_context_sha256": base.manifest.context_sha256,
        "persisted_lead_context_sha256": persisted.manifest.context_sha256,
    }
    serialized = packet.model_dump_json().casefold()
    assert "lead reasoning history excluded" in serialized
    assert "chain_of_thought" not in serialized
    assert "private reasoning" not in serialized
    await seed.engine.dispose()


@pytest.mark.anyio
async def test_loader_rejects_missing_case_and_lineage(tmp_path):
    seed = await _seed(tmp_path)
    with pytest.raises(ContextLoadError) as missing_run:
        await _loader(seed).load_initial(
            seed.workspace_id,
            RunId.new(),
            budget=AgentBudgetLimit(),
        )
    assert missing_run.value.reason is ContextLoadReason.RUN_NOT_FOUND

    with pytest.raises(ContextLoadError) as missing_case:
        await _loader(seed).load_case_packet(
            seed.workspace_id,
            CaseId.new(),
            goal="Explain the anomaly",
            budget=AgentBudgetLimit(),
        )
    assert missing_case.value.reason is ContextLoadReason.CASE_NOT_FOUND

    async with seed.factory() as session, session.begin():
        await session.execute(delete(CaseLineageRow).where(CaseLineageRow.case_id == str(seed.case_id)))
    with pytest.raises(ContextLoadError) as missing_lineage:
        await _loader(seed).load_case_packet(
            seed.workspace_id,
            seed.case_id,
            goal="Explain the anomaly",
            budget=AgentBudgetLimit(),
        )
    assert missing_lineage.value.reason is ContextLoadReason.LINEAGE_NOT_FOUND
    await seed.engine.dispose()


@pytest.mark.anyio
async def test_loader_rejects_missing_or_tampered_artifact(tmp_path):
    missing = await _seed(tmp_path / "missing")
    missing.artifact_path.unlink()
    with pytest.raises(ContextLoadError) as missing_error:
        await _loader(missing).load_case_packet(
            missing.workspace_id,
            missing.case_id,
            goal="Explain the anomaly",
            budget=AgentBudgetLimit(),
        )
    assert missing_error.value.reason is ContextLoadReason.ARTIFACT_NOT_FOUND
    await missing.engine.dispose()

    tampered = await _seed(tmp_path / "tampered")
    await _rewrite_artifact(
        tampered,
        lambda payload: payload.update({"seller_external_key": "tampered"}),
        update_persisted_sha=False,
    )
    with pytest.raises(ContextLoadError) as hash_error:
        await _loader(tampered).load_case_packet(
            tampered.workspace_id,
            tampered.case_id,
            goal="Explain the anomaly",
            budget=AgentBudgetLimit(),
        )
    assert hash_error.value.reason is ContextLoadReason.ARTIFACT_HASH_MISMATCH
    await tampered.engine.dispose()


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("mutation", "expected_reason"),
    [
        (
            lambda payload: payload.update({"dataset_id": str(DatasetId.new())}),
            ContextLoadReason.ARTIFACT_IDENTITY_MISMATCH,
        ),
        (
            lambda payload: payload["capabilities"]["capabilities"][0].update({"status": "unavailable", "reason_codes": ["missing_required_semantics"]}),
            ContextLoadReason.CAPABILITY_MISMATCH,
        ),
        (
            lambda payload: payload.update({"hidden_labels": {"expected_facts": ["carrier caused it"]}}),
            ContextLoadReason.HIDDEN_EVALUATION_LABEL,
        ),
    ],
)
async def test_loader_rejects_identity_capability_and_hidden_label_tampering(
    tmp_path,
    mutation,
    expected_reason,
):
    seed = await _seed(tmp_path)
    await _rewrite_artifact(seed, mutation, update_persisted_sha=True)

    with pytest.raises(ContextLoadError) as error:
        await _loader(seed).load_case_packet(
            seed.workspace_id,
            seed.case_id,
            goal="Explain the anomaly",
            budget=AgentBudgetLimit(),
        )

    assert error.value.reason is expected_reason
    await seed.engine.dispose()


@pytest.mark.anyio
async def test_loader_rejects_case_reference_and_context_budget_mismatch(tmp_path):
    seed = await _seed(tmp_path)
    async with seed.factory() as session, session.begin():
        selected_evidence_id = await session.scalar(select(EvidenceRow.evidence_id).where(EvidenceRow.case_id == str(seed.case_id)).limit(1))
        assert selected_evidence_id is not None
        evidence_id = (await session.execute(update(EvidenceRow).where(EvidenceRow.evidence_id == selected_evidence_id).values(case_id=str(CaseId.new())).returning(EvidenceRow.evidence_id))).scalar_one()
    assert evidence_id
    with pytest.raises(ContextLoadError) as reference_error:
        await _loader(seed).load_case_packet(
            seed.workspace_id,
            seed.case_id,
            goal="Explain the anomaly",
            budget=AgentBudgetLimit(),
        )
    assert reference_error.value.reason is ContextLoadReason.CASE_REFERENCE_MISMATCH
    await seed.engine.dispose()

    budget_seed = await _seed(tmp_path / "budget")
    with pytest.raises(ContextLoadError) as budget_error:
        await _loader(budget_seed).load_case_packet(
            budget_seed.workspace_id,
            budget_seed.case_id,
            goal="Explain the anomaly",
            budget=AgentBudgetLimit(max_tokens=1),
        )
    assert budget_error.value.reason is ContextLoadReason.CONTEXT_BUDGET_EXCEEDED
    await budget_seed.engine.dispose()


@pytest.mark.anyio
async def test_loader_rejects_path_traversal_and_missing_dataset_manifest(tmp_path):
    traversal = await _seed(tmp_path / "traversal")
    async with traversal.factory() as session, session.begin():
        await session.execute(update(CaseLineageRow).where(CaseLineageRow.case_id == str(traversal.case_id)).values(analysis_artifact_relative_path="../manifest.json"))
    with pytest.raises(ContextLoadError) as traversal_error:
        await _loader(traversal).load_case_packet(
            traversal.workspace_id,
            traversal.case_id,
            goal="Explain the anomaly",
            budget=AgentBudgetLimit(),
        )
    assert traversal_error.value.reason is ContextLoadReason.ARTIFACT_PATH_UNSAFE
    await traversal.engine.dispose()

    missing_manifest = await _seed(tmp_path / "manifest")
    manifest_path = missing_manifest.data_service.storage_root / str(missing_manifest.workspace_id) / str(missing_manifest.dataset_id) / "manifest.json"
    manifest_path.unlink()
    with pytest.raises(ContextLoadError) as manifest_error:
        await _loader(missing_manifest).load_case_packet(
            missing_manifest.workspace_id,
            missing_manifest.case_id,
            goal="Explain the anomaly",
            budget=AgentBudgetLimit(),
        )
    assert manifest_error.value.reason is ContextLoadReason.DATASET_MANIFEST_NOT_FOUND
    await missing_manifest.engine.dispose()
