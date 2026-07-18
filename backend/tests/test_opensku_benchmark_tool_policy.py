from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.gateway.services import merge_run_context_overrides
from deerflow.agents.lead_agent import agent as lead_agent_module
from deerflow.config.app_config import AppConfig
from deerflow.config.model_config import ModelConfig
from deerflow.config.sandbox_config import SandboxConfig
from deerflow.skills.tool_policy import filter_tools_by_runtime_constraints, runtime_disables_external_search


def _tool(name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name)


def _tool_names(tools: list[SimpleNamespace]) -> list[str]:
    return [tool.name for tool in tools]


def _make_app_config() -> AppConfig:
    return AppConfig(
        models=[
            ModelConfig(
                name="safe-model",
                display_name="safe-model",
                description=None,
                use="langchain_openai:ChatOpenAI",
                model="safe-model",
                supports_thinking=False,
                supports_vision=False,
            )
        ],
        sandbox=SandboxConfig(use="deerflow.sandbox.local:LocalSandboxProvider"),
    )


def test_opensku_benchmark_fixture_mode_filters_external_search_tools():
    tools = [
        _tool("web_search"),
        _tool("web_fetch"),
        _tool("image_search"),
        _tool("read_file"),
        _tool("write_file"),
        _tool("present_files"),
        _tool("task"),
    ]

    filtered = filter_tools_by_runtime_constraints(
        tools,
        {"opensku_benchmark_fixture_mode": True},
    )

    assert _tool_names(filtered) == ["read_file", "write_file", "present_files", "task"]


def test_disable_external_search_filters_same_tool_surface():
    tools = [_tool("web_search"), _tool("web_fetch"), _tool("image_search"), _tool("read_file")]

    assert runtime_disables_external_search({"disable_external_search": True}) is True
    assert runtime_disables_external_search({"opensku_benchmark_fixture_mode": True}) is True
    assert runtime_disables_external_search({"disable_external_search": False}) is False
    assert _tool_names(filter_tools_by_runtime_constraints(tools, {"disable_external_search": True})) == ["read_file"]


def test_gateway_forwards_opensku_benchmark_tool_policy_context():
    config: dict = {}

    merge_run_context_overrides(
        config,
        {
            "opensku_benchmark_fixture_mode": True,
            "disable_external_search": True,
        },
    )

    assert config["configurable"]["opensku_benchmark_fixture_mode"] is True
    assert config["context"]["opensku_benchmark_fixture_mode"] is True
    assert config["configurable"]["disable_external_search"] is True
    assert config["context"]["disable_external_search"] is True


def test_make_lead_agent_removes_external_search_before_tool_binding(monkeypatch):
    app_config = _make_app_config()
    raw_tools = [
        _tool("web_search"),
        _tool("web_fetch"),
        _tool("image_search"),
        _tool("read_file"),
        _tool("write_file"),
        _tool("present_files"),
        _tool("task"),
    ]

    import deerflow.tools as tools_module

    monkeypatch.setattr(lead_agent_module, "get_app_config", lambda: app_config)
    monkeypatch.setattr(tools_module, "get_available_tools", MagicMock(return_value=raw_tools))
    monkeypatch.setattr(lead_agent_module, "_load_enabled_skills_for_tool_policy", lambda available, *, app_config: [])
    monkeypatch.setattr(lead_agent_module, "build_middlewares", lambda config, model_name, agent_name=None, **kwargs: [])
    monkeypatch.setattr(
        lead_agent_module,
        "create_chat_model",
        lambda **kwargs: object(),
    )
    monkeypatch.setattr(lead_agent_module, "create_agent", lambda **kwargs: kwargs)

    graph = lead_agent_module._make_lead_agent(
        {
            "context": {
                "model_name": "safe-model",
                "subagent_enabled": True,
                "opensku_benchmark_fixture_mode": True,
            }
        },
        app_config=app_config,
    )

    assert _tool_names(graph["tools"]) == ["read_file", "write_file", "present_files", "task"]
