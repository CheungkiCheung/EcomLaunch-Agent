"""Parent-facing tools for durable, non-blocking Subagent lifecycles."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Annotated, Any, Literal, cast

from langchain.tools import InjectedToolCallId, tool
from langchain_core.callbacks import BaseCallbackManager
from langchain_core.tools import BaseTool
from pydantic import Field

from deerflow.config import get_app_config
from deerflow.runtime.user_context import resolve_runtime_user_id
from deerflow.sandbox.security import (
    LOCAL_BASH_SUBAGENT_DISABLED_MESSAGE,
    is_host_bash_allowed,
)
from deerflow.skills.tool_policy import filter_tools_by_runtime_constraints
from deerflow.subagents import (
    SubagentExecutor,
    get_available_subagent_names,
    get_subagent_config,
)
from deerflow.subagents.config import resolve_subagent_model_name
from deerflow.subagents.tasks import (
    ContextPacket,
    DurableSubagentTaskRuntime,
    SubagentTask,
    SubagentTaskStatus,
    TaskNotFoundError,
    TaskWaitMode,
)
from deerflow.tools.types import Runtime

if TYPE_CHECKING:
    from deerflow.config.app_config import AppConfig
    from deerflow.subagents.config import SubagentConfig


@dataclass(frozen=True)
class SubagentExecutorBundle:
    """Resolved execution adapter plus the delegated capability envelope."""

    executor: Any
    config: Any
    available_tools: tuple[str, ...]


def _runtime_app_config(runtime: Any) -> AppConfig | None:
    context = getattr(runtime, "context", None)
    if isinstance(context, dict):
        app_config = context.get("app_config")
        if app_config is not None:
            return cast("AppConfig", app_config)
    return None


def _runtime_policy_context(runtime: Any) -> dict[str, Any]:
    policy_context: dict[str, Any] = {}
    config = getattr(runtime, "config", None)
    if isinstance(config, dict):
        configurable = config.get("configurable")
        if isinstance(configurable, dict):
            policy_context.update(configurable)
        metadata = config.get("metadata")
        if isinstance(metadata, dict):
            policy_context.update(metadata)
    context = getattr(runtime, "context", None)
    if isinstance(context, dict):
        policy_context.update(context)
    return policy_context


def _validate_explicit_subagent_scope(
    runtime: Runtime,
    *,
    skills: list[str] | None,
    tools: list[str] | None,
    max_tool_rounds: int | None,
    max_tool_calls: int | None,
) -> None:
    if not _runtime_policy_context(runtime).get(
        "require_explicit_subagent_scope",
        False,
    ):
        return
    if (
        not skills
        or not tools
        or max_tool_rounds is None
        or max_tool_calls is None
    ):
        raise ValueError(
            "explicit non-empty skills, tools, max_tool_rounds, and "
            "max_tool_calls are required by Parent policy"
        )


def _merge_skill_allowlists(
    parent: list[str] | None,
    child: list[str] | None,
) -> list[str] | None:
    if parent is None:
        return child
    if child is None:
        return list(parent)
    parent_set = set(parent)
    return [skill for skill in child if skill in parent_set]


def _build_subagent_executor(
    runtime: Runtime,
    subagent_type: str,
    requested_skills: list[str] | None = None,
    requested_tools: list[str] | None = None,
    requested_max_tool_rounds: int | None = None,
    requested_max_tool_calls: int | None = None,
) -> SubagentExecutorBundle:
    """Resolve one isolated executor under the Parent's model/tool policy."""
    runtime_app_config = _runtime_app_config(runtime)
    available_names = get_available_subagent_names(app_config=runtime_app_config) if runtime_app_config is not None else get_available_subagent_names()
    config: SubagentConfig | None = get_subagent_config(subagent_type, app_config=runtime_app_config) if runtime_app_config is not None else get_subagent_config(subagent_type)
    if config is None:
        raise ValueError(f"未知 Subagent 类型 {subagent_type!r}；可用类型：{', '.join(available_names)}")
    if subagent_type == "bash":
        host_bash_allowed = is_host_bash_allowed(runtime_app_config) if runtime_app_config is not None else is_host_bash_allowed()
        if not host_bash_allowed:
            raise PermissionError(LOCAL_BASH_SUBAGENT_DISABLED_MESSAGE)

    runtime_config = getattr(runtime, "config", None)
    metadata = runtime_config.get("metadata", {}) if isinstance(runtime_config, dict) else {}
    parent_skills = metadata.get("available_skills")
    if parent_skills is not None:
        config = replace(
            config,
            skills=_merge_skill_allowlists(list(parent_skills), config.skills),
        )
    if requested_skills is not None:
        if len(requested_skills) != len(set(requested_skills)):
            raise ValueError("requested Subagent skills cannot contain duplicates")
        if not requested_skills:
            config = replace(config, skills=[])
        else:
            available_skills = set(config.skills or requested_skills)
            unavailable = sorted(set(requested_skills) - available_skills)
            if unavailable:
                raise ValueError("Subagent skills are unavailable under the Parent/Profile policy: " + ", ".join(unavailable))
            config = replace(config, skills=list(requested_skills))
    if requested_max_tool_rounds is not None:
        if requested_max_tool_rounds < 1:
            raise ValueError("requested max_tool_rounds must be positive")
        if config.max_tool_rounds is not None and requested_max_tool_rounds > config.max_tool_rounds:
            raise ValueError("requested max_tool_rounds exceeds the Subagent Profile budget")
        config = replace(config, max_tool_rounds=requested_max_tool_rounds)
    if requested_max_tool_calls is not None:
        if requested_max_tool_calls < 1:
            raise ValueError("requested max_tool_calls must be positive")
        if config.max_tool_calls is not None and requested_max_tool_calls > config.max_tool_calls:
            raise ValueError("requested max_tool_calls exceeds the Subagent Profile budget")
        config = replace(config, max_tool_calls=requested_max_tool_calls)

    parent_model = metadata.get("model_name")
    parent_tool_groups = metadata.get("tool_groups")
    resolved_app_config = runtime_app_config
    if config.model == "inherit" and parent_model is None and resolved_app_config is None:
        resolved_app_config = get_app_config()
    effective_model = resolve_subagent_model_name(
        config,
        parent_model,
        app_config=resolved_app_config,
    )

    from deerflow.tools import get_available_tools

    available_tools_kwargs: dict[str, Any] = {
        "model_name": effective_model,
        "groups": parent_tool_groups,
        "subagent_enabled": False,
    }
    if resolved_app_config is not None:
        available_tools_kwargs["app_config"] = resolved_app_config
    tools = get_available_tools(**available_tools_kwargs)
    tools = filter_tools_by_runtime_constraints(
        tools,
        _runtime_policy_context(runtime),
    )
    if config.tools is not None:
        allowed_by_profile = set(config.tools)
        tools = [tool for tool in tools if tool.name in allowed_by_profile]
    if config.disallowed_tools is not None:
        denied_by_profile = set(config.disallowed_tools)
        tools = [tool for tool in tools if tool.name not in denied_by_profile]
    if requested_tools is not None:
        if len(requested_tools) != len(set(requested_tools)):
            raise ValueError("requested Subagent tools cannot contain duplicates")
        available_tool_names = {tool.name for tool in tools}
        unavailable_tools = sorted(set(requested_tools) - available_tool_names)
        if unavailable_tools:
            raise ValueError("Subagent tools are unavailable under the Parent/Profile policy: " + ", ".join(unavailable_tools))
        requested_tool_names = set(requested_tools)
        tools = [tool for tool in tools if tool.name in requested_tool_names]

    state = getattr(runtime, "state", {}) or {}
    context = getattr(runtime, "context", {}) or {}
    thread_id = context.get("thread_id")
    trace_id = metadata.get("trace_id") or uuid.uuid4().hex[:8]
    executor_kwargs: dict[str, Any] = {
        "config": config,
        "tools": tools,
        "parent_model": parent_model,
        "sandbox_state": state.get("sandbox"),
        "thread_data": state.get("thread_data"),
        "thread_id": thread_id,
        "user_id": resolve_runtime_user_id(runtime),
        "trace_id": trace_id,
    }
    if resolved_app_config is not None:
        executor_kwargs["app_config"] = resolved_app_config
    executor = SubagentExecutor(**executor_kwargs)
    return SubagentExecutorBundle(
        executor=executor,
        config=config,
        available_tools=tuple(tool.name for tool in tools),
    )


