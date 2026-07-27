"""Shared fixtures for real dynamic Commerce Chat release gates."""

from __future__ import annotations

import importlib
import sys

import pytest


@pytest.fixture
def real_executor_module(monkeypatch):
    """Replace the suite-wide circular-import mock with the real executor."""

    __import__("deerflow.agents")
    package = importlib.import_module("deerflow.subagents")
    module_name = "deerflow.subagents.executor"
    original_module = sys.modules.get(module_name)
    original_attribute = getattr(package, "executor", None)
    sys.modules.pop(module_name, None)
    if hasattr(package, "executor"):
        delattr(package, "executor")
    module = importlib.import_module(module_name)

    from deerflow.tools.builtins import durable_task_tools

    monkeypatch.setattr(
        durable_task_tools,
        "SubagentExecutor",
        module.SubagentExecutor,
    )
    try:
        yield module
    finally:
        sys.modules.pop(module_name, None)
        if original_module is not None:
            sys.modules[module_name] = original_module
        if original_attribute is not None:
            setattr(package, "executor", original_attribute)
