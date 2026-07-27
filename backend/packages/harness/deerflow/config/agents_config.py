"""Configuration and loaders for custom agents.

Custom agents are stored per-user under ``{base_dir}/users/{user_id}/agents/{name}/``.
A legacy shared layout at ``{base_dir}/agents/{name}/`` is still readable so that
installations that pre-date user isolation continue to work until they run the
``scripts/migrate_user_isolation.py`` migration. New writes always target the
per-user layout.
"""

import logging
import os
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

from deerflow.config.paths import get_paths
from deerflow.config.runtime_paths import project_root
from deerflow.runtime.user_context import get_effective_user_id

logger = logging.getLogger(__name__)

SOUL_FILENAME = "SOUL.md"
AGENT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9-]+$")
BUILTIN_AGENTS_DIRNAME = "agents"


def _is_agent_definition_dir(path: Path) -> bool:
    """Return whether a directory contains an agent definition.

    Runtime may create ``users/{id}/agents/{name}/memory.json`` for a built-in
    agent. That memory-only directory must not shadow the repository-shipped
    agent definition.
    """
    return path.is_dir() and (path / "config.yaml").is_file()


def validate_agent_name(name: str | None) -> str | None:
    """Validate a custom agent name before using it in filesystem paths."""
    if name is None:
        return None
    if not isinstance(name, str):
        raise ValueError("Invalid agent name. Expected a string or None.")
    if not AGENT_NAME_PATTERN.fullmatch(name):
        raise ValueError(f"Invalid agent name '{name}'. Must match pattern: {AGENT_NAME_PATTERN.pattern}")
    return name


def builtin_agents_dir() -> Path:
    """Return the read-only repository directory for built-in agent definitions.

    ``project_root()`` is intentionally caller-relative for standalone harness
    usage. In the monorepo, however, developers often start the Gateway from
    ``backend/`` while repository-shipped agents live one level up at
    ``../agents``. If ``DEER_FLOW_PROJECT_ROOT`` is explicitly set, respect it
    as authoritative; otherwise fall back to the parent repository root for that
    common local-dev startup path.
    """
    root = project_root()
    project_default = root / BUILTIN_AGENTS_DIRNAME
    if project_default.is_dir():
        return project_default

    if os.getenv("DEER_FLOW_PROJECT_ROOT"):
        return project_default

    if root.name == "backend":
        repo_root_candidate = root.parent / BUILTIN_AGENTS_DIRNAME
        if repo_root_candidate.is_dir():
            return repo_root_candidate

    return project_default


def builtin_agent_dir(name: str) -> Path:
    """Return the read-only built-in definition directory for an agent name."""
    return builtin_agents_dir() / name.lower()


def is_builtin_agent(name: str, *, user_id: str | None = None) -> bool:
    """Return True when agent resolution lands on the repository built-in copy."""
    name = validate_agent_name(name)
    if name is None:
        return False
    return resolve_agent_dir(name, user_id=user_id).resolve() == builtin_agent_dir(name).resolve()


class AgentLocalTitleRule(BaseModel):
    """Deterministic, agent-configured title rule used without an LLM call."""

    keywords: list[str] = Field(min_length=1)
    title: str = Field(min_length=1)


class AgentSubagentScopeRule(BaseModel):
    """Config-driven least-privilege normalization for matching spawn_task calls."""

    name: str = Field(min_length=1)
    subagent_type: str = Field(min_length=1)
    match_skills_all: list[str] = Field(default_factory=list)
    prompt_keywords_any: list[str] = Field(default_factory=list)
    enforced_skills: list[str] = Field(min_length=1)
    enforced_tools: list[str] = Field(min_length=1)
    inherit_source_tools: bool = False
    prompt_suffix: str | None = Field(default=None, min_length=1)
    max_tool_rounds: int = Field(ge=1, le=64)
    max_tool_calls: int = Field(ge=1, le=256)


class AgentConfig(BaseModel):
    """Configuration for a custom agent."""

    name: str
    description: str = ""
    model: str | None = None
    tool_groups: list[str] | None = None
    subagent_required: bool = False
    subagent_complexity_tool_call_threshold: int = Field(default=2, ge=1, le=100)
    required_subagent_types: list[str] = Field(default_factory=list)
    subagent_requirement_recovery_mode: Literal["remind", "force_dispatch"] = "remind"
    max_subagent_requirement_recovery_attempts: int = Field(
        default=8,
        ge=1,
        le=32,
    )
    max_concurrent_subagents: int = Field(default=3, ge=1, le=20)
    max_subagent_tasks_per_run: int | None = Field(
        default=None,
        ge=1,
        le=256,
    )
    max_failed_subagent_tasks_per_run: int | None = Field(
        default=None,
        ge=1,
        le=256,
    )
    max_parent_direct_tool_calls: int | None = Field(
        default=None,
        ge=1,
        le=256,
    )
    max_parent_direct_tool_rounds: int | None = Field(
        default=None,
        ge=1,
        le=64,
    )
    require_explicit_subagent_scope: bool = False
    todo_list_enabled: bool = True
    memory_enabled: bool = True
    model_generated_title: bool = True
    local_title_rules: list[AgentLocalTitleRule] = Field(default_factory=list)
    local_title_fallback: str | None = None
    subagent_scope_rules: list[AgentSubagentScopeRule] = Field(default_factory=list)
    final_answer_forbidden_phrases: list[str] = Field(default_factory=list)
    max_final_answer_repairs: int = Field(default=1, ge=1, le=3)
    # skills controls which skills are loaded into the agent's prompt:
    # - None (or omitted): load all enabled skills (default fallback behavior)
    # - [] (explicit empty list): disable all skills
    # - ["skill1", "skill2"]: load only the specified skills
    skills: list[str] | None = None