def _task_runtime(runtime: Runtime) -> DurableSubagentTaskRuntime:
    context = getattr(runtime, "context", None)
    value = context.get("__subagent_task_runtime") if isinstance(context, dict) else None
    if value is None:
        raise RuntimeError("Durable Subagent Task Runtime 未注入当前 Parent Run")
    return cast(DurableSubagentTaskRuntime, value)


def _run_identity(runtime: Runtime) -> tuple[str, str, str]:
    context = getattr(runtime, "context", None)
    if not isinstance(context, dict):
        raise RuntimeError("当前 ToolRuntime 缺少运行上下文")
    thread_id = str(context.get("thread_id") or "").strip()
    run_id = str(context.get("run_id") or "").strip()
    if not thread_id or not run_id:
        raise RuntimeError("当前 ToolRuntime 缺少 thread_id 或 run_id")
    return thread_id, run_id, resolve_runtime_user_id(runtime)


def _authorize_task(runtime: Runtime, task: SubagentTask) -> None:
    thread_id, _run_id, user_id = _run_identity(runtime)
    if task.thread_id != thread_id or (task.user_id is not None and task.user_id != user_id):
        raise PermissionError(f"Subagent task {task.task_id} does not belong to the current thread/user")


def _authorize_current_run_task(runtime: Runtime, task: SubagentTask) -> None:
    _authorize_task(runtime, task)
    _thread_id, run_id, _user_id = _run_identity(runtime)
    if task.run_id != run_id:
        raise PermissionError(f"Subagent task {task.task_id} does not belong to the current run")


