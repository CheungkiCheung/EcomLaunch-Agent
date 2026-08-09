"""Task tool for delegating work to subagents."""

import asyncio
import logging
import re
import time
import uuid
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, cast

from langchain.tools import InjectedToolCallId, tool
from langchain_core.callbacks import BaseCallbackManager
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.config import get_stream_writer

from deerflow.agents.middlewares.run_budget_middleware import INTERNAL_HUMAN_MESSAGE_NAMES, RUN_BUDGET_CONTEXT_KEY
from deerflow.config import get_app_config
from deerflow.sandbox.security import LOCAL_BASH_SUBAGENT_DISABLED_MESSAGE, is_host_bash_allowed
from deerflow.subagents import SubagentExecutor, get_available_subagent_names, get_subagent_config
from deerflow.subagents.config import resolve_subagent_model_name
from deerflow.subagents.executor import (
    SubagentStatus,
    cleanup_background_task,
    get_background_task_result,
    request_cancel_background_task,
)
from deerflow.tools.builtins.launch_pack_guard import prepare_launch_pack_for_audit, validate_launch_pack
from deerflow.tools.types import Runtime

if TYPE_CHECKING:
    from deerflow.config.app_config import AppConfig

logger = logging.getLogger(__name__)

# Cache subagent token usage by tool_call_id so TokenUsageMiddleware can
# write it back to the triggering AIMessage's usage_metadata.
_subagent_usage_cache: dict[str, dict[str, int]] = {}
_EVIDENCE_VERDICT_PATTERN = re.compile(r"(?im)^\s*(?:#{1,6}\s*)?(?:[-*]\s*)?(?:verdict|审计结论|审计结果|结论)\s*[:：]\s*`?(pass|revise|blocked)\b")
_INCOMPLETE_AUDIT_PATTERN = re.compile(r"execution budget|执行预算|token\s*上限|model call limit", re.IGNORECASE)
_UNRESOLVED_ENV_CONFIG_PATTERN = re.compile(
    r"Environment variable .+ not found for config value .+",
    re.IGNORECASE,
)


def _token_usage_cache_enabled(app_config: "AppConfig | None") -> bool:
    if app_config is None:
        try:
            app_config = get_app_config()
        except FileNotFoundError:
            return False
        except ValueError as exc:
            if _UNRESOLVED_ENV_CONFIG_PATTERN.search(str(exc)):
                return False
            raise
    return bool(getattr(getattr(app_config, "token_usage", None), "enabled", False))


def _cache_subagent_usage(tool_call_id: str, usage: dict | None, *, enabled: bool = True) -> None:
    if enabled and usage:
        _subagent_usage_cache[tool_call_id] = usage


def pop_cached_subagent_usage(tool_call_id: str) -> dict | None:
    return _subagent_usage_cache.pop(tool_call_id, None)


def _is_subagent_terminal(result: Any) -> bool:
    """Return whether a background subagent result is safe to clean up."""
    return result.status in {SubagentStatus.COMPLETED, SubagentStatus.FAILED, SubagentStatus.CANCELLED, SubagentStatus.TIMED_OUT} or getattr(result, "completed_at", None) is not None


async def _await_subagent_terminal(task_id: str, max_polls: int) -> Any | None:
    """Poll until the background subagent reaches a terminal status or we run out of polls."""
    for _ in range(max_polls):
        result = get_background_task_result(task_id)
        if result is None:
            return None
        if _is_subagent_terminal(result):
            return result
        await asyncio.sleep(5)
    return None


async def _deferred_cleanup_subagent_task(task_id: str, trace_id: str, max_polls: int) -> None:
    """Keep polling a cancelled subagent until it can be safely removed."""
    cleanup_poll_count = 0
    while True:
        result = get_background_task_result(task_id)
        if result is None:
            return
        if _is_subagent_terminal(result):
            cleanup_background_task(task_id)
            return
        if cleanup_poll_count >= max_polls:
            logger.warning(f"[trace={trace_id}] Deferred cleanup for task {task_id} timed out after {cleanup_poll_count} polls")
            return
        await asyncio.sleep(5)
        cleanup_poll_count += 1


