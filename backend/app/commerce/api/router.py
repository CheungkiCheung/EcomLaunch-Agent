"""Feature-flagged Commerce Case data, investigation, and read API."""

from __future__ import annotations

import asyncio
import hashlib
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Path, Query, UploadFile
from starlette.concurrency import run_in_threadpool

from app.commerce.actions.approval import (
    ApprovalDecisionType,
    ApprovalRequest,
    ApprovalStateError,
)
from app.commerce.actions.execution import (
    ActionExecutionError,
    ActionExecutionService,
)
from app.commerce.actions.follow_up import FollowUpError, FollowUpService
from app.commerce.actions.planner import (
    ActionCatalogError,
    ActionPlannerParseError,
)
from app.commerce.actions.service import (
    ActionProposalError,
    ApprovalDecisionError,
)
from app.commerce.actions.validator import ActionValidationError
from app.commerce.agents.context_loader import ContextLoadError
from app.commerce.agents.contracts import CaseTriggerDigest, CaseTriggerType
from app.commerce.agents.verified_call import VerifiedModelCallBlockedError
from app.commerce.api.action_service import CommerceActionService
from app.commerce.api.analysis_service import CommerceAnalysisService
from app.commerce.api.data_service import (
    CommerceDataService,
    DatasetNotFoundError,
    MappingResumeConflictError,
)
from app.commerce.api.dependencies import (
    get_commerce_action_execution_service,
    get_commerce_action_service,
    get_commerce_actor_id,
    get_commerce_analysis_service,
    get_commerce_data_service,
    get_commerce_follow_up_service,
    get_commerce_read_service,
    get_commerce_run_reconciliation_service,
    get_commerce_run_service,
    get_commerce_semantic_candidate_service,
    get_commerce_skill_candidate_service,
    get_commerce_workspace_id,
)
from app.commerce.api.run_reconciliation_service import (
    CommerceRunReconciliationService,
    RunReconciliationConflictError,
    RunReconciliationNotFoundError,
)
from app.commerce.api.run_service import (
    CommerceRunService,
    InvestigationCaseNotFoundError,
    InvestigationIdempotencyConflictError,
    ReplanParentNotFoundError,
    ReplanParentStateError,
)
from app.commerce.api.schemas import (
    ActionDetailResponse,
    ActionExecutionRequest,
    ActionExecutionResponse,
    ActionProposalRequest,
    ActionProposalResponse,
    ActionRecordListResponse,
    AgentActionPlanRequest,
    AgentActionPlanResponse,
    AnalysisRequest,
    AnalysisResponse,
    ApprovalCommandRequest,
    ApprovalDecisionResponse,
    ApprovalModifyRequest,
    CaseActionSummaryResponse,
    CaseAnalysisResponse,
    CaseAnomalyResponse,
    CaseDetailResponse,
    CaseLineageResponse,
    CaseListResponse,
    CaseResponse,
    DatasetCheckSummaryResponse,
    DatasetDetailResponse,
    DatasetFileSummaryResponse,
    DatasetIntakeResponse,
    DatasetListItemResponse,
    DatasetListResponse,
    DomainEventListResponse,
    DomainEventResponse,
    EvidenceListResponse,
    EvidenceResponse,
    ExplicitCaseRequest,
    ExplicitCaseResponse,
    FollowUpEvaluationResponse,
    FollowUpListResponse,
    FollowUpStartRequest,
    HypothesisListResponse,
    HypothesisResponse,
    InvestigationStartRequest,
    InvestigationStartResponse,
    MappingResumeRequest,
    MappingResumeResponse,
    MetricObservationResponse,
    ReplanStartRequest,
    RunCheckpointListResponse,
    RunCheckpointResponse,
    RunDetailResponse,
    RunListResponse,
    RunReconciliationRequest,
    RunReconciliationResponse,
    RunResponse,
    SemanticConfirmationRequest,
    SkillCandidateEvidenceResponse,
    SkillCandidateListResponse,
    SkillCandidatePromotionRequest,
    SkillCandidateProposalRequest,
    SkillCandidateProposalResponse,
    SkillCandidateRollbackRequest,
    SkillCandidateTransitionResponse,
)
from app.commerce.api.service import CommerceReadService
from app.commerce.api.skill_candidate_service import (
    CommerceSkillCandidateService,
    SkillCandidateEvidenceNotFoundError,
    SkillCandidateNotFoundError,
    SkillCandidateProposalConflictError,
    SkillCandidateTransitionConflictError,
)
from app.commerce.data.capabilities import CapabilityProfile
from app.commerce.data.intake import DataIntakeError, DatasetIntegrityError
from app.commerce.data.profiler import DatasetProfile
from app.commerce.data.semantic_candidate_service import (
    RealModelBlockedError,
    SemanticCandidateParseError,
    SemanticCandidateResult,
    SemanticCandidateService,
)
from app.commerce.data.semantic_mapper import SemanticConfirmation, SemanticMappingProfile
from app.commerce.domain.enums import CaseStatus
from app.commerce.domain.events import DomainEventEnvelope
from app.commerce.domain.ids import (
    ActionId,
    CaseId,
    DatasetId,
    EvidenceId,
    RunId,
    SkillCandidateId,
    WorkspaceId,
)
from app.commerce.domain.lineage import CaseLineage
from app.commerce.domain.models import Case, Evidence, Hypothesis, MetricObservation
from app.commerce.domain.runs import CommerceRun
from app.commerce.evaluation.skill_evolution import ActiveSkillPointer, SkillCandidate
from app.commerce.persistence.actions import ActionRecord
from app.commerce.persistence.repositories import DuplicateEntityError
from app.commerce.persistence.runs import RunCheckpointRecord, RunLeaseConflictError

router = APIRouter(prefix="/api/commerce", tags=["commerce"])


def _case_response(case: Case) -> CaseResponse:
    return CaseResponse(
        id=str(case.id),
        workspace_id=str(case.workspace_id),
        title=case.title,
        severity=case.severity.value,
        status=case.status.value,
        summary=case.summary,
        evidence_ids=[str(value) for value in case.evidence_ids],
        hypothesis_ids=[str(value) for value in case.hypothesis_ids],
        action_ids=[str(value) for value in case.action_ids],
        opened_at=case.opened_at,
        updated_at=case.updated_at,
        version=case.version,
    )