async def _authorized_current_run_tasks(
    runtime: Runtime,
    task_runtime: DurableSubagentTaskRuntime,
) -> list[SubagentTask]:
    thread_id, run_id, user_id = _run_identity(runtime)
    tasks = await task_runtime.manager.list_by_run(run_id)
    authorized = [task for task in tasks if task.thread_id == thread_id and (task.user_id is None or task.user_id == user_id)]
    return sorted(authorized, key=lambda task: (task.created_at, task.task_id))


def _task_snapshot(task: SubagentTask) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "thread_id": task.thread_id,
        "run_id": task.run_id,
        "parent_task_id": task.parent_task_id,
        "subagent_type": task.subagent_type,
        "description": task.description,
        "status": task.status.value,
        "attempt": task.attempt,
        "max_attempts": task.max_attempts,
        "depends_on": list(task.depends_on),
        "source_refs": list(task.context_packet.source_refs),
        "evidence_refs": list(task.context_packet.evidence_refs),
        "result": task.result,
        "error": task.error,
        "telemetry": task.telemetry,
        "wait_reason": task.wait_reason,
        "checkpoint": task.checkpoint,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
        "completed_at": (task.completed_at.isoformat() if task.completed_at is not None else None),
    }


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _find_usage_recorder(runtime: Runtime) -> Any | None:
    config = getattr(runtime, "config", None)
    if not isinstance(config, dict):
        return None
    callbacks = config.get("callbacks")
    if isinstance(callbacks, BaseCallbackManager):
        callbacks = callbacks.handlers
    if not isinstance(callbacks, list):
        return None
    return next(
        (callback for callback in callbacks if hasattr(callback, "record_external_llm_usage_records")),
        None,
    )


def _report_durable_task_usage(
    runtime: Runtime,
    tasks: list[SubagentTask],
) -> None:
    recorder = _find_usage_recorder(runtime)
    if recorder is None:
        return
    for task in tasks:
        records = task.telemetry.get("usage_records")
        if not isinstance(records, list) or not records:
            continue
        recorder.record_external_llm_usage_records(records)


