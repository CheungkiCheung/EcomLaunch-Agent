"""Fail-closed gate for Agent profiles that require durable Subagent evidence.

The subagent_required configuration originally guaranteed only that durable
task tools were available. A model could still complete a complex multi-tool
investigation entirely in the Parent context and publish an unverified final
answer. This middleware turns that flag into a behavioral contract while
keeping simple turns direct.
"""

from __future__ import annotations

import json
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
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.runtime import Runtime

from deerflow.agents.middlewares.tool_call_metadata import (
    clone_ai_message_with_tool_calls,
)

logger = logging.getLogger(__name__)

_DISPATCH_TOOL_NAMES = {
    "task",
    "spawn_task",
    "follow_up_task",
    "resume_task",
}
_CONTROL_TOOL_NAMES = {
    *_DISPATCH_TOOL_NAMES,
    "wait_task",
    "cancel_task",
    "write_todos",
    "ask_clarification",
}
_TOOL_CALL_FINISH_REASONS = {"tool_calls", "function_call"}
_DEFAULT_MAX_TRACKED_RUNS = 4096
_DURABLE_RECOVERY_TOOL_NAMES = {"spawn_task", "wait_task"}
_TERMINAL_TASK_STATUSES = {
    "completed",
    "failed",
    "cancelled",
    "timed_out",
    "blocked",
}