def _log_cleanup_failure(cleanup_task: asyncio.Task[None], *, trace_id: str, task_id: str) -> None:
    if cleanup_task.cancelled():
        return

    exc = cleanup_task.exception()
    if exc is not None:
        logger.error(f"[trace={trace_id}] Deferred cleanup failed for task {task_id}: {exc}")


def _schedule_deferred_subagent_cleanup(task_id: str, trace_id: str, max_polls: int) -> None:
    logger.debug(f"[trace={trace_id}] Scheduling deferred cleanup for cancelled task {task_id}")
    cleanup_task = asyncio.create_task(_deferred_cleanup_subagent_task(task_id, trace_id, max_polls))
    cleanup_task.add_done_callback(lambda task: _log_cleanup_failure(task, trace_id=trace_id, task_id=task_id))


def _find_usage_recorder(runtime: Any) -> Any | None:
    """Find a callback handler with ``record_external_llm_usage_records`` in the runtime config.

    LangChain may pass ``config["callbacks"]`` in three different shapes:

    - ``None`` (no callbacks registered): no recorder.
    - A plain ``list[BaseCallbackHandler]``: iterate it directly.
    - A ``BaseCallbackManager`` instance (e.g. ``AsyncCallbackManager`` on async
      tool runs): managers are not iterable, so we unwrap ``.handlers`` first.

    Any other shape (e.g. a single handler object accidentally passed without a
    list wrapper) cannot be iterated safely; treat it as "no recorder" rather
    than raise.
    """
    if runtime is None:
        return None
    config = getattr(runtime, "config", None)
    if not isinstance(config, dict):
        return None
    callbacks = config.get("callbacks")
    if isinstance(callbacks, BaseCallbackManager):
        callbacks = callbacks.handlers
    if not callbacks:
        return None
    if not isinstance(callbacks, list):
        return None
    for cb in callbacks:
        if hasattr(cb, "record_external_llm_usage_records"):
            return cb
    return None


def _summarize_usage(records: list[dict] | None) -> dict | None:
    """Summarize token usage records into a compact dict for SSE events."""
    if not records:
        return None
    return {
        "input_tokens": sum(r.get("input_tokens", 0) or 0 for r in records),
        "output_tokens": sum(r.get("output_tokens", 0) or 0 for r in records),
        "total_tokens": sum(r.get("total_tokens", 0) or 0 for r in records),
    }


def _report_subagent_usage(runtime: Any, result: Any) -> None:
    """Report subagent token usage to the parent RunJournal, if available.

    Each subagent task must be reported only once (guarded by usage_reported).
    """
    if getattr(result, "usage_reported", True):
        return
    records = getattr(result, "token_usage_records", None) or []
    if not records:
        return
    journal = _find_usage_recorder(runtime)
    if journal is None:
        logger.debug("No usage recorder found in runtime callbacks — subagent token usage not recorded")
        return
    try:
        journal.record_external_llm_usage_records(records)
        result.usage_reported = True
    except Exception:
        logger.warning("Failed to report subagent token usage", exc_info=True)


def _get_runtime_app_config(runtime: Any) -> "AppConfig | None":
    context = getattr(runtime, "context", None)
    if isinstance(context, dict):
        app_config = context.get("app_config")
        if app_config is not None:
            return cast("AppConfig", app_config)
    return None


def _merge_skill_allowlists(parent: list[str] | None, child: list[str] | None) -> list[str] | None:
    """Return the effective subagent skill allowlist.

    An explicit subagent list is an administrator-defined capability boundary
    and must not be intersected with the lead agent's router-only skills. When
    the subagent omits its own list, it inherits the lead agent's allowlist.
    """
    if child is not None:
        return list(child)
    if parent is not None:
        return list(parent)
    return None


