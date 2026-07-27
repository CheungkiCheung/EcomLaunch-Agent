"""Pre-execution policy for verifier lineage in dynamic Subagent dispatch.

The durable runtime intentionally rejects a verifier without completed task
lineage. Waiting until Tool execution to discover that mistake turns a
recoverable planning error into a visible Tool failure. This middleware keeps
the authorization boundary intact while removing only invalid verifier calls
before ToolNode execution and giving the Parent one hidden correction prompt.
Valid calls in the same model batch continue normally.
"""

from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from collections.abc import Awaitable, Callable
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

from deerflow.agents.middlewares.subagent_requirement_middleware import (
    _completed_subagent_tasks,
    _current_run_messages,
    _runtime_key,
    _subagent_tasks,
    _tool_message_payload,
)

logger = logging.getLogger(__name__)

_DEFAULT_MAX_TRACKED_RUNS = 4096


def _is_verifier_spawn(tool_call: dict[str, Any]) -> bool:
    if tool_call.get("name") != "spawn_task":
        return False
    args = tool_call.get("args")
    return isinstance(args, dict) and args.get("subagent_type") == "verifier"


def _verifier_task_refs(tool_call: dict[str, Any]) -> tuple[str, ...]:
    args = tool_call.get("args")
    if not isinstance(args, dict):
        return ()
    source_refs = args.get("source_refs")
    if not isinstance(source_refs, list):
        return ()
    refs: list[str] = []
    for source_ref in source_refs:
        if not isinstance(source_ref, str) or not source_ref.startswith("task:"):
            continue
        task_id = source_ref.removeprefix("task:").strip()
        if task_id:
            refs.append(task_id)
    return tuple(refs)


def _dedupe_strings(values: list[Any]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if isinstance(value, str) and value.strip()))


def _dispatch_signature(tool_call: dict[str, Any]) -> str | None:
    """Return a stable signature for one durable spawn request."""

    if tool_call.get("name") != "spawn_task":
        return None
    args = tool_call.get("args")
    if not isinstance(args, dict):
        return None
    payload = {
        "subagent_type": str(args.get("subagent_type") or "").strip(),
        "description": str(args.get("description") or "").strip(),
        "prompt": str(args.get("prompt") or "").strip(),
        "source_refs": sorted(_dedupe_strings(list(args.get("source_refs") or ()))),
        "skills": sorted(_dedupe_strings(list(args.get("skills") or ()))),
        "tools": sorted(_dedupe_strings(list(args.get("tools") or ()))),
    }
    return repr(payload)


def _historical_dispatch_signatures(
    messages: list[Any],
    current_message: AIMessage,
) -> set[str]:
    successful_call_ids = {
        str(message.tool_call_id)
        for message in messages
        if isinstance(message, ToolMessage)
        and (payload := _tool_message_payload(message)) is not None
        and payload.get("ok") is True
        and isinstance(payload.get("task"), dict)
    }
    signatures: set[str] = set()
    for message in messages:
        if message is current_message or not isinstance(message, AIMessage):
            continue
        for tool_call in message.tool_calls or ():
            if str(tool_call.get("id") or "") not in successful_call_ids:
                continue
            signature = _dispatch_signature(tool_call)
            if signature is not None:
                signatures.add(signature)
    return signatures


def _scope_rule_matches(
    tool_call: dict[str, Any],
    rule: dict[str, Any],
) -> bool:
    if tool_call.get("name") != "spawn_task":
        return False
    args = tool_call.get("args")
    if not isinstance(args, dict):
        return False
    if args.get("subagent_type") != rule.get("subagent_type"):
        return False

    skills = set(_dedupe_strings(list(args.get("skills") or ())))
    required_skills = set(_dedupe_strings(list(rule.get("match_skills_all") or ())))
    if required_skills and not required_skills.issubset(skills):
        return False

    prompt_keywords = _dedupe_strings(list(rule.get("prompt_keywords_any") or ()))
    if prompt_keywords:
        prompt_text = " ".join(str(args.get(key) or "") for key in ("description", "prompt"))
        if not any(keyword in prompt_text for keyword in prompt_keywords):
            return False
    return True


