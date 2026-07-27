"""Public DeerFlow Agent exports without eager graph assembly imports."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "create_deerflow_agent",
    "RuntimeFeatures",
    "Next",
    "Prev",
    "make_lead_agent",
    "SandboxState",
    "ThreadState",
]

_EXPORTS = {
    "create_deerflow_agent": ("deerflow.agents.factory", "create_deerflow_agent"),
    "RuntimeFeatures": ("deerflow.agents.features", "RuntimeFeatures"),
    "Next": ("deerflow.agents.features", "Next"),
    "Prev": ("deerflow.agents.features", "Prev"),
    "make_lead_agent": ("deerflow.agents.lead_agent", "make_lead_agent"),
    "SandboxState": ("deerflow.agents.thread_state", "SandboxState"),
    "ThreadState": ("deerflow.agents.thread_state", "ThreadState"),
}


def __getattr__(name: str) -> Any:
    """Load heavy Agent factories only when the public symbol is requested."""

    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = target
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    if name in {"create_deerflow_agent", "make_lead_agent"}:
        prompt = import_module("deerflow.agents.lead_agent.prompt")
        prompt.prime_enabled_skills_cache()
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *__all__})
