"""Fail closed when a final answer exceeds its configured evidence language.

The policy is intentionally business-agnostic.  A custom Agent may configure
phrases that are unsafe for its evidence contract (for example, unsupported
causal or exclusion claims).  Intermediate tool-call messages are ignored;
only a candidate final answer is inspected.

The first violation is hidden from the UI and repaired with one fresh model
turn.  Repeated violations are replaced with a visible, deterministic message
instead of leaking the unsafe draft to the user.
"""

from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Collection
from copy import deepcopy
from typing import Any, override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import (
    ModelCallResult,
    ModelRequest,
    ModelResponse,
    hook_config,
)
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.runtime import Runtime

from deerflow.agents.middlewares.subagent_requirement_middleware import (
    _completed_subagent_tasks,
    _current_run_messages,
    _has_tool_call_intent_or_error,
    _runtime_key,
)

logger = logging.getLogger(__name__)

_DEFAULT_MAX_TRACKED_RUNS = 4096
_CLAIM_BOUNDARIES = ("。", "！", "？", "；", ";", "\n", "，", ",")
_CONTRAST_BOUNDARIES = ("但是", "但", "然而", "不过", "but", "however")
_NEGATION_MARKERS = (
    "无法",
    "不能",
    "不可",
    "不应",
    "不是",
    "未能",
    "尚不能",
    "未观察到",
    "没有证据",
    "缺少证据",
    "数据不足",
    "不代表",
    "不等于",
    "不能说明",
    "不能证明",
    "不能确认",
    "未确认",
    "未知",
    "cannot",
    "can't",
    "unable",
    "no evidence",
    "not enough data",
    "not confirmed",
    "unknown",
)
_TRAILING_NEGATION_MARKERS = (
    "不成立",
    "未被证实",
    "没有依据",
    "缺乏依据",
    "不支持该结论",
    "不能得出",
    "无法得出",
    "cannot be concluded",
    "cannot conclude",
    "not supported",
    "not established",
)