def _context_packet(
    *,
    prompt: str,
    bundle: SubagentExecutorBundle,
    source_refs: list[str] | None,
    evidence_refs: list[str] | None,
    metadata: dict[str, Any] | None = None,
) -> ContextPacket:
    config = bundle.config
    return ContextPacket(
        goal=prompt,
        source_refs=tuple(source_refs or ()),
        evidence_refs=tuple(evidence_refs or ()),
        available_skills=tuple(config.skills or ()),
        available_tools=bundle.available_tools,
        budget={
            "max_turns": config.max_turns,
            "timeout_seconds": config.timeout_seconds,
            **({"max_tool_rounds": config.max_tool_rounds} if config.max_tool_rounds is not None else {}),
            **({"max_tool_calls": config.max_tool_calls} if config.max_tool_calls is not None else {}),
        },
        expected_output_schema={
            "type": "object",
            "required": [
                "findings",
                "evidence_refs",
                "counter_evidence_refs",
                "unknowns",
                "data_limitations",
                "recommended_next_tasks",
                "confidence",
                "stop_reason",
            ],
        },
        metadata={
            "trace_id": getattr(bundle.executor, "trace_id", None),
            **(metadata or {}),
        },
    )


async def _explicit_task_source_snapshots(
    runtime: Runtime,
    task_runtime: DurableSubagentTaskRuntime,
    source_refs: list[str],
    *,
    require_current_run: bool = False,
) -> dict[str, dict[str, Any]]:
    snapshots: dict[str, dict[str, Any]] = {}
    for source_ref in source_refs:
        if not source_ref.startswith("task:"):
            continue
        task_id = source_ref.removeprefix("task:").strip()
        if not task_id:
            raise ValueError("task source reference must use task:<task_id>")
        task = await task_runtime.manager.get(task_id)
        if require_current_run:
            _authorize_current_run_task(runtime, task)
        else:
            _authorize_task(runtime, task)
        if not task.status.is_terminal:
            raise ValueError(f"source task {task_id} is still {task.status.value}; call wait_task first")
        snapshots[source_ref] = {
            "status": task.status.value,
            "result": task.result,
            "error": task.error,
            "evidence_refs": list(task.context_packet.evidence_refs),
        }
    return snapshots


async def _normalize_verifier_source_refs(
    runtime: Runtime,
    task_runtime: DurableSubagentTaskRuntime,
    source_refs: list[str],
) -> list[str]:
    """Normalize only exact, authorized Task IDs from the current Parent Run."""
    tasks_by_id = {task.task_id: task for task in await _authorized_current_run_tasks(runtime, task_runtime)}
    normalized: list[str] = []
    for source_ref in source_refs:
        if source_ref.startswith("task:") or ":" in source_ref:
            normalized.append(source_ref)
            continue
        task = tasks_by_id.get(source_ref)
        if task is None:
            normalized.append(source_ref)
            continue
        if not task.status.is_terminal:
            raise ValueError(f"source task {source_ref} is still {task.status.value}; call wait_task first")
        normalized.append(f"task:{source_ref}")
    return normalized


