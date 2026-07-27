"""Deterministic package-boundary contracts for Commerce Case Agent."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "module_name",
    (
        "app.commerce",
        "app.commerce.api",
        "app.commerce.agents",
        "app.commerce.chat",
        "app.commerce.data",
        "app.commerce.domain",
        "app.commerce.evaluation",
        "app.commerce.metrics",
        "app.commerce.persistence",
        "app.commerce.tools",
    ),
)
def test_commerce_package_is_importable(module_name: str):
    module = importlib.import_module(module_name)

    assert module.__name__ == module_name


def test_deerflow_harness_has_no_commerce_imports():
    harness_root = Path(__file__).parents[2] / "packages" / "harness" / "deerflow"
    forbidden: list[str] = []
    for source_path in harness_root.rglob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        for node in ast.walk(tree):
            imported = None
            if isinstance(node, ast.Import):
                imported = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported = (node.module,)
            if imported and any(name == "app" or name.startswith("app.") for name in imported):
                forbidden.append(f"{source_path}:{','.join(imported)}")

    assert forbidden == []
