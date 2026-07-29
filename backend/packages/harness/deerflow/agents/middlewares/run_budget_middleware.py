"""Bound one lead-agent request by model calls, tokens, and wall time."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any, override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelCallResult, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.runtime import Runtime

from deerflow.agents.middlewares.tool_call_metadata import clone_ai_message_with_tool_calls
from deerflow.config.agent_run_budget_config import AgentRunBudgetConfig

RUN_BUDGET_CONTEXT_KEY = "__deerflow_agent_run_budget"
TERMINAL_DELIVERY_TOOLS = frozenset({"present_files"})
FINALIZATION_MESSAGE = """Execution budget finalization:
- This is the final model response available before the hard execution limit.
- Do not call more research or drafting tools.
- Return a concise result from the evidence already collected.
- Clearly mark failures, uncertainty, unsupported claims, and missing evidence.
- If you are the lead agent and final files already exist, `present_files` is the only allowed terminal tool."""


def _current_turn_messages(messages: list[Any]) -> list[Any]:
    """Return messages belonging to the latest user request only."""
    for index in range(len(messages) - 1, -1, -1):
        if isinstance(messages[index], HumanMessage):
            return messages[index + 1 :]
    return messages


def _message_total_tokens(message: Any) -> int:
    usage = getattr(message, "usage_metadata", None)
    if not isinstance(usage, dict):
        return 0
    value = usage.get("total_tokens", 0)
    return value if isinstance(value, int) and value > 0 else 0


class RunBudgetMiddleware(AgentMiddleware[AgentState]):
    """Prevent an agent run from repeatedly expanding after useful work exists."""

    def __init__(self, config: AgentRunBudgetConfig):
        super().__init__()
        self.config = config

    def _initialize(self, runtime: Runtime) -> None:
        context = getattr(runtime, "context", None)
        if not isinstance(context, dict):
            return

        started_at = time.monotonic()
        context[RUN_BUDGET_CONTEXT_KEY] = {
            "config": self.config.model_dump(),
            "started_at_monotonic": started_at,
            "deadline_monotonic": started_at + self.config.max_execution_seconds,
            "subagent_calls_started": 0,
            "subagent_types_started": set(),
        }

    @override
    def before_agent(self, state: AgentState, runtime: Runtime) -> dict | None:
        self._initialize(runtime)
        return None

    @override
    async def abefore_agent(self, state: AgentState, runtime: Runtime) -> dict | None:
        self._initialize(runtime)
        return None

    def _stop_reason(self, messages: list[Any], runtime: Runtime) -> str | None:
        turn_messages = _current_turn_messages(messages)
        lead_model_calls = sum(isinstance(message, AIMessage) for message in turn_messages)
        if lead_model_calls >= self.config.max_lead_model_calls:
            return f"主智能体模型调用上限 {self.config.max_lead_model_calls} 次"

        total_tokens = sum(_message_total_tokens(message) for message in turn_messages)
        if total_tokens >= self.config.max_total_tokens:
            return f"Token 上限 {self.config.max_total_tokens}"

        context = getattr(runtime, "context", None)
        if isinstance(context, dict):
            budget_state = context.get(RUN_BUDGET_CONTEXT_KEY)
            if isinstance(budget_state, dict):
                deadline = budget_state.get("deadline_monotonic")
                if isinstance(deadline, (int, float)) and time.monotonic() >= deadline:
                    return f"时间上限 {self.config.max_execution_seconds} 秒"

        return None

    def _finalization_reason(self, messages: list[Any], runtime: Runtime) -> str | None:
        turn_messages = _current_turn_messages(messages)
        lead_model_calls = sum(isinstance(message, AIMessage) for message in turn_messages)
        if lead_model_calls >= self.config.max_lead_model_calls - 1:
            return "model_calls"

        total_tokens = sum(_message_total_tokens(message) for message in turn_messages)
        token_warning_threshold = max(1, int(self.config.max_total_tokens * 0.8))
        if total_tokens >= token_warning_threshold:
            return "tokens"

        context = getattr(runtime, "context", None)
        if isinstance(context, dict):
            budget_state = context.get(RUN_BUDGET_CONTEXT_KEY)
            if isinstance(budget_state, dict):
                deadline = budget_state.get("deadline_monotonic")
                if isinstance(deadline, (int, float)):
                    remaining = deadline - time.monotonic()
                    warning_window = max(5, min(30, self.config.max_execution_seconds // 5))
                    if remaining <= warning_window:
                        return "wall_time"

        return None

    def _augment_request(self, request: ModelRequest) -> ModelRequest:
        if self._finalization_reason(request.messages, request.runtime) is None:
            return request
        messages = [
            *request.messages,
            HumanMessage(
                content=FINALIZATION_MESSAGE,
                name="run_budget_finalization",
                additional_kwargs={"hide_from_ui": True},
            ),
        ]
        return request.override(messages=messages)

    def _apply(self, state: AgentState, runtime: Runtime) -> dict | None:
        messages = state.get("messages", [])
        if not messages:
            return None

        last = messages[-1]
        if not isinstance(last, AIMessage):
            return None

        # A completed text response is already terminal and useful. Budgets stop
        # further work; they do not overwrite an answer after it has been written.
        tool_calls = list(last.tool_calls or [])
        if not tool_calls:
            return None

        reason = self._stop_reason(messages, runtime)
        if reason is None:
            return None

        terminal_calls = [tool_call for tool_call in tool_calls if tool_call.get("name") in TERMINAL_DELIVERY_TOOLS]
        if terminal_calls:
            if len(terminal_calls) == len(tool_calls):
                return None
            return {"messages": [clone_ai_message_with_tool_calls(last, terminal_calls)]}

        existing_content = last.content.strip() if isinstance(last.content, str) else ""
        stop_content = f"{self.config.stop_message}\n\n停止原因：{reason}。"
        if existing_content:
            stop_content = f"{existing_content}\n\n{stop_content}"

        stopped = clone_ai_message_with_tool_calls(last, [], content=stop_content)
        return {"messages": [stopped]}

    @override
    def after_model(self, state: AgentState, runtime: Runtime) -> dict | None:
        return self._apply(state, runtime)

    @override
    async def aafter_model(self, state: AgentState, runtime: Runtime) -> dict | None:
        return self._apply(state, runtime)

    @override
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelCallResult:
        return handler(self._augment_request(request))

    @override
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelCallResult:
        return await handler(self._augment_request(request))