@tool("spawn_task", parse_docstring=True)
async def spawn_task_tool(
    runtime: Runtime,
    description: str,
    prompt: str,
    subagent_type: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    source_refs: list[str] | None = None,
    evidence_refs: list[str] | None = None,
    skills: list[str] | None = None,
    tools: list[str] | None = None,
    max_tool_rounds: int | None = None,
    max_tool_calls: Annotated[int | None, Field(ge=1, le=256)] = None,
    depends_on: list[str] | None = None,
) -> str:
    """启动一个持久化 Subagent 任务并立即返回，不等待模型执行结束。

    当 subagent_type=verifier 时，source_refs 必须包含至少一个
    ``task:<task_id>``；Harness 会校验归属和终态，并向 fresh ContextPacket
    注入只读结果快照。

    Args:
        description: 供用户界面展示的简短中文任务名。
        prompt: 交给 Subagent 的完整、独立、可执行目标。
        subagent_type: 要使用的通用 Subagent Profile 名称。
        source_refs: 可选的显式数据集、文件、任务或 Artifact 引用；verifier 必须使用 wait_task 返回的精确 task_id，按 task:<task_id> 引用至少一个终态任务，不能使用任务描述、别名或占位符。
        evidence_refs: 可选的既有 Evidence 引用。
        skills: 可选的最小 Skill 名称列表；只加载完成当前目标所需 Skill，避免把所有业务 Skill 注入同一 Subagent。
        tools: 可选的最小 Tool 名称列表；只能收窄 Parent/Profile 已允许的能力，不能扩权。
        max_tool_rounds: 可选的 Tool 轮次预算；同一模型响应中的并行 Tool 调用只消耗一轮，且不能超过 Profile 上限。
        max_tool_calls: 可选的 Tool 调用总数预算；并行调用分别计数，且不能超过 Profile 上限。
        depends_on: 可选的同一 Run 前置任务 ID；只有确有依赖时才填写。
    """
    _validate_explicit_subagent_scope(
        runtime,
        skills=skills,
        tools=tools,
        max_tool_rounds=max_tool_rounds,
        max_tool_calls=max_tool_calls,
    )
    task_runtime = _task_runtime(runtime)
    normalized_source_refs = list(source_refs or ())
    if subagent_type == "verifier":
        normalized_source_refs = await _normalize_verifier_source_refs(
            runtime,
            task_runtime,
            normalized_source_refs,
        )
    if len(normalized_source_refs) != len(set(normalized_source_refs)):
        raise ValueError("source_refs cannot contain duplicates")
    task_source_refs = [reference for reference in normalized_source_refs if reference.startswith("task:")]
    if subagent_type == "verifier" and not task_source_refs:
        raise ValueError("verifier requires at least one explicit task:<task_id> source_ref")

    source_snapshots = await _explicit_task_source_snapshots(
        runtime,
        task_runtime,
        normalized_source_refs,
        require_current_run=subagent_type == "verifier",
    )
    if subagent_type == "verifier":
        incomplete_sources = [source_ref for source_ref, snapshot in source_snapshots.items() if snapshot.get("status") != SubagentTaskStatus.completed.value]
        if incomplete_sources:
            raise ValueError("verifier source tasks must be completed successfully: " + ", ".join(incomplete_sources))
    thread_id, run_id, user_id = _run_identity(runtime)
    bundle = _build_subagent_executor(
        runtime,
        subagent_type,
        skills,
        tools,
        max_tool_rounds,
        max_tool_calls,
    )
    context_packet = _context_packet(
        prompt=prompt,
        bundle=bundle,
        source_refs=normalized_source_refs,
        evidence_refs=evidence_refs,
        metadata={
            "source_snapshots": source_snapshots,
        }
        if source_snapshots
        else None,
    )
    task = await task_runtime.spawn(
        task_id=tool_call_id,
        thread_id=thread_id,
        run_id=run_id,
        user_id=user_id,
        subagent_type=subagent_type,
        description=description,
        context_packet=context_packet,
        executor=bundle.executor,
        depends_on=tuple(depends_on or ()),
        tool_policy={
            "allowed_tools": list(bundle.available_tools),
            "disallowed_tools": list(bundle.config.disallowed_tools or ()),
        },
        max_attempts=2,
    )
    return _json(
        {
            "ok": True,
            "message": "任务已启动；Parent 可以继续工作或一次等待一个/任意/全部任务。",
            "task": _task_snapshot(task),
        }
    )


class _ExplicitSpawnTaskInput(spawn_task_tool.args_schema):
    """Model-visible schema for Parents that require least-privilege dispatch."""

    skills: Annotated[
        list[str],
        Field(
            min_length=1,
            description="必填的最小 Skill 名称列表；至少包含一项。",
        ),
    ]
    tools: Annotated[
        list[str],
        Field(
            min_length=1,
            description="必填的最小 Tool 名称列表；至少包含一项。",
        ),
    ]
    max_tool_rounds: Annotated[
        int,
        Field(
            ge=1,
            le=64,
            description="必填的 Tool 轮次预算，不能超过 Profile 上限。",
        ),
    ]
    max_tool_calls: Annotated[
        int,
        Field(
            ge=1,
            le=256,
            description="必填的 Tool 调用总数预算，不能超过 Profile 上限。",
        ),
    ]


def with_explicit_subagent_scope_schema(candidate: BaseTool) -> BaseTool:
    """Require least-privilege fields in the model schema for ``spawn_task``.

    Runtime validation remains the final authorization boundary.  This schema
    adapter prevents a strict Parent from first learning about missing scope
    through a failed Tool call while keeping Profile-default behavior available
    to agents whose policy does not require explicit scoping.
    """

    if candidate.name != spawn_task_tool.name:
        return candidate
    return candidate.model_copy(update={"args_schema": _ExplicitSpawnTaskInput})


