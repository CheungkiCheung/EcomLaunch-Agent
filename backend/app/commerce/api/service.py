"""Application read service for the Commerce Case workspace."""

from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.commerce.agents.context_loader import ContextPacketLoader, LoadedCaseAnalysis
from app.commerce.api.data_service import CommerceDataService
from app.commerce.domain.enums import CaseStatus
from app.commerce.domain.events import DomainEventEnvelope
from app.commerce.domain.ids import CaseId, EvidenceId, WorkspaceId
from app.commerce.domain.lineage import CaseLineage
from app.commerce.domain.models import Case, Evidence, Hypothesis
from app.commerce.persistence.actions import ActionRecord, SqlActionRepository
from app.commerce.persistence.events import SqlDomainEventStore
from app.commerce.persistence.lineage import SqlCaseLineageRepository
from app.commerce.persistence.repositories import SqlCaseRepository
from app.commerce.persistence.work_records import (
    SqlEvidenceRepository,
    SqlHypothesisRepository,
)


class CommerceReadService:
    """Read-only application service; it never infers state from chat text."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        data_service: CommerceDataService | None = None,
    ) -> None:
        self._cases = SqlCaseRepository(session_factory)
        self._evidence = SqlEvidenceRepository(session_factory)
        self._hypotheses = SqlHypothesisRepository(session_factory)
        self._events = SqlDomainEventStore(session_factory)
        self._lineage = SqlCaseLineageRepository(session_factory)
        self._actions = SqlActionRepository(session_factory)
        self._analysis_loader = (
            ContextPacketLoader(
                data_service=data_service,
                session_factory=session_factory,
            )
            if data_service is not None
            else None
        )

    async def list_cases(
        self,
        workspace_id: WorkspaceId,
        *,
        status: CaseStatus | None,
        limit: int,
        offset: int,
    ) -> tuple[Case, ...]:
        return await self._cases.list(
            workspace_id,
            status=status,
            limit=limit,
            offset=offset,
        )

    async def get_case(self, workspace_id: WorkspaceId, case_id: CaseId) -> Case | None:
        return await self._cases.get(workspace_id, case_id)

    async def get_case_lineage(
        self,
        workspace_id: WorkspaceId,
        case_id: CaseId,
    ) -> CaseLineage | None:
        return await self._lineage.get(workspace_id, case_id)

    async def get_case_analysis(
        self,
        workspace_id: WorkspaceId,
        case_id: CaseId,
    ) -> LoadedCaseAnalysis | None:
        if self._analysis_loader is None:
            return None
        return await self._analysis_loader.load_case_analysis(workspace_id, case_id)

    async def list_case_actions(
        self,
        workspace_id: WorkspaceId,
        case_id: CaseId,
    ) -> tuple[ActionRecord, ...]:
        return await self._actions.list_case(workspace_id, case_id)

    async def get_evidence(
        self,
        workspace_id: WorkspaceId,
        evidence_id: EvidenceId,
    ) -> Evidence | None:
        return await self._evidence.get(workspace_id, evidence_id)

    async def list_case_evidence(
        self,
        workspace_id: WorkspaceId,
        case_id: CaseId,
    ) -> tuple[Evidence, ...]:
        return await self._evidence.list_case(workspace_id, case_id)

    async def list_case_hypotheses(
        self,
        workspace_id: WorkspaceId,
        case: Case,
    ) -> tuple[Hypothesis, ...]:
        versions = await asyncio.gather(*(self._hypotheses.get_latest(workspace_id, hypothesis_id) for hypothesis_id in case.hypothesis_ids))
        return tuple(hypothesis for hypothesis in versions if hypothesis is not None)

    async def list_case_events(
        self,
        workspace_id: WorkspaceId,
        case_id: CaseId,
    ) -> tuple[DomainEventEnvelope, ...]:
        return await self._events.list_case(workspace_id, case_id)