def _lineage_response(lineage: CaseLineage) -> CaseLineageResponse:
    return CaseLineageResponse(
        schema_version=lineage.schema_version,
        workspace_id=str(lineage.workspace_id),
        case_id=str(lineage.case_id),
        dataset_id=str(lineage.dataset_id),
        seller_entity_id=str(lineage.seller_entity_id),
        seller_external_key=lineage.seller_external_key,
        baseline_start=lineage.baseline_start,
        baseline_end=lineage.baseline_end,
        current_start=lineage.current_start,
        current_end=lineage.current_end,
        anomaly_ids=[str(value) for value in lineage.anomaly_ids],
        metric_observation_ids=[str(value) for value in lineage.metric_observation_ids],
        analysis_artifact_relative_path=lineage.analysis_artifact_relative_path,
        analysis_artifact_sha256=lineage.analysis_artifact_sha256,
        created_at=lineage.created_at,
    )


def _evidence_response(evidence: Evidence) -> EvidenceResponse:
    return EvidenceResponse(
        id=str(evidence.id),
        workspace_id=str(evidence.workspace_id),
        case_id=str(evidence.case_id),
        summary=evidence.summary,
        relation=evidence.relation.value,
        semantic_status=evidence.semantic_status.value,
        confidence=evidence.confidence,
        fact_ids=[str(value) for value in evidence.fact_ids],
        metric_observation_ids=[str(value) for value in evidence.metric_observation_ids],
    )


def _hypothesis_response(hypothesis: Hypothesis) -> HypothesisResponse:
    return HypothesisResponse(
        id=str(hypothesis.id),
        workspace_id=str(hypothesis.workspace_id),
        case_id=str(hypothesis.case_id),
        statement=hypothesis.statement,
        status=hypothesis.status.value,
        confidence=hypothesis.confidence,
        supporting_evidence_ids=[str(value) for value in hypothesis.supporting_evidence_ids],
        contradicting_evidence_ids=[str(value) for value in hypothesis.contradicting_evidence_ids],
        version=hypothesis.version,
    )


def _number_text(value: int | float | Decimal | None) -> str | None:
    return None if value is None else str(value)


def _dataset_checks(view) -> DatasetCheckSummaryResponse:
    return DatasetCheckSummaryResponse(
        file_count=len(view.manifest.files),
        table_count=len(view.manifest.tables),
        row_count=sum(table.row_count for table in view.profile.tables),
        confirmed_mapping_count=sum(mapping.status.value == "confirmed" for mapping in view.mappings.mappings),
        unresolved_mapping_count=len(view.mappings.unresolved_columns),
        available_capability_count=sum(capability.status.value == "available" for capability in view.capabilities.capabilities),
        partial_capability_count=sum(capability.status.value == "partial" for capability in view.capabilities.capabilities),
        unavailable_capability_count=sum(capability.status.value == "unavailable" for capability in view.capabilities.capabilities),
    )


def _dataset_item(view) -> DatasetListItemResponse:
    return DatasetListItemResponse(
        dataset_id=str(view.manifest.dataset_id),
        workspace_id=str(view.manifest.workspace_id),
        created_at=view.manifest.created_at,
        files=[
            DatasetFileSummaryResponse(
                original_name=file.original_name,
                format=file.format.value,
                size_bytes=file.size_bytes,
                sha256=file.sha256,
                archive_member=file.archive_member,
            )
            for file in view.manifest.files
        ],
        checks=_dataset_checks(view),
        integrity_status="verified",
    )


def _dataset_detail(view, confirmations) -> DatasetDetailResponse:
    return DatasetDetailResponse(
        manifest=view.manifest,
        profile=view.profile,
        mappings=view.mappings,
        capabilities=view.capabilities,
        confirmations=list(confirmations),
        checks=_dataset_checks(view),
        integrity_status="verified",
    )


def _metric_response(metric: MetricObservation) -> MetricObservationResponse:
    return MetricObservationResponse(
        id=str(metric.id),
        metric_name=metric.metric_name,
        semantic_status=metric.semantic_status.value,
        value=_number_text(metric.value),
        unit=metric.unit,
        formula_version=metric.formula_version,
        window_start=metric.window_start,
        window_end=metric.window_end,
        sample_size=metric.sample_size,
        numerator=_number_text(metric.numerator),
        denominator=_number_text(metric.denominator),
        source_fact_count=len(metric.source_fact_ids),
        unknown_reason=metric.unknown_reason,
    )


def _action_summary_response(record: ActionRecord) -> CaseActionSummaryResponse:
    action = record.action
    return CaseActionSummaryResponse(
        id=str(action.id),
        title=action.title,
        description=action.description,
        kind=record.decision.validated.draft.kind.value,
        status=action.status.value,
        risk_level=action.risk_level.value,
        policy_level=record.decision.level.value,
        approval_required=action.approval.required,
        approval_status=action.approval.status.value,
        evidence_ids=[str(value) for value in action.evidence_ids],
        created_at=record.created_at,
        updated_at=record.updated_at,
        version=record.version,
    )


async def _case_analysis_response(
    service: CommerceReadService,
    workspace_id: WorkspaceId,
    case_id: CaseId,
) -> CaseAnalysisResponse:
    try:
        loaded = await service.get_case_analysis(workspace_id, case_id)
    except ContextLoadError as exc:
        return CaseAnalysisResponse(
            status="unavailable",
            unavailable_reason=exc.reason.value,
            baseline_metrics=[],
            current_metrics=[],
            anomalies=[],
        )
    if loaded is None:
        return CaseAnalysisResponse(
            status="unavailable",
            unavailable_reason="analysis_reader_unconfigured",
            baseline_metrics=[],
            current_metrics=[],
            anomalies=[],
        )
    return CaseAnalysisResponse(
        status="available",
        unavailable_reason=None,
        baseline_metrics=[_metric_response(item) for item in loaded.artifact.baseline.observations],
        current_metrics=[_metric_response(item) for item in loaded.artifact.current.observations],
        anomalies=[
            CaseAnomalyResponse(
                id=str(item.id),
                metric_name=item.metric_name.value,
                baseline_observation_id=str(item.baseline_observation_id),
                current_observation_id=str(item.current_observation_id),
                baseline_value=str(item.baseline_value),
                current_value=str(item.current_value),
                absolute_change=str(item.absolute_change),
                relative_change=(str(item.relative_change) if item.relative_change is not None else None),
                direction=item.direction.value,
                severity=item.severity.value,
                confidence=item.confidence,
                baseline_sample_size=item.baseline_sample_size,
                current_sample_size=item.current_sample_size,
                sample_adequate=item.sample_adequate,
                reason=item.reason,
            )
            for item in loaded.artifact.signals
        ],
    )


