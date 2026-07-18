"""SQLite-backed Case Repository and optimistic-concurrency contracts."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.commerce.domain.enums import CaseSeverity, CaseStatus
from app.commerce.domain.ids import WorkspaceId
from app.commerce.domain.models import Case
from app.commerce.persistence.repositories import (
    DuplicateEntityError,
    OptimisticConcurrencyError,
    SqlCaseRepository,
)
from app.commerce.persistence.schema import create_commerce_schema


def _case(workspace_id: WorkspaceId, *, title: str = "Delivery anomaly") -> Case:
    now = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
    return Case(
        workspace_id=workspace_id,
        title=title,
        severity=CaseSeverity.HIGH,
        opened_at=now,
        updated_at=now,
    )


async def _repository(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'commerce.db'}")
    await create_commerce_schema(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, SqlCaseRepository(factory)


@pytest.mark.anyio
async def test_case_repository_round_trips_domain_model_and_workspace_scope(tmp_path):
    engine, repository = await _repository(tmp_path)
    workspace_id = WorkspaceId.new()
    case = _case(workspace_id)

    await repository.create(case)

    assert await repository.get(workspace_id, case.id) == case
    assert await repository.get(WorkspaceId.new(), case.id) is None
    assert await repository.list(workspace_id) == (case,)
    await engine.dispose()


@pytest.mark.anyio
async def test_case_repository_rejects_duplicate_create(tmp_path):
    engine, repository = await _repository(tmp_path)
    case = _case(WorkspaceId.new())
    await repository.create(case)

    with pytest.raises(DuplicateEntityError):
        await repository.create(case)

    await engine.dispose()


@pytest.mark.anyio
async def test_case_save_uses_optimistic_concurrency_and_preserves_winner(tmp_path):
    engine, repository = await _repository(tmp_path)
    workspace_id = WorkspaceId.new()
    original = _case(workspace_id)
    await repository.create(original)
    triaged = original.transition_to(CaseStatus.TRIAGED)

    await repository.save(triaged, expected_version=1)

    with pytest.raises(OptimisticConcurrencyError):
        await repository.save(
            original.model_copy(update={"summary": "stale writer", "version": 2}),
            expected_version=1,
        )

    stored = await repository.get(workspace_id, original.id)
    assert stored == triaged
    await engine.dispose()


@pytest.mark.anyio
async def test_case_list_filters_by_status_and_orders_latest_first(tmp_path):
    engine, repository = await _repository(tmp_path)
    workspace_id = WorkspaceId.new()
    first = _case(workspace_id, title="First")
    second = _case(workspace_id, title="Second").model_copy(
        update={"updated_at": datetime(2026, 7, 18, 13, 0, tzinfo=UTC)}
    )
    await repository.create(first)
    await repository.create(second)
    await repository.save(
        first.transition_to(
            CaseStatus.TRIAGED,
            occurred_at=datetime(2026, 7, 18, 12, 30, tzinfo=UTC),
        ),
        expected_version=1,
    )

    triaged = await repository.list(workspace_id, status=CaseStatus.TRIAGED)
    all_cases = await repository.list(workspace_id)

    assert tuple(case.title for case in triaged) == ("First",)
    assert tuple(case.title for case in all_cases) == ("Second", "First")
    await engine.dispose()
