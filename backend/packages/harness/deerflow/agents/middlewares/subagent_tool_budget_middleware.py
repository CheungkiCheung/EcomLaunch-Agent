"""Force a Subagent to synthesize once its delegated tool-round budget is spent."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import (
    ModelCallResult,
    ModelRequest,
    ModelResponse,
)
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.runtime import Runtime

from deerflow.agents.middlewares.tool_call_metadata import clone_ai_message_with_tool_calls

_STOP_MESSAGE = "Subagent 的确定性 Tool 预算已经用完。不要再调用任何 Tool；请立即综合已获得的事实、证据引用、反证、未知项和数据限制，按照 ContextPacket 要求的输出结构给出最终结果。证据不足时明确返回 unknown 或 not_verified。"


class SubagentToolBudgetMiddleware(AgentMiddleware[AgentState]):
    """Remove tools after a fixed number of model→tool execution rounds.

    One round is one prior ``AIMessage`` containing one or more tool calls.
    Parallel tool calls in that message consume one round, which rewards useful
    fan-out without allowing an open-ended ReAct loop. The middleware runs at
    the next model boundary, after matching ToolMessages exist, so provider
    tool-call pairing remains valid.
    """

    def __init__(
        self,
        *,
        max_tool_rounds: int | None = None,
        max_tool_calls: int | None = None,
    ) -> None:
        super().__init__()
        if max_tool_rounds is None and max_tool_calls is None:
            raise ValueError("at least one Tool budget is required")
        if max_tool_rounds is not None and max_tool_rounds < 1:
            raise ValueError("max_tool_rounds must be positive")
        if max_tool_calls is not None and max_tool_calls < 1:
            raise ValueError("max_tool_calls must be positive")
        self.max_tool_rounds = max_tool_rounds
        self.max_tool_calls = max_tool_calls

    @staticmethod
    def _completed_tool_rounds(messages: Sequence[BaseMessage]) -> int:
        return sum(isinstance(message, AIMessage) and bool(message.tool_calls) for message in messages)

    @staticmethod
    def _completed_tool_calls(messages: Sequence[BaseMessage]) -> int:
        return sum(len(message.tool_calls or ()) for message in messages if isinstance(message, AIMessage))

    def _budget_exhausted(self, messages: Sequence[BaseMessage]) -> tuple[bool, str | None, int | None]:
        rounds = self._completed_tool_rounds(messages)
        if self.max_tool_rounds is not None and rounds >= self.max_tool_rounds:
            return True, "tool_rounds", self.max_tool_rounds
        calls = self._completed_tool_calls(messages)
        if self.max_tool_calls is not None and calls >= self.max_tool_calls:
            return True, "tool_calls", self.max_tool_calls
        return False, None, None

    def _apply_budget(self, request: ModelRequest) -> ModelRequest:
        exhausted, budget_type, budget_limit = self._budget_exhausted(request.messages)
        if not exhausted:
            return request

        messages = list(request.messages)
        already_injected = bool(messages and isinstance(messages[-1], HumanMessage) and messages[-1].name == "subagent_budget_stop")
        if not already_injected:
            messages.append(
                HumanMessage(
                    content=_STOP_MESSAGE,
                    name="subagent_budget_stop",
                    additional_kwargs={
                        "hide_from_ui": True,
                        "budget_type": budget_type,
                        "budget_limit": budget_limit,
                    },
                )
            )
        return request.override(messages=messages, tools=[])

    def _truncate_excess_calls(self, state: AgentState) -> dict | None:
        """Keep a provider's current parallel batch within the total call cap."""
        if self.max_tool_calls is None:
            return None
        messages = state.get("messages", [])
        if not messages:
            return None
        last_message = messages[-1]
        if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
            return None
        prior_messages = messages[:-1]
        prior_calls = self._completed_tool_calls(prior_messages)
        remaining = self.max_tool_calls - prior_calls
        if remaining <= 0:
            return {"messages": [clone_ai_message_with_tool_calls(last_message, [])]}
        if len(last_message.tool_calls) <= remaining:
            return None
        kept = list(last_message.tool_calls[:remaining])
        return {"messages": [clone_ai_message_with_tool_calls(last_message, kept)]}

    @override
    def after_model(self, state: AgentState, runtime: Runtime) -> dict | None:
        return self._truncate_excess_calls(state)

    @override
    async def aafter_model(self, state: AgentState, runtime: Runtime) -> dict | None:
        return self._truncate_excess_calls(state)

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
