"""Bound Parent-side direct work before forcing durable delegation/synthesis."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Collection, Sequence
from typing import Any, override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import (
    ModelCallResult,
    ModelRequest,
    ModelResponse,
)
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.runtime import Runtime

from deerflow.agents.middlewares.subagent_requirement_middleware import (
    _CONTROL_TOOL_NAMES,
    _completed_subagent_tasks,
    _current_run_messages,
)
from deerflow.agents.middlewares.tool_call_metadata import (
    clone_ai_message_with_tool_calls,
)

_DELEGATE_MESSAGE = (
    "Parent 的直接工作 Tool 预算已经用完。不要继续在 Parent 重复扫描或计算；"
    "现在只使用 Durable Task 控制工具，先完成最小分析任务，再用带 "
    'source_refs=["task:<task_id>"] 的 fresh-context verifier 独立核验，'
    "最后一次 wait_task 后综合。派工预算不得超过 Profile 默认上限。"
)

_SYNTHESIZE_MESSAGE = (
    "Parent 的直接工作 Tool 预算已经用完，必需的 Durable Subagent 结果也已满足。"
    "不要再调用任何 Tool；立即综合已获得的事实、支持证据、反证、未知项和数据限制。"
    "只能使用相关性或阶段定位措辞，不得把观察性变化写成因果结论。"
)


def _deep_merge_dicts(base: dict[str, Any] | None, override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base or {})
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def _required_tool_model_settings(request: ModelRequest) -> tuple[dict[str, Any], str]:
    settings = (
        dict(request.model_settings)
        if isinstance(request.model_settings, dict)
        else {}
    )
    model_extra_body = getattr(request.model, "extra_body", None)
    invocation_extra_body = settings.get("extra_body")
    extra_body = _deep_merge_dicts(
        model_extra_body if isinstance(model_extra_body, dict) else None,
        invocation_extra_body if isinstance(invocation_extra_body, dict) else {},
    )
    thinking = extra_body.get("thinking")
    if isinstance(thinking, dict) and thinking.get("type") == "enabled":
        settings["extra_body"] = _deep_merge_dicts(
            extra_body,
            {"thinking": {"type": "disabled"}},
        )
        return settings, "tool_control_without_thinking"
    return settings, "required_tool_choice"


class ParentDirectToolBudgetMiddleware(AgentMiddleware[AgentState]):
    """Switch a complex Parent from direct work to delegation, then synthesis.

    Direct deterministic tools are useful for initial capability checks and a
    small number of decisive calculations.  They become counterproductive when
    the Parent keeps scanning after enough evidence exists.  Once the configured
    direct-work budget is exhausted this middleware keeps only durable control
    tools until required Subagent profiles complete; afterwards it removes all
    tools and asks for bounded synthesis.
    """

    def __init__(
        self,
        *,
        max_direct_tool_calls: int | None = None,
        max_direct_tool_rounds: int | None = None,
        required_subagent_types: Collection[str] = (),
    ) -> None:
        super().__init__()
        if max_direct_tool_calls is None and max_direct_tool_rounds is None:
            raise ValueError("at least one Parent direct Tool budget is required")
        if max_direct_tool_calls is not None and max_direct_tool_calls < 1:
            raise ValueError("max_direct_tool_calls must be positive")
        if max_direct_tool_rounds is not None and max_direct_tool_rounds < 1:
            raise ValueError("max_direct_tool_rounds must be positive")
        self.max_direct_tool_calls = max_direct_tool_calls
        self.max_direct_tool_rounds = max_direct_tool_rounds
        self.required_subagent_types = tuple(
            dict.fromkeys(
                profile.strip()
                for profile in required_subagent_types
                if isinstance(profile, str) and profile.strip()
            )
        )

    @staticmethod
    def _direct_tool_calls(messages: Sequence[BaseMessage]) -> int:
        return sum(
            1
            for message in messages
            if isinstance(message, AIMessage)
            for call in message.tool_calls or ()
            if call.get("name") not in _CONTROL_TOOL_NAMES
        )

    @staticmethod
    def _direct_tool_rounds(messages: Sequence[BaseMessage]) -> int:
        return sum(
            isinstance(message, AIMessage)
            and any(
                call.get("name") not in _CONTROL_TOOL_NAMES
                for call in message.tool_calls or ()
            )
            for message in messages
        )

    def _budget_exhausted(self, messages: Sequence[BaseMessage]) -> bool:
        if (
            self.max_direct_tool_calls is not None
            and self._direct_tool_calls(messages) >= self.max_direct_tool_calls
        ):
            return True
        return bool(
            self.max_direct_tool_rounds is not None
            and self._direct_tool_rounds(messages)
            >= self.max_direct_tool_rounds
        )

    def _missing_required_profiles(
        self,
        messages: Sequence[BaseMessage],
    ) -> tuple[str, ...]:
        completed = _completed_subagent_tasks(messages)

        def satisfied(profile: str) -> bool:
            candidates = [
                task
                for task in completed
                if task.get("subagent_type") == profile
            ]
            if profile != "verifier":
                return bool(candidates)
            return any(
                any(
                    isinstance(source_ref, str)
                    and source_ref.startswith("task:")
                    and bool(source_ref.removeprefix("task:").strip())
                    for source_ref in task.get("source_refs") or ()
                )
                for task in candidates
            )

        return tuple(
            profile
            for profile in self.required_subagent_types
            if not satisfied(profile)
        )

    @staticmethod
    def _tool_name(tool: object) -> str | None:
        name = getattr(tool, "name", None)
        return name if isinstance(name, str) else None

    def _apply_budget(self, request: ModelRequest) -> ModelRequest:
        messages = _current_run_messages(request.messages, request.runtime)
        if not self._budget_exhausted(messages):
            return request

        missing = self._missing_required_profiles(messages)
        if missing:
            allowed_tools = [
                tool
                for tool in request.tools
                if self._tool_name(tool) in _CONTROL_TOOL_NAMES
            ]
            instruction = _DELEGATE_MESSAGE
            message_name = "parent_direct_tool_budget"
            model_settings, dispatch_model_mode = _required_tool_model_settings(
                request
            )
        else:
            allowed_tools = []
            instruction = _SYNTHESIZE_MESSAGE
            message_name = "parent_direct_tool_budget_stop"
            model_settings = (
                dict(request.model_settings)
                if isinstance(request.model_settings, dict)
                else {}
            )
            dispatch_model_mode = "synthesis_without_tools"

        return request.override(
            messages=[
                *request.messages,
                HumanMessage(
                    content=instruction,
                    name=message_name,
                    additional_kwargs={
                        "hide_from_ui": True,
                        "missing_subagent_types": list(missing),
                        "dispatch_model_mode": dispatch_model_mode,
                    },
                ),
            ],
            model_settings=model_settings,
            tool_choice="required" if missing else "none",
            tools=allowed_tools,
        )

    def _truncate_excess_direct_calls(
        self,
        state: AgentState,
        runtime: Runtime,
    ) -> dict[str, Any] | None:
        messages = _current_run_messages(state.get("messages") or [], runtime)
        if not messages:
            return None
        last = messages[-1]
        if not isinstance(last, AIMessage) or not last.tool_calls:
            return None

        prior = messages[:-1]
        remaining_calls = (
            None
            if self.max_direct_tool_calls is None
            else max(
                0,
                self.max_direct_tool_calls - self._direct_tool_calls(prior),
            )
        )
        direct_round_available = bool(
            self.max_direct_tool_rounds is None
            or self._direct_tool_rounds(prior)
            < self.max_direct_tool_rounds
        )
        kept: list[dict[str, Any]] = []
        changed = False
        for call in last.tool_calls:
            if call.get("name") in _CONTROL_TOOL_NAMES:
                kept.append(call)
                continue
            if not direct_round_available or remaining_calls == 0:
                changed = True
                continue
            kept.append(call)
            if remaining_calls is not None:
                remaining_calls -= 1

        if not changed:
            return None
        return {"messages": [clone_ai_message_with_tool_calls(last, kept)]}

    @override
    def after_model(
        self,
        state: AgentState,
        runtime: Runtime,
    ) -> dict[str, Any] | None:
        return self._truncate_excess_direct_calls(state, runtime)

    @override
    async def aafter_model(
        self,
        state: AgentState,
        runtime: Runtime,
    ) -> dict[str, Any] | None:
        return self._truncate_excess_direct_calls(state, runtime)

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
