"""Fenced persistence contracts for validated DeerFlow Subagent outcomes."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.commerce.agents.budget import BudgetSnapshot, BudgetUsage
from app.commerce.agents.contracts import (
    AgentBudgetLimit,
    ContextManifest,
    ModelProfile,
    PathType,
)
from app.commerce.agents.goal_loop import GoalLoopCheckpoint, SkillVersionRef
from app.commerce.agents.model_router import (
    ModelAssignment,
    ModelEffort,
    ModelRole,
    ModelRouteReasonCode,
)
from app.commerce.agents.path_result import (
    ModelExecutionTrace,
    PathCost,
    PathEvidenceItem,
    PathResult,
    PathUnknown,
)
from app.commerce.agents.subagent_adapter import (
    CommerceAgentTask,
    CommerceSubagentErrorCode,
    CommerceSubagentOutcome,
    CommerceSubagentStatus,
    CommerceSubagentToolEvent,
    CommerceSubagentToolStatus,
)
from app.commerce.agents.subagent_committer import (
    CommerceSubagentCommitError,
    CommerceSubagentCommitter,
)
from app.commerce.domain.enums import (
    CaseSeverity,
    RunPhase,
    RunType,
    SemanticStatus,
)
from app.commerce.domain.events import DomainEventActor
from app.commerce.domain.ids import (
    AgentTaskId,
    CorrelationId,
    DatasetId,
    EvidenceId,
    MetricObservationId,
    TraceId,
    WorkspaceId,
)
from app.commerce.domain.models import Case, Evidence, EvidenceRelation
from app.commerce.domain.runs import CommerceRun
from app.commerce.persistence.events import SqlDomainEventStore
from app.commerce.persistence.repositories import SqlCaseRepository
from app.commerce.persistence.runs import (
    RunLeaseGrant,
    RunLeaseLostError,
    SqlRunLeaseRepository,
)
from app.commerce.persistence.schema import create_commerce_schema
from app.commerce.persistence.unit_of_work import SqlCommerceUnitOfWork
from app.commerce.persistence.work_records import SqlEvidenceRepository

NOW = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)


async def _storage(tmp_path):
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'commerce-subagent-committer.db'}"
    )
    await create_commerce_schema(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, factory


async def _seed(factory) -> tuple[Case, CommerceRun, RunLeaseGrant]:
    workspace_id = WorkspaceId.new()
    case = Case(
        workspace_id=workspace_id,
        title="Delivery anomaly",
        severity=CaseSeverity.HIGH,
        opened_at=NOW,
        updated_at=NOW,
    )
    run = CommerceRun(
        workspace_id=workspace_id,
        case_id=case.id,
        run_type=RunType.CASE_INVESTIGATION,
        phase=RunPhase.INVESTIGATING,
        goal="Explain the delivery anomaly",
        idempotency_key_sha256="a" * 64,
        created_at=NOW,
        updated_at=NOW,
    )
    uow = SqlCommerceUnitOfWork(factory)
    await uow.create_case(
        case,
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
        actor=DomainEventActor.SYSTEM,
    )
    await uow.create_run(
        run,
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
        actor=DomainEventActor.USER,
    )
    grant = await SqlRunLeaseRepository(factory).acquire(
        workspace_id,
        run.id,
        worker_id="commerce-subagent-worker",
        ttl=timedelta(seconds=30),
        acquired_at=NOW + timedelta(seconds=1),
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
    )
    return case, grant.run, grant


def _assignment() -> ModelAssignment:
    return ModelAssignment(
        role=ModelRole.PATH,
        base_profile=ModelProfile.BALANCED_TOOL_USER,
        profile=ModelProfile.BALANCED_TOOL_USER,
        model_alias="deepseek-reasoner",
        effort=ModelEffort.MEDIUM,
        max_output_tokens=1_600,
        timeout_seconds=120,
        reason_codes=frozenset({ModelRouteReasonCode.PROFILE_BINDING}),
        escalation_count=0,
    )


def _manifest(case: Case, metric_id: MetricObservationId) -> ContextManifest:
    return ContextManifest(
        context_version="commerce-fulfillment-path-context@1.0.0",
        workspace_id=case.workspace_id,
        case_id=case.id,
        dataset_id=DatasetId.new(),
        source_artifact_sha256="a" * 64,
        context_sha256="b" * 64,
        estimated_tokens=900,
        included_metric_observation_ids=(metric_id,),
    )


def _task(
    run: CommerceRun,
    grant: RunLeaseGrant,
    manifest: ContextManifest,
    *,
    task_id: AgentTaskId | None = None,
) -> CommerceAgentTask:
    return CommerceAgentTask(
        workspace_id=run.workspace_id,
        case_id=run.case_id,
        run_id=run.id,
        task_id=task_id or AgentTaskId.new(),
        path_type=PathType.FULFILLMENT,
        subagent_name="commerce-fulfillment-path",
        context_sha256=manifest.context_sha256,
        budget=AgentBudgetLimit(max_path_agents=0),
        model_assignment=_assignment(),
        skill_id="commerce.fulfillment-investigation",
        skill_version="1.0.0",
        allowed_tools=frozenset({"metric_query"}),
        expected_result_schema="commerce.path_result@1.0.0",
        lease_worker_id=grant.credentials.worker_id,
        fencing_token=grant.credentials.fencing_token,
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
    )


def _checkpoint(
    task: CommerceAgentTask,
    *,
    active: bool,
    iteration: int,
    evidence_ids: tuple[EvidenceId, ...] = (),
) -> GoalLoopCheckpoint:
    return GoalLoopCheckpoint(
        workspace_id=task.workspace_id,
        run_id=task.run_id,
        case_id=task.case_id,
        goal="Explain the delivery anomaly",
        loop_iteration=iteration,
        budget_snapshot=BudgetSnapshot(
            limit=task.budget,
            usage=BudgetUsage(iterations=iteration),
        ),
        evidence_ids=evidence_ids,
        active_path_task_ids=(task.task_id,) if active else (),
        model_assignments=(task.model_assignment,),
        skill_versions=(
            SkillVersionRef(skill_id=task.skill_id, version=task.skill_version),
        ),
        context_sha256=task.context_sha256,
    )


def _completed_outcome(
    task: CommerceAgentTask,
    metric_id: MetricObservationId,
    *,
    evidence_id: EvidenceId | None = None,
) -> CommerceSubagentOutcome:
    result = PathResult(
        path_type=task.path_type,
        evidence=(
            PathEvidenceItem(
                evidence_id=evidence_id or EvidenceId.new(),
                summary="Transit time increased in the current window",
                relation=EvidenceRelation.CONTEXT,
                semantic_status=SemanticStatus.DERIVED,
                confidence=0.9,
                metric_observation_ids=(metric_id,),
            ),
        ),
        unknowns=(
            PathUnknown(
                question="Which carrier event changed?",
                reason="Carrier scan events were not uploaded",
            ),
        ),
        cost=PathCost(
            input_tokens=120,
            output_tokens=80,
            latency_ms=400,
            tool_call_count=0,
        ),
        trace_id=task.trace_id,
        model_assignment=task.model_assignment,
        model_execution=ModelExecutionTrace(
            provider_request_id="provider-request-1",
            actual_model_identity="deepseek-v4-flash",
            retry_count=0,
            stop_reason="stop",
            prompt_version="commerce.fulfillment-subagent@1.0.0",
            context_version="commerce-fulfillment-path-context@1.0.0",
        ),
        skill_version=f"{task.skill_id}@{task.skill_version}",
        context_sha256=task.context_sha256,
    )
    canonical = json.dumps(
        result.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return CommerceSubagentOutcome(
        task_id=task.task_id,
        path_type=task.path_type,
        status=CommerceSubagentStatus.COMPLETED,
        harness_trace_id=str(task.trace_id),
        result=result,
        result_sha256=hashlib.sha256(canonical).hexdigest(),
    )


def _committer(factory) -> CommerceSubagentCommitter:
    return CommerceSubagentCommitter(
        uow=SqlCommerceUnitOfWork(factory),
        cases=SqlCaseRepository(factory),
        evidence=SqlEvidenceRepository(factory),
    )


@pytest.mark.anyio
async def test_committer_records_started_and_atomically_commits_completed_path(
    tmp_path,
):
    engine, factory = await _storage(tmp_path)
    case, run, grant = await _seed(factory)
    metric_id = MetricObservationId.new()
    manifest = _manifest(case, metric_id)
    task = _task(run, grant, manifest)
    outcome = _completed_outcome(task, metric_id)
    outcome = outcome.model_copy(
        update={
            "tool_events": (
                CommerceSubagentToolEvent(
                    tool_call_id="call-1",
                    tool_name="metric_query",
                    status=CommerceSubagentToolStatus.SUCCEEDED,
                    request_sha256="a" * 64,
                    response_sha256="b" * 64,
                    latency_ms=12.5,
                ),
            )
        }
    )
    assert outcome.result is not None
    evidence_id = outcome.result.evidence[0].evidence_id
    committer = _committer(factory)

    pre_checkpoint = _checkpoint(task, active=True, iteration=0)
    started = await committer.commit_started(
        task,
        pre_checkpoint,
        lease=grant.credentials,
        checked_at=NOW + timedelta(seconds=2),
    )
    events_after_start = await SqlDomainEventStore(factory).list_run(
        run.workspace_id, run.id
    )
    repeated_start = await committer.commit_started(
        task,
        pre_checkpoint,
        lease=grant.credentials,
        checked_at=NOW + timedelta(seconds=2, milliseconds=500),
    )
    assert repeated_start.event_ids == started.event_ids
    assert (
        await SqlDomainEventStore(factory).list_run(run.workspace_id, run.id)
        == events_after_start
    )
    completed = await committer.commit_outcome(
        task,
        outcome,
        manifest,
        _checkpoint(task, active=False, iteration=1),
        lease=grant.credentials,
        checked_at=NOW + timedelta(seconds=3),
        causation_event_id=started.lifecycle_event_id,
    )

    assert started.status is CommerceSubagentStatus.RUNNING
    assert completed.status is CommerceSubagentStatus.COMPLETED
    assert completed.evidence_ids == (evidence_id,)
    persisted_case = await SqlCaseRepository(factory).get(case.workspace_id, case.id)
    assert persisted_case is not None
    assert persisted_case.evidence_ids == (evidence_id,)
    assert persisted_case.version == case.version + 1
    persisted = await SqlEvidenceRepository(factory).get(case.workspace_id, evidence_id)
    assert persisted is not None
    assert persisted.id == evidence_id
    run_events = await SqlDomainEventStore(factory).list_run(run.workspace_id, run.id)
    path_events = [event for event in run_events if event.event_type.startswith("path.")]
    assert [event.event_type for event in path_events] == [
        "path.started",
        "path.completed",
    ]
    terminal_slice = [
        event.event_type
        for event in run_events
        if event.id in set(completed.event_ids)
    ]
    assert terminal_slice == [
        "evidence.appended",
        "tool.completed",
        "path.completed",
        "run.checkpoint_saved",
    ]
    completed_event = next(
        event for event in run_events if event.event_type == "path.completed"
    )
    persisted_scope = completed_event.payload["evidence_scope"]
    assert persisted_scope["task_id"] == str(task.task_id)
    assert persisted_scope["path_type"] == PathType.FULFILLMENT.value
    assert persisted_scope["context_sha256"] == manifest.context_sha256
    assert persisted_scope["evidence_ids"] == [str(evidence_id)]
    assert persisted_scope["included_metric_observation_ids"] == [str(metric_id)]
    tool_event = next(event for event in run_events if event.event_type == "tool.completed")
    assert tool_event.payload["request_sha256"] == "a" * 64
    assert "late_delivery_rate" not in str(tool_event.payload)
    await engine.dispose()


@pytest.mark.anyio
async def test_committer_records_blocked_without_writing_evidence(tmp_path):
    engine, factory = await _storage(tmp_path)
    case, run, grant = await _seed(factory)
    metric_id = MetricObservationId.new()
    manifest = _manifest(case, metric_id)
    task = _task(run, grant, manifest)
    outcome = CommerceSubagentOutcome(
        task_id=task.task_id,
        path_type=task.path_type,
        status=CommerceSubagentStatus.BLOCKED,
        harness_trace_id=str(task.trace_id),
        error_code=CommerceSubagentErrorCode.INVALID_PATH_RESULT,
        error_message="Structured result was invalid",
    )

    committer = _committer(factory)
    checkpoint = _checkpoint(task, active=False, iteration=1)
    receipt = await committer.commit_outcome(
        task,
        outcome,
        manifest,
        checkpoint,
        lease=grant.credentials,
        checked_at=NOW + timedelta(seconds=2),
    )

    assert receipt.status is CommerceSubagentStatus.BLOCKED
    assert receipt.evidence_ids == ()
    assert await SqlEvidenceRepository(factory).list_case(case.workspace_id, case.id) == ()
    run_events = await SqlDomainEventStore(factory).list_run(run.workspace_id, run.id)
    blocked = [event for event in run_events if event.event_type == "path.blocked"]
    assert len(blocked) == 1
    assert blocked[0].payload["error_code"] == "invalid_path_result"
    assert blocked[0].payload["evidence_scope"]["evidence_ids"] == []
    assert blocked[0].payload["evidence_scope"]["context_sha256"] == (
        manifest.context_sha256
    )

    repeated = await committer.commit_outcome(
        task,
        outcome,
        manifest,
        checkpoint,
        lease=grant.credentials,
        checked_at=NOW + timedelta(seconds=3),
    )
    repeated_events = await SqlDomainEventStore(factory).list_run(
        run.workspace_id, run.id
    )
    assert repeated.event_ids == receipt.event_ids
    assert repeated_events == run_events
    await engine.dispose()


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("status", "error_code"),
    [
        (CommerceSubagentStatus.FAILED, CommerceSubagentErrorCode.HARNESS_FAILED),
        (
            CommerceSubagentStatus.CANCELLED,
            CommerceSubagentErrorCode.HARNESS_CANCELLED,
        ),
        (
            CommerceSubagentStatus.TIMED_OUT,
            CommerceSubagentErrorCode.HARNESS_TIMED_OUT,
        ),
    ],
)
async def test_committer_maps_unsuccessful_harness_states_to_structured_failure(
    tmp_path,
    status,
    error_code,
):
    engine, factory = await _storage(tmp_path)
    case, run, grant = await _seed(factory)
    manifest = _manifest(case, MetricObservationId.new())
    task = _task(run, grant, manifest)
    outcome = CommerceSubagentOutcome(
        task_id=task.task_id,
        path_type=task.path_type,
        status=status,
        harness_trace_id=str(task.trace_id),
        error_code=error_code,
        error_message="Harness terminal state",
    )

    receipt = await _committer(factory).commit_outcome(
        task,
        outcome,
        manifest,
        _checkpoint(task, active=False, iteration=1),
        lease=grant.credentials,
        checked_at=NOW + timedelta(seconds=2),
    )

    assert receipt.status is status
    run_events = await SqlDomainEventStore(factory).list_run(run.workspace_id, run.id)
    failed = [event for event in run_events if event.event_type == "path.failed"]
    assert len(failed) == 1
    assert failed[0].payload["status"] == status.value
    assert failed[0].payload["error_code"] == error_code.value
    assert await SqlEvidenceRepository(factory).list_case(case.workspace_id, case.id) == ()
    await engine.dispose()


@pytest.mark.anyio
async def test_committer_completes_explicit_unknown_without_case_mutation(tmp_path):
    engine, factory = await _storage(tmp_path)
    case, run, grant = await _seed(factory)
    metric_id = MetricObservationId.new()
    manifest = _manifest(case, metric_id)
    task = _task(run, grant, manifest)
    outcome = _completed_outcome(task, metric_id)
    assert outcome.result is not None
    result = outcome.result.model_copy(update={"evidence": ()})
    canonical = json.dumps(
        result.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    outcome = outcome.model_copy(
        update={
            "result": result,
            "result_sha256": hashlib.sha256(canonical).hexdigest(),
        }
    )

    receipt = await _committer(factory).commit_outcome(
        task,
        outcome,
        manifest,
        _checkpoint(task, active=False, iteration=1),
        lease=grant.credentials,
        checked_at=NOW + timedelta(seconds=2),
    )

    assert receipt.status is CommerceSubagentStatus.COMPLETED
    assert receipt.evidence_ids == ()
    assert receipt.case_version == case.version
    assert await SqlCaseRepository(factory).get(case.workspace_id, case.id) == case
    run_events = await SqlDomainEventStore(factory).list_run(run.workspace_id, run.id)
    completed = [event for event in run_events if event.event_type == "path.completed"]
    assert len(completed) == 1
    assert completed[0].payload["evidence_ids"] == []
    await engine.dispose()


@pytest.mark.anyio
async def test_committer_rejects_tampered_structured_result_hash(tmp_path):
    engine, factory = await _storage(tmp_path)
    case, run, grant = await _seed(factory)
    metric_id = MetricObservationId.new()
    manifest = _manifest(case, metric_id)
    task = _task(run, grant, manifest)
    outcome = _completed_outcome(task, metric_id).model_copy(
        update={"result_sha256": "f" * 64}
    )

    with pytest.raises(CommerceSubagentCommitError, match="hash"):
        await _committer(factory).commit_outcome(
            task,
            outcome,
            manifest,
            _checkpoint(task, active=False, iteration=1),
            lease=grant.credentials,
            checked_at=NOW + timedelta(seconds=2),
        )

    assert await SqlEvidenceRepository(factory).list_case(case.workspace_id, case.id) == ()
    await engine.dispose()


@pytest.mark.anyio
async def test_committer_rejects_nonterminal_outcome_without_domain_writes(tmp_path):
    engine, factory = await _storage(tmp_path)
    case, run, grant = await _seed(factory)
    manifest = _manifest(case, MetricObservationId.new())
    task = _task(run, grant, manifest)
    outcome = CommerceSubagentOutcome(
        task_id=task.task_id,
        path_type=task.path_type,
        status=CommerceSubagentStatus.RUNNING,
        harness_trace_id=str(task.trace_id),
    )
    before = await SqlDomainEventStore(factory).list_run(run.workspace_id, run.id)

    with pytest.raises(CommerceSubagentCommitError, match="terminal"):
        await _committer(factory).commit_outcome(
            task,
            outcome,
            manifest,
            _checkpoint(task, active=False, iteration=0),
            lease=grant.credentials,
            checked_at=NOW + timedelta(seconds=2),
        )

    assert await SqlDomainEventStore(factory).list_run(run.workspace_id, run.id) == before
    await engine.dispose()


@pytest.mark.anyio
@pytest.mark.parametrize("mismatch", ["worker", "fencing"])
async def test_committer_rejects_lease_identity_mismatch_before_writing(
    tmp_path,
    mismatch,
):
    engine, factory = await _storage(tmp_path)
    case, run, grant = await _seed(factory)
    manifest = _manifest(case, MetricObservationId.new())
    task = _task(run, grant, manifest)
    if mismatch == "worker":
        task = task.model_copy(update={"lease_worker_id": "different-worker"})
    else:
        task = task.model_copy(update={"fencing_token": task.fencing_token + 1})
    before = await SqlDomainEventStore(factory).list_run(run.workspace_id, run.id)

    with pytest.raises(CommerceSubagentCommitError, match=mismatch):
        await _committer(factory).commit_started(
            task,
            _checkpoint(task, active=True, iteration=0),
            lease=grant.credentials,
            checked_at=NOW + timedelta(seconds=2),
        )

    assert await SqlDomainEventStore(factory).list_run(run.workspace_id, run.id) == before
    await engine.dispose()


@pytest.mark.anyio
async def test_committer_rejects_stale_database_lease_without_partial_evidence(tmp_path):
    engine, factory = await _storage(tmp_path)
    case, run, first = await _seed(factory)
    metric_id = MetricObservationId.new()
    manifest = _manifest(case, metric_id)
    task = _task(run, first, manifest)
    outcome = _completed_outcome(task, metric_id)
    await SqlRunLeaseRepository(factory).acquire(
        run.workspace_id,
        run.id,
        worker_id="takeover-worker",
        ttl=timedelta(seconds=30),
        acquired_at=NOW + timedelta(seconds=32),
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
    )

    with pytest.raises(RunLeaseLostError):
        await _committer(factory).commit_outcome(
            task,
            outcome,
            manifest,
            _checkpoint(task, active=False, iteration=1),
            lease=first.credentials,
            checked_at=NOW + timedelta(seconds=33),
        )

    assert await SqlEvidenceRepository(factory).list_case(case.workspace_id, case.id) == ()
    assert await SqlCaseRepository(factory).get(case.workspace_id, case.id) == case
    await engine.dispose()


@pytest.mark.anyio
async def test_committer_rejects_evidence_outside_context_manifest(tmp_path):
    engine, factory = await _storage(tmp_path)
    case, run, grant = await _seed(factory)
    allowed_metric_id = MetricObservationId.new()
    manifest = _manifest(case, allowed_metric_id)
    task = _task(run, grant, manifest)
    outcome = _completed_outcome(task, MetricObservationId.new())

    with pytest.raises(CommerceSubagentCommitError, match="ContextManifest"):
        await _committer(factory).commit_outcome(
            task,
            outcome,
            manifest,
            _checkpoint(task, active=False, iteration=1),
            lease=grant.credentials,
            checked_at=NOW + timedelta(seconds=2),
        )

    assert await SqlEvidenceRepository(factory).list_case(case.workspace_id, case.id) == ()
    run_events = await SqlDomainEventStore(factory).list_run(run.workspace_id, run.id)
    assert not any(event.event_type == "path.completed" for event in run_events)
    await engine.dispose()


@pytest.mark.anyio
async def test_committer_rebases_a_parallel_path_on_the_latest_case_version(tmp_path):
    engine, factory = await _storage(tmp_path)
    case, run, grant = await _seed(factory)
    existing = Evidence(
        workspace_id=case.workspace_id,
        case_id=case.id,
        summary="Existing peer evidence",
        relation=EvidenceRelation.CONTEXT,
        semantic_status=SemanticStatus.DERIVED,
        confidence=0.8,
        metric_observation_ids=(MetricObservationId.new(),),
    )
    case_with_existing = case.model_copy(
        update={
            "evidence_ids": (existing.id,),
            "version": case.version + 1,
            "updated_at": NOW + timedelta(seconds=2),
        }
    )
    await SqlCommerceUnitOfWork(factory).append_evidence(
        case_with_existing,
        existing,
        expected_version=case.version,
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
        actor=DomainEventActor.AGENT,
        run_id=run.id,
        lease=grant.credentials,
        lease_checked_at=NOW + timedelta(seconds=2),
    )
    metric_id = MetricObservationId.new()
    manifest = _manifest(case, metric_id)
    task = _task(run, grant, manifest)
    outcome = _completed_outcome(task, metric_id)
    assert outcome.result is not None
    new_evidence_id = outcome.result.evidence[0].evidence_id

    receipt = await _committer(factory).commit_outcome(
        task,
        outcome,
        manifest,
        _checkpoint(task, active=False, iteration=1),
        lease=grant.credentials,
        checked_at=NOW + timedelta(seconds=3),
    )

    persisted_case = await SqlCaseRepository(factory).get(case.workspace_id, case.id)
    assert persisted_case is not None
    assert persisted_case.evidence_ids == (existing.id, new_evidence_id)
    assert persisted_case.version == case.version + 2
    assert receipt.case_version == persisted_case.version
    await engine.dispose()
