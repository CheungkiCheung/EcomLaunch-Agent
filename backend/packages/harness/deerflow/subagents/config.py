"""Subagent configuration definitions."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from deerflow.config.app_config import AppConfig


@dataclass
class SubagentConfig:
    """Configuration for a subagent.

    Attributes:
        name: Unique identifier for the subagent.
        description: When Claude should delegate to this subagent.
        system_prompt: The system prompt that guides the subagent's behavior.
        tools: Optional list of tool names to allow. If None, inherits all tools.
        disallowed_tools: Optional list of tool names to deny.
        skills: Optional list of skill names to load. If None, inherits all enabled skills.
                If an empty list, no skills are loaded.
        model: Model to use - 'inherit' uses parent's model.
        max_turns: Maximum number of agent turns before stopping.
        max_tool_rounds: Optional model-to-tool round budget. Parallel calls in
            one model response consume one round.
        max_tool_calls: Optional total deterministic Tool call budget. Parallel
            calls each consume one call.
        min_successful_tool_calls: Minimum successful ToolResult events required
            before the execution may be marked completed.
        timeout_seconds: Maximum execution time in seconds (default: 900 = 15 minutes).
        max_output_tokens: Optional per-model-call output limit.
        model_max_retries: Optional provider-client retry limit.
        llm_retry_max_attempts: Harness middleware attempt limit, including the first call.
    """

    name: str
    description: str
    system_prompt: str | None = None
    tools: list[str] | None = None
    disallowed_tools: list[str] | None = field(
        default_factory=lambda: [
            "task",
            "spawn_task",
            "wait_task",
            "follow_up_task",
            "cancel_task",
            "resume_task",
        ]
    )
    skills: list[str] | None = None
    model: str = "inherit"
    max_turns: int = 50
    max_tool_rounds: int | None = None
    max_tool_calls: int | None = None
    min_successful_tool_calls: int = 0
    timeout_seconds: int = 900
    max_output_tokens: int | None = None
    model_max_retries: int | None = None
    llm_retry_max_attempts: int = 3


def _default_model_name(app_config: "AppConfig") -> str:
    if not app_config.models:
        raise ValueError("No chat models are configured. Please configure at least one model in config.yaml.")
    return app_config.models[0].name


def resolve_subagent_model_name(config: SubagentConfig, parent_model: str | None, *, app_config: "AppConfig | None" = None) -> str:
    """Resolve the effective model name a subagent should use."""
    if config.model != "inherit":
        return config.model

    if parent_model is not None:
        return parent_model

    if app_config is None:
        from deerflow.config import get_app_config

        app_config = get_app_config()
    return _default_model_name(app_config)
