import logging
from collections.abc import Mapping
from typing import Protocol

from deerflow.skills.types import Skill

logger = logging.getLogger(__name__)

EXTERNAL_SEARCH_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "web_search",
        "web_fetch",
        "image_search",
    }
)


class NamedTool(Protocol):
    name: str


def allowed_tool_names_for_skills(skills: list[Skill]) -> set[str] | None:
    """Return the union of explicit skill allowed-tools declarations.

    None means legacy allow-all behavior. It is returned only when no loaded
    skill declares allowed-tools. Once any skill declares the field, legacy
    skills without the field contribute no tools instead of disabling the
    explicit restrictions from other skills.
    """
    if not skills:
        return None

    allowed: set[str] = set()
    has_explicit_declaration = False
    for skill in skills:
        if skill.allowed_tools is None:
            continue
        has_explicit_declaration = True
        if not skill.allowed_tools:
            logger.info("Skill %s declared empty allowed-tools", skill.name)
        allowed.update(skill.allowed_tools)

    if not has_explicit_declaration:
        return None
    return allowed


def filter_tools_by_skill_allowed_tools[ToolT: NamedTool](tools: list[ToolT], skills: list[Skill]) -> list[ToolT]:
    allowed = allowed_tool_names_for_skills(skills)
    if allowed is None:
        return tools

    return [tool for tool in tools if tool.name in allowed]


def runtime_disables_external_search(runtime_config: Mapping[str, object] | None) -> bool:
    """Return whether this run should hide external search tools.

    ``disable_external_search`` is the generic switch. ``opensku_benchmark_fixture_mode``
    is an OpenSKU eval/product mode that must be fixture-only, so it implies the
    generic switch.
    """
    if not runtime_config:
        return False
    return bool(
        runtime_config.get("disable_external_search")
        or runtime_config.get("opensku_benchmark_fixture_mode")
    )


def filter_tools_by_runtime_constraints[ToolT: NamedTool](
    tools: list[ToolT],
    runtime_config: Mapping[str, object] | None,
) -> list[ToolT]:
    """Apply run-scoped tool restrictions after skill policy filtering."""
    if not runtime_disables_external_search(runtime_config):
        return tools

    filtered = [tool for tool in tools if tool.name not in EXTERNAL_SEARCH_TOOL_NAMES]
    removed = len(tools) - len(filtered)
    if removed:
        logger.info("Runtime external-search gate removed %s tool(s)", removed)
    return filtered
