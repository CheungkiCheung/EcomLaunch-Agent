"""Feature-flagged, read-only Commerce Case API."""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Path, Query, UploadFile

from app.commerce.api.data_service import (
    CommerceDataService,
    DatasetNotFoundError,
)
from app.commerce.api.dependencies import (
    get_commerce_data_service,
    get_commerce_read_service,
    get_commerce_workspace_id,
)
from app.commerce.api.schemas import (
    CaseDetailResponse,
    CaseListResponse,
    CaseResponse,
    DatasetIntakeResponse,
    DomainEventListResponse,
    DomainEventResponse,
    EvidenceListResponse,
    EvidenceResponse,
    HypothesisListResponse,
    HypothesisResponse,
)
from app.commerce.api.service import CommerceReadService
from app.commerce.data.capabilities import CapabilityProfile
from app.commerce.data.intake import DataIntakeError
from app.commerce.data.profiler import DatasetProfile
from app.commerce.domain.enums import CaseStatus
from app.commerce.domain.events import DomainEventEnvelope
from app.commerce.domain.ids import CaseId, DatasetId, EvidenceId, WorkspaceId
from app.commerce.domain.models import Case, Evidence, Hypothesis

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
        supporting_evidence_ids=[
            str(value) for value in hypothesis.supporting_evidence_ids
        ],
        contradicting_evidence_ids=[
            str(value) for value in hypothesis.contradicting_evidence_ids
        ],
        version=hypothesis.version,
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
        causation_event_id=(
            str(event.causation_event_id)
            if event.causation_event_id is not None
            else None
        ),
        actor=event.actor.value,
        payload=event.payload,
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


async def _require_case(
    service: CommerceReadService,
    workspace_id: WorkspaceId,
    case_id: CaseId,
) -> Case:
    case = await service.get_case(workspace_id, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Commerce Case not found")
    return case


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
    evidence, hypotheses = await asyncio.gather(
        service.list_case_evidence(workspace_id, case.id),
        service.list_case_hypotheses(workspace_id, case),
    )
    return CaseDetailResponse(
        case=_case_response(case),
        evidence=[_evidence_response(item) for item in evidence],
        hypotheses=[_hypothesis_response(item) for item in hypotheses],
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
    return HypothesisListResponse(
        items=[_hypothesis_response(item) for item in hypotheses]
    )


@router.get("/cases/{raw_case_id}/events", response_model=DomainEventListResponse)
async def list_case_events(
    raw_case_id: Annotated[str, Path()],
    service: Annotated[CommerceReadService, Depends(get_commerce_read_service)],
    workspace_id: Annotated[WorkspaceId, Depends(get_commerce_workspace_id)],
) -> DomainEventListResponse:
    case = await _require_case(service, workspace_id, _parse_case_id(raw_case_id))
    events = await service.list_case_events(workspace_id, case.id)
    return DomainEventListResponse(items=[_event_response(item) for item in events])