def _event_response(event: DomainEventEnvelope) -> DomainEventResponse:
    return DomainEventResponse(
        id=str(event.id),
        workspace_id=str(event.workspace_id),
        case_id=str(event.case_id) if event.case_id is not None else None,
        run_id=str(event.run_id) if event.run_id is not None else None,
        event_type=event.event_type,
        schema_version=event.schema_version,
        case_sequence=event.case_sequence,
        run_sequence=event.run_sequence,
        occurred_at=event.occurred_at,
        recorded_at=event.recorded_at,
        trace_id=str(event.trace_id),
        correlation_id=str(event.correlation_id),
        causation_event_id=(str(event.causation_event_id) if event.causation_event_id is not None else None),
        actor=event.actor.value,
        payload=event.payload,
    )


def _run_response(run: CommerceRun) -> RunResponse:
    return RunResponse(
        id=str(run.id),
        workspace_id=str(run.workspace_id),
        case_id=str(run.case_id),
        run_type=run.run_type.value,
        status=run.status.value,
        phase=run.phase.value,
        goal=run.goal,
        parent_run_id=(str(run.parent_run_id) if run.parent_run_id is not None else None),
        subject_action_id=(str(run.subject_action_id) if run.subject_action_id is not None else None),
        action_operation=run.action_operation,
        requested_paths=list(run.requested_paths),
        wait_reason=run.wait_reason,
        stop_reason=run.stop_reason,
        created_at=run.created_at,
        started_at=run.started_at,
        ended_at=run.ended_at,
        updated_at=run.updated_at,
        version=run.version,
    )


def _checkpoint_response(record: RunCheckpointRecord) -> RunCheckpointResponse:
    return RunCheckpointResponse(
        id=str(record.id),
        sequence=record.sequence,
        checkpoint=record.checkpoint,
        created_at=record.created_at,
    )


