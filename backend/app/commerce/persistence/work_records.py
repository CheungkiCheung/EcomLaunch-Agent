"""Append-only Evidence and versioned Hypothesis repositories."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.commerce.domain.ids import CaseId, EvidenceId, HypothesisId, WorkspaceId
from app.commerce.domain.models import Evidence, Hypothesis
from app.commerce.persistence.models import EvidenceRow, HypothesisRow


class ImmutableRecordConflictError(ValueError):
    """An immutable Evidence or Hypothesis version ID was reused with new data."""


class HypothesisVersionConflictError(RuntimeError):
    """A Hypothesis version was appended out of sequence."""


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _evidence_values(evidence: Evidence) -> dict[str, object]:
    return {
        "evidence_id": str(evidence.id),
        "workspace_id": str(evidence.workspace_id),
        "case_id": str(evidence.case_id),
        "summary": evidence.summary,
        "relation": evidence.relation.value,
        "semantic_status": evidence.semantic_status.value,
        "confidence": evidence.confidence,
        "fact_ids_json": [str(value) for value in evidence.fact_ids],
        "metric_observation_ids_json": [
            str(value) for value in evidence.metric_observation_ids
        ],
    }


def _row_to_evidence(row: EvidenceRow) -> Evidence:
    return Evidence.model_validate(
        {
            "id": row.evidence_id,
            "workspace_id": row.workspace_id,
            "case_id": row.case_id,
            "summary": row.summary,
            "relation": row.relation,
            "semantic_status": row.semantic_status,
            "confidence": row.confidence,
            "fact_ids": tuple(row.fact_ids_json or ()),
            "metric_observation_ids": tuple(row.metric_observation_ids_json or ()),
        }
    )


def _hypothesis_values(hypothesis: Hypothesis) -> dict[str, object]:
    return {
        "hypothesis_id": str(hypothesis.id),
        "version": hypothesis.version,
        "workspace_id": str(hypothesis.workspace_id),
        "case_id": str(hypothesis.case_id),
        "statement": hypothesis.statement,
        "status": hypothesis.status.value,
        "confidence": hypothesis.confidence,
        "supporting_evidence_ids_json": [
            str(value) for value in hypothesis.supporting_evidence_ids
        ],
        "contradicting_evidence_ids_json": [
            str(value) for value in hypothesis.contradicting_evidence_ids
        ],
    }


def _row_to_hypothesis(row: HypothesisRow) -> Hypothesis:
    return Hypothesis.model_validate(
        {
            "id": row.hypothesis_id,
            "version": row.version,
            "workspace_id": row.workspace_id,
            "case_id": row.case_id,
            "statement": row.statement,
            "status": row.status,
            "confidence": row.confidence,
            "supporting_evidence_ids": tuple(row.supporting_evidence_ids_json or ()),
            "contradicting_evidence_ids": tuple(
                row.contradicting_evidence_ids_json or ()
            ),
        }
    )


@runtime_checkable
class EvidenceRepository(Protocol):
    async def append(self, evidence: Evidence) -> Evidence: ...

    async def get(
        self,
        workspace_id: WorkspaceId,
        evidence_id: EvidenceId,
    ) -> Evidence | None: ...

    async def list_case(
        self,
        workspace_id: WorkspaceId,
        case_id: CaseId,
    ) -> tuple[Evidence, ...]: ...


class SqlEvidenceRepository:
    """Short-session repository for immutable Evidence records."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def append(self, evidence: Evidence) -> Evidence:
        try:
            async with self._session_factory() as session, session.begin():
                return await self.append_in_session(session, evidence)
        except IntegrityError as exc:
            # A concurrent writer may have committed the same immutable record.
            async with self._session_factory() as session:
                row = await session.get(EvidenceRow, str(evidence.id))
            if row is not None and _row_to_evidence(row) == evidence:
                return evidence
            raise ImmutableRecordConflictError(
                f"Evidence ID {evidence.id} already exists with different immutable data"
            ) from exc

    async def get(
        self,
        workspace_id: WorkspaceId,
        evidence_id: EvidenceId,
    ) -> Evidence | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(EvidenceRow).where(
                    EvidenceRow.workspace_id == str(workspace_id),
                    EvidenceRow.evidence_id == str(evidence_id),
                )
            )
            return _row_to_evidence(row) if row is not None else None

    async def list_case(
        self,
        workspace_id: WorkspaceId,
        case_id: CaseId,
    ) -> tuple[Evidence, ...]:
        statement = (
            select(EvidenceRow)
            .where(
                EvidenceRow.workspace_id == str(workspace_id),
                EvidenceRow.case_id == str(case_id),
            )
            .order_by(EvidenceRow.recorded_at.asc(), EvidenceRow.evidence_id.asc())
        )
        async with self._session_factory() as session:
            rows = (await session.scalars(statement)).all()
            return tuple(_row_to_evidence(row) for row in rows)

    @staticmethod
    async def append_in_session(
        session: AsyncSession,
        evidence: Evidence,
    ) -> Evidence:
        existing_row = await session.get(EvidenceRow, str(evidence.id))
        if existing_row is not None:
            existing = _row_to_evidence(existing_row)
            if existing != evidence:
                raise ImmutableRecordConflictError(
                    f"Evidence ID {evidence.id} already exists with different immutable data"
                )
            return existing

        row = EvidenceRow(**_evidence_values(evidence))
        session.add(row)
        await session.flush()
        return _row_to_evidence(row)