def _scheduled_sibling_subagent_types(runtime: Any) -> set[str]:
    """Return specialist types scheduled in the current lead-agent tool batch."""
    state = getattr(runtime, "state", None)
    if not isinstance(state, dict):
        return set()
    messages = state.get("messages")
    if not isinstance(messages, (list, tuple)):
        return set()

    for message in reversed(messages):
        if not isinstance(message, AIMessage):
            continue
        scheduled: set[str] = set()
        for tool_call in message.tool_calls or []:
            if tool_call.get("name") != "task":
                continue
            args = tool_call.get("args")
            subagent_type = args.get("subagent_type") if isinstance(args, dict) else None
            if isinstance(subagent_type, str) and subagent_type:
                scheduled.add(subagent_type)
        return scheduled
    return set()


def _message_text(message: Any) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and isinstance(block.get("text"), str):
            parts.append(block["text"])
    return "\n".join(parts)


def _complete_workflow_requested(runtime: Any, budget_config: dict[str, Any]) -> bool:
    patterns = budget_config.get("complete_workflow_patterns")
    if not isinstance(patterns, list) or not patterns:
        return False
    state = getattr(runtime, "state", None)
    messages = state.get("messages") if isinstance(state, dict) else None
    if not isinstance(messages, (list, tuple)):
        return False
    for message in reversed(messages):
        if not isinstance(message, HumanMessage) or message.name in INTERNAL_HUMAN_MESSAGE_NAMES:
            continue
        user_text = _message_text(message)
        return any(re.search(pattern, user_text, re.IGNORECASE) for pattern in patterns if isinstance(pattern, str) and pattern)
    return False


def _latest_user_request_text(runtime: Any) -> str:
    state = getattr(runtime, "state", None)
    messages = state.get("messages") if isinstance(state, dict) else None
    if not isinstance(messages, (list, tuple)):
        return ""
    for message in reversed(messages):
        if isinstance(message, HumanMessage) and message.name not in INTERNAL_HUMAN_MESSAGE_NAMES:
            return _message_text(message)
    return ""


def _terminal_specialist_preflight(runtime: Any, subagent_type: str) -> str | None:
    """Block the terminal audit until the deterministic candidate-pack contract passes."""
    context = getattr(runtime, "context", None)
    budget_state = context.get(RUN_BUDGET_CONTEXT_KEY) if isinstance(context, dict) else None
    if not isinstance(budget_state, dict):
        return None
    budget_config = budget_state.get("config")
    if not isinstance(budget_config, dict):
        return None
    if not budget_config.get("validate_pack_before_evidence"):
        return None
    if subagent_type != budget_config.get("finalize_after_subagent"):
        return None

    required_files = budget_config.get("required_output_files")
    if not isinstance(required_files, list) or not required_files:
        return None
    required_names = [name for name in required_files if isinstance(name, str) and name]
    state = getattr(runtime, "state", None)
    thread_data = state.get("thread_data") if isinstance(state, dict) else None
    outputs_path = thread_data.get("outputs_path") if isinstance(thread_data, dict) else None
    if not outputs_path:
        return "Task skipped: launch-pack preflight could not resolve the thread outputs directory."

    resolved_outputs = Path(outputs_path).resolve()
    normalized_files = prepare_launch_pack_for_audit(
        resolved_outputs,
        required_names,
        user_request=_latest_user_request_text(runtime),
    )
    if normalized_files:
        logger.info("Normalized candidate Launch Pack before evidence audit: %s", ", ".join(normalized_files))

    issues = validate_launch_pack(
        resolved_outputs,
        required_names,
        user_request=_latest_user_request_text(runtime),
    )
    if not issues:
        return None
    formatted = "\n".join(f"- {issue}" for issue in issues)
    return (
        f"Task skipped: candidate Launch Pack preflight must pass before specialist '{subagent_type}' starts. "
        "Fix only the listed files, then call the same specialist again; this skipped attempt did not reserve a specialist slot.\n"
        f"{formatted}"
    )


