"""Atomic layered budget contracts for Commerce Goal Loops."""

from __future__ import annotations

import asyncio

import pytest

from app.commerce.agents.budget import (
    BudgetDelta,
    BudgetDimension,
    BudgetExceededError,
    BudgetManager,
)
from app.commerce.agents.contracts import AgentBudgetLimit


@pytest.mark.anyio
async def test_budget_consumption_is_atomic_under_concurrency():
    manager = BudgetManager(AgentBudgetLimit(max_tool_calls=10))

    results = await asyncio.gather(
        *(manager.consume(BudgetDelta(tool_calls=1)) for _ in range(20)),
        return_exceptions=True,
    )

    successes = [result for result in results if not isinstance(result, Exception)]
    failures = [result for result in results if isinstance(result, BudgetExceededError)]
    assert len(successes) == 10
    assert len(failures) == 10
    assert all(error.dimension is BudgetDimension.TOOL_CALLS for error in failures)
    assert manager.snapshot.usage.tool_calls == 10


@pytest.mark.anyio
async def test_budget_rejects_multi_dimension_delta_without_partial_consumption():
    manager = BudgetManager(
        AgentBudgetLimit(max_iterations=2, max_tokens=100)
    )
    await manager.consume(BudgetDelta(iterations=2, tokens=50))

    with pytest.raises(BudgetExceededError) as error:
        await manager.consume(BudgetDelta(iterations=1, tokens=50))

    assert error.value.dimension is BudgetDimension.ITERATIONS
    assert manager.snapshot.usage.iterations == 2
    assert manager.snapshot.usage.tokens == 50
