"""Workspace-scoped persistence for real internal Action artifacts."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.commerce.actions.artifacts import ActionExecutionArtifact
from app.commerce.domain.ids import ActionId, WorkspaceId
from app.commerce.persistence.models import ActionArtifactRow
from app.commerce.persistence.repositories import (
    DuplicateEntityError,
    OptimisticConcurrencyError,
)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _values(artifact: ActionExecutionArtifact) -> dict:
    return {
        "workspace_id": str(artifact.workspace_id),
        "case_id": str(artifact.case_id),
        "kind": artifact.kind.value,
        "status": artifact.status.value,
        "artifact_json": artifact.model_dump(mode="json"),
        "created_at": artifact.created_at,
        "updated_at": artifact.updated_at,
        "version": artifact.version,
    }


def _from_row(row: ActionArtifactRow) -> ActionExecutionArtifact:
    payload = {
        **row.artifact_json,
        "created_at": _utc(row.created_at),
        "updated_at": _utc(row.updated_at),
        "version": row.version,
    }
    return ActionExecutionArtifact.model_validate(payload)


class SqlActionArtifactRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(self, artifact: ActionExecutionArtifact) -> None:
        try:
            async with self._session_factory() as session, session.begin():
                await self.create_in_session(session, artifact)
        except IntegrityError as exc:
            raise DuplicateEntityError(f"Action artifact already exists: {artifact.action_id}") from exc

    @staticmethod
    async def create_in_session(
        session: AsyncSession,
        artifact: ActionExecutionArtifact,
    ) -> None:
        session.add(
            ActionArtifactRow(
                action_id=str(artifact.action_id),
                **_values(artifact),
            )
        )
        await session.flush()

    async def get(
        self,
        workspace_id: WorkspaceId,
        action_id: ActionId,
    ) -> ActionExecutionArtifact | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(ActionArtifactRow).where(
                    ActionArtifactRow.workspace_id == str(workspace_id),
                    ActionArtifactRow.action_id == str(action_id),
                )
            )
            return _from_row(row) if row is not None else None

    @staticmethod
    async def get_in_session(
        session: AsyncSession,
        workspace_id: WorkspaceId,
        action_id: ActionId,
    ) -> ActionExecutionArtifact | None:
        row = await session.scalar(
            select(ActionArtifactRow).where(
                ActionArtifactRow.workspace_id == str(workspace_id),
                ActionArtifactRow.action_id == str(action_id),
            )
        )
        return _from_row(row) if row is not None else None

    async def save(
        self,
        artifact: ActionExecutionArtifact,
        *,
        expected_version: int,
    ) -> None:
        if artifact.version != expected_version + 1:
            raise ValueError("Saved Action artifact version must advance by one")
        async with self._session_factory() as session, session.begin():
            result = await session.execute(
                update(ActionArtifactRow)
                .where(
                    ActionArtifactRow.workspace_id == str(artifact.workspace_id),
                    ActionArtifactRow.action_id == str(artifact.action_id),
                    ActionArtifactRow.version == expected_version,
                )
                .values(**_values(artifact))
            )
            if result.rowcount != 1:
                raise OptimisticConcurrencyError(f"Action artifact {artifact.action_id} changed during save")

    @staticmethod
    async def save_in_session(
        session: AsyncSession,
        artifact: ActionExecutionArtifact,
        *,
        expected_version: int,
    ) -> None:
        if artifact.version != expected_version + 1:
            raise ValueError("Saved Action artifact version must advance by one")
        result = await session.execute(
            update(ActionArtifactRow)
            .where(
                ActionArtifactRow.workspace_id == str(artifact.workspace_id),
                ActionArtifactRow.action_id == str(artifact.action_id),
                ActionArtifactRow.version == expected_version,
            )
            .values(**_values(artifact))
        )
        if result.rowcount != 1:
            raise OptimisticConcurrencyError(f"Action artifact {artifact.action_id} changed during save")