def _scoped_message(
    message: AIMessage,
    *,
    tool_calls: list[dict[str, Any]],
    applied_rule_names: tuple[str, ...],
) -> AIMessage:
    additional_kwargs = dict(message.additional_kwargs or {})
    additional_kwargs.pop("tool_calls", None)
    additional_kwargs.pop("function_call", None)
    additional_kwargs["subagent_dispatch_policy_status"] = "scope_normalized"
    additional_kwargs["subagent_dispatch_policy_scope_rules"] = list(applied_rule_names)
    response_metadata = deepcopy(message.response_metadata or {})
    response_metadata["finish_reason"] = "tool_calls"
    return message.model_copy(
        update={
            "tool_calls": tool_calls,
            "invalid_tool_calls": [],
            "additional_kwargs": additional_kwargs,
            "response_metadata": response_metadata,
        }
    )


def _replacement_message(
    message: AIMessage,
    *,
    valid_calls: list[dict[str, Any]],
    rejected_call_ids: tuple[str, ...],
) -> AIMessage:
    additional_kwargs = dict(message.additional_kwargs or {})
    additional_kwargs.pop("tool_calls", None)
    additional_kwargs.pop("function_call", None)
    additional_kwargs["subagent_dispatch_policy_status"] = "verifier_deferred"
    additional_kwargs["subagent_dispatch_policy_rejected_call_ids"] = list(rejected_call_ids)
    if valid_calls:
        additional_kwargs.pop("hide_from_ui", None)
        content = "正在启动当前可执行的调查任务，独立核验将在前置任务完成后进行。"
    else:
        additional_kwargs["hide_from_ui"] = True
        content = "独立核验需要等待前置任务完成。"

    response_metadata = deepcopy(message.response_metadata or {})
    response_metadata["finish_reason"] = "tool_calls" if valid_calls else "stop"

    return message.model_copy(
        update={
            "content": content,
            "tool_calls": valid_calls,
            "invalid_tool_calls": [],
            "additional_kwargs": additional_kwargs,
            "response_metadata": response_metadata,
        }
    )


def _guarded_dispatch_message(
    message: AIMessage,
    *,
    valid_calls: list[dict[str, Any]],
    rejected_call_ids: tuple[str, ...],
    rejection_reasons: tuple[str, ...],
) -> AIMessage:
    additional_kwargs = dict(message.additional_kwargs or {})
    additional_kwargs.pop("tool_calls", None)
    additional_kwargs.pop("function_call", None)
    additional_kwargs["subagent_dispatch_policy_status"] = "dispatch_guarded"
    additional_kwargs["subagent_dispatch_policy_rejected_call_ids"] = list(rejected_call_ids)
    additional_kwargs["subagent_dispatch_policy_rejection_reasons"] = list(rejection_reasons)
    if valid_calls:
        additional_kwargs.pop("hide_from_ui", None)
        content = "正在启动当前仍有必要的最小任务；重复或超出预算的派工已跳过。"
    else:
        additional_kwargs["hide_from_ui"] = True
        content = "重复或超出预算的派工已跳过，请基于已有任务结果继续。"

    response_metadata = deepcopy(message.response_metadata or {})
    response_metadata["finish_reason"] = "tool_calls" if valid_calls else "stop"
    return message.model_copy(
        update={
            "content": content,
            "tool_calls": valid_calls,
            "invalid_tool_calls": [],
            "additional_kwargs": additional_kwargs,
            "response_metadata": response_metadata,
        }
    )


