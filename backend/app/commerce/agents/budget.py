"""Concurrency-safe layered budget accounting for Commerce Goal Loops."""

from __future__ import annotations

import asyncio
from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from app.commerce.agents.contracts import AgentBudgetLimit
from app.commerce.domain.models import CommerceModel


class BudgetDimension(StrEnum):
    ITERATIONS = "iterations"
    TOOL_CALLS = "tool_calls"
    PATH_AGENTS = "path_agents"
    TOKENS = "tokens"
    WALL_TIME_SECONDS = "wall_time_seconds"
    MODEL_ESCALATIONS = "model_escalations"
    VERIFICATION_REPAIRS = "verification_repairs"
    REPEATED_ACTIONS = "repeated_actions"
    CONSECUTIVE_NO_NEW_EVIDENCE = "consecutive_no_new_evidence"


class BudgetDelta(CommerceModel):
    iterations: int = Field(default=0, ge=0)
    tool_calls: int = Field(default=0, ge=0)
    path_agents: int = Field(default=0, ge=0)
    tokens: int = Field(default=0, ge=0)
    wall_time_seconds: float = Field(default=0.0, ge=0)
    model_escalations: int = Field(default=0, ge=0)
    verification_repairs: int = Field(default=0, ge=0)
    repeated_actions: int = Field(default=0, ge=0)
    consecutive_no_new_evidence: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def require_consumption(self) -> Self:
        if not any(value > 0 for value in self.model_dump().values()):
            raise ValueError("BudgetDelta must consume at least one dimension")
        return self


class BudgetUsage(CommerceModel):
    iterations: int = Field(default=0, ge=0)
    tool_calls: int = Field(default=0, ge=0)
    path_agents: int = Field(default=0, ge=0)
    tokens: int = Field(default=0, ge=0)
    wall_time_seconds: float = Field(default=0.0, ge=0)
    model_escalations: int = Field(default=0, ge=0)
    verification_repairs: int = Field(default=0, ge=0)
    repeated_actions: int = Field(default=0, ge=0)
    consecutive_no_new_evidence: int = Field(default=0, ge=0)


class BudgetSnapshot(CommerceModel):
    limit: AgentBudgetLimit
    usage: BudgetUsage


class BudgetExceededError(RuntimeError):
    def __init__(
        self,
        dimension: BudgetDimension,
        *,
        attempted: int | float,
        limit: int | float,
    ) -> None:
        super().__init__(
            f"Budget exceeded for {dimension.value}: attempted {attempted}, limit {limit}"
        )
        self.dimension = dimension
        self.attempted = attempted
        self.limit = limit


_LIMIT_FIELDS = {
    BudgetDimension.ITERATIONS: "max_iterations",
    BudgetDimension.TOOL_CALLS: "max_tool_calls",
    BudgetDimension.PATH_AGENTS: "max_path_agents",
    BudgetDimension.TOKENS: "max_tokens",
    BudgetDimension.WALL_TIME_SECONDS: "max_wall_time_seconds",
    BudgetDimension.MODEL_ESCALATIONS: "max_model_escalations",
    BudgetDimension.VERIFICATION_REPAIRS: "max_verification_repairs",
    BudgetDimension.REPEATED_ACTIONS: "max_repeated_actions",
    BudgetDimension.CONSECUTIVE_NO_NEW_EVIDENCE: "max_consecutive_no_new_evidence",
}


class BudgetManager:
    """Check all dimensions before committing one immutable usage snapshot."""

    def __init__(self, limit: AgentBudgetLimit) -> None:
        self._snapshot = BudgetSnapshot(limit=limit, usage=BudgetUsage())
        self._lock = asyncio.Lock()

    @property
    def snapshot(self) -> BudgetSnapshot:
        return self._snapshot

    async def consume(self, delta: BudgetDelta) -> BudgetSnapshot:
        async with self._lock:
            usage_values = self._snapshot.usage.model_dump()
            delta_values = delta.model_dump()
            candidate = {
                key: usage_values[key] + delta_values[key]
                for key in usage_values
            }
            for dimension, limit_field in _LIMIT_FIELDS.items():
                attempted = candidate[dimension.value]
                allowed = getattr(self._snapshot.limit, limit_field)
                if attempted > allowed:
                    raise BudgetExceededError(
                        dimension,
                        attempted=attempted,
                        limit=allowed,
                    )
            self._snapshot = BudgetSnapshot(
                limit=self._snapshot.limit,
                usage=BudgetUsage.model_validate(candidate),
            )
            return self._snapshot
