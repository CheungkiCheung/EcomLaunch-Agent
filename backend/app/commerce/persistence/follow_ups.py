"""Workspace-scoped Follow-up request and evaluation persistence."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.commerce.actions.follow_up_contracts import FollowUpRecord
from app.commerce.domain.ids import (
    ActionId,
    FollowUpId,
    RunId,
    WorkspaceId,
)
from app.commerce.persistence.models import FollowUpRow
from app.commerce.persistence.repositories import (
    DuplicateEntityError,
    OptimisticConcurrencyError,
)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _values(record: FollowUpRecord) -> dict:
    return {
        "workspace_id": str(record.workspace_id),
        "case_id": str(record.case_id),
        "action_id": str(record.action_id),
        "run_id": str(record.run_id),
        "dataset_id": str(record.dataset_id),
        "status": record.status.value,
        "outcome": record.outcome.value if record.outcome is not None else None,
        "follow_up_json": record.model_dump(mode="json"),
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "version": record.version,
    }


def _from_row(row: FollowUpRow) -> FollowUpRecord:
    return FollowUpRecord.model_validate_json(
        json.dumps(
            {
                **row.follow_up_json,
                "created_at": _utc(row.created_at).isoformat(),
                "updated_at": _utc(row.updated_at).isoformat(),
                "version": row.version,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )


class SqlFollowUpRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(self, record: FollowUpRecord) -> None:
        try:
            async with self._session_factory() as session, session.begin():
                await self.create_in_session(session, record)
        except IntegrityError as exc:
            raise DuplicateEntityError(f"Follow-up already exists: {record.id}") from exc

    @staticmethod
    async def create_in_session(
        session: AsyncSession,
        record: FollowUpRecord,
    ) -> None:
        session.add(
            FollowUpRow(
                follow_up_id=str(record.id),
                **_values(record),
            )
        )
        await session.flush()

    async def get(
        self,
        workspace_id: WorkspaceId,
        follow_up_id: FollowUpId,
    ) -> FollowUpRecord | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(FollowUpRow).where(
                    FollowUpRow.workspace_id == str(workspace_id),
                    FollowUpRow.follow_up_id == str(follow_up_id),
                )
            )
            return _from_row(row) if row is not None else None

    async def get_by_run(
        self,
        workspace_id: WorkspaceId,
        run_id: RunId,
    ) -> FollowUpRecord | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(FollowUpRow).where(
                    FollowUpRow.workspace_id == str(workspace_id),
                    FollowUpRow.run_id == str(run_id),
                )
            )
            return _from_row(row) if row is not None else None

    async def list_action(
        self,
        workspace_id: WorkspaceId,
        action_id: ActionId,
    ) -> tuple[FollowUpRecord, ...]:
        statement = (
            select(FollowUpRow)
            .where(
                FollowUpRow.workspace_id == str(workspace_id),
                FollowUpRow.action_id == str(action_id),
            )
            .order_by(FollowUpRow.created_at.asc(), FollowUpRow.follow_up_id.asc())
        )
        async with self._session_factory() as session:
            rows = (await session.scalars(statement)).all()
            return tuple(_from_row(row) for row in rows)

    @staticmethod
    async def save_in_session(
        session: AsyncSession,
        record: FollowUpRecord,
        *,
        expected_version: int,
    ) -> None:
        if record.version != expected_version + 1:
            raise ValueError("Saved Follow-up version must advance by one")
        result = await session.execute(
            update(FollowUpRow)
            .where(
                FollowUpRow.workspace_id == str(record.workspace_id),
                FollowUpRow.follow_up_id == str(record.id),
                FollowUpRow.version == expected_version,
            )
            .values(**_values(record))
        )
        if result.rowcount != 1:
            raise OptimisticConcurrencyError(f"Follow-up {record.id} changed during save")