@runtime_checkable
class HypothesisRepository(Protocol):
    async def append_version(self, hypothesis: Hypothesis) -> Hypothesis: ...

    async def list_versions(
        self,
        workspace_id: WorkspaceId,
        hypothesis_id: HypothesisId,
    ) -> tuple[Hypothesis, ...]: ...

    async def get_latest(
        self,
        workspace_id: WorkspaceId,
        hypothesis_id: HypothesisId,
    ) -> Hypothesis | None: ...


class SqlHypothesisRepository:
    """Short-session repository enforcing contiguous immutable versions."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def append_version(self, hypothesis: Hypothesis) -> Hypothesis:
        try:
            async with self._session_factory() as session, session.begin():
                return await self.append_version_in_session(session, hypothesis)
        except IntegrityError as exc:
            async with self._session_factory() as session:
                row = await session.get(
                    HypothesisRow,
                    (str(hypothesis.id), hypothesis.version),
                )
                current = await session.scalar(
                    select(func.max(HypothesisRow.version)).where(
                        HypothesisRow.workspace_id == str(hypothesis.workspace_id),
                        HypothesisRow.hypothesis_id == str(hypothesis.id),
                    )
                )
            if row is not None and _row_to_hypothesis(row) == hypothesis:
                return hypothesis
            if row is None:
                expected = int(current or 0) + 1
                raise HypothesisVersionConflictError(
                    f"Hypothesis {hypothesis.id} expected version {expected}"
                ) from exc
            raise ImmutableRecordConflictError(
                f"Hypothesis {hypothesis.id} version {hypothesis.version} already exists with different immutable data"
            ) from exc

    async def list_versions(
        self,
        workspace_id: WorkspaceId,
        hypothesis_id: HypothesisId,
    ) -> tuple[Hypothesis, ...]:
        statement = (
            select(HypothesisRow)
            .where(
                HypothesisRow.workspace_id == str(workspace_id),
                HypothesisRow.hypothesis_id == str(hypothesis_id),
            )
            .order_by(HypothesisRow.version.asc())
        )
        async with self._session_factory() as session:
            rows = (await session.scalars(statement)).all()
            return tuple(_row_to_hypothesis(row) for row in rows)

    async def get_latest(
        self,
        workspace_id: WorkspaceId,
        hypothesis_id: HypothesisId,
    ) -> Hypothesis | None:
        statement = (
            select(HypothesisRow)
            .where(
                HypothesisRow.workspace_id == str(workspace_id),
                HypothesisRow.hypothesis_id == str(hypothesis_id),
            )
            .order_by(HypothesisRow.version.desc())
            .limit(1)
        )
        async with self._session_factory() as session:
            row = await session.scalar(statement)
            return _row_to_hypothesis(row) if row is not None else None

    @staticmethod
    async def append_version_in_session(
        session: AsyncSession,
        hypothesis: Hypothesis,
    ) -> Hypothesis:
        existing_row = await session.get(
            HypothesisRow,
            (str(hypothesis.id), hypothesis.version),
        )
        if existing_row is not None:
            existing = _row_to_hypothesis(existing_row)
            if existing != hypothesis:
                raise ImmutableRecordConflictError(
                    f"Hypothesis {hypothesis.id} version {hypothesis.version} already exists with different immutable data"
                )
            return existing

        current = await session.scalar(
            select(func.max(HypothesisRow.version)).where(
                HypothesisRow.workspace_id == str(hypothesis.workspace_id),
                HypothesisRow.hypothesis_id == str(hypothesis.id),
            )
        )
        expected = int(current or 0) + 1
        if hypothesis.version != expected:
            raise HypothesisVersionConflictError(
                f"Hypothesis {hypothesis.id} expected version {expected}, got {hypothesis.version}"
            )

        row = HypothesisRow(**_hypothesis_values(hypothesis))
        session.add(row)
        await session.flush()
        return _row_to_hypothesis(row)
