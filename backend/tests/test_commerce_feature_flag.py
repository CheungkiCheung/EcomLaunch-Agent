"""Deterministic contract tests for the Commerce Case Agent feature flag.

These tests only validate application configuration parsing. They do not
exercise an LLM or Agent path and therefore must remain model-free.
"""

from __future__ import annotations

import app.gateway.config as gateway_config


def _reload_config() -> gateway_config.GatewayConfig:
    gateway_config._gateway_config = None
    return gateway_config.get_gateway_config()


def test_commerce_case_agent_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("COMMERCE_CASE_AGENT_ENABLED", raising=False)

    config = _reload_config()

    assert config.commerce_case_agent_enabled is False


def test_commerce_case_agent_requires_explicit_true(monkeypatch):
    for value in ("false", "0", "yes", "on", "unexpected"):
        monkeypatch.setenv("COMMERCE_CASE_AGENT_ENABLED", value)

        config = _reload_config()

        assert config.commerce_case_agent_enabled is False


def test_commerce_case_agent_true_is_case_insensitive(monkeypatch):
    for value in ("true", "TRUE", "True"):
        monkeypatch.setenv("COMMERCE_CASE_AGENT_ENABLED", value)

        config = _reload_config()

        assert config.commerce_case_agent_enabled is True


def test_commerce_router_is_not_mounted_when_disabled(monkeypatch):
    monkeypatch.delenv("COMMERCE_CASE_AGENT_ENABLED", raising=False)
    _reload_config()

    from app.gateway.app import create_app

    app = create_app()

    assert not any(route.path == "/api/commerce/cases" for route in app.routes)


def test_commerce_router_is_mounted_only_when_enabled(monkeypatch):
    monkeypatch.setenv("COMMERCE_CASE_AGENT_ENABLED", "true")
    _reload_config()

    from app.gateway.app import create_app

    app = create_app()

    assert any(route.path == "/api/commerce/cases" for route in app.routes)