def _content_text(content: Any) -> str:
    """Flatten provider-neutral message content for deterministic inspection."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return ""


def _matched_phrases(
    message: AIMessage,
    forbidden_phrases: Collection[str],
) -> tuple[str, ...]:
    content = _content_text(message.content)
    return tuple(phrase for phrase in forbidden_phrases if _contains_asserted_phrase(content, phrase))


def _contains_asserted_phrase(content: str, phrase: str) -> bool:
    """Ignore explicitly negated mentions while retaining asserted violations."""

    folded = content.casefold()
    needle = phrase.casefold()
    start = 0
    while True:
        index = folded.find(needle, start)
        if index < 0:
            return False

        context_start = max(0, index - 64)
        prefix = folded[context_start:index]
        boundary = max(
            (prefix.rfind(value) for value in _CLAIM_BOUNDARIES),
            default=-1,
        )
        contrast = max(
            (prefix.rfind(value) + len(value) - 1 for value in _CONTRAST_BOUNDARIES if prefix.rfind(value) >= 0),
            default=-1,
        )
        local_prefix = prefix[max(boundary, contrast) + 1 :]

        suffix = folded[index + len(needle) : index + len(needle) + 64]
        suffix_boundaries = [position for value in (*_CLAIM_BOUNDARIES, *_CONTRAST_BOUNDARIES) if (position := suffix.find(value)) >= 0]
        local_suffix = suffix[: min(suffix_boundaries)] if suffix_boundaries else suffix

        negated_before = any(marker in local_prefix for marker in _NEGATION_MARKERS)
        negated_after = any(marker in local_suffix for marker in _TRAILING_NEGATION_MARKERS)
        if not negated_before and not negated_after:
            return True
        start = index + len(needle)


def _replace_message(
    message: AIMessage,
    *,
    content: Any,
    status: str,
    hide_from_ui: bool,
) -> AIMessage:
    additional_kwargs = dict(message.additional_kwargs or {})
    additional_kwargs.pop("tool_calls", None)
    additional_kwargs.pop("function_call", None)
    additional_kwargs["final_answer_policy_status"] = status
    if hide_from_ui:
        additional_kwargs["hide_from_ui"] = True
    else:
        additional_kwargs.pop("hide_from_ui", None)

    response_metadata = deepcopy(message.response_metadata or {})
    response_metadata["finish_reason"] = "stop"

    return message.model_copy(
        update={
            "content": content,
            "tool_calls": [],
            "invalid_tool_calls": [],
            "additional_kwargs": additional_kwargs,
            "response_metadata": response_metadata,
        }
    )


def _hidden_rejected_message(message: AIMessage) -> AIMessage:
    return _replace_message(
        message,
        content=message.content,
        status="repair_required",
        hide_from_ui=True,
    )


def _blocked_message(message: AIMessage) -> AIMessage:
    return _replace_message(
        message,
        content=("本次回答被 Harness 阻止交付：模型连续使用了超出证据范围的确定性表述。当前结果只能作为有边界的调查线索，请重新运行或补充可用于核验的可靠证据。"),
        status="blocked",
        hide_from_ui=False,
    )


class FinalAnswerPolicyMiddleware(AgentMiddleware[AgentState]):
    """Repair, then block, final answers containing configured phrases."""

    def __init__(
        self,
        *,
        forbidden_phrases: Collection[str],
        max_repairs: int = 1,
        max_tracked_runs: int = _DEFAULT_MAX_TRACKED_RUNS,
    ) -> None:
        super().__init__()
        if max_repairs < 0:
            raise ValueError("max_repairs must not be negative")
        if max_tracked_runs < 1:
            raise ValueError("max_tracked_runs must be positive")

        self.forbidden_phrases = tuple(dict.fromkeys(phrase.strip() for phrase in forbidden_phrases if isinstance(phrase, str) and phrase.strip()))
        if not self.forbidden_phrases:
            raise ValueError("forbidden_phrases must not be empty")
        self.max_repairs = max_repairs
        self.max_tracked_runs = max_tracked_runs
        self._lock = threading.Lock()
        self._repair_counts: OrderedDict[tuple[str, str], int] = OrderedDict()
        self._pending_repair_phrases: dict[tuple[str, str], tuple[str, ...]] = {}

    def _touch_locked(self, key: tuple[str, str]) -> None:
        count = self._repair_counts.pop(key, 0)
        self._repair_counts[key] = count
        while len(self._repair_counts) > self.max_tracked_runs:
            stale_key, _ = self._repair_counts.popitem(last=False)
            self._pending_repair_phrases.pop(stale_key, None)

    def repair_count(self, runtime: Runtime) -> int:
        key = _runtime_key(runtime)
        with self._lock:
            return self._repair_counts.get(key, 0)

    def _queue_repair(
        self,
        runtime: Runtime,
        matched: tuple[str, ...],
    ) -> None:
        key = _runtime_key(runtime)
        with self._lock:
            count = self._repair_counts.pop(key, 0) + 1
            self._repair_counts[key] = count
            self._pending_repair_phrases[key] = matched
            while len(self._repair_counts) > self.max_tracked_runs:
                stale_key, _ = self._repair_counts.popitem(last=False)
                self._pending_repair_phrases.pop(stale_key, None)

    def _drain_repair(self, runtime: Runtime) -> tuple[str, ...]:
        key = _runtime_key(runtime)
        with self._lock:
            matched = self._pending_repair_phrases.pop(key, ())
            if key in self._repair_counts:
                self._touch_locked(key)
            return matched

    def _clear_key(self, key: tuple[str, str]) -> None:
        with self._lock:
            self._repair_counts.pop(key, None)
            self._pending_repair_phrases.pop(key, None)

    def _clear_other_runs(self, runtime: Runtime) -> None:
        thread_id, run_id = _runtime_key(runtime)
        with self._lock:
            stale = [key for key in self._repair_counts if key[0] == thread_id and key[1] != run_id]
            for key in stale:
                self._repair_counts.pop(key, None)
                self._pending_repair_phrases.pop(key, None)

    @override
    def before_agent(
        self,
        state: AgentState,
        runtime: Runtime,
    ) -> dict[str, Any] | None:
        self._clear_other_runs(runtime)
        return None

    @override
    async def abefore_agent(
        self,
        state: AgentState,
        runtime: Runtime,
    ) -> dict[str, Any] | None:
        return self.before_agent(state, runtime)

    @hook_config(can_jump_to=["model"])
    @override
    def after_model(
        self,
        state: AgentState,
        runtime: Runtime,
    ) -> dict[str, Any] | None:
        messages = _current_run_messages(state.get("messages") or [], runtime)
        last_ai = next(
            (message for message in reversed(messages) if isinstance(message, AIMessage)),
            None,
        )
        if last_ai is None or _has_tool_call_intent_or_error(last_ai):
            return None

        matched = _matched_phrases(last_ai, self.forbidden_phrases)
        if not matched:
            return None

        if self.repair_count(runtime) < self.max_repairs:
            self._queue_repair(runtime, matched)
            logger.warning(
                "Rejecting final answer for evidence-language repair: %s",
                ", ".join(matched),
            )
            return {
                "messages": [_hidden_rejected_message(last_ai)],
                "jump_to": "model",
            }

        logger.error(
            "Failing closed after final-answer policy repair was ignored: %s",
            ", ".join(matched),
        )
        return {"messages": [_blocked_message(last_ai)]}

    @hook_config(can_jump_to=["model"])
    @override
    async def aafter_model(
        self,
        state: AgentState,
        runtime: Runtime,
    ) -> dict[str, Any] | None:
        return self.after_model(state, runtime)

    def _augment_request(self, request: ModelRequest) -> ModelRequest:
        matched = self._drain_repair(request.runtime)
        if matched:
            phrases = "、".join(matched)
            reminder = (
                "<system_reminder>\n"
                "上一版最终回答已被 Harness 隐藏，因为使用了超出当前证据边界的"
                f"表述：{phrases}。\n"
                "请重新生成完整的中文最终回答，并遵守以下要求：\n"
                "1. 只陈述可复算的指标变化、阶段定位、相关性和数据限制；\n"
                "2. 明确区分支持证据、反证、未知项与待补数据；\n"
                "3. 不确认因果，不声称已经排除其他解释；\n"
                "4. 不使用 Markdown 表格、装饰性 Emoji 或‘重新提交终答’等元话语；\n"
                "5. 不解释这条系统提醒，也不要引用被隐藏的草稿。\n"
                "</system_reminder>"
            )
            reminder_name = "final_answer_policy_repair"
        elif self._has_completed_verifier(request):
            phrases = "、".join(self.forbidden_phrases)
            reminder = (
                "<system_reminder>\n"
                "独立核验任务已完成。下一条无 Tool Call 的回复应直接交付完整中文终答，"
                "不要再输出过程性占位语。\n"
                "生成前请一次性遵守以下交付合同：\n"
                "1. 只陈述可复算指标、阶段定位、支持证据、反证、未知项和数据限制；\n"
                f"2. 不把以下词语用于肯定结论：{phrases}；\n"
                "3. 不确认因果，不声称已经排除其他解释；\n"
                "4. 不使用 Markdown 表格、装饰性 Emoji、分隔线，"
                "也不要写‘好，重新提交终答’或‘重新提交终答’；\n"
                "5. 不复述内部派工过程，优先使用紧凑自然段，全文不超过 1800 个中文字符；\n"
                "6. 不解释或展示这条系统提醒。\n"
                "</system_reminder>"
            )
            reminder_name = "final_answer_policy_preflight"
        else:
            return request

        return request.override(
            messages=[
                *request.messages,
                HumanMessage(
                    content=reminder,
                    name=reminder_name,
                    additional_kwargs={"hide_from_ui": True},
                ),
            ]
        )

    @staticmethod
    def _has_completed_verifier(request: ModelRequest) -> bool:
        messages = _current_run_messages(request.messages, request.runtime)
        return any(
            task.get("subagent_type") == "verifier" and any(isinstance(source_ref, str) and source_ref.startswith("task:") and bool(source_ref.removeprefix("task:").strip()) for source_ref in task.get("source_refs") or ())
            for task in _completed_subagent_tasks(messages)
        )

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

    @override
    def after_agent(
        self,
        state: AgentState,
        runtime: Runtime,
    ) -> dict[str, Any] | None:
        self._clear_key(_runtime_key(runtime))
        return None

    @override
    async def aafter_agent(
        self,
        state: AgentState,
        runtime: Runtime,
    ) -> dict[str, Any] | None:
        return self.after_agent(state, runtime)