@tool("wait_task", parse_docstring=True)
async def wait_task_tool(
    runtime: Runtime,
    task_ids: list[str],
    mode: Literal["one", "any", "all"] = "all",
    timeout_seconds: Annotated[int, Field(ge=0, le=60)] = 30,
) -> str:
    """一次等待一个、任意或全部 Durable Subagent 任务进入可处理状态。

    如果某个 ID 不存在，已授权的精确 ID 仍会正常等待；返回值会列出
    unknown_task_ids 以及当前 Run 的 known_task_ids / known_tasks，供 Parent
    修正后继续，不会进行模糊匹配或跨 Run 暴露任务。

    Args:
        task_ids: 要等待的任务 ID 列表。
        mode: one 要求一个 ID；any 在任一任务可处理时返回；all 等待全部可处理。
        timeout_seconds: 本次最多等待秒数，范围 0 到 60；超时会返回当前快照。
    """
    task_runtime = _task_runtime(runtime)
    wait_mode = TaskWaitMode(mode)
    unique_ids = tuple(dict.fromkeys(task_ids))
    if not unique_ids:
        raise ValueError("task_ids must not be empty")
    if wait_mode is TaskWaitMode.one and len(unique_ids) != 1:
        raise ValueError("wait mode 'one' requires exactly one task ID")

    requested_tasks: list[SubagentTask] = []
    unknown_task_ids: list[str] = []
    for task_id in unique_ids:
        try:
            task = await task_runtime.manager.get(task_id)
        except TaskNotFoundError:
            unknown_task_ids.append(task_id)
            continue
        _authorize_current_run_task(runtime, task)
        requested_tasks.append(task)

    waited = None
    if requested_tasks:
        waited = await task_runtime.wait(
            [task.task_id for task in requested_tasks],
            mode=wait_mode,
            timeout_seconds=timeout_seconds,
        )
        for task in waited.tasks:
            _authorize_current_run_task(runtime, task)
        _report_durable_task_usage(runtime, list(waited.tasks))

    ready = waited.ready if waited is not None else False
    if unknown_task_ids and wait_mode in {TaskWaitMode.one, TaskWaitMode.all}:
        ready = False
    payload: dict[str, Any] = {
        "ok": not unknown_task_ids,
        "mode": wait_mode.value,
        "ready": ready,
        "timed_out": waited.timed_out if waited is not None else False,
        "tasks": ([_task_snapshot(task) for task in waited.tasks] if waited is not None else []),
    }
    if unknown_task_ids:
        # Recovery metadata is intentionally returned only on the degraded
        # path. Normal waits must stay small enough for the Parent to consume
        # Subagent results inline rather than receiving the same snapshots
        # twice and triggering tool-output externalization.
        known_tasks = await _authorized_current_run_tasks(runtime, task_runtime)
        payload.update(
            {
                "unknown_task_ids": unknown_task_ids,
                "known_task_ids": [task.task_id for task in known_tasks],
                "known_tasks": [_task_snapshot(task) for task in known_tasks],
            }
        )
    return _json(payload)


