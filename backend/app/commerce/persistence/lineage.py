"""Immutable Case data-lineage repository."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.commerce.domain.ids import CaseId, WorkspaceId
from app.commerce.domain.lineage import CaseLineage
from app.commerce.persistence.models import CaseLineageRow
from app.commerce.persistence.repositories import DuplicateEntityError


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _row_to_lineage(row: CaseLineageRow) -> CaseLineage:
    return CaseLineage.model_validate(
        {
            "schema_version": row.schema_version,
            "workspace_id": row.workspace_id,
            "case_id": row.case_id,
            "dataset_id": row.dataset_id,
            "seller_entity_id": row.seller_entity_id,
            "seller_external_key": row.seller_external_key,
            "baseline_start": _utc(row.baseline_start),
            "baseline_end": _utc(row.baseline_end),
            "current_start": _utc(row.current_start),
            "current_end": _utc(row.current_end),
            "anomaly_ids": tuple(row.anomaly_ids_json),
            "metric_observation_ids": tuple(row.metric_observation_ids_json),
            "analysis_artifact_relative_path": row.analysis_artifact_relative_path,
            "analysis_artifact_sha256": row.analysis_artifact_sha256,
            "created_at": _utc(row.created_at),
        }
    )


class SqlCaseLineageRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get(
        self,
        workspace_id: WorkspaceId,
        case_id: CaseId,
    ) -> CaseLineage | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(CaseLineageRow).where(
                    CaseLineageRow.workspace_id == str(workspace_id),
                    CaseLineageRow.case_id == str(case_id),
                )
            )
            return _row_to_lineage(row) if row is not None else None

    async def create(self, lineage: CaseLineage) -> None:
        try:
            async with self._session_factory() as session, session.begin():
                await self.create_in_session(session, lineage)
        except IntegrityError as exc:
            raise DuplicateEntityError(
                f"Case lineage already exists: {lineage.case_id}"
            ) from exc

    @staticmethod
    async def create_in_session(
        session: AsyncSession,
        lineage: CaseLineage,
    ) -> None:
        session.add(
            CaseLineageRow(
                case_id=str(lineage.case_id),
                workspace_id=str(lineage.workspace_id),
                dataset_id=str(lineage.dataset_id),
                seller_entity_id=str(lineage.seller_entity_id),
                seller_external_key=lineage.seller_external_key,
                baseline_start=lineage.baseline_start,
                baseline_end=lineage.baseline_end,
                current_start=lineage.current_start,
                current_end=lineage.current_end,
                anomaly_ids_json=[str(value) for value in lineage.anomaly_ids],
                metric_observation_ids_json=[
                    str(value) for value in lineage.metric_observation_ids
                ],
                schema_version=lineage.schema_version,
                analysis_artifact_relative_path=lineage.analysis_artifact_relative_path,
                analysis_artifact_sha256=lineage.analysis_artifact_sha256,
                created_at=lineage.created_at,
            )
        )
        await session.flush()