def _record_terminal_preflight_failure(runtime: Any, subagent_type: str, result: str) -> bool:
    """Stop a complete workflow after a repeated terminal preflight failure."""
    context = getattr(runtime, "context", None)
    budget_state = context.get(RUN_BUDGET_CONTEXT_KEY) if isinstance(context, dict) else None
    if not isinstance(budget_state, dict):
        return False
    budget_config = budget_state.get("config")
    if not isinstance(budget_config, dict) or subagent_type != budget_config.get("finalize_after_subagent"):
        return False

    failures = budget_state.get("terminal_preflight_failures", 0)
    failures = failures if isinstance(failures, int) and failures >= 0 else 0
    failures += 1
    budget_state["terminal_preflight_failures"] = failures
    budget_state["terminal_preflight_result"] = result
    if failures < 2:
        return False

    budget_state["terminal_subagent_finished"] = True
    budget_state["evidence_checker_completed"] = False
    budget_state["evidence_checker_verdict"] = None
    return True


def _apply_run_budget_to_subagent(runtime: Any, config: Any, subagent_type: str) -> tuple[Any, str | None]:
    """Reserve one run-scoped subagent slot and clamp its timeout.

    The reservation happens before the first await in ``task_tool``. Parallel
    async task calls therefore observe the updated counter/type set before a
    second call of the same type can start.
    """
    context = getattr(runtime, "context", None)
    if not isinstance(context, dict):
        return config, None

    budget_state = context.get(RUN_BUDGET_CONTEXT_KEY)
    if not isinstance(budget_state, dict):
        return config, None

    budget_config = budget_state.get("config")
    if not isinstance(budget_config, dict):
        return config, None

    allowed_subagent_types = budget_config.get("allowed_subagent_types")
    if allowed_subagent_types is not None:
        allowed = {name for name in allowed_subagent_types if isinstance(name, str)}
        if subagent_type not in allowed:
            allowed_display = ", ".join(sorted(allowed)) or "none"
            return config, f"Task skipped: subagent type '{subagent_type}' is not allowed for this agent. Allowed types: {allowed_display}."

    deadline = budget_state.get("deadline_monotonic")
    if isinstance(deadline, (int, float)):
        remaining_seconds = int(deadline - time.monotonic())
        if remaining_seconds < 1:
            return config, "Task skipped: the whole-run wall-time budget has expired. Use the evidence already collected and finish with explicit limitations."
    else:
        remaining_seconds = config.timeout_seconds

    started_types = budget_state.setdefault("subagent_types_started", set())
    if not isinstance(started_types, set):
        started_types = set(started_types) if isinstance(started_types, (list, tuple)) else set()
        budget_state["subagent_types_started"] = started_types

    completed_types = budget_state.setdefault("subagent_types_completed", set())
    if not isinstance(completed_types, set):
        completed_types = set(completed_types) if isinstance(completed_types, (list, tuple)) else set()
        budget_state["subagent_types_completed"] = completed_types

    dependency_config = budget_config.get("subagent_dependencies")
    degraded_types = budget_state.setdefault("subagent_types_degraded", {})
    degraded_names = set(degraded_types) if isinstance(degraded_types, dict) else set()
    if isinstance(dependency_config, dict):
        raw_dependencies = dependency_config.get(subagent_type)
        if isinstance(raw_dependencies, list):
            dependencies = {name for name in raw_dependencies if isinstance(name, str) and name}
            if _complete_workflow_requested(runtime, budget_config):
                active_dependencies = dependencies
            else:
                active_dependencies = dependencies.intersection(started_types | _scheduled_sibling_subagent_types(runtime))
            incomplete_dependencies = sorted(active_dependencies - completed_types - degraded_names)
            if incomplete_dependencies:
                dependency_display = ", ".join(incomplete_dependencies)
                return config, (f"Task skipped: specialist '{subagent_type}' must wait for prerequisite(s) {dependency_display} to complete. Call it again after those results are available.")

    if budget_config.get("deduplicate_subagents", True) and subagent_type in started_types:
        return config, f"Task skipped: specialist '{subagent_type}' already ran in this user request. Reuse its earlier result instead of starting duplicate research."

    calls_started = budget_state.get("subagent_calls_started", 0)
    calls_started = calls_started if isinstance(calls_started, int) and calls_started >= 0 else 0
    max_subagent_calls = budget_config.get("max_subagent_calls")
    if isinstance(max_subagent_calls, int) and calls_started >= max_subagent_calls:
        return config, f"Task skipped: the whole-run budget allows at most {max_subagent_calls} subagent call(s). Use the results already available and finish the response."

    budget_state["subagent_calls_started"] = calls_started + 1
    started_types.add(subagent_type)
    clamped_timeout = max(1, min(config.timeout_seconds, remaining_seconds))
    return replace(config, timeout_seconds=clamped_timeout), None


