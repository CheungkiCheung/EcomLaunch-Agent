"""Lazy public Tool exports that keep low-level Tool types importable alone."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = ["get_available_tools", "skill_manage_tool"]

_EXPORTS = {
    "get_available_tools": ("deerflow.tools.tools", "get_available_tools"),
    "skill_manage_tool": ("deerflow.tools.skill_manage_tool", "skill_manage_tool"),
}


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = target
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *__all__})
