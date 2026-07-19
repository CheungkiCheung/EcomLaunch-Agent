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
    canonical_context_sha256,
)
from app.commerce.api.analysis_service import CommerceAnalysisService
from app.commerce.api.data_service import CommerceDataService
from app.commerce.api.run_service import CommerceRunService
from app.commerce.data.gold_cases import load_evaluation_case
from app.commerce.domain.events import DomainEventActor
from app.commerce.domain.ids import (
    CaseId,
    CorrelationId,
    DatasetId,
    RunId,
    TraceId,
    WorkspaceId,
)
from app.commerce.metrics.registry import MetricWindow
from app.commerce.persistence.models import CaseLineageRow, EvidenceRow
from app.commerce.persistence.runs import SqlRunLeaseRepository
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
    artifact_path = (
        storage_root
        / str(workspace_id)
        / str(view.manifest.dataset_id)
        / lineage.analysis_artifact_relative_path
    )
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
            await session.execute(
                update(CaseLineageRow)
                .where(CaseLineageRow.case_id == str(seed.case_id))
                .values(analysis_artifact_sha256=digest)
            )


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
    assert loaded.packet.manifest.source_artifact_sha256 == hashlib.sha256(
        seed.artifact_path.read_bytes()
    ).hexdigest()
    assert loaded.packet.manifest.context_sha256 == canonical_context_sha256(
        loaded.packet
    )
    assert loaded.packet.manifest.estimated_tokens <= loaded.packet.budget.max_tokens
    assert loaded.packet.analysis.seller_external_key == SELLER_ID
    assert loaded.packet.capabilities
    assert loaded.packet.evidence
    assert set(loaded.packet.manifest.included_evidence_ids) == set(
        loaded.state.evidence_ids
    )
    assert loaded.state.loop_iteration == 0
    assert loaded.state.context_sha256 == loaded.packet.manifest.context_sha256
    assert loaded.checkpoint.loop_iteration == 0
    assert loaded.checkpoint.budget_snapshot.usage.iterations == 0
    serialized = loaded.checkpoint.model_dump_json()
    assert "resume-only-in-worker-memory" not in serialized
    assert loaded.state.resume_token_sha256 == hashlib.sha256(
        b"resume-only-in-worker-memory"
    ).hexdigest()

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
    assert (
        duplicate_initialization.value.reason
        is ContextLoadReason.CHECKPOINT_ALREADY_EXISTS
    )
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
        await session.execute(
            delete(CaseLineageRow).where(
                CaseLineageRow.case_id == str(seed.case_id)
            )
        )
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
            lambda payload: payload["capabilities"]["capabilities"][0].update(
                {"status": "unavailable", "reason_codes": ["missing_required_semantics"]}
            ),
            ContextLoadReason.CAPABILITY_MISMATCH,
        ),
        (
            lambda payload: payload.update(
                {"hidden_labels": {"expected_facts": ["carrier caused it"]}}
            ),
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
        selected_evidence_id = await session.scalar(
            select(EvidenceRow.evidence_id)
            .where(EvidenceRow.case_id == str(seed.case_id))
            .limit(1)
        )
        assert selected_evidence_id is not None
        evidence_id = (
            await session.execute(
                update(EvidenceRow)
                .where(EvidenceRow.evidence_id == selected_evidence_id)
                .values(case_id=str(CaseId.new()))
                .returning(EvidenceRow.evidence_id)
            )
        ).scalar_one()
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
        await session.execute(
            update(CaseLineageRow)
            .where(CaseLineageRow.case_id == str(traversal.case_id))
            .values(analysis_artifact_relative_path="../manifest.json")
        )
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
    manifest_path = (
        missing_manifest.data_service.storage_root
        / str(missing_manifest.workspace_id)
        / str(missing_manifest.dataset_id)
        / "manifest.json"
    )
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