def _mark_completed_subagent(runtime: Any, subagent_type: str, result: str | None) -> None:
    """Persist completion signals needed by configured terminal-delivery contracts."""
    context = getattr(runtime, "context", None)
    if not isinstance(context, dict):
        return
    budget_state = context.get(RUN_BUDGET_CONTEXT_KEY)
    if not isinstance(budget_state, dict):
        return
    budget_config = budget_state.get("config")
    if isinstance(budget_config, dict) and subagent_type == budget_config.get("finalize_after_subagent"):
        budget_state["terminal_subagent_finished"] = True
    result_text = result or ""
    incomplete_result = _INCOMPLETE_AUDIT_PATTERN.search(result_text) is not None
    if incomplete_result:
        if subagent_type == "evidence-checker":
            budget_state["evidence_checker_completed"] = False
            budget_state["evidence_checker_verdict"] = None
            budget_state["evidence_checker_result"] = result_text
        required_subagents = budget_config.get("required_completed_subagents") if isinstance(budget_config, dict) else None
        required = {name for name in required_subagents if isinstance(name, str) and name} if isinstance(required_subagents, list) else set()
        if subagent_type in required and _complete_workflow_requested(runtime, budget_config):
            budget_state["workflow_failed_subagent"] = subagent_type
            budget_state["workflow_failed_result"] = result_text
            budget_state["terminal_subagent_finished"] = True
        return

    completed_types = budget_state.setdefault("subagent_types_completed", set())
    if not isinstance(completed_types, set):
        completed_types = set(completed_types) if isinstance(completed_types, (list, tuple)) else set()
        budget_state["subagent_types_completed"] = completed_types
    completed_types.add(subagent_type)
    if subagent_type == "evidence-checker":
        verdict_match = _EVIDENCE_VERDICT_PATTERN.search(result_text)
        valid_verdict = verdict_match is not None
        budget_state["evidence_checker_completed"] = valid_verdict
        budget_state["evidence_checker_verdict"] = verdict_match.group(1).lower() if valid_verdict and verdict_match else None
        budget_state["evidence_checker_result"] = result_text


def _mark_degraded_subagent(runtime: Any, subagent_type: str, reason: str) -> None:
    """Record an optional specialist failure without dead-ending a launch pack."""
    context = getattr(runtime, "context", None)
    budget_state = context.get(RUN_BUDGET_CONTEXT_KEY) if isinstance(context, dict) else None
    if not isinstance(budget_state, dict):
        return
    budget_config = budget_state.get("config")
    if not isinstance(budget_config, dict) or not _complete_workflow_requested(runtime, budget_config):
        return
    degraded = budget_state.setdefault("subagent_types_degraded", {})
    if not isinstance(degraded, dict):
        degraded = {}
        budget_state["subagent_types_degraded"] = degraded
    degraded[subagent_type] = reason or "specialist unavailable"