@tool("follow_up_task", parse_docstring=True)
async def follow_up_task_tool(
    runtime: Runtime,
    parent_task_id: str,
    description: str,
    prompt: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    subagent_type: str | None = None,
    skills: list[str] | None = None,
    tools: list[str] | None = None,
    max_tool_rounds: int | None = None,
    max_tool_calls: Annotated[int | None, Field(ge=1, le=256)] = None,
) -> str:
    """基于一个既有任务的显式结果快照创建新的 Child Task。

    Args:
        parent_task_id: 要追问的父任务 ID，可来自同一 Thread 的较早 Run。
        description: 供界面展示的简短中文追问任务名。
        prompt: 新的独立追问目标，不要粘贴父 Agent 的隐式推理历史。
        subagent_type: 可选的新 Profile；省略时继承父任务的 Profile。
        skills: 可选的最小 Skill 列表；省略时继承父任务 ContextPacket 的 Skill。
        tools: 可选的最小 Tool 列表；省略时继承父任务 ContextPacket 的 Tool 能力包。
        max_tool_rounds: 可选的新 Tool 轮次预算；省略时继承父任务预算，且不能超过 Profile 上限。
        max_tool_calls: 可选的新 Tool 调用总数预算；省略时继承父任务预算，且不能超过 Profile 上限。
    """
    task_runtime = _task_runtime(runtime)
    parent = await task_runtime.manager.get(parent_task_id)
    _authorize_task(runtime, parent)
    if parent.status not in {
        SubagentTaskStatus.completed,
        SubagentTaskStatus.failed,
        SubagentTaskStatus.cancelled,
        SubagentTaskStatus.timed_out,
        SubagentTaskStatus.blocked,
    }:
        raise ValueError(f"父任务 {parent_task_id} 仍处于 {parent.status.value}，请先 wait_task")

    resolved_type = subagent_type or parent.subagent_type
    inherited_skills = skills if skills is not None else list(parent.context_packet.available_skills)
    inherited_tools = tools if tools is not None else (list(parent.context_packet.available_tools) if parent.context_packet.available_tools else None)
    inherited_max_tool_rounds = max_tool_rounds if max_tool_rounds is not None else parent.context_packet.budget.get("max_tool_rounds")
    inherited_max_tool_calls = max_tool_calls if max_tool_calls is not None else parent.context_packet.budget.get("max_tool_calls")
    bundle = _build_subagent_executor(
        runtime,
        resolved_type,
        inherited_skills,
        inherited_tools,
        inherited_max_tool_rounds,
        inherited_max_tool_calls,
    )
    source_ref = f"task:{parent_task_id}"
    source_snapshot = {
        "status": parent.status.value,
        "result": parent.result,
        "error": parent.error,
        "evidence_refs": list(parent.context_packet.evidence_refs),
    }
    thread_id, run_id, user_id = _run_identity(runtime)
    context_packet = _context_packet(
        prompt=prompt,
        bundle=bundle,
        source_refs=[source_ref],
        evidence_refs=list(parent.context_packet.evidence_refs),
        metadata={"source_snapshots": {source_ref: source_snapshot}},
    )
    task = await task_runtime.spawn(
        task_id=tool_call_id,
        thread_id=thread_id,
        run_id=run_id,
        user_id=user_id,
        parent_task_id=parent_task_id,
        subagent_type=resolved_type,
        description=description,
        context_packet=context_packet,
        executor=bundle.executor,
        tool_policy={
            "allowed_tools": list(bundle.available_tools),
            "disallowed_tools": list(bundle.config.disallowed_tools or ()),
        },
        max_attempts=2,
    )
    return _json({"ok": True, "task": _task_snapshot(task)})


@tool("cancel_task", parse_docstring=True)
async def cancel_task_tool(
    runtime: Runtime,
    task_id: str,
    reason: str = "Parent requested cancellation",
) -> str:
    """协作式取消一个 Durable Subagent 任务并持久化最终状态。

    Args:
        task_id: 要取消的任务 ID。
        reason: 取消原因，必须能让用户和后续恢复流程理解。
    """
    task_runtime = _task_runtime(runtime)
    current = await task_runtime.manager.get(task_id)
    _authorize_task(runtime, current)
    task = await task_runtime.cancel(task_id, reason=reason)
    return _json({"ok": True, "task": _task_snapshot(task)})


@tool("resume_task", parse_docstring=True)
async def resume_task_tool(runtime: Runtime, task_id: str) -> str:
    """在新 fencing lease 和 attempt 下恢复 blocked/waiting 任务。

    Args:
        task_id: 要恢复的 Durable Subagent 任务 ID。
    """
    task_runtime = _task_runtime(runtime)
    current = await task_runtime.manager.get(task_id)
    _authorize_task(runtime, current)
    inherited_tools = list(current.context_packet.available_tools) if current.context_packet.available_tools else None
    bundle = _build_subagent_executor(
        runtime,
        current.subagent_type,
        list(current.context_packet.available_skills),
        inherited_tools,
        current.context_packet.budget.get("max_tool_rounds"),
        current.context_packet.budget.get("max_tool_calls"),
    )
    task = await task_runtime.resume(task_id, executor=bundle.executor)
    return _json({"ok": True, "task": _task_snapshot(task)})