def _parse_case_id(raw_case_id: str) -> CaseId:
    try:
        return CaseId(raw_case_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid CaseId") from exc


def _parse_evidence_id(raw_evidence_id: str) -> EvidenceId:
    try:
        return EvidenceId(raw_evidence_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid EvidenceId") from exc


def _parse_dataset_id(raw_dataset_id: str) -> DatasetId:
    try:
        return DatasetId(raw_dataset_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid DatasetId") from exc


def _parse_run_id(raw_run_id: str) -> RunId:
    try:
        return RunId(raw_run_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid RunId") from exc


def _parse_action_id(raw_action_id: str) -> ActionId:
    try:
        return ActionId(raw_action_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid ActionId") from exc


def _parse_skill_candidate_id(raw_candidate_id: str) -> SkillCandidateId:
    try:
        return SkillCandidateId(raw_candidate_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid SkillCandidateId") from exc


async def _require_case(
    service: CommerceReadService,
    workspace_id: WorkspaceId,
    case_id: CaseId,
) -> Case:
    case = await service.get_case(workspace_id, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Commerce Case not found")
    return case


async def _require_run(
    service: CommerceRunService,
    workspace_id: WorkspaceId,
    run_id: RunId,
) -> CommerceRun:
    run = await service.get_run(workspace_id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Commerce Run not found")
    return run


@router.get("/cases", response_model=CaseListResponse)
async def list_cases(
    service: Annotated[CommerceReadService, Depends(get_commerce_read_service)],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
    status: CaseStatus | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> CaseListResponse:
    cases = await service.list_cases(
        workspace_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return CaseListResponse(
        items=[_case_response(case) for case in cases],
        limit=limit,
        offset=offset,
    )


@router.post(
    "/cases/{raw_case_id}/investigations",
    response_model=InvestigationStartResponse,
    status_code=201,
)
async def start_case_investigation(
    raw_case_id: Annotated[str, Path()],
    request: InvestigationStartRequest,
    service: Annotated[CommerceRunService, Depends(get_commerce_run_service)],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
) -> InvestigationStartResponse:
    try:
        outcome = await service.start_investigation(
            workspace_id,
            _parse_case_id(raw_case_id),
            goal=request.goal,
            idempotency_key=request.idempotency_key,
        )
    except InvestigationCaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Commerce Case not found") from exc
    except InvestigationIdempotencyConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    latest = await service.get_latest_checkpoint(workspace_id, outcome.run.id)
    return InvestigationStartResponse(
        run=_run_response(outcome.run),
        created=outcome.created,
        latest_checkpoint=_checkpoint_response(latest) if latest else None,
    )


@router.post(
    "/runs/{raw_parent_run_id}/replans",
    response_model=InvestigationStartResponse,
    status_code=201,
)
async def start_run_replan(
    raw_parent_run_id: Annotated[str, Path()],
    request: ReplanStartRequest,
    service: Annotated[CommerceRunService, Depends(get_commerce_run_service)],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
) -> InvestigationStartResponse:
    try:
        outcome = await service.start_replan(
            workspace_id,
            _parse_run_id(raw_parent_run_id),
            goal=request.goal,
            requested_paths=tuple(request.requested_paths),
            idempotency_key=request.idempotency_key,
        )
    except ReplanParentNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Parent Commerce Run not found",
        ) from exc
    except ReplanParentStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvestigationIdempotencyConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    latest = await service.get_latest_checkpoint(workspace_id, outcome.run.id)
    return InvestigationStartResponse(
        run=_run_response(outcome.run),
        created=outcome.created,
        latest_checkpoint=_checkpoint_response(latest) if latest else None,
    )


@router.post(
    "/datasets/intake",
    response_model=DatasetIntakeResponse,
    status_code=201,
)
async def intake_dataset(
    files: Annotated[list[UploadFile], File(...)],
    service: Annotated[CommerceDataService, Depends(get_commerce_data_service)],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
) -> DatasetIntakeResponse:
    uploads: list[tuple[str, bytes]] = []
    try:
        for upload in files:
            uploads.append((upload.filename or "", await upload.read()))
        view = service.ingest_uploads(workspace_id, tuple(uploads))
    except DataIntakeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        for upload in files:
            await upload.close()
    return DatasetIntakeResponse(
        manifest=view.manifest,
        profile=view.profile,
        mappings=view.mappings,
        capabilities=view.capabilities,
    )


@router.get("/datasets", response_model=DatasetListResponse)
async def list_datasets(
    service: Annotated[CommerceDataService, Depends(get_commerce_data_service)],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> DatasetListResponse:
    try:
        views = service.list_views(workspace_id, limit=limit, offset=offset)
    except DatasetIntegrityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return DatasetListResponse(
        items=[_dataset_item(view) for view in views],
        limit=limit,
        offset=offset,
    )


@router.get("/datasets/{raw_dataset_id}", response_model=DatasetDetailResponse)
async def get_dataset_detail(
    raw_dataset_id: Annotated[str, Path()],
    service: Annotated[CommerceDataService, Depends(get_commerce_data_service)],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
) -> DatasetDetailResponse:
    dataset_id = _parse_dataset_id(raw_dataset_id)
    try:
        view = service.get_view(workspace_id, dataset_id)
        confirmations = service.semantic_confirmations(workspace_id, dataset_id)
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Commerce Dataset not found") from exc
    except DatasetIntegrityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _dataset_detail(view, confirmations)


@router.get("/datasets/{raw_dataset_id}/profile", response_model=DatasetProfile)
async def get_dataset_profile(
    raw_dataset_id: Annotated[str, Path()],
    service: Annotated[CommerceDataService, Depends(get_commerce_data_service)],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
) -> DatasetProfile:
    try:
        return service.get_view(
            workspace_id,
            _parse_dataset_id(raw_dataset_id),
        ).profile
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Commerce Dataset not found") from exc
    except DatasetIntegrityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/datasets/{raw_dataset_id}/mappings", response_model=SemanticMappingProfile)
async def get_dataset_mappings(
    raw_dataset_id: Annotated[str, Path()],
    service: Annotated[CommerceDataService, Depends(get_commerce_data_service)],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
) -> SemanticMappingProfile:
    try:
        return service.get_view(
            workspace_id,
            _parse_dataset_id(raw_dataset_id),
        ).mappings
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Commerce Dataset not found") from exc
    except DatasetIntegrityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/datasets/{raw_dataset_id}/semantic-confirmations",
    response_model=SemanticConfirmation,
    status_code=201,
)
async def confirm_dataset_mapping(
    raw_dataset_id: Annotated[str, Path()],
    request: SemanticConfirmationRequest,
    service: Annotated[CommerceDataService, Depends(get_commerce_data_service)],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
) -> SemanticConfirmation:
    try:
        return service.confirm_mapping(
            workspace_id,
            _parse_dataset_id(raw_dataset_id),
            table_name=request.table_name,
            column_name=request.column_name,
            semantic_field=request.semantic_field,
        )
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Commerce Dataset not found") from exc
    except DataIntakeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/datasets/{raw_dataset_id}/mapping-resume",
    response_model=MappingResumeResponse,
)
async def resume_dataset_mapping(
    raw_dataset_id: Annotated[str, Path()],
    request: MappingResumeRequest,
    service: Annotated[CommerceDataService, Depends(get_commerce_data_service)],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
    actor_id: Annotated[str, Depends(get_commerce_actor_id)],
) -> MappingResumeResponse:
    try:
        result = await run_in_threadpool(
            service.resume_mapping,
            workspace_id,
            _parse_dataset_id(raw_dataset_id),
            confirmations=tuple(
                (
                    item.table_name,
                    item.column_name,
                    item.semantic_field,
                )
                for item in request.confirmations
            ),
            actor_id=actor_id,
            idempotency_key=request.idempotency_key,
        )
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Commerce Dataset not found") from exc
    except DatasetIntegrityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DataIntakeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except MappingResumeConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return MappingResumeResponse(
        confirmations=list(result.confirmations),
        mappings=result.mappings,
        capabilities=result.capabilities,
        created=result.created,
        replayed=result.replayed,
    )


@router.post(
    "/datasets/{raw_dataset_id}/semantic-candidates",
    response_model=SemanticCandidateResult,
)
async def generate_semantic_candidates(
    raw_dataset_id: Annotated[str, Path()],
    data_service: Annotated[CommerceDataService, Depends(get_commerce_data_service)],
    candidate_service: Annotated[
        SemanticCandidateService,
        Depends(get_commerce_semantic_candidate_service),
    ],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
) -> SemanticCandidateResult:
    try:
        view = data_service.get_view(
            workspace_id,
            _parse_dataset_id(raw_dataset_id),
        )
        return await run_in_threadpool(
            candidate_service.suggest,
            view.profile,
            view.mappings,
        )
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Commerce Dataset not found") from exc
    except RealModelBlockedError as exc:
        code = exc.preflight.status.value if exc.preflight is not None else "blocked_real_model"
        raise HTTPException(
            status_code=503,
            detail={"code": code, "message": str(exc)},
        ) from exc
    except SemanticCandidateParseError as exc:
        raise HTTPException(
            status_code=502,
            detail={"code": "semantic_candidate_parse_failed", "message": str(exc)},
        ) from exc


@router.post(
    "/datasets/{raw_dataset_id}/analyze",
    response_model=AnalysisResponse,
)
async def analyze_dataset(
    raw_dataset_id: Annotated[str, Path()],
    request: AnalysisRequest,
    service: Annotated[CommerceAnalysisService, Depends(get_commerce_analysis_service)],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
) -> AnalysisResponse:
    try:
        outcome = await service.analyze(
            workspace_id,
            _parse_dataset_id(raw_dataset_id),
            baseline_window=request.baseline_window,
            current_window=request.current_window,
            seller_id=request.seller_id,
        )
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Commerce Dataset not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AnalysisResponse(
        dataset_id=outcome.dataset_id,
        workspace_id=str(outcome.workspace_id),
        baseline_window=outcome.baseline_window,
        current_window=outcome.current_window,
        signals=list(outcome.signals),
        cases=[_case_response(case) for case in outcome.cases],
        skipped_sellers=[{"seller_id": item.seller_id, "reason": item.reason} for item in outcome.skipped_sellers],
    )


@router.post(
    "/datasets/{raw_dataset_id}/cases",
    response_model=ExplicitCaseResponse,
    status_code=201,
)
async def create_explicit_case(
    raw_dataset_id: Annotated[str, Path()],
    request: ExplicitCaseRequest,
    service: Annotated[CommerceAnalysisService, Depends(get_commerce_analysis_service)],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
) -> ExplicitCaseResponse:
    dataset_id = _parse_dataset_id(raw_dataset_id)
    trigger = CaseTriggerDigest(
        trigger_type=CaseTriggerType.EXPLICIT_USER,
        requested_paths=tuple(request.requested_paths),
        peer_policy=request.peer_policy,
    )
    try:
        outcome = await service.open_explicit_case(
            workspace_id,
            dataset_id,
            seller_id=request.seller_id,
            baseline_window=request.baseline_window,
            current_window=request.current_window,
            requested_paths=trigger.requested_paths,
            peer_policy=trigger.peer_policy,
        )
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Commerce Dataset not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ExplicitCaseResponse(
        case=_case_response(outcome.cases[0]),
        trigger=trigger,
        baseline_window=outcome.baseline_window,
        current_window=outcome.current_window,
    )


@router.get("/datasets/{raw_dataset_id}/capabilities", response_model=CapabilityProfile)
async def get_dataset_capabilities(
    raw_dataset_id: Annotated[str, Path()],
    service: Annotated[CommerceDataService, Depends(get_commerce_data_service)],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
) -> CapabilityProfile:
    try:
        return service.get_view(
            workspace_id,
            _parse_dataset_id(raw_dataset_id),
        ).capabilities
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Commerce Dataset not found") from exc


@router.get("/cases/{raw_case_id}", response_model=CaseDetailResponse)
async def get_case_detail(
    raw_case_id: Annotated[str, Path()],
    service: Annotated[CommerceReadService, Depends(get_commerce_read_service)],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
) -> CaseDetailResponse:
    case = await _require_case(service, workspace_id, _parse_case_id(raw_case_id))
    lineage, evidence, hypotheses, analysis, actions = await asyncio.gather(
        service.get_case_lineage(workspace_id, case.id),
        service.list_case_evidence(workspace_id, case.id),
        service.list_case_hypotheses(workspace_id, case),
        _case_analysis_response(service, workspace_id, case.id),
        service.list_case_actions(workspace_id, case.id),
    )
    return CaseDetailResponse(
        case=_case_response(case),
        lineage=_lineage_response(lineage) if lineage else None,
        evidence=[_evidence_response(item) for item in evidence],
        hypotheses=[_hypothesis_response(item) for item in hypotheses],
        analysis=analysis,
        actions=[_action_summary_response(item) for item in actions],
    )


@router.get("/cases/{raw_case_id}/evidence", response_model=EvidenceListResponse)
async def list_case_evidence(
    raw_case_id: Annotated[str, Path()],
    service: Annotated[CommerceReadService, Depends(get_commerce_read_service)],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
) -> EvidenceListResponse:
    case = await _require_case(service, workspace_id, _parse_case_id(raw_case_id))
    evidence = await service.list_case_evidence(workspace_id, case.id)
    return EvidenceListResponse(items=[_evidence_response(item) for item in evidence])


@router.get("/cases/{raw_case_id}/lineage", response_model=CaseLineageResponse)
async def get_case_lineage(
    raw_case_id: Annotated[str, Path()],
    service: Annotated[CommerceReadService, Depends(get_commerce_read_service)],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
) -> CaseLineageResponse:
    case = await _require_case(service, workspace_id, _parse_case_id(raw_case_id))
    lineage = await service.get_case_lineage(workspace_id, case.id)
    if lineage is None:
        raise HTTPException(status_code=404, detail="Commerce Case lineage not found")
    return _lineage_response(lineage)


@router.get(
    "/cases/{raw_case_id}/evidence/{raw_evidence_id}",
    response_model=EvidenceResponse,
)
async def get_case_evidence(
    raw_case_id: Annotated[str, Path()],
    raw_evidence_id: Annotated[str, Path()],
    service: Annotated[CommerceReadService, Depends(get_commerce_read_service)],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
) -> EvidenceResponse:
    case = await _require_case(service, workspace_id, _parse_case_id(raw_case_id))
    evidence = await service.get_evidence(
        workspace_id,
        _parse_evidence_id(raw_evidence_id),
    )
    if evidence is None or evidence.case_id != case.id:
        raise HTTPException(status_code=404, detail="Commerce Evidence not found")
    return _evidence_response(evidence)


@router.get("/cases/{raw_case_id}/hypotheses", response_model=HypothesisListResponse)
async def list_case_hypotheses(
    raw_case_id: Annotated[str, Path()],
    service: Annotated[CommerceReadService, Depends(get_commerce_read_service)],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
) -> HypothesisListResponse:
    case = await _require_case(service, workspace_id, _parse_case_id(raw_case_id))
    hypotheses = await service.list_case_hypotheses(workspace_id, case)
    return HypothesisListResponse(items=[_hypothesis_response(item) for item in hypotheses])


@router.get("/cases/{raw_case_id}/events", response_model=DomainEventListResponse)
async def list_case_events(
    raw_case_id: Annotated[str, Path()],
    service: Annotated[CommerceReadService, Depends(get_commerce_read_service)],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
) -> DomainEventListResponse:
    case = await _require_case(service, workspace_id, _parse_case_id(raw_case_id))
    events = await service.list_case_events(workspace_id, case.id)
    return DomainEventListResponse(items=[_event_response(item) for item in events])


@router.get("/cases/{raw_case_id}/runs", response_model=RunListResponse)
async def list_case_runs(
    raw_case_id: Annotated[str, Path()],
    service: Annotated[CommerceRunService, Depends(get_commerce_run_service)],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> RunListResponse:
    try:
        runs = await service.list_case_runs(
            workspace_id,
            _parse_case_id(raw_case_id),
            limit=limit,
            offset=offset,
        )
    except InvestigationCaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Commerce Case not found") from exc
    return RunListResponse(
        items=[_run_response(run) for run in runs],
        limit=limit,
        offset=offset,
    )


@router.get("/runs/{raw_run_id}", response_model=RunDetailResponse)
async def get_run_detail(
    raw_run_id: Annotated[str, Path()],
    service: Annotated[CommerceRunService, Depends(get_commerce_run_service)],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
) -> RunDetailResponse:
    run = await _require_run(service, workspace_id, _parse_run_id(raw_run_id))
    latest = await service.get_latest_checkpoint(workspace_id, run.id)
    return RunDetailResponse(
        run=_run_response(run),
        latest_checkpoint=_checkpoint_response(latest) if latest else None,
    )


@router.post(
    "/runs/{raw_run_id}/reconciliations",
    response_model=RunReconciliationResponse,
)
async def reconcile_run_unknown_outcome(
    raw_run_id: Annotated[str, Path()],
    request: RunReconciliationRequest,
    service: Annotated[
        CommerceRunReconciliationService,
        Depends(get_commerce_run_reconciliation_service),
    ],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
    actor_id: Annotated[str, Depends(get_commerce_actor_id)],
) -> RunReconciliationResponse:
    try:
        result = await service.reconcile_unknown_outcome(
            workspace_id,
            _parse_run_id(raw_run_id),
            actor_id=actor_id,
            reason=request.reason,
            idempotency_key=request.idempotency_key,
        )
    except RunReconciliationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RunReconciliationConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return RunReconciliationResponse(
        run=_run_response(result.run),
        latest_checkpoint=_checkpoint_response(result.latest_checkpoint),
        disposition=result.disposition,
        replayed=result.replayed,
    )


@router.get("/runs/{raw_run_id}/events", response_model=DomainEventListResponse)
async def list_run_events(
    raw_run_id: Annotated[str, Path()],
    service: Annotated[CommerceRunService, Depends(get_commerce_run_service)],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
) -> DomainEventListResponse:
    run = await _require_run(service, workspace_id, _parse_run_id(raw_run_id))
    events = await service.list_run_events(workspace_id, run.id)
    return DomainEventListResponse(items=[_event_response(item) for item in events])


@router.get(
    "/runs/{raw_run_id}/checkpoints",
    response_model=RunCheckpointListResponse,
)
async def list_run_checkpoints(
    raw_run_id: Annotated[str, Path()],
    service: Annotated[CommerceRunService, Depends(get_commerce_run_service)],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
) -> RunCheckpointListResponse:
    run = await _require_run(service, workspace_id, _parse_run_id(raw_run_id))
    checkpoints = await service.list_run_checkpoints(workspace_id, run.id)
    return RunCheckpointListResponse(items=[_checkpoint_response(item) for item in checkpoints])


@router.post(
    "/cases/{raw_case_id}/action-plans",
    response_model=AgentActionPlanResponse,
    status_code=201,
)
async def plan_case_action(
    raw_case_id: Annotated[str, Path()],
    request: AgentActionPlanRequest,
    service: Annotated[CommerceActionService, Depends(get_commerce_action_service)],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
    actor_id: Annotated[str, Depends(get_commerce_actor_id)],
) -> AgentActionPlanResponse:
    try:
        result = await service.plan_and_propose(
            workspace_id,
            _parse_case_id(raw_case_id),
            idempotency_key=request.idempotency_key,
            actor_id=actor_id,
        )
    except VerifiedModelCallBlockedError as exc:
        raise HTTPException(
            status_code=503,
            detail="Fresh DeepSeek V4 Action Planner is unavailable",
        ) from exc
    except (ActionPlannerParseError, ActionCatalogError) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Action Planner output was rejected: {exc}",
        ) from exc
    except ActionValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"{exc.reason.value}: {exc}",
        ) from exc
    except ContextLoadError as exc:
        status_code = 404 if "not found" in str(exc).lower() else 409
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except ActionProposalError as exc:
        status_code = 404 if "does not exist" in str(exc).lower() else 409
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    proposal = result.proposal
    return AgentActionPlanResponse(
        planning=result.planning,
        record=proposal.record,
        approval=proposal.approval,
        created=proposal.created,
    )


@router.post(
    "/cases/{raw_case_id}/actions",
    response_model=ActionProposalResponse,
    status_code=201,
)
async def propose_case_action(
    raw_case_id: Annotated[str, Path()],
    request: ActionProposalRequest,
    service: Annotated[CommerceActionService, Depends(get_commerce_action_service)],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
    actor_id: Annotated[str, Depends(get_commerce_actor_id)],
) -> ActionProposalResponse:
    try:
        result = await service.propose(
            workspace_id,
            _parse_case_id(raw_case_id),
            idempotency_key=request.idempotency_key,
            title=request.title,
            description=request.description,
            evidence_ids=request.evidence_ids,
            hypothesis_ids=request.hypothesis_ids,
            expected_signal_metric_ids=request.expected_signal_metric_ids,
            parameters=request.parameters,
            rollback_plan=request.rollback_plan,
            actor_id=actor_id,
        )
    except ActionValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"{exc.reason.value}: {exc}",
        ) from exc
    except ContextLoadError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"Case context unavailable: {exc.reason.value}",
        ) from exc
    except ActionProposalError as exc:
        detail = str(exc)
        if "Action ID was reused" in detail:
            detail = "Action idempotency key was reused with another proposal"
        raise HTTPException(status_code=409, detail=detail) from exc
    except DuplicateEntityError as exc:
        raise HTTPException(
            status_code=409,
            detail="Action proposal conflicted with a concurrent request",
        ) from exc
    return ActionProposalResponse(
        record=result.record,
        approval=result.approval,
        created=result.created,
    )


@router.get(
    "/cases/{raw_case_id}/actions",
    response_model=ActionRecordListResponse,
)
async def list_case_actions(
    raw_case_id: Annotated[str, Path()],
    service: Annotated[CommerceActionService, Depends(get_commerce_action_service)],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
) -> ActionRecordListResponse:
    records = await service.list_case_actions(
        workspace_id,
        _parse_case_id(raw_case_id),
    )
    if records is None:
        raise HTTPException(status_code=404, detail="Commerce Case not found")
    return ActionRecordListResponse(items=list(records))


@router.get(
    "/actions/{raw_action_id}",
    response_model=ActionDetailResponse,
)
async def get_action_detail(
    raw_action_id: Annotated[str, Path()],
    service: Annotated[CommerceActionService, Depends(get_commerce_action_service)],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
) -> ActionDetailResponse:
    action_id = _parse_action_id(raw_action_id)
    record = await service.get_action(workspace_id, action_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Commerce Action not found")
    approval = await service.get_approval(workspace_id, action_id)
    artifact = await service.get_artifact(workspace_id, action_id)
    follow_ups = await service.list_follow_ups(workspace_id, action_id)
    return ActionDetailResponse(
        record=record,
        approval=approval,
        artifact=artifact,
        follow_ups=list(follow_ups),
    )


@router.post(
    "/actions/{raw_action_id}/executions",
    response_model=ActionExecutionResponse,
    status_code=201,
)
async def execute_or_rollback_action(
    raw_action_id: Annotated[str, Path()],
    request: ActionExecutionRequest,
    service: Annotated[
        ActionExecutionService,
        Depends(get_commerce_action_execution_service),
    ],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
    actor_id: Annotated[str, Depends(get_commerce_actor_id)],
) -> ActionExecutionResponse:
    action_id = _parse_action_id(raw_action_id)
    try:
        started = await service.start(
            workspace_id,
            action_id,
            operation=request.operation,
            idempotency_key=request.idempotency_key,
            actor_id=actor_id,
        )
        worker_digest = hashlib.sha256(actor_id.encode("utf-8")).hexdigest()[:16]
        result = await service.execute(
            workspace_id,
            started.run.id,
            worker_id=f"commerce-api-{worker_digest}",
        )
    except ActionExecutionError as exc:
        status_code = 404 if "not found" in str(exc).lower() else 409
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except RunLeaseConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail="Action Execution Run is already owned by another Worker",
        ) from exc
    return ActionExecutionResponse(
        run=_run_response(result.run),
        record=result.record,
        artifact=result.artifact,
        created=started.created,
        replayed=result.replayed,
        error_message=result.error_message,
    )


@router.post(
    "/actions/{raw_action_id}/follow-ups",
    response_model=FollowUpEvaluationResponse,
    status_code=201,
)
async def evaluate_action_follow_up(
    raw_action_id: Annotated[str, Path()],
    request: FollowUpStartRequest,
    service: Annotated[FollowUpService, Depends(get_commerce_follow_up_service)],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
    actor_id: Annotated[str, Depends(get_commerce_actor_id)],
) -> FollowUpEvaluationResponse:
    action_id = _parse_action_id(raw_action_id)
    try:
        started = await service.start(
            workspace_id,
            action_id,
            dataset_id=request.dataset_id,
            evaluation_window=request.evaluation_window,
            idempotency_key=request.idempotency_key,
            actor_id=actor_id,
        )
        worker_digest = hashlib.sha256(actor_id.encode()).hexdigest()[:16]
        result = await service.evaluate(
            workspace_id,
            started.run.id,
            worker_id=f"commerce-follow-up-api-{worker_digest}",
        )
    except FollowUpError as exc:
        status_code = 404 if "not found" in str(exc).lower() else 409
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except RunLeaseConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail="Follow-up Run is already owned by another Worker",
        ) from exc
    return FollowUpEvaluationResponse(
        run=_run_response(result.run),
        follow_up=result.follow_up,
        record=result.record,
        case=_case_response(result.case),
        created=started.created,
        replayed=result.replayed,
    )


@router.get(
    "/actions/{raw_action_id}/follow-ups",
    response_model=FollowUpListResponse,
)
async def list_action_follow_ups(
    raw_action_id: Annotated[str, Path()],
    service: Annotated[FollowUpService, Depends(get_commerce_follow_up_service)],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
) -> FollowUpListResponse:
    records = await service.list_action(
        workspace_id,
        _parse_action_id(raw_action_id),
    )
    if records is None:
        raise HTTPException(status_code=404, detail="Commerce Action not found")
    return FollowUpListResponse(items=list(records))


@router.get(
    "/actions/{raw_action_id}/approval",
    response_model=ApprovalRequest,
)
async def get_action_approval(
    raw_action_id: Annotated[str, Path()],
    service: Annotated[CommerceActionService, Depends(get_commerce_action_service)],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
) -> ApprovalRequest:
    action_id = _parse_action_id(raw_action_id)
    approval = await service.get_approval(workspace_id, action_id)
    if approval is None:
        raise HTTPException(
            status_code=404,
            detail="Commerce Action Approval not found",
        )
    return approval


async def _decide_action_approval(
    *,
    service: CommerceActionService,
    workspace_id: WorkspaceId,
    action_id: ActionId,
    decision: ApprovalDecisionType,
    actor_id: str,
    idempotency_key: str,
    reason: str | None,
    replacement_draft=None,
) -> ApprovalDecisionResponse:
    try:
        result = await service.decide(
            workspace_id,
            action_id,
            decision=decision,
            actor_id=actor_id,
            idempotency_key=idempotency_key,
            reason=reason,
            replacement_draft=replacement_draft,
        )
    except ApprovalDecisionError as exc:
        status_code = 404 if "not found" in str(exc).lower() else 409
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except ApprovalStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DuplicateEntityError as exc:
        raise HTTPException(
            status_code=409,
            detail="Approval decision conflicted with a concurrent request",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail="Approval state changed; reload the Action and retry",
        ) from exc
    return ApprovalDecisionResponse(
        record=result.record,
        approval=result.approval,
        command=result.command,
        replayed=result.replayed,
    )


@router.post(
    "/actions/{raw_action_id}/approvals/approve",
    response_model=ApprovalDecisionResponse,
)
async def approve_action(
    raw_action_id: Annotated[str, Path()],
    request: ApprovalCommandRequest,
    service: Annotated[CommerceActionService, Depends(get_commerce_action_service)],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
    actor_id: Annotated[str, Depends(get_commerce_actor_id)],
) -> ApprovalDecisionResponse:
    return await _decide_action_approval(
        service=service,
        workspace_id=workspace_id,
        action_id=_parse_action_id(raw_action_id),
        decision=ApprovalDecisionType.APPROVE,
        actor_id=actor_id,
        idempotency_key=request.idempotency_key,
        reason=request.reason,
    )


@router.post(
    "/actions/{raw_action_id}/approvals/reject",
    response_model=ApprovalDecisionResponse,
)
async def reject_action(
    raw_action_id: Annotated[str, Path()],
    request: ApprovalCommandRequest,
    service: Annotated[CommerceActionService, Depends(get_commerce_action_service)],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
    actor_id: Annotated[str, Depends(get_commerce_actor_id)],
) -> ApprovalDecisionResponse:
    return await _decide_action_approval(
        service=service,
        workspace_id=workspace_id,
        action_id=_parse_action_id(raw_action_id),
        decision=ApprovalDecisionType.REJECT,
        actor_id=actor_id,
        idempotency_key=request.idempotency_key,
        reason=request.reason,
    )


@router.post(
    "/actions/{raw_action_id}/approvals/modify",
    response_model=ApprovalDecisionResponse,
)
async def modify_action(
    raw_action_id: Annotated[str, Path()],
    request: ApprovalModifyRequest,
    service: Annotated[CommerceActionService, Depends(get_commerce_action_service)],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
    actor_id: Annotated[str, Depends(get_commerce_actor_id)],
) -> ApprovalDecisionResponse:
    action_id = _parse_action_id(raw_action_id)
    record = await service.get_action(workspace_id, action_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Commerce Action not found")
    replacement = request.replacement
    replacement_draft = service.build_draft(
        workspace_id,
        record.action.case_id,
        idempotency_key=request.replacement_idempotency_key,
        title=replacement.title,
        description=replacement.description,
        evidence_ids=replacement.evidence_ids,
        hypothesis_ids=replacement.hypothesis_ids,
        expected_signal_metric_ids=replacement.expected_signal_metric_ids,
        parameters=replacement.parameters,
        rollback_plan=replacement.rollback_plan,
    )
    if replacement_draft.id == action_id:
        raise HTTPException(
            status_code=409,
            detail="Replacement Action must use a new idempotency key",
        )
    return await _decide_action_approval(
        service=service,
        workspace_id=workspace_id,
        action_id=action_id,
        decision=ApprovalDecisionType.MODIFY,
        actor_id=actor_id,
        idempotency_key=request.idempotency_key,
        reason=request.reason,
        replacement_draft=replacement_draft,
    )


@router.post(
    "/skill-candidates",
    response_model=SkillCandidateProposalResponse,
    status_code=201,
)
async def propose_skill_candidate(
    request: SkillCandidateProposalRequest,
    service: Annotated[
        CommerceSkillCandidateService,
        Depends(get_commerce_skill_candidate_service),
    ],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
    actor_id: Annotated[str, Depends(get_commerce_actor_id)],
) -> SkillCandidateProposalResponse:
    try:
        result = await run_in_threadpool(
            service.propose,
            workspace_id,
            actor_id=actor_id,
            idempotency_key=request.idempotency_key,
            skill_name=request.skill_name,
            base_version=request.base_version,
            candidate_version=request.candidate_version,
            content=request.content,
            source_failure_codes=request.source_failure_codes,
            experiment_id=request.experiment_id,
        )
    except SkillCandidateEvidenceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SkillCandidateProposalConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return SkillCandidateProposalResponse(
        candidate=result.candidate,
        created=result.created,
    )


@router.get(
    "/skill-candidates",
    response_model=SkillCandidateListResponse,
)
async def list_skill_candidates(
    service: Annotated[
        CommerceSkillCandidateService,
        Depends(get_commerce_skill_candidate_service),
    ],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
) -> SkillCandidateListResponse:
    candidates = await run_in_threadpool(service.list, workspace_id)
    return SkillCandidateListResponse(items=list(candidates))


@router.get(
    "/skill-candidates/{raw_candidate_id}",
    response_model=SkillCandidate,
)
async def get_skill_candidate(
    raw_candidate_id: Annotated[str, Path()],
    service: Annotated[
        CommerceSkillCandidateService,
        Depends(get_commerce_skill_candidate_service),
    ],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
) -> SkillCandidate:
    candidate = await run_in_threadpool(
        service.get,
        workspace_id,
        _parse_skill_candidate_id(raw_candidate_id),
    )
    if candidate is None:
        raise HTTPException(status_code=404, detail="Skill Candidate not found")
    return candidate


@router.get(
    "/skill-candidates/{raw_candidate_id}/evidence",
    response_model=SkillCandidateEvidenceResponse,
)
async def get_skill_candidate_evidence(
    raw_candidate_id: Annotated[str, Path()],
    service: Annotated[
        CommerceSkillCandidateService,
        Depends(get_commerce_skill_candidate_service),
    ],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
) -> SkillCandidateEvidenceResponse:
    try:
        result = await run_in_threadpool(
            service.evidence,
            workspace_id,
            _parse_skill_candidate_id(raw_candidate_id),
        )
    except SkillCandidateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SkillCandidateEvidenceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (
        SkillCandidateProposalConflictError,
        SkillCandidateTransitionConflictError,
    ) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return SkillCandidateEvidenceResponse(
        candidate=result.candidate,
        experiment_role=result.experiment_role,
        definition=result.definition,
        report=result.report,
        active_pointer=result.active_pointer,
    )


@router.post(
    "/skill-candidates/{raw_candidate_id}/promote",
    response_model=SkillCandidateTransitionResponse,
)
async def promote_skill_candidate(
    raw_candidate_id: Annotated[str, Path()],
    request: SkillCandidatePromotionRequest,
    service: Annotated[
        CommerceSkillCandidateService,
        Depends(get_commerce_skill_candidate_service),
    ],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
    actor_id: Annotated[str, Depends(get_commerce_actor_id)],
) -> SkillCandidateTransitionResponse:
    try:
        result = await run_in_threadpool(
            service.promote,
            workspace_id,
            _parse_skill_candidate_id(raw_candidate_id),
            reviewer_id=actor_id,
            idempotency_key=request.idempotency_key,
        )
    except SkillCandidateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SkillCandidateTransitionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return SkillCandidateTransitionResponse(
        candidate=result.candidate,
        active_pointer=result.active_pointer,
        replayed=result.replayed,
    )


@router.get(
    "/skills/{skill_name}/active",
    response_model=ActiveSkillPointer,
)
async def get_active_skill_pointer(
    skill_name: Annotated[str, Path(pattern=r"^[a-z][a-z0-9-]*$")],
    service: Annotated[
        CommerceSkillCandidateService,
        Depends(get_commerce_skill_candidate_service),
    ],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
) -> ActiveSkillPointer:
    try:
        pointer = await run_in_threadpool(
            service.active_pointer,
            workspace_id,
            skill_name,
        )
    except SkillCandidateTransitionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if pointer is None:
        raise HTTPException(status_code=404, detail="Active Skill pointer not found")
    return pointer


@router.post(
    "/skills/{skill_name}/rollback",
    response_model=SkillCandidateTransitionResponse,
)
async def rollback_active_skill(
    skill_name: Annotated[str, Path(pattern=r"^[a-z][a-z0-9-]*$")],
    request: SkillCandidateRollbackRequest,
    service: Annotated[
        CommerceSkillCandidateService,
        Depends(get_commerce_skill_candidate_service),
    ],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
    actor_id: Annotated[str, Depends(get_commerce_actor_id)],
) -> SkillCandidateTransitionResponse:
    try:
        result = await run_in_threadpool(
            service.rollback,
            workspace_id,
            skill_name,
            reviewer_id=actor_id,
            reason=request.reason,
            idempotency_key=request.idempotency_key,
        )
    except SkillCandidateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SkillCandidateTransitionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return SkillCandidateTransitionResponse(
        candidate=result.candidate,
        active_pointer=result.active_pointer,
        replayed=result.replayed,
    )
