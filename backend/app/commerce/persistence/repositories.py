"""Commerce Repository protocols and SQLAlchemy implementations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.commerce.domain.enums import CaseStatus
from app.commerce.domain.ids import CaseId, WorkspaceId
from app.commerce.domain.models import Case
from app.commerce.persistence.models import CaseRow


class DuplicateEntityError(ValueError):
    """The immutable entity ID already exists."""


class EntityNotFoundError(LookupError):
    """The entity does not exist inside the requested Workspace."""


class OptimisticConcurrencyError(RuntimeError):
    """The persisted entity version no longer matches the caller's version."""


@runtime_checkable
class CaseRepository(Protocol):
    async def create(self, case: Case) -> None: ...

    async def get(self, workspace_id: WorkspaceId, case_id: CaseId) -> Case | None: ...

    async def list(
        self,
        workspace_id: WorkspaceId,
        *,
        status: CaseStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[Case, ...]: ...

    async def save(self, case: Case, *, expected_version: int) -> None: ...


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _case_values(case: Case) -> dict:
    return {
        "workspace_id": str(case.workspace_id),
        "title": case.title,
        "severity": case.severity.value,
        "status": case.status.value,
        "summary": case.summary,
        "evidence_ids_json": [str(value) for value in case.evidence_ids],
        "hypothesis_ids_json": [str(value) for value in case.hypothesis_ids],
        "action_ids_json": [str(value) for value in case.action_ids],
        "opened_at": case.opened_at,
        "updated_at": case.updated_at,
        "version": case.version,
    }


def _row_to_case(row: CaseRow) -> Case:
    return Case.model_validate(
        {
            "id": row.case_id,
            "workspace_id": row.workspace_id,
            "title": row.title,
            "severity": row.severity,
            "status": row.status,
            "summary": row.summary,
            "evidence_ids": tuple(row.evidence_ids_json or ()),
            "hypothesis_ids": tuple(row.hypothesis_ids_json or ()),
            "action_ids": tuple(row.action_ids_json or ()),
            "opened_at": _utc(row.opened_at),
            "updated_at": _utc(row.updated_at),
            "version": row.version,
        }
    )


class SqlCaseRepository:
    """Short-session Case repository for SQLite and PostgreSQL."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(self, case: Case) -> None:
        try:
            async with self._session_factory() as session, session.begin():
                await self.create_in_session(session, case)
        except IntegrityError as exc:
            raise DuplicateEntityError(f"Case already exists: {case.id}") from exc

    async def get(self, workspace_id: WorkspaceId, case_id: CaseId) -> Case | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(CaseRow).where(
                    CaseRow.workspace_id == str(workspace_id),
                    CaseRow.case_id == str(case_id),
                )
            )
            return _row_to_case(row) if row is not None else None

    async def list(
        self,
        workspace_id: WorkspaceId,
        *,
        status: CaseStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[Case, ...]:
        if limit < 1 or limit > 500:
            raise ValueError("Case list limit must be between 1 and 500")
        if offset < 0:
            raise ValueError("Case list offset cannot be negative")
        statement = select(CaseRow).where(CaseRow.workspace_id == str(workspace_id))
        if status is not None:
            statement = statement.where(CaseRow.status == status.value)
        statement = statement.order_by(
            CaseRow.updated_at.desc(),
            CaseRow.case_id.asc(),
        ).limit(limit).offset(offset)
        async with self._session_factory() as session:
            rows = (await session.scalars(statement)).all()
            return tuple(_row_to_case(row) for row in rows)

    async def save(self, case: Case, *, expected_version: int) -> None:
        async with self._session_factory() as session, session.begin():
            await self.save_in_session(session, case, expected_version=expected_version)

    @staticmethod
    async def create_in_session(session: AsyncSession, case: Case) -> None:
        session.add(CaseRow(case_id=str(case.id), **_case_values(case)))
        await session.flush()

    @staticmethod
    async def save_in_session(
        session: AsyncSession,
        case: Case,
        *,
        expected_version: int,
    ) -> CaseStatus:
        if expected_version < 1:
            raise ValueError("expected_version must be positive")
        if case.version != expected_version + 1:
            raise ValueError("Saved Case version must equal expected_version + 1")

        current = (
            await session.execute(
                select(CaseRow.status, CaseRow.version).where(
                    CaseRow.workspace_id == str(case.workspace_id),
                    CaseRow.case_id == str(case.id),
                )
            )
        ).one_or_none()
        if current is None:
            raise EntityNotFoundError(f"Case not found: {case.id}")
        if current.version != expected_version:
            raise OptimisticConcurrencyError(
                f"Case {case.id} expected version {expected_version}, found {current.version}"
            )

        result = await session.execute(
            update(CaseRow)
            .where(
                CaseRow.workspace_id == str(case.workspace_id),
                CaseRow.case_id == str(case.id),
                CaseRow.version == expected_version,
            )
            .values(**_case_values(case))
        )
        if result.rowcount != 1:
            raise OptimisticConcurrencyError(
                f"Case {case.id} changed while saving version {case.version}"
            )
        return CaseStatus(current.status)