def _deep_merge_dicts(
    base: dict[str, Any] | None,
    override: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(base or {})
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def _force_dispatch_model_settings(request: ModelRequest) -> dict[str, Any]:
    settings = dict(request.model_settings) if isinstance(request.model_settings, dict) else {}
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
    return settings


def _has_tool_call_intent_or_error(message: AIMessage) -> bool:
    if message.tool_calls or getattr(message, "invalid_tool_calls", None):
        return True
    additional_kwargs = getattr(message, "additional_kwargs", {}) or {}
    if additional_kwargs.get("tool_calls") or additional_kwargs.get("function_call"):
        return True
    response_metadata = getattr(message, "response_metadata", {}) or {}
    return response_metadata.get("finish_reason") in _TOOL_CALL_FINISH_REASONS


def _runtime_key(runtime: Runtime) -> tuple[str, str]:
    context = getattr(runtime, "context", None) or {}
    thread_id = str(context.get("thread_id") or "default")
    run_id = str(context.get("run_id") or "default")
    return thread_id, run_id


def _message_tool_calls(messages: Collection[Any]):
    for message in messages:
        if not isinstance(message, AIMessage):
            continue
        yield from message.tool_calls or ()


def _current_run_messages(
    messages: Collection[Any],
    runtime: Runtime,
) -> list[Any]:
    """Return only the active user turn, excluding prior thread history."""
    ordered = list(messages)
    run_id = _runtime_key(runtime)[1]
    explicit_boundaries = [
        index for index, message in enumerate(ordered) if isinstance(message, HumanMessage) and not (message.additional_kwargs or {}).get("hide_from_ui") and str((message.additional_kwargs or {}).get("run_id") or "") == run_id
    ]
    if explicit_boundaries:
        return ordered[explicit_boundaries[-1] :]

    fallback_boundaries = [index for index, message in enumerate(ordered) if isinstance(message, HumanMessage) and not (message.additional_kwargs or {}).get("hide_from_ui") and message.name not in {"summary", "loop_warning"}]
    if fallback_boundaries:
        return ordered[fallback_boundaries[-1] :]
    return ordered


def _complex_tool_call_count(messages: Collection[Any]) -> int:
    return sum(1 for tool_call in _message_tool_calls(messages) if tool_call.get("name") not in _CONTROL_TOOL_NAMES)


def _json_object(content: Any) -> dict[str, Any] | None:
    if not isinstance(content, str):
        return None
    try:
        payload = json.loads(content)
    except (TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _tool_message_payload(message: ToolMessage) -> dict[str, Any] | None:
    payload = _json_object(message.content)
    if payload is not None:
        return payload
    compact = (message.additional_kwargs or {}).get("durable_task_control")
    return compact if isinstance(compact, dict) else None


def _subagent_tasks(messages: Collection[Any]) -> list[dict[str, Any]]:
    """Collect the latest durable task snapshots from successful exchanges."""
    tool_calls = {str(tool_call.get("id")): tool_call for tool_call in _message_tool_calls(messages) if tool_call.get("id")}
    task_snapshots: dict[str, dict[str, Any]] = {}
    successful_dispatches: dict[str, dict[str, Any]] = {}

    for message in messages:
        if not isinstance(message, ToolMessage):
            continue
        payload = _tool_message_payload(message)
        if payload is None or payload.get("ok") is not True:
            continue

        tool_call = tool_calls.get(str(message.tool_call_id))
        tool_name = tool_call.get("name") if tool_call else None
        tool_args = tool_call.get("args") if tool_call else None
        if not isinstance(tool_args, dict):
            tool_args = {}

        snapshots: list[dict[str, Any]] = []
        task_payload = payload.get("task")
        if isinstance(task_payload, dict):
            snapshots.append(task_payload)
        for key in ("tasks", "known_tasks"):
            value = payload.get(key)
            if isinstance(value, list):
                snapshots.extend(item for item in value if isinstance(item, dict))

        for snapshot in snapshots:
            task_id = str(snapshot.get("task_id") or "").strip()
            if not task_id:
                continue
            merged = {**task_snapshots.get(task_id, {}), **snapshot}
            task_snapshots[task_id] = merged
            if tool_name in _DISPATCH_TOOL_NAMES:
                successful_dispatches[task_id] = tool_args

    tasks: list[dict[str, Any]] = []
    for task_id, snapshot in task_snapshots.items():
        dispatch_args = successful_dispatches.get(task_id, {})
        subagent_type = snapshot.get("subagent_type") or dispatch_args.get("subagent_type")
        if not isinstance(subagent_type, str) or not subagent_type.strip():
            continue
        source_refs = snapshot.get("source_refs")
        if not isinstance(source_refs, list):
            source_refs = dispatch_args.get("source_refs") or []
        tasks.append(
            {
                **snapshot,
                "task_id": task_id,
                "subagent_type": subagent_type.strip(),
                "source_refs": list(source_refs),
                "skills": list(dispatch_args.get("skills") or ()),
                "tools": list(dispatch_args.get("tools") or ()),
                "max_tool_rounds": dispatch_args.get("max_tool_rounds"),
                "max_tool_calls": dispatch_args.get("max_tool_calls"),
            }
        )
    return tasks


def _completed_subagent_tasks(
    messages: Collection[Any],
) -> list[dict[str, Any]]:
    """Collect completed tasks only from successful durable tool exchanges."""

    return [task for task in _subagent_tasks(messages) if task.get("status") == "completed"]


def _blocked_final_message(last_ai: AIMessage) -> AIMessage:
    additional_kwargs = dict(last_ai.additional_kwargs or {})
    additional_kwargs.pop("tool_calls", None)
    additional_kwargs.pop("function_call", None)
    additional_kwargs["subagent_gate_status"] = "blocked"

    response_metadata = deepcopy(last_ai.response_metadata or {})
    response_metadata["finish_reason"] = "stop"

    return last_ai.model_copy(
        update={
            "content": ("本次复杂执行已被 Harness 阻止交付：关键结论未通过独立子智能体核验。系统不会把未经核验的分析包装成最终结论。请重新运行，或检查持久化任务服务。"),
            "tool_calls": [],
            "invalid_tool_calls": [],
            "additional_kwargs": additional_kwargs,
            "response_metadata": response_metadata,
        }
    )


def _forced_retry_message(
    last_ai: AIMessage,
    *,
    expected_tool: str,
) -> AIMessage:
    additional_kwargs = dict(last_ai.additional_kwargs or {})
    additional_kwargs.pop("tool_calls", None)
    additional_kwargs.pop("function_call", None)
    additional_kwargs["hide_from_ui"] = True
    additional_kwargs["subagent_gate_status"] = "force_dispatch_retry"
    additional_kwargs["expected_control_tool"] = expected_tool
    response_metadata = deepcopy(last_ai.response_metadata or {})
    response_metadata["finish_reason"] = "stop"
    return last_ai.model_copy(
        update={
            "content": f"Harness 正在校正 Durable Task 生命周期，下一步必须调用 {expected_tool}。",
            "tool_calls": [],
            "invalid_tool_calls": [],
            "additional_kwargs": additional_kwargs,
            "response_metadata": response_metadata,
        }
    )


class SubagentRequirementMiddleware(AgentMiddleware[AgentState]):
    """Require configured Subagent profiles before complex final delivery."""

    def __init__(
        self,
        *,
        complexity_tool_call_threshold: int = 2,
        required_subagent_types: Collection[str] = (),
        max_reminders: int = 1,
        recovery_mode: str = "remind",
        max_recovery_attempts: int = 8,
        max_tracked_runs: int = _DEFAULT_MAX_TRACKED_RUNS,
    ) -> None:
        super().__init__()
        if complexity_tool_call_threshold < 1:
            raise ValueError("complexity_tool_call_threshold must be positive")
        if max_reminders < 1:
            raise ValueError("max_reminders must be positive")
        if recovery_mode not in {"remind", "force_dispatch"}:
            raise ValueError("recovery_mode must be 'remind' or 'force_dispatch'")
        if max_recovery_attempts < 1:
            raise ValueError("max_recovery_attempts must be positive")
        if max_tracked_runs < 1:
            raise ValueError("max_tracked_runs must be positive")

        self.complexity_tool_call_threshold = complexity_tool_call_threshold
        self.required_subagent_types = tuple(dict.fromkeys(item.strip() for item in required_subagent_types if isinstance(item, str) and item.strip()))
        self.max_reminders = max_reminders
        self.recovery_mode = recovery_mode
        self.max_recovery_attempts = max_recovery_attempts
        self.max_tracked_runs = max_tracked_runs
        self._lock = threading.Lock()
        self._reminder_counts: OrderedDict[tuple[str, str], int] = OrderedDict()
        self._pending_reminders: dict[tuple[str, str], list[str]] = {}
        self._forced_attempts: OrderedDict[tuple[str, str], int] = OrderedDict()

    def _touch_locked(self, key: tuple[str, str]) -> None:
        count = self._reminder_counts.pop(key, 0)
        self._reminder_counts[key] = count
        while len(self._reminder_counts) > self.max_tracked_runs:
            stale_key, _ = self._reminder_counts.popitem(last=False)
            self._pending_reminders.pop(stale_key, None)

    def _touch_forced_locked(self, key: tuple[str, str]) -> None:
        attempts = self._forced_attempts.pop(key, 0)
        self._forced_attempts[key] = attempts
        while len(self._forced_attempts) > self.max_tracked_runs:
            self._forced_attempts.popitem(last=False)

    def _force_active(self, runtime: Runtime) -> bool:
        key = _runtime_key(runtime)
        with self._lock:
            return key in self._forced_attempts

    def _start_force(self, runtime: Runtime) -> None:
        key = _runtime_key(runtime)
        with self._lock:
            self._forced_attempts[key] = 0
            self._touch_forced_locked(key)

    def _increment_force_attempt(self, runtime: Runtime) -> int:
        key = _runtime_key(runtime)
        with self._lock:
            attempts = self._forced_attempts.pop(key, 0) + 1
            self._forced_attempts[key] = attempts
            self._touch_forced_locked(key)
            return attempts

    def _clear_force(self, key: tuple[str, str]) -> None:
        with self._lock:
            self._forced_attempts.pop(key, None)

    def reminder_count(self, runtime: Runtime) -> int:
        key = _runtime_key(runtime)
        with self._lock:
            return self._reminder_counts.get(key, 0)

    def _queue_reminder(self, runtime: Runtime, reminder: str) -> None:
        key = _runtime_key(runtime)
        with self._lock:
            count = self._reminder_counts.pop(key, 0) + 1
            self._reminder_counts[key] = count
            self._pending_reminders.setdefault(key, []).append(reminder)
            while len(self._reminder_counts) > self.max_tracked_runs:
                stale_key, _ = self._reminder_counts.popitem(last=False)
                self._pending_reminders.pop(stale_key, None)

    def _drain_reminders(self, runtime: Runtime) -> list[str]:
        key = _runtime_key(runtime)
        with self._lock:
            reminders = self._pending_reminders.pop(key, [])
            if key in self._reminder_counts:
                self._touch_locked(key)
            return reminders

    def _clear_key(self, key: tuple[str, str]) -> None:
        with self._lock:
            self._reminder_counts.pop(key, None)
            self._pending_reminders.pop(key, None)
            self._forced_attempts.pop(key, None)

    def _clear_other_runs(self, runtime: Runtime) -> None:
        thread_id, run_id = _runtime_key(runtime)
        with self._lock:
            stale = [key for key in self._reminder_counts if key[0] == thread_id and key[1] != run_id]
            for key in stale:
                self._reminder_counts.pop(key, None)
                self._pending_reminders.pop(key, None)
            forced_stale = [key for key in self._forced_attempts if key[0] == thread_id and key[1] != run_id]
            for key in forced_stale:
                self._forced_attempts.pop(key, None)

    def _missing_requirements(self, messages: Collection[Any]) -> tuple[str, ...]:
        completed = _completed_subagent_tasks(messages)

        def profile_is_satisfied(profile: str) -> bool:
            candidates = [task for task in completed if task.get("subagent_type") == profile]
            if profile != "verifier":
                return bool(candidates)
            return any(any(isinstance(source_ref, str) and source_ref.startswith("task:") and bool(source_ref.removeprefix("task:").strip()) for source_ref in task.get("source_refs") or ()) for task in candidates)

        if self.required_subagent_types:
            return tuple(profile for profile in self.required_subagent_types if not profile_is_satisfied(profile))
        return () if completed else ("任意动态 Profile",)

    @staticmethod
    def _expected_recovery_tool(messages: Collection[Any]) -> str:
        tasks = _subagent_tasks(messages)
        has_active_task = any(task.get("status") not in _TERMINAL_TASK_STATUSES for task in tasks)
        return "wait_task" if has_active_task else "spawn_task"

    @staticmethod
    def _tool_name(tool: object) -> str | None:
        name = getattr(tool, "name", None)
        return name if isinstance(name, str) else None

    @staticmethod
    def _format_force_dispatch_reminder(
        *,
        missing: tuple[str, ...],
        expected_tool: str,
    ) -> str:
        missing_text = "、".join(missing)
        if expected_tool == "wait_task":
            action = "当前 Run 已有未进入终态的 Durable Task。只调用 wait_task，使用已返回的精确 task_id 等待任务；不要启动重复任务。"
        else:
            action = '当前没有需要等待的活动 Task。只调用 spawn_task 创建最小必要任务。缺 analyst 时先创建 analyst；verifier 只能在前置任务成功后，使用 source_refs=["task:<精确 task_id>"] 创建。'
        return (
            "<system_reminder>\n"
            "Durable Parent–Subagent Harness 已进入有界强制恢复模式。\n"
            f"- 尚缺必需 Profile：{missing_text}；\n"
            f"- 本轮唯一允许的控制动作：{expected_tool}。\n"
            f"{action}\n"
            "任务仍必须显式传入最小 skills、tools、max_tool_rounds 和 "
            "max_tool_calls。不要调用业务 Tool，不要解释或展示本提醒。\n"
            "</system_reminder>"
        )

    def _format_reminder(
        self,
        *,
        complex_tool_calls: int,
        missing: tuple[str, ...],
    ) -> str:
        missing_text = "、".join(missing)
        verifier_guidance = '\n3. verifier 必须使用 fresh ContextPacket，并通过 source_refs=["task:<task_id>"] 显式引用已完成的前置任务；\n4. 再调用一次 wait_task，只综合核验后的结果。' if "verifier" in missing else ""
        return (
            "<system_reminder>\n"
            "当前回合已经形成复杂工具链，但尚未满足 Durable Parent–Subagent "
            "Harness 的交付条件。\n"
            f"- 已观察到 {complex_tool_calls} 个直接工作 Tool 调用；\n"
            f"- 缺少必需的 Subagent Profile：{missing_text}。\n\n"
            "在给出最终答案前：\n"
            "1. 使用 spawn_task 启动最小必要的独立分析任务，避免在 Parent "
            "重复已经完成的确定性计算；\n"
            "2. 使用一次 wait_task 获取终态结果；"
            f"{verifier_guidance}\n"
            "所有任务都必须带清晰 Goal、最小 Skill/Tool 权限、Budget 和 Stop "
            "Condition。不要解释这条系统提醒，不要把它显示给用户。\n"
            "</system_reminder>"
        )

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
        messages = _current_run_messages(
            state.get("messages") or [],
            runtime,
        )
        last_ai = next(
            (message for message in reversed(messages) if isinstance(message, AIMessage)),
            None,
        )

        if last_ai is not None and self.recovery_mode == "force_dispatch" and self._force_active(runtime):
            missing = self._missing_requirements(messages)
            if not missing:
                self._clear_force(_runtime_key(runtime))
            else:
                expected_tool = self._expected_recovery_tool(messages)
                attempts = self._increment_force_attempt(runtime)
                if attempts > self.max_recovery_attempts:
                    logger.error(
                        "Failing closed after force-dispatch recovery exhausted; missing profiles: %s",
                        ", ".join(missing),
                    )
                    return {"messages": [_blocked_final_message(last_ai)]}

                expected_calls = [call for call in last_ai.tool_calls or () if call.get("name") == expected_tool]
                if expected_calls:
                    if len(expected_calls) == len(last_ai.tool_calls or ()):
                        return None
                    return {
                        "messages": [
                            clone_ai_message_with_tool_calls(
                                last_ai,
                                expected_calls,
                            )
                        ]
                    }

                logger.warning(
                    "Force-dispatch recovery rejected model action; expected %s (attempt %s/%s)",
                    expected_tool,
                    attempts,
                    self.max_recovery_attempts,
                )
                return {
                    "messages": [
                        _forced_retry_message(
                            last_ai,
                            expected_tool=expected_tool,
                        )
                    ],
                    "jump_to": "model",
                }

        if last_ai is None or _has_tool_call_intent_or_error(last_ai):
            return None

        complex_tool_calls = _complex_tool_call_count(messages)
        if complex_tool_calls < self.complexity_tool_call_threshold:
            return None

        missing = self._missing_requirements(messages)
        if not missing:
            return None

        if self.recovery_mode == "force_dispatch":
            self._start_force(runtime)
            logger.warning(
                "Entering force-dispatch recovery before final delivery; missing required Subagent profiles: %s",
                ", ".join(missing),
            )
            return {"jump_to": "model"}

        if self.reminder_count(runtime) < self.max_reminders:
            self._queue_reminder(
                runtime,
                self._format_reminder(
                    complex_tool_calls=complex_tool_calls,
                    missing=missing,
                ),
            )
            logger.warning(
                "Re-engaging complex Parent run before final delivery; missing required Subagent profiles: %s",
                ", ".join(missing),
            )
            return {"jump_to": "model"}

        logger.error(
            "Failing closed after model ignored required Subagent profiles: %s",
            ", ".join(missing),
        )
        return {"messages": [_blocked_final_message(last_ai)]}

    @hook_config(can_jump_to=["model"])
    @override
    async def aafter_model(
        self,
        state: AgentState,
        runtime: Runtime,
    ) -> dict[str, Any] | None:
        return self.after_model(state, runtime)

    def _augment_request(self, request: ModelRequest) -> ModelRequest:
        if self.recovery_mode == "force_dispatch" and self._force_active(request.runtime):
            messages = _current_run_messages(
                request.messages,
                request.runtime,
            )
            missing = self._missing_requirements(messages)
            if not missing:
                self._clear_force(_runtime_key(request.runtime))
            else:
                expected_tool = self._expected_recovery_tool(messages)
                allowed_tools = [tool for tool in request.tools if self._tool_name(tool) == expected_tool]
                if not allowed_tools:
                    raise RuntimeError(f"force-dispatch recovery tool is unavailable: {expected_tool}")
                reminder = self._format_force_dispatch_reminder(
                    missing=missing,
                    expected_tool=expected_tool,
                )
                return request.override(
                    messages=[
                        *request.messages,
                        HumanMessage(
                            content=reminder,
                            name="subagent_requirement_force_dispatch",
                            additional_kwargs={
                                "hide_from_ui": True,
                                "missing_subagent_types": list(missing),
                                "expected_control_tool": expected_tool,
                            },
                        ),
                    ],
                    model_settings=_force_dispatch_model_settings(request),
                    tool_choice={
                        "type": "function",
                        "function": {"name": expected_tool},
                    },
                    tools=allowed_tools,
                )

        reminders = self._drain_reminders(request.runtime)
        if not reminders:
            return request
        reminder = "\n\n".join(dict.fromkeys(reminders))
        return request.override(
            messages=[
                *request.messages,
                HumanMessage(
                    content=reminder,
                    name="subagent_requirement_reminder",
                    additional_kwargs={"hide_from_ui": True},
                ),
            ]
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
