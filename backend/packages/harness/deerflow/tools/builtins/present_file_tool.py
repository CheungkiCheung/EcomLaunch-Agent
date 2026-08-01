from pathlib import Path
from typing import Annotated

from langchain.tools import InjectedToolCallId, tool
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.config import get_config
from langgraph.types import Command

from deerflow.agents.middlewares.run_budget_middleware import INTERNAL_HUMAN_MESSAGE_NAMES
from deerflow.config.paths import VIRTUAL_PATH_PREFIX, get_paths
from deerflow.runtime.user_context import get_effective_user_id
from deerflow.tools.builtins.launch_pack_guard import prepare_launch_pack_for_audit, validate_launch_pack
from deerflow.tools.types import Runtime

OUTPUTS_VIRTUAL_PREFIX = f"{VIRTUAL_PATH_PREFIX}/outputs"
RUN_BUDGET_CONTEXT_KEY = "__deerflow_agent_run_budget"


def _message_text(message: object) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "\n".join(
        block if isinstance(block, str) else block.get("text", "")
        for block in content
        if isinstance(block, str) or (isinstance(block, dict) and isinstance(block.get("text"), str))
    )


def _latest_user_request_text(runtime: Runtime) -> str:
    messages = runtime.state.get("messages") if runtime.state else None
    if not isinstance(messages, (list, tuple)):
        return ""
    for message in reversed(messages):
        if isinstance(message, HumanMessage) and message.name not in INTERNAL_HUMAN_MESSAGE_NAMES:
            return _message_text(message)
    return ""


def _get_thread_id(runtime: Runtime) -> str | None:
    """Resolve the current thread id from runtime context or RunnableConfig."""
    thread_id = runtime.context.get("thread_id") if runtime.context else None
    if thread_id:
        return thread_id

    runtime_config = getattr(runtime, "config", None) or {}
    thread_id = runtime_config.get("configurable", {}).get("thread_id")
    if thread_id:
        return thread_id

    try:
        return get_config().get("configurable", {}).get("thread_id")
    except RuntimeError:
        return None


def _normalize_presented_filepath(
    runtime: Runtime,
    filepath: str,
) -> str:
    """Normalize a presented file path to the `/mnt/user-data/outputs/*` contract.

    Accepts either:
    - A virtual sandbox path such as `/mnt/user-data/outputs/report.md`
    - A host-side thread outputs path such as
      `/app/backend/.deer-flow/threads/<thread>/user-data/outputs/report.md`

    Returns:
        The normalized virtual path.

    Raises:
        ValueError: If runtime metadata is missing or the path is outside the
            current thread's outputs directory.
    """
    if runtime.state is None:
        raise ValueError("Thread runtime state is not available")

    thread_id = _get_thread_id(runtime)
    if not thread_id:
        raise ValueError("Thread ID is not available in runtime context or runtime config")

    thread_data = runtime.state.get("thread_data") or {}
    outputs_path = thread_data.get("outputs_path")
    if not outputs_path:
        raise ValueError("Thread outputs path is not available in runtime state")

    outputs_dir = Path(outputs_path).resolve()
    stripped = filepath.lstrip("/")
    virtual_prefix = VIRTUAL_PATH_PREFIX.lstrip("/")

    if stripped == virtual_prefix or stripped.startswith(virtual_prefix + "/"):
        try:
            actual_path = get_paths().resolve_virtual_path(thread_id, filepath, user_id=get_effective_user_id())
        except TypeError:
            actual_path = get_paths().resolve_virtual_path(thread_id, filepath)
    else:
        actual_path = Path(filepath).expanduser().resolve()

    try:
        relative_path = actual_path.relative_to(outputs_dir)
    except ValueError as exc:
        raise ValueError(f"Only files in {OUTPUTS_VIRTUAL_PREFIX} can be presented: {filepath}") from exc

    return f"{OUTPUTS_VIRTUAL_PREFIX}/{relative_path.as_posix()}"


