"""Deterministic tool-call budget for bounded subagent runs."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelCallResult, ModelRequest, ModelResponse
from langchain_core.messages import HumanMessage, ToolMessage

logger = logging.getLogger(__name__)

_BUDGET_NOTICE = (
    "[TOOL BUDGET EXHAUSTED] 工具调用预算已经用完。不得继续调用工具；"
    "请立即基于已经获得的证据返回简洁结果，并明确仍未解决的限制。"
)


class SubagentToolCallBudgetMiddleware(AgentMiddleware[AgentState]):
    """Remove tool schemas after a subagent reaches its configured budget.

    Prompt-only budgets are advisory and can be ignored by a model. This
    middleware counts completed tool calls in the current subagent history and
    removes all tool schemas from the next model request once the hard budget is
    reached. The final model turn can then only synthesize collected evidence.
    """

    def __init__(self, max_tool_calls: int):
        super().__init__()
        if max_tool_calls < 1:
            raise ValueError("max_tool_calls must be at least 1")
        self.max_tool_calls = max_tool_calls

    @staticmethod
    def _completed_tool_calls(request: ModelRequest) -> int:
        return sum(isinstance(message, ToolMessage) for message in request.messages)

    def _apply_budget(self, request: ModelRequest) -> ModelRequest:
        completed = self._completed_tool_calls(request)
        if completed < self.max_tool_calls or not request.tools:
            return request

        messages = list(request.messages)
        if not (
            messages
            and isinstance(messages[-1], HumanMessage)
            and messages[-1].content == _BUDGET_NOTICE
        ):
            messages.append(HumanMessage(content=_BUDGET_NOTICE))

        logger.info(
            "Subagent tool-call budget exhausted: completed=%s limit=%s",
            completed,
            self.max_tool_calls,
        )
        return request.override(messages=messages, tools=[])

    @override
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelCallResult:
        return handler(self._apply_budget(request))

    @override
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelCallResult:
        return await handler(self._apply_budget(request))