class SubagentDispatchPolicyMiddleware(AgentMiddleware[AgentState]):
    """Defer verifier dispatch until exact completed task lineage exists."""

    def __init__(
        self,
        *,
        scope_rules: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
        max_tasks_per_run: int | None = None,
        max_failed_tasks_per_run: int | None = None,
        max_tracked_runs: int = _DEFAULT_MAX_TRACKED_RUNS,
    ) -> None:
        super().__init__()
        if max_tracked_runs < 1:
            raise ValueError("max_tracked_runs must be positive")
        if max_tasks_per_run is not None and max_tasks_per_run < 1:
            raise ValueError("max_tasks_per_run must be positive")
        if max_failed_tasks_per_run is not None and max_failed_tasks_per_run < 1:
            raise ValueError("max_failed_tasks_per_run must be positive")
        self.max_tracked_runs = max_tracked_runs
        self.max_tasks_per_run = max_tasks_per_run
        self.max_failed_tasks_per_run = max_failed_tasks_per_run
        self.scope_rules = tuple(deepcopy(list(scope_rules)))
        self._lock = threading.Lock()
        self._pending_reminders: OrderedDict[tuple[str, str], set[str]] = OrderedDict()

    def _queue_reminder(self, runtime: Runtime, reason: str) -> None:
        key = _runtime_key(runtime)
        with self._lock:
            reasons = self._pending_reminders.pop(key, set())
            reasons.add(reason)
            self._pending_reminders[key] = reasons
            while len(self._pending_reminders) > self.max_tracked_runs:
                self._pending_reminders.popitem(last=False)

    def _drain_reminder(self, runtime: Runtime) -> tuple[str, ...]:
        key = _runtime_key(runtime)
        with self._lock:
            return tuple(sorted(self._pending_reminders.pop(key, set())))

    def _clear_other_runs(self, runtime: Runtime) -> None:
        thread_id, run_id = _runtime_key(runtime)
        with self._lock:
            stale = [key for key in self._pending_reminders if key[0] == thread_id and key[1] != run_id]
            for key in stale:
                self._pending_reminders.pop(key, None)

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
        if last_ai is None or not last_ai.tool_calls:
            return None

        completed_task_ids = {str(task.get("task_id")) for task in _completed_subagent_tasks(messages) if task.get("task_id")}
        completed_tasks_by_id = {str(task.get("task_id")): task for task in _completed_subagent_tasks(messages) if task.get("task_id")}
        task_snapshots = _subagent_tasks(messages)
        task_count = len(task_snapshots)
        failed_task_count = sum(1 for task in task_snapshots if task.get("status") == "failed")
        has_verifier_task = any(task.get("subagent_type") == "verifier" for task in task_snapshots)
        seen_dispatch_signatures = _historical_dispatch_signatures(
            messages,
            last_ai,
        )
        valid_calls: list[dict[str, Any]] = []
        lineage_rejected_call_ids: list[str] = []
        guarded_rejected_call_ids: list[str] = []
        guarded_rejection_reasons: list[str] = []
        applied_rule_names: list[str] = []
        for tool_call in last_ai.tool_calls:
            if _is_verifier_spawn(tool_call):
                task_refs = _verifier_task_refs(tool_call)
                if not task_refs or not set(task_refs).issubset(completed_task_ids):
                    lineage_rejected_call_ids.append(str(tool_call.get("id") or "unknown"))
                    continue

            normalized_call = tool_call
            for rule in self.scope_rules:
                if not _scope_rule_matches(tool_call, rule):
                    continue
                normalized_call = self._apply_scope_rule(
                    tool_call,
                    rule,
                    completed_tasks_by_id,
                )
                if normalized_call != tool_call:
                    applied_rule_names.append(str(rule.get("name") or "unnamed"))
                break

            if normalized_call.get("name") == "spawn_task":
                args = normalized_call.get("args")
                subagent_type = str(args.get("subagent_type") or "").strip() if isinstance(args, dict) else ""
                signature = _dispatch_signature(normalized_call)
                rejection_reason: str | None = None
                if signature is not None and signature in seen_dispatch_signatures:
                    rejection_reason = "duplicate_dispatch"
                elif self.max_tasks_per_run is not None and task_count >= self.max_tasks_per_run and not (subagent_type == "verifier" and not has_verifier_task):
                    rejection_reason = "task_budget_exhausted"
                elif subagent_type != "verifier" and self.max_failed_tasks_per_run is not None and failed_task_count >= self.max_failed_tasks_per_run:
                    rejection_reason = "failed_task_budget_exhausted"

                if rejection_reason is not None:
                    guarded_rejected_call_ids.append(str(normalized_call.get("id") or "unknown"))
                    guarded_rejection_reasons.append(rejection_reason)
                    continue

                if signature is not None:
                    seen_dispatch_signatures.add(signature)
                if subagent_type == "verifier":
                    has_verifier_task = True
                task_count += 1
            valid_calls.append(normalized_call)

        if not lineage_rejected_call_ids and not guarded_rejected_call_ids and not applied_rule_names:
            return None

        if not lineage_rejected_call_ids and not guarded_rejected_call_ids:
            return {
                "messages": [
                    _scoped_message(
                        last_ai,
                        tool_calls=valid_calls,
                        applied_rule_names=tuple(applied_rule_names),
                    )
                ]
            }

        if lineage_rejected_call_ids:
            self._queue_reminder(runtime, "verifier_lineage")
            logger.warning(
                "Deferring verifier dispatch before Tool execution; missing exact completed task lineage: %s",
                ", ".join(lineage_rejected_call_ids),
            )
        for reason in set(guarded_rejection_reasons):
            self._queue_reminder(runtime, reason)
        if guarded_rejected_call_ids:
            logger.warning(
                "Rejecting duplicate or over-budget Subagent dispatch before Tool execution: %s (%s)",
                ", ".join(guarded_rejected_call_ids),
                ", ".join(sorted(set(guarded_rejection_reasons))),
            )

        all_rejected_ids = tuple([*lineage_rejected_call_ids, *guarded_rejected_call_ids])
        only_lineage_rejected = bool(lineage_rejected_call_ids) and not (guarded_rejected_call_ids)
        update: dict[str, Any] = {
            "messages": [
                (
                    _replacement_message(
                        last_ai,
                        valid_calls=valid_calls,
                        rejected_call_ids=all_rejected_ids,
                    )
                    if only_lineage_rejected
                    else _guarded_dispatch_message(
                        last_ai,
                        valid_calls=valid_calls,
                        rejected_call_ids=all_rejected_ids,
                        rejection_reasons=tuple(sorted(set(guarded_rejection_reasons))),
                    )
                )
            ]
        }
        if not valid_calls:
            update["jump_to"] = "model"
        return update

    @staticmethod
    def _apply_scope_rule(
        tool_call: dict[str, Any],
        rule: dict[str, Any],
        completed_tasks_by_id: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        normalized = deepcopy(tool_call)
        args = dict(normalized.get("args") or {})
        expected_tools: list[Any] = []
        if bool(rule.get("inherit_source_tools")):
            for task_id in _verifier_task_refs(tool_call):
                source_task = completed_tasks_by_id.get(task_id) or {}
                expected_tools.extend(source_task.get("tools") or ())
        expected_tools.extend(rule.get("enforced_tools") or ())

        args["skills"] = _dedupe_strings(list(rule.get("enforced_skills") or ()))
        args["tools"] = _dedupe_strings(expected_tools)
        prompt_suffix = str(rule.get("prompt_suffix") or "").strip()
        if prompt_suffix:
            prompt = str(args.get("prompt") or "").strip()
            if prompt_suffix not in prompt:
                args["prompt"] = f"{prompt}\n\n{prompt_suffix}" if prompt else prompt_suffix
        args["max_tool_rounds"] = int(rule["max_tool_rounds"])
        args["max_tool_calls"] = int(rule["max_tool_calls"])
        normalized["args"] = args
        return normalized

    @hook_config(can_jump_to=["model"])
    @override
    async def aafter_model(
        self,
        state: AgentState,
        runtime: Runtime,
    ) -> dict[str, Any] | None:
        return self.after_model(state, runtime)

    def _augment_request(self, request: ModelRequest) -> ModelRequest:
        reasons = self._drain_reminder(request.runtime)
        if not reasons:
            return request
        sections: list[str] = []
        if "verifier_lineage" in reasons:
            sections.append(
                "上一轮过早或使用无效 lineage 的 verifier 派工已在 Tool 执行前"
                "被 Harness 延后，没有创建失败 Task。创建 verifier 前必须先 "
                "wait_task，复制精确 task_id，并使用 "
                'source_refs=["task:<精确 task_id>"]；不得使用任务描述、自造别名或占位符。'
            )
        if "duplicate_dispatch" in reasons:
            sections.append(
                "上一轮与当前 Run 既有任务完全相同的 spawn_task 已被跳过。不要再次创建相同 Profile、目标和 scope 的任务；成功结果应直接用于核验，失败结果应作为能力边界。如确有不同修复目标，只能使用一次带变化 scope 的 follow_up_task。"
            )
        if "task_budget_exhausted" in reasons:
            sections.append("当前 Run 的 Durable Task 总预算已经耗尽。除非仍缺少配置要求的 verifier，不要继续扩展调查；请基于已完成任务综合或明确返回 blocked/unknown。")
        if "failed_task_budget_exhausted" in reasons:
            sections.append("当前 Run 的失败 Task 预算已经耗尽。不要再为可选角度创建任务；若已有成功分析任务，立即以其精确 task_id 创建必要 verifier，否则显式停止。")
        reminder = "<system_reminder>\n" + "\n".join(sections) + "\nverifier 仍需显式传入最小 skills、tools、max_tool_rounds 和 max_tool_calls。不要解释或展示这条提醒。\n</system_reminder>"
        return request.override(
            messages=[
                *request.messages,
                HumanMessage(
                    content=reminder,
                    name="subagent_dispatch_policy_reminder",
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
        with self._lock:
            self._pending_reminders.pop(_runtime_key(runtime), None)
        return None

    @override
    async def aafter_agent(
        self,
        state: AgentState,
        runtime: Runtime,
    ) -> dict[str, Any] | None:
        return self.after_agent(state, runtime)