def _complete_pack_preflight(runtime: Runtime, filepaths: list[str]) -> list[str]:
    """Run configured terminal checks only when the complete filename set is presented."""
    context = getattr(runtime, "context", None)
    if not isinstance(context, dict):
        return []
    budget_state = context.get(RUN_BUDGET_CONTEXT_KEY)
    if not isinstance(budget_state, dict):
        return []
    budget_config = budget_state.get("config")
    if not isinstance(budget_config, dict):
        return []

    required_files = budget_config.get("required_output_files")
    if not isinstance(required_files, list) or not required_files:
        return []
    required_names = {name for name in required_files if isinstance(name, str) and name}
    presented_names = {Path(filepath).name for filepath in filepaths}
    if not required_names or not required_names.issubset(presented_names):
        return []

    issues: list[str] = []
    required_subagents = budget_config.get("required_completed_subagents")
    if isinstance(required_subagents, list):
        completed_subagents = budget_state.get("subagent_types_completed", set())
        if not isinstance(completed_subagents, set):
            completed_subagents = set(completed_subagents) if isinstance(completed_subagents, (list, tuple)) else set()
        missing_subagents = sorted(
            name for name in required_subagents if isinstance(name, str) and name and name not in completed_subagents
        )
        if missing_subagents:
            issues.append(f"configured specialist(s) have not completed for this user request: {', '.join(missing_subagents)}")

    if budget_config.get("require_evidence_checker") and not budget_state.get("evidence_checker_completed"):
        issues.append("the configured evidence-checker did not return a valid pass/revise/blocked verdict for this user request")
    if budget_config.get("require_evidence_checker") and budget_state.get("evidence_checker_verdict") == "blocked":
        issues.append("the configured evidence-checker returned blocked and did not authorize delivery")

    if budget_config.get("validate_pack_before_present"):
        thread_data = runtime.state.get("thread_data") if runtime.state else None
        outputs_path = thread_data.get("outputs_path") if isinstance(thread_data, dict) else None
        if not outputs_path:
            issues.append("thread outputs path is unavailable for launch-pack validation")
        else:
            resolved_outputs = Path(outputs_path).resolve()
            user_request = _latest_user_request_text(runtime)
            if not budget_config.get("require_evidence_checker"):
                prepare_launch_pack_for_audit(
                    resolved_outputs,
                    list(required_names),
                    user_request=user_request,
                )
            issues.extend(
                validate_launch_pack(
                    resolved_outputs,
                    list(required_names),
                    user_request=user_request,
                )
            )
    return issues


@tool("present_files", parse_docstring=True)
def present_file_tool(
    runtime: Runtime,
    filepaths: list[str],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Make files visible to the user for viewing and rendering in the client interface.

    When to use the present_files tool:

    - Making any file available for the user to view, download, or interact with
    - Presenting multiple related files at once
    - After creating files that should be presented to the user

    When NOT to use the present_files tool:
    - When you only need to read file contents for your own processing
    - For temporary or intermediate files not meant for user viewing

    Notes:
    - You should call this tool after creating files and moving them to the `/mnt/user-data/outputs` directory.
    - This tool can be safely called in parallel with other tools. State updates are handled by a reducer to prevent conflicts.

    Args:
        filepaths: List of absolute file paths to present to the user. **Only** files in `/mnt/user-data/outputs` can be presented.
    """
    preflight_issues = _complete_pack_preflight(runtime, filepaths)
    if preflight_issues:
        formatted = "\n".join(f"- {issue}" for issue in preflight_issues)
        return Command(
            update={"messages": [ToolMessage(f"Error: Launch Pack preflight blocked delivery:\n{formatted}", tool_call_id=tool_call_id, status="error")]},
        )

    try:
        normalized_paths = [_normalize_presented_filepath(runtime, filepath) for filepath in filepaths]
    except ValueError as exc:
        return Command(
            update={"messages": [ToolMessage(f"Error: {exc}", tool_call_id=tool_call_id, status="error")]},
        )

    # The merge_artifacts reducer will handle merging and deduplication
    return Command(
        update={
            "artifacts": normalized_paths,
            "messages": [ToolMessage("Successfully presented files", tool_call_id=tool_call_id, status="success")],
        },
    )