def resolve_agent_dir(name: str, *, user_id: str | None = None) -> Path:
    """Return the on-disk directory for an agent, preferring the per-user layout.

    Resolution order:
    1. ``{base_dir}/users/{user_id}/agents/{name}/`` (per-user, current layout).
    2. ``{base_dir}/agents/{name}/`` (legacy shared layout — read-only fallback).
    3. ``{project_root}/agents/{name}/`` (repository-shipped built-in fallback).

    If neither exists, the per-user path is returned so callers that intend to
    create the agent write into the new layout.

    Args:
        name: Validated agent name.
        user_id: Owner of the agent. Defaults to the effective user from the
            request context (or ``"default"`` in no-auth mode).
    """
    paths = get_paths()
    effective_user = user_id or get_effective_user_id()
    user_path = paths.user_agent_dir(effective_user, name)
    if _is_agent_definition_dir(user_path):
        return user_path

    legacy_path = paths.agent_dir(name)
    if _is_agent_definition_dir(legacy_path):
        return legacy_path

    builtin_path = builtin_agent_dir(name)
    if _is_agent_definition_dir(builtin_path):
        return builtin_path

    return user_path


def load_agent_config(name: str | None, *, user_id: str | None = None) -> AgentConfig | None:
    """Load the custom or default agent's config from its directory.

    Reads from the per-user layout first; falls back to the legacy shared layout
    for installations that have not yet been migrated.

    Args:
        name: The agent name.
        user_id: Owner of the agent. Defaults to the effective user from the
            current request context.

    Returns:
        AgentConfig instance, or ``None`` if ``name`` is ``None``.

    Raises:
        FileNotFoundError: If the agent directory or config.yaml does not exist.
        ValueError: If config.yaml cannot be parsed.
    """

    if name is None:
        return None

    name = validate_agent_name(name)
    agent_dir = resolve_agent_dir(name, user_id=user_id)
    config_file = agent_dir / "config.yaml"

    if not agent_dir.exists():
        raise FileNotFoundError(f"Agent directory not found: {agent_dir}")

    if not config_file.exists():
        raise FileNotFoundError(f"Agent config not found: {config_file}")

    try:
        with open(config_file, encoding="utf-8") as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse agent config {config_file}: {e}") from e

    # Ensure name is set from directory name if not in file
    if "name" not in data:
        data["name"] = name

    # Strip unknown fields before passing to Pydantic (e.g. legacy prompt_file)
    known_fields = set(AgentConfig.model_fields.keys())
    data = {k: v for k, v in data.items() if k in known_fields}

    return AgentConfig(**data)


def load_agent_soul(agent_name: str | None, *, user_id: str | None = None) -> str | None:
    """Read the SOUL.md file for a custom agent, if it exists.

    SOUL.md defines the agent's personality, values, and behavioral guardrails.
    It is injected into the lead agent's system prompt as additional context.

    Args:
        agent_name: The name of the agent or None for the default agent.
        user_id: Owner of the agent. Defaults to the effective user from the
            current request context.

    Returns:
        The SOUL.md content as a string, or None if the file does not exist.
    """
    if agent_name:
        agent_dir = resolve_agent_dir(agent_name, user_id=user_id)
    else:
        agent_dir = get_paths().base_dir
    soul_path = agent_dir / SOUL_FILENAME
    if not soul_path.exists():
        return None
    content = soul_path.read_text(encoding="utf-8").strip()
    return content or None


def list_custom_agents(*, user_id: str | None = None) -> list[AgentConfig]:
    """Scan the agents directory and return all valid custom agents.

    Returns the union of agents in the per-user layout and the legacy shared
    layout, so that pre-migration installations remain visible until they are
    migrated. Per-user entries shadow legacy entries with the same name.

    Args:
        user_id: Owner whose agents to list. Defaults to the effective user
            from the current request context.

    Returns:
        List of AgentConfig for each valid agent directory found.
    """
    paths = get_paths()
    effective_user = user_id or get_effective_user_id()

    seen: set[str] = set()
    agents: list[AgentConfig] = []

    user_root = paths.user_agents_dir(effective_user)
    legacy_root = paths.agents_dir
    builtin_root = builtin_agents_dir()

    for root in (user_root, legacy_root, builtin_root):
        if not root.exists():
            continue
        for entry in sorted(root.iterdir()):
            if not entry.is_dir():
                continue
            if entry.name in seen:
                continue
            config_file = entry / "config.yaml"
            if not config_file.exists():
                logger.debug(f"Skipping {entry.name}: no config.yaml")
                continue

            try:
                agent_cfg = load_agent_config(entry.name, user_id=effective_user)
                if agent_cfg is None:
                    continue
                agents.append(agent_cfg)
                seen.add(entry.name)
            except Exception as e:
                logger.warning(f"Skipping agent '{entry.name}': {e}")

    agents.sort(key=lambda a: a.name)
    return agents