@tool("task", parse_docstring=True)
async def task_tool(
    runtime: Runtime,
    description: str,
    prompt: str,
    subagent_type: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> str:
    """Delegate a task to a specialized subagent that runs in its own context.

    Subagents help you:
    - Preserve context by keeping exploration and implementation separate
    - Handle complex multi-step tasks autonomously
    - Execute commands or operations in isolated contexts

    Built-in subagent types:
    - **general-purpose**: A capable agent for complex, multi-step tasks that require
      both exploration and action. Use when the task requires complex reasoning,
      multiple dependent steps, or would benefit from isolated context.
    - **bash**: Command execution specialist for running bash commands. This is only
      available when host bash is explicitly allowed or when using an isolated shell
      sandbox such as `AioSandboxProvider`.

    Additional custom subagent types may be defined in config.yaml under
    `subagents.custom_agents`. Each custom type can have its own system prompt,
    tools, skills, model, and timeout configuration. If an unknown subagent_type
    is provided, the error message will list all available types.

    When to use this tool:
    - Complex tasks requiring multiple steps or tools
    - Tasks that produce verbose output
    - When you want to isolate context from the main conversation
    - Parallel research or exploration tasks

    When NOT to use this tool:
    - Simple, single-step operations (use tools directly)
    - Tasks requiring user interaction or clarification

    Args:
        description: A short (3-5 word) description of the task for logging/display. ALWAYS PROVIDE THIS PARAMETER FIRST.
        prompt: The task description for the subagent. Be specific and clear about what needs to be done. ALWAYS PROVIDE THIS PARAMETER SECOND.
        subagent_type: The type of subagent to use. ALWAYS PROVIDE THIS PARAMETER THIRD.
    """
    runtime_app_config = _get_runtime_app_config(runtime)
    cache_token_usage = _token_usage_cache_enabled(runtime_app_config)
    available_subagent_names = get_available_subagent_names(app_config=runtime_app_config) if runtime_app_config is not None else get_available_subagent_names()

    # Get subagent configuration
    config = get_subagent_config(subagent_type, app_config=runtime_app_config) if runtime_app_config is not None else get_subagent_config(subagent_type)
    if config is None:
        available = ", ".join(available_subagent_names)
        return f"Error: Unknown subagent type '{subagent_type}'. Available: {available}"
    if subagent_type == "bash":
        host_bash_allowed = is_host_bash_allowed(runtime_app_config) if runtime_app_config is not None else is_host_bash_allowed()
        if not host_bash_allowed:
            return f"Error: {LOCAL_BASH_SUBAGENT_DISABLED_MESSAGE}"

    # Build config overrides
    overrides: dict = {}

    # Skills are loaded by SubagentExecutor per-session (aligned with Codex's pattern:
    # each subagent loads its own skills based on config, injected as conversation items).
    # No longer appended to system_prompt here.

    # Extract parent context from runtime
    sandbox_state = None
    thread_data = None
    thread_id = None
    parent_model = None
    trace_id = None
    metadata: dict = {}

    if runtime is not None:
        sandbox_state = runtime.state.get("sandbox")
        thread_data = runtime.state.get("thread_data")
        thread_id = runtime.context.get("thread_id") if runtime.context else None
        if thread_id is None:
            thread_id = runtime.config.get("configurable", {}).get("thread_id")

        # Try to get parent model from configurable
        metadata = runtime.config.get("metadata", {})
        parent_model = metadata.get("model_name")

        # Get or generate trace_id for distributed tracing
        trace_id = metadata.get("trace_id") or str(uuid.uuid4())[:8]

    parent_available_skills = metadata.get("available_skills")
    if parent_available_skills is not None:
        overrides["skills"] = _merge_skill_allowlists(list(parent_available_skills), config.skills)

    if overrides:
        config = replace(config, **overrides)

    preflight_error = _terminal_specialist_preflight(runtime, subagent_type)
    if preflight_error is not None:
        terminal_failure = _record_terminal_preflight_failure(runtime, subagent_type, preflight_error)
        logger.info("Skipped subagent %s because candidate-pack preflight failed", subagent_type)
        if terminal_failure:
            return f"{preflight_error}\nTask skipped: the candidate-pack preflight failed twice; no further audit or delivery attempts are allowed in this request."
        return preflight_error

    config, budget_error = _apply_run_budget_to_subagent(runtime, config, subagent_type)
    if budget_error is not None:
        logger.info("Skipped subagent %s because of the parent run budget: %s", subagent_type, budget_error)
        return budget_error

    # Get available tools (excluding task tool to prevent nesting)
    # Lazy import to avoid circular dependency
    from deerflow.tools import get_available_tools

    # Inherit parent agent's tool_groups so subagents respect the same restrictions
    parent_tool_groups = metadata.get("tool_groups")
    resolved_app_config = runtime_app_config
    if config.model == "inherit" and parent_model is None and resolved_app_config is None:
        resolved_app_config = get_app_config()
    effective_model = resolve_subagent_model_name(config, parent_model, app_config=resolved_app_config)

    # Subagents should not have subagent tools enabled (prevent recursive nesting)
    available_tools_kwargs = {
        "model_name": effective_model,
        "groups": parent_tool_groups,
        "subagent_enabled": False,
    }
    if resolved_app_config is not None:
        available_tools_kwargs["app_config"] = resolved_app_config
    tools = get_available_tools(**available_tools_kwargs)

    # Create executor
    executor_kwargs = {
        "config": config,
        "tools": tools,
        "parent_model": parent_model,
        "sandbox_state": sandbox_state,
        "thread_data": thread_data,
        "thread_id": thread_id,
        "trace_id": trace_id,
    }
    if resolved_app_config is not None:
        executor_kwargs["app_config"] = resolved_app_config
    executor = SubagentExecutor(**executor_kwargs)

    # Start background execution (always async to prevent blocking)
    # Use tool_call_id as task_id for better traceability
    task_id = executor.execute_async(prompt, task_id=tool_call_id)

    # Poll for task completion in backend (removes need for LLM to poll)
    poll_count = 0
    last_status = None
    last_message_count = 0  # Track how many AI messages we've already sent
    # Polling timeout: execution timeout + 60s buffer, checked every 5s
    max_poll_count = (config.timeout_seconds + 60) // 5

    logger.info(f"[trace={trace_id}] Started background task {task_id} (subagent={subagent_type}, timeout={config.timeout_seconds}s, polling_limit={max_poll_count} polls)")

    writer = get_stream_writer()
    # Send Task Started message'
    writer({"type": "task_started", "task_id": task_id, "description": description})

    try:
        while True:
            result = get_background_task_result(task_id)

            if result is None:
                logger.error(f"[trace={trace_id}] Task {task_id} not found in background tasks")
                writer({"type": "task_failed", "task_id": task_id, "error": "Task disappeared from background tasks"})
                cleanup_background_task(task_id)
                return f"Error: Task {task_id} disappeared from background tasks"

            # Log status changes for debugging
            if result.status != last_status:
                logger.info(f"[trace={trace_id}] Task {task_id} status: {result.status.value}")
                last_status = result.status

            # Check for new AI messages and send task_running events
            ai_messages = result.ai_messages or []
            current_message_count = len(ai_messages)
            if current_message_count > last_message_count:
                # Send task_running event for each new message
                for i in range(last_message_count, current_message_count):
                    message = ai_messages[i]
                    writer(
                        {
                            "type": "task_running",
                            "task_id": task_id,
                            "message": message,
                            "message_index": i + 1,  # 1-based index for display
                            "total_messages": current_message_count,
                        }
                    )
                    logger.info(f"[trace={trace_id}] Task {task_id} sent message #{i + 1}/{current_message_count}")
                last_message_count = current_message_count

            # Check if task completed, failed, or timed out
            usage = _summarize_usage(getattr(result, "token_usage_records", None))
            if result.status == SubagentStatus.COMPLETED:
                _cache_subagent_usage(tool_call_id, usage, enabled=cache_token_usage)
                _report_subagent_usage(runtime, result)
                _mark_completed_subagent(runtime, subagent_type, result.result)
                writer({"type": "task_completed", "task_id": task_id, "result": result.result, "usage": usage})
                logger.info(f"[trace={trace_id}] Task {task_id} completed after {poll_count} polls")
                cleanup_background_task(task_id)
                return f"Task Succeeded. Result: {result.result}"
            elif result.status == SubagentStatus.FAILED:
                _cache_subagent_usage(tool_call_id, usage, enabled=cache_token_usage)
                _report_subagent_usage(runtime, result)
                writer({"type": "task_failed", "task_id": task_id, "error": result.error, "usage": usage})
                logger.error(f"[trace={trace_id}] Task {task_id} failed: {result.error}")
                degraded_workflow = _complete_workflow_requested(runtime, (runtime.context or {}).get(RUN_BUDGET_CONTEXT_KEY, {}).get("config", {})) if runtime is not None else False
                _mark_degraded_subagent(runtime, subagent_type, result.error or "specialist failed")
                cleanup_background_task(task_id)
                if degraded_workflow:
                    return f"Task degraded: {subagent_type} unavailable. Continue with explicit unavailable/assumption labels."
                return f"Task failed. Error: {result.error}"
            elif result.status == SubagentStatus.CANCELLED:
                _cache_subagent_usage(tool_call_id, usage, enabled=cache_token_usage)
                _report_subagent_usage(runtime, result)
                writer({"type": "task_cancelled", "task_id": task_id, "error": result.error, "usage": usage})
                logger.info(f"[trace={trace_id}] Task {task_id} cancelled: {result.error}")
                cleanup_background_task(task_id)
                return "Task cancelled by user."
            elif result.status == SubagentStatus.TIMED_OUT:
                _cache_subagent_usage(tool_call_id, usage, enabled=cache_token_usage)
                _report_subagent_usage(runtime, result)
                writer({"type": "task_timed_out", "task_id": task_id, "error": result.error, "usage": usage})
                logger.warning(f"[trace={trace_id}] Task {task_id} timed out: {result.error}")
                degraded_workflow = _complete_workflow_requested(runtime, (runtime.context or {}).get(RUN_BUDGET_CONTEXT_KEY, {}).get("config", {})) if runtime is not None else False
                _mark_degraded_subagent(runtime, subagent_type, result.error or "specialist timed out")
                cleanup_background_task(task_id)
                if degraded_workflow:
                    return f"Task degraded: {subagent_type} timed out. Continue with explicit unavailable/assumption labels."
                return f"Task timed out. Error: {result.error}"

            # Still running, wait before next poll
            await asyncio.sleep(5)
            poll_count += 1

            # Polling timeout as a safety net (in case thread pool timeout doesn't work)
            # Set to execution timeout + 60s buffer, in 5s poll intervals
            # This catches edge cases where the background task gets stuck
            if poll_count > max_poll_count:
                timeout_minutes = config.timeout_seconds // 60
                logger.error(f"[trace={trace_id}] Task {task_id} polling timed out after {poll_count} polls (should have been caught by thread pool timeout)")
                _report_subagent_usage(runtime, result)
                usage = _summarize_usage(getattr(result, "token_usage_records", None))
                _cache_subagent_usage(tool_call_id, usage, enabled=cache_token_usage)
                writer({"type": "task_timed_out", "task_id": task_id, "usage": usage})
                # The task may still be running in the background. Signal cooperative
                # cancellation and schedule deferred cleanup to remove the entry from
                # _background_tasks once the background thread reaches a terminal state.
                request_cancel_background_task(task_id)
                _schedule_deferred_subagent_cleanup(task_id, trace_id, max_poll_count)
                return f"Task polling timed out after {timeout_minutes} minutes. This may indicate the background task is stuck. Status: {result.status.value}"
    except asyncio.CancelledError:
        # Signal the background subagent thread to stop cooperatively.
        request_cancel_background_task(task_id)

        # Wait (shielded) for the subagent to reach a terminal state so the
        # final token usage snapshot is reported to the parent RunJournal
        # before the parent worker persists get_completion_data().
        terminal_result = None
        try:
            terminal_result = await asyncio.shield(_await_subagent_terminal(task_id, max_poll_count))
        except asyncio.CancelledError:
            pass

        # Report whatever the subagent collected (even if we timed out).
        final_result = terminal_result or get_background_task_result(task_id)
        if final_result is not None:
            _report_subagent_usage(runtime, final_result)
        if final_result is not None and _is_subagent_terminal(final_result):
            cleanup_background_task(task_id)
        else:
            _schedule_deferred_subagent_cleanup(task_id, trace_id, max_poll_count)
        _subagent_usage_cache.pop(tool_call_id, None)
        raise
    except Exception:
        _subagent_usage_cache.pop(tool_call_id, None)
        raise
