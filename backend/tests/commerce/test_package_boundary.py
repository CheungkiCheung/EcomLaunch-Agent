"""Deterministic package-boundary contracts for Commerce Case Agent."""

from __future__ import annotations

import importlib

import pytest


@pytest.mark.parametrize(
    "module_name",
    (
        "app.commerce",
        "app.commerce.api",
        "app.commerce.agents",
        "app.commerce.data",
        "app.commerce.domain",
        "app.commerce.metrics",
        "app.commerce.persistence",
    ),
)
def test_commerce_package_is_importable(module_name: str):
    module = importlib.import_module(module_name)

    assert module.__name__ == module_name
