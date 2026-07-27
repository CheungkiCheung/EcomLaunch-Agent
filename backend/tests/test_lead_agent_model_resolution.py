"""Tests for lead agent runtime model resolution behavior."""

from __future__ import annotations

import inspect
from unittest.mock import MagicMock

import pytest

from deerflow.agents.lead_agent import agent as lead_agent_module
from deerflow.agents.middlewares.final_answer_policy_middleware import (
    FinalAnswerPolicyMiddleware,
)
from deerflow.agents.middlewares.loop_detection_middleware import LoopDetectionMiddleware
from deerflow.agents.middlewares.parent_direct_tool_budget_middleware import (
    ParentDirectToolBudgetMiddleware,
)
from deerflow.agents.middlewares.subagent_dispatch_policy_middleware import (
    SubagentDispatchPolicyMiddleware,
)
from deerflow.agents.middlewares.subagent_requirement_middleware import (
    SubagentRequirementMiddleware,
)
from deerflow.config.agents_config import AgentConfig
from deerflow.config.app_config import AppConfig
from deerflow.config.loop_detection_config import LoopDetectionConfig
from deerflow.config.memory_config import MemoryConfig
from deerflow.config.model_config import ModelConfig
from deerflow.config.sandbox_config import SandboxConfig
from deerflow.config.summarization_config import SummarizationConfig


def _make_app_config(models: list[ModelConfig], loop_detection: LoopDetectionConfig | None = None) -> AppConfig:
    return AppConfig(
        models=models,
        sandbox=SandboxConfig(use="deerflow.sandbox.local:LocalSandboxProvider"),
        loop_detection=loop_detection or LoopDetectionConfig(),
    )


def _make_model(name: str, *, supports_thinking: bool) -> ModelConfig:
    return ModelConfig(
        name=name,
        display_name=name,
        description=None,
        use="langchain_openai:ChatOpenAI",
        model=name,
        supports_thinking=supports_thinking,
        supports_vision=False,
    )


def test_make_lead_agent_signature_matches_langgraph_server_factory_abi():
    assert list(inspect.signature(lead_agent_module.make_lead_agent).parameters) == ["config"]


def test_make_lead_agent_attaches_tracing_callbacks_at_graph_root(monkeypatch):
    """Regression guard: tracing handlers must be appended to
    ``config["callbacks"]`` (graph invocation root), and every in-graph
    ``create_chat_model`` call must pass ``attach_tracing=False``.

    Catches future contributors who forget the flag when adding new
    in-graph model creation, which would silently produce duplicate
    spans and break Langfuse session/user propagation.
    """
    app_config = _make_app_config([_make_model("safe-model", supports_thinking=False)])

    import deerflow.tools as tools_module

    monkeypatch.setattr(lead_agent_module, "get_app_config", lambda: app_config)
    monkeypatch.setattr(tools_module, "get_available_tools", lambda **kwargs: [])
    monkeypatch.setattr(lead_agent_module, "build_middlewares", lambda config, model_name, agent_name=None, **kwargs: [])

    sentinel_handler = object()
    monkeypatch.setattr(lead_agent_module, "build_tracing_callbacks", lambda: [sentinel_handler])

    seen_attach_tracing: list[bool] = []

    def _fake_create_chat_model(*, name, thinking_enabled, reasoning_effort=None, app_config=None, attach_tracing=True):
        seen_attach_tracing.append(attach_tracing)
        return object()

    monkeypatch.setattr(lead_agent_module, "create_chat_model", _fake_create_chat_model)
    monkeypatch.setattr(lead_agent_module, "create_agent", lambda **kwargs: kwargs)

    config: dict = {"configurable": {"model_name": "safe-model"}}
    lead_agent_module._make_lead_agent(config, app_config=app_config)

    # Handler must land on the graph invocation config so the Langfuse
    # CallbackHandler fires ``on_chain_start(parent_run_id=None)`` and
    # propagates ``session_id`` / ``user_id`` onto the trace.
    assert sentinel_handler in (config.get("callbacks") or []), "build_tracing_callbacks output must be appended to config['callbacks']"

    # Every in-graph create_chat_model call must opt out of model-level
    # tracing to avoid duplicate spans.
    assert seen_attach_tracing, "_make_lead_agent did not call create_chat_model"
    assert all(flag is False for flag in seen_attach_tracing), f"in-graph create_chat_model must pass attach_tracing=False; got {seen_attach_tracing}"


def test_internal_make_lead_agent_uses_explicit_app_config(monkeypatch):
    app_config = _make_app_config([_make_model("explicit-model", supports_thinking=False)])

    import deerflow.tools as tools_module

    def _raise_get_app_config():
        raise AssertionError("ambient get_app_config() must not be used when app_config is explicit")

    monkeypatch.setattr(lead_agent_module, "get_app_config", _raise_get_app_config)
    monkeypatch.setattr(tools_module, "get_available_tools", lambda **kwargs: [])
    monkeypatch.setattr(lead_agent_module, "build_middlewares", lambda config, model_name, agent_name=None, **kwargs: [])

    captured: dict[str, object] = {}

    def _fake_create_chat_model(*, name, thinking_enabled, reasoning_effort=None, app_config=None, attach_tracing=True):
        captured["name"] = name
        captured["app_config"] = app_config
        return object()

    monkeypatch.setattr(lead_agent_module, "create_chat_model", _fake_create_chat_model)
    monkeypatch.setattr(lead_agent_module, "create_agent", lambda **kwargs: kwargs)

    result = lead_agent_module._make_lead_agent(
        {"configurable": {"model_name": "explicit-model"}},
        app_config=app_config,
    )

    assert captured == {
        "name": "explicit-model",
        "app_config": app_config,
    }
    assert result["model"] is not None


def test_make_lead_agent_uses_runtime_app_config_from_context_without_global_read(monkeypatch):
    app_config = _make_app_config([_make_model("context-model", supports_thinking=False)])

    import deerflow.tools as tools_module

    def _raise_get_app_config():
        raise AssertionError("ambient get_app_config() must not be used when runtime context already carries app_config")

    monkeypatch.setattr(lead_agent_module, "get_app_config", _raise_get_app_config)
    monkeypatch.setattr(tools_module, "get_available_tools", lambda **kwargs: [])
    monkeypatch.setattr(lead_agent_module, "build_middlewares", lambda config, model_name, agent_name=None, **kwargs: [])

    captured: dict[str, object] = {}

    def _fake_create_chat_model(*, name, thinking_enabled, reasoning_effort=None, app_config=None, attach_tracing=True):
        captured["name"] = name
        captured["app_config"] = app_config
        return object()

    monkeypatch.setattr(lead_agent_module, "create_chat_model", _fake_create_chat_model)
    monkeypatch.setattr(lead_agent_module, "create_agent", lambda **kwargs: kwargs)

    result = lead_agent_module.make_lead_agent(
        {
            "context": {
                "model_name": "context-model",
                "app_config": app_config,
            }
        }
    )

    assert captured == {
        "name": "context-model",
        "app_config": app_config,
    }
    assert result["model"] is not None


def test_resolve_model_name_falls_back_to_default(monkeypatch, caplog):
    app_config = _make_app_config(
        [
            _make_model("default-model", supports_thinking=False),
            _make_model("other-model", supports_thinking=True),
        ]
    )

    monkeypatch.setattr(lead_agent_module, "get_app_config", lambda: app_config)

    with caplog.at_level("WARNING"):
        resolved = lead_agent_module._resolve_model_name("missing-model")

    assert resolved == "default-model"
    assert "fallback to default model 'default-model'" in caplog.text


def test_resolve_model_name_uses_default_when_none(monkeypatch):
    app_config = _make_app_config(
        [
            _make_model("default-model", supports_thinking=False),
            _make_model("other-model", supports_thinking=True),
        ]
    )

    monkeypatch.setattr(lead_agent_module, "get_app_config", lambda: app_config)

    resolved = lead_agent_module._resolve_model_name(None)

    assert resolved == "default-model"


def test_resolve_model_name_raises_when_no_models_configured(monkeypatch):
    app_config = _make_app_config([])

    monkeypatch.setattr(lead_agent_module, "get_app_config", lambda: app_config)

    with pytest.raises(
        ValueError,
        match="No chat models are configured",
    ):
        lead_agent_module._resolve_model_name("missing-model")


def test_make_lead_agent_disables_thinking_when_model_does_not_support_it(monkeypatch):
    app_config = _make_app_config([_make_model("safe-model", supports_thinking=False)])

    import deerflow.tools as tools_module

    monkeypatch.setattr(lead_agent_module, "get_app_config", lambda: app_config)
    monkeypatch.setattr(tools_module, "get_available_tools", lambda **kwargs: [])
    monkeypatch.setattr(lead_agent_module, "build_middlewares", lambda config, model_name, agent_name=None, **kwargs: [])

    captured: dict[str, object] = {}

    def _fake_create_chat_model(*, name, thinking_enabled, reasoning_effort=None, app_config=None, attach_tracing=True):
        captured["name"] = name
        captured["thinking_enabled"] = thinking_enabled
        captured["reasoning_effort"] = reasoning_effort
        captured["app_config"] = app_config
        return object()

    monkeypatch.setattr(lead_agent_module, "create_chat_model", _fake_create_chat_model)
    monkeypatch.setattr(lead_agent_module, "create_agent", lambda **kwargs: kwargs)

    result = lead_agent_module.make_lead_agent(
        {
            "configurable": {
                "model_name": "safe-model",
                "thinking_enabled": True,
                "is_plan_mode": False,
                "subagent_enabled": False,
            }
        }
    )

    assert captured["name"] == "safe-model"
    assert captured["thinking_enabled"] is False
    assert captured["app_config"] is app_config
    assert result["model"] is not None


def test_make_lead_agent_reads_runtime_options_from_context(monkeypatch):
    app_config = _make_app_config(
        [
            _make_model("default-model", supports_thinking=False),
            _make_model("context-model", supports_thinking=True),
        ]
    )

    import deerflow.tools as tools_module

    get_available_tools = MagicMock(return_value=[])
    monkeypatch.setattr(lead_agent_module, "get_app_config", lambda: app_config)
    monkeypatch.setattr(tools_module, "get_available_tools", get_available_tools)
    monkeypatch.setattr(lead_agent_module, "build_middlewares", lambda config, model_name, agent_name=None, **kwargs: [])

    captured: dict[str, object] = {}

    def _fake_create_chat_model(*, name, thinking_enabled, reasoning_effort=None, app_config=None, attach_tracing=True):
        captured["name"] = name
        captured["thinking_enabled"] = thinking_enabled
        captured["reasoning_effort"] = reasoning_effort
        captured["app_config"] = app_config
        return object()

    monkeypatch.setattr(lead_agent_module, "create_chat_model", _fake_create_chat_model)
    monkeypatch.setattr(lead_agent_module, "create_agent", lambda **kwargs: kwargs)

    result = lead_agent_module.make_lead_agent(
        {
            "context": {
                "model_name": "context-model",
                "thinking_enabled": False,
                "reasoning_effort": "high",
                "is_plan_mode": True,
                "subagent_enabled": True,
                "max_concurrent_subagents": 7,
            }
        }
    )

    assert captured == {
        "name": "context-model",
        "thinking_enabled": False,
        "reasoning_effort": "high",
        "app_config": app_config,
    }
    get_available_tools.assert_called_once_with(model_name="context-model", groups=None, subagent_enabled=True, app_config=app_config)
    assert result["model"] is not None


def test_builtin_agent_can_require_subagent_harness_even_when_client_disables_it(
    monkeypatch,
):
    app_config = _make_app_config([_make_model("commerce-model", supports_thinking=True)])

    import deerflow.tools as tools_module

    get_available_tools = MagicMock(return_value=[])
    runtime_seen: dict[str, object] = {}
    prompt_seen: dict[str, object] = {}
    config: dict = {
        "configurable": {
            "agent_name": "commerce-agent",
            "subagent_enabled": False,
        }
    }

    monkeypatch.setattr(
        lead_agent_module,
        "load_agent_config",
        lambda name: AgentConfig(
            name="commerce-agent",
            model="commerce-model",
            tool_groups=["commerce"],
            skills=[],
            subagent_required=True,
            subagent_complexity_tool_call_threshold=2,
            required_subagent_types=["verifier"],
            max_concurrent_subagents=3,
            max_parent_direct_tool_calls=8,
            max_parent_direct_tool_rounds=6,
            require_explicit_subagent_scope=True,
            memory_enabled=False,
            model_generated_title=False,
            local_title_rules=[
                {
                    "keywords": ["履约", "延迟"],
                    "title": "订单履约异常诊断",
                }
            ],
            local_title_fallback="电商经营数据诊断",
            subagent_scope_rules=[
                {
                    "name": "fulfillment-verifier",
                    "subagent_type": "verifier",
                    "match_skills_all": ["fulfillment-investigation"],
                    "prompt_keywords_any": ["核验", "重算"],
                    "enforced_skills": ["fulfillment-investigation"],
                    "enforced_tools": ["commerce_evidence_query"],
                    "inherit_source_tools": True,
                    "max_tool_rounds": 2,
                    "max_tool_calls": 3,
                }
            ],
        ),
    )
    monkeypatch.setattr(lead_agent_module, "is_builtin_agent", lambda name: True)
    monkeypatch.setattr(tools_module, "get_available_tools", get_available_tools)
    monkeypatch.setattr(
        lead_agent_module,
        "_load_enabled_skills_for_tool_policy",
        lambda available_skills, *, app_config: [],
    )

    def fake_build_middlewares(config, model_name, agent_name=None, **kwargs):
        runtime_seen.update(lead_agent_module._get_runtime_config(config))
        return []

    monkeypatch.setattr(lead_agent_module, "build_middlewares", fake_build_middlewares)
    monkeypatch.setattr(
        lead_agent_module,
        "apply_prompt_template",
        lambda **kwargs: prompt_seen.update(kwargs) or "commerce prompt",
    )
    monkeypatch.setattr(
        lead_agent_module,
        "create_chat_model",
        lambda **kwargs: object(),
    )
    monkeypatch.setattr(
        lead_agent_module,
        "create_agent",
        lambda **kwargs: kwargs,
    )

    lead_agent_module._make_lead_agent(config, app_config=app_config)

    get_available_tools.assert_called_once_with(
        model_name="commerce-model",
        groups=["commerce"],
        subagent_enabled=True,
        app_config=app_config,
    )
    assert runtime_seen["subagent_enabled"] is True
    assert runtime_seen["subagent_required"] is True
    assert runtime_seen["subagent_complexity_tool_call_threshold"] == 2
    assert runtime_seen["required_subagent_types"] == ["verifier"]
    assert runtime_seen["max_concurrent_subagents"] == 3
    assert runtime_seen["max_parent_direct_tool_calls"] == 8
    assert runtime_seen["max_parent_direct_tool_rounds"] == 6
    assert runtime_seen["require_explicit_subagent_scope"] is True
    assert runtime_seen["memory_enabled"] is False
    assert runtime_seen["model_generated_title"] is False
    assert runtime_seen["local_title_rules"] == [
        {"keywords": ["履约", "延迟"], "title": "订单履约异常诊断"}
    ]
    assert runtime_seen["local_title_fallback"] == "电商经营数据诊断"
    assert runtime_seen["subagent_scope_rules"][0]["name"] == (
        "fulfillment-verifier"
    )
    assert prompt_seen["subagent_required"] is True
    assert prompt_seen["subagent_complexity_tool_call_threshold"] == 2
    assert prompt_seen["required_subagent_types"] == ["verifier"]
    assert prompt_seen["require_explicit_subagent_scope"] is True
    assert config["metadata"]["subagent_enabled"] is True
    assert config["metadata"]["memory_enabled"] is False
    assert config["metadata"]["model_generated_title"] is False
    assert config["metadata"]["subagent_scope_rule_count"] == 1


def test_make_lead_agent_rejects_invalid_bootstrap_agent_name(monkeypatch):
    app_config = _make_app_config([_make_model("safe-model", supports_thinking=False)])

    monkeypatch.setattr(lead_agent_module, "get_app_config", lambda: app_config)

    with pytest.raises(ValueError, match="Invalid agent name"):
        lead_agent_module.make_lead_agent(
            {
                "configurable": {
                    "model_name": "safe-model",
                    "thinking_enabled": False,
                    "is_plan_mode": False,
                    "subagent_enabled": False,
                    "is_bootstrap": True,
                    "agent_name": "../../../tmp/evil",
                }
            }
        )


def test_build_middlewares_uses_resolved_model_name_for_vision(monkeypatch):
    app_config = _make_app_config(
        [
            _make_model("stale-model", supports_thinking=False),
            ModelConfig(
                name="vision-model",
                display_name="vision-model",
                description=None,
                use="langchain_openai:ChatOpenAI",
                model="vision-model",
                supports_thinking=False,
                supports_vision=True,
            ),
        ]
    )

    monkeypatch.setattr(lead_agent_module, "get_app_config", lambda: app_config)
    monkeypatch.setattr(lead_agent_module, "_create_summarization_middleware", lambda **kwargs: None)
    monkeypatch.setattr(lead_agent_module, "_create_todo_list_middleware", lambda is_plan_mode: None)

    middlewares = lead_agent_module.build_middlewares(
        {"configurable": {"model_name": "stale-model", "is_plan_mode": False, "subagent_enabled": False}},
        model_name="vision-model",
        custom_middlewares=[MagicMock()],
        app_config=app_config,
    )

    assert any(isinstance(m, lead_agent_module.ViewImageMiddleware) for m in middlewares)
    # verify the custom middleware is injected correctly.
    # Chain tail order after the custom middleware is:
    #   ..., custom, SafetyFinishReasonMiddleware, ClarificationMiddleware
    # so the custom mock sits at index [-3].
    assert len(middlewares) > 0 and isinstance(middlewares[-3], MagicMock)


def test_build_middlewares_can_disable_todos_for_plan_mode(monkeypatch):
    app_config = _make_app_config([_make_model("safe-model", supports_thinking=False)])
    todo_enabled_values: list[bool] = []

    monkeypatch.setattr(
        lead_agent_module,
        "build_lead_runtime_middlewares",
        lambda *, app_config, lazy_init=True: [],
    )
    monkeypatch.setattr(
        lead_agent_module,
        "_create_summarization_middleware",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        lead_agent_module,
        "_create_todo_list_middleware",
        lambda enabled: todo_enabled_values.append(enabled) or None,
    )

    lead_agent_module.build_middlewares(
        {
            "configurable": {
                "is_plan_mode": True,
                "todo_list_enabled": False,
                "subagent_enabled": False,
            }
        },
        model_name="safe-model",
        app_config=app_config,
    )

    assert todo_enabled_values == [False]


def test_build_middlewares_can_disable_agent_memory_and_model_title(monkeypatch):
    from deerflow.agents.middlewares.dynamic_context_middleware import (
        DynamicContextMiddleware,
    )
    from deerflow.agents.middlewares.memory_middleware import MemoryMiddleware
    from deerflow.agents.middlewares.title_middleware import TitleMiddleware

    app_config = _make_app_config(
        [_make_model("safe-model", supports_thinking=False)]
    )
    app_config.memory = MemoryConfig(enabled=True, injection_enabled=True)

    monkeypatch.setattr(
        lead_agent_module,
        "build_lead_runtime_middlewares",
        lambda *, app_config, lazy_init=True: [],
    )
    monkeypatch.setattr(
        lead_agent_module,
        "_create_summarization_middleware",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        lead_agent_module,
        "_create_todo_list_middleware",
        lambda enabled: None,
    )

    middlewares = lead_agent_module.build_middlewares(
        {
            "configurable": {
                "is_plan_mode": False,
                "subagent_enabled": False,
                "memory_enabled": False,
                "model_generated_title": False,
                "local_title_rules": [
                    {
                        "keywords": ["履约", "延迟"],
                        "title": "订单履约异常诊断",
                    }
                ],
                "local_title_fallback": "电商经营数据诊断",
            }
        },
        model_name="safe-model",
        agent_name="commerce-agent",
        app_config=app_config,
    )

    dynamic_context = next(
        item for item in middlewares if isinstance(item, DynamicContextMiddleware)
    )
    title = next(item for item in middlewares if isinstance(item, TitleMiddleware))
    assert dynamic_context._memory_enabled is False
    assert title._use_model is False
    assert title._local_title_fallback == "电商经营数据诊断"
    assert not any(isinstance(item, MemoryMiddleware) for item in middlewares)


def test_build_middlewares_passes_explicit_app_config_to_shared_factory(monkeypatch):
    app_config = _make_app_config([_make_model("safe-model", supports_thinking=False)])
    captured: dict[str, object] = {}

    def _raise_get_app_config():
        raise AssertionError("ambient get_app_config() must not be used when app_config is explicit")

    def _fake_build_lead_runtime_middlewares(*, app_config, lazy_init):
        captured["app_config"] = app_config
        captured["lazy_init"] = lazy_init
        return ["base-middleware"]

    monkeypatch.setattr(lead_agent_module, "get_app_config", _raise_get_app_config)
    monkeypatch.setattr(
        lead_agent_module,
        "build_lead_runtime_middlewares",
        _fake_build_lead_runtime_middlewares,
    )
    monkeypatch.setattr(lead_agent_module, "_create_summarization_middleware", lambda **kwargs: None)
    monkeypatch.setattr(lead_agent_module, "_create_todo_list_middleware", lambda is_plan_mode: None)
    monkeypatch.setattr(
        lead_agent_module,
        "TitleMiddleware",
        lambda *, app_config, **kwargs: captured.setdefault(
            "title_app_config", app_config
        )
        or "title-middleware",
    )
    monkeypatch.setattr(
        lead_agent_module,
        "MemoryMiddleware",
        lambda agent_name=None, *, memory_config: captured.setdefault("memory_config", memory_config) or "memory-middleware",
    )

    middlewares = lead_agent_module.build_middlewares(
        {"configurable": {"is_plan_mode": False, "subagent_enabled": False}},
        model_name="safe-model",
        app_config=app_config,
    )

    assert captured == {
        "app_config": app_config,
        "lazy_init": True,
        "title_app_config": app_config,
        "memory_config": app_config.memory,
    }
    assert middlewares[0] == "base-middleware"


def test_build_middlewares_uses_loop_detection_config(monkeypatch):
    app_config = _make_app_config(
        [_make_model("safe-model", supports_thinking=False)],
        loop_detection=LoopDetectionConfig(
            warn_threshold=7,
            hard_limit=9,
            window_size=30,
            max_tracked_threads=40,
            tool_freq_warn=50,
            tool_freq_hard_limit=60,
        ),
    )

    monkeypatch.setattr(lead_agent_module, "get_app_config", lambda: app_config)
    monkeypatch.setattr(lead_agent_module, "build_lead_runtime_middlewares", lambda *, app_config, lazy_init=True: [])
    monkeypatch.setattr(
        lead_agent_module, "_create_summarization_middleware", lambda **kwargs: None
    )
    monkeypatch.setattr(lead_agent_module, "_create_todo_list_middleware", lambda is_plan_mode: None)

    middlewares = lead_agent_module.build_middlewares(
        {"configurable": {"is_plan_mode": False, "subagent_enabled": False}},
        model_name="safe-model",
        app_config=app_config,
    )

    loop_detection = next(m for m in middlewares if isinstance(m, LoopDetectionMiddleware))
    assert loop_detection.warn_threshold == 7
    assert loop_detection.hard_limit == 9
    assert loop_detection.window_size == 30
    assert loop_detection.max_tracked_threads == 40
    assert loop_detection.tool_freq_warn == 50
    assert loop_detection.tool_freq_hard_limit == 60


def test_build_middlewares_adds_fail_closed_subagent_requirement(monkeypatch):
    app_config = _make_app_config([_make_model("safe-model", supports_thinking=False)])

    monkeypatch.setattr(lead_agent_module, "get_app_config", lambda: app_config)
    monkeypatch.setattr(
        lead_agent_module,
        "build_lead_runtime_middlewares",
        lambda *, app_config, lazy_init=True: [],
    )
    monkeypatch.setattr(
        lead_agent_module,
        "_create_summarization_middleware",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        lead_agent_module,
        "_create_todo_list_middleware",
        lambda is_plan_mode: None,
    )

    middlewares = lead_agent_module.build_middlewares(
        {
            "configurable": {
                "is_plan_mode": False,
                "subagent_enabled": True,
                "subagent_required": True,
                "subagent_complexity_tool_call_threshold": 4,
                "required_subagent_types": ["verifier"],
                "max_parent_direct_tool_calls": 8,
                "max_parent_direct_tool_rounds": 6,
                "final_answer_forbidden_phrases": ["主因", "完全排除"],
                "max_final_answer_repairs": 1,
                "subagent_scope_rules": [
                    {
                        "name": "fulfillment-verifier",
                        "subagent_type": "verifier",
                        "match_skills_all": ["fulfillment-investigation"],
                        "prompt_keywords_any": ["核验"],
                        "enforced_skills": ["fulfillment-investigation"],
                        "enforced_tools": ["commerce_evidence_query"],
                        "inherit_source_tools": True,
                        "max_tool_rounds": 2,
                        "max_tool_calls": 3,
                    }
                ],
            }
        },
        model_name="safe-model",
        app_config=app_config,
    )

    requirement = next(middleware for middleware in middlewares if isinstance(middleware, SubagentRequirementMiddleware))
    assert requirement.complexity_tool_call_threshold == 4
    assert requirement.required_subagent_types == ("verifier",)
    parent_budget = next(middleware for middleware in middlewares if isinstance(middleware, ParentDirectToolBudgetMiddleware))
    assert parent_budget.max_direct_tool_calls == 8
    assert parent_budget.max_direct_tool_rounds == 6
    final_answer_policy = next(middleware for middleware in middlewares if isinstance(middleware, FinalAnswerPolicyMiddleware))
    assert final_answer_policy.forbidden_phrases == ("主因", "完全排除")
    assert final_answer_policy.max_repairs == 1
    assert any(
        isinstance(middleware, SubagentDispatchPolicyMiddleware)
        for middleware in middlewares
    )
    dispatch_policy = next(
        middleware
        for middleware in middlewares
        if isinstance(middleware, SubagentDispatchPolicyMiddleware)
    )
    assert dispatch_policy.scope_rules[0]["name"] == "fulfillment-verifier"
    assert middlewares.index(dispatch_policy) < middlewares.index(requirement)


def test_build_middlewares_omits_loop_detection_when_disabled(monkeypatch):
    app_config = _make_app_config(
        [_make_model("safe-model", supports_thinking=False)],
        loop_detection=LoopDetectionConfig(enabled=False),
    )

    monkeypatch.setattr(lead_agent_module, "get_app_config", lambda: app_config)
    monkeypatch.setattr(lead_agent_module, "build_lead_runtime_middlewares", lambda *, app_config, lazy_init=True: [])
    monkeypatch.setattr(
        lead_agent_module, "_create_summarization_middleware", lambda **kwargs: None
    )
    monkeypatch.setattr(lead_agent_module, "_create_todo_list_middleware", lambda is_plan_mode: None)

    middlewares = lead_agent_module.build_middlewares(
        {"configurable": {"is_plan_mode": False, "subagent_enabled": False}},
        model_name="safe-model",
        app_config=app_config,
    )

    assert not any(isinstance(m, LoopDetectionMiddleware) for m in middlewares)


def test_create_summarization_middleware_uses_configured_model_alias(monkeypatch):
    app_config = _make_app_config([_make_model("model-masswork", supports_thinking=False)])
    app_config.summarization = SummarizationConfig(enabled=True, model_name="model-masswork")
    app_config.memory = MemoryConfig(enabled=False)

    from unittest.mock import MagicMock

    captured: dict[str, object] = {}
    fake_model = MagicMock()
    fake_model.with_config.return_value = fake_model

    def _fake_create_chat_model(*, name=None, thinking_enabled, reasoning_effort=None, app_config=None, attach_tracing=True):
        captured["name"] = name
        captured["thinking_enabled"] = thinking_enabled
        captured["reasoning_effort"] = reasoning_effort
        captured["app_config"] = app_config
        return fake_model

    def _raise_get_app_config():
        raise AssertionError("ambient get_app_config() must not be used when app_config is explicit")

    monkeypatch.setattr(lead_agent_module, "get_app_config", _raise_get_app_config)
    monkeypatch.setattr(lead_agent_module, "create_chat_model", _fake_create_chat_model)
    monkeypatch.setattr(lead_agent_module, "DeerFlowSummarizationMiddleware", lambda **kwargs: kwargs)

    middleware = lead_agent_module._create_summarization_middleware(app_config=app_config)

    assert captured["name"] == "model-masswork"
    assert captured["thinking_enabled"] is False
    assert captured["app_config"] is app_config
    assert middleware["model"] is fake_model
    fake_model.with_config.assert_called_once_with(tags=["middleware:summarize"])


def test_create_summarization_middleware_uses_frontend_supported_update_key(monkeypatch):
    """LangGraph update keys use the middleware class name plus hook name."""

    app_config = _make_app_config([_make_model("safe-model", supports_thinking=False)])
    app_config.summarization = SummarizationConfig(enabled=True)
    app_config.memory = MemoryConfig(enabled=False)

    fake_model = MagicMock()
    fake_model.with_config.return_value = fake_model
    monkeypatch.setattr(lead_agent_module, "create_chat_model", lambda **kwargs: fake_model)

    middleware = lead_agent_module._create_summarization_middleware(app_config=app_config)

    assert middleware is not None
    update_key = f"{type(middleware).__name__}.before_model"
    assert update_key == "DeerFlowSummarizationMiddleware.before_model"


def test_create_summarization_middleware_omits_memory_flush_for_agent_opt_out(
    monkeypatch,
):
    app_config = _make_app_config(
        [_make_model("safe-model", supports_thinking=False)]
    )
    app_config.summarization = SummarizationConfig(enabled=True)
    app_config.memory = MemoryConfig(enabled=True)

    fake_model = MagicMock()
    fake_model.with_config.return_value = fake_model
    monkeypatch.setattr(
        lead_agent_module, "create_chat_model", lambda **kwargs: fake_model
    )
    monkeypatch.setattr(
        lead_agent_module,
        "DeerFlowSummarizationMiddleware",
        lambda **kwargs: kwargs,
    )

    middleware = lead_agent_module._create_summarization_middleware(
        app_config=app_config,
        memory_enabled=False,
    )

    assert middleware["before_summarization"] == []


def test_create_summarization_middleware_threads_resolved_app_config_to_model(monkeypatch):
    fallback_app_config = _make_app_config([_make_model("fallback-model", supports_thinking=False)])
    fallback_app_config.summarization = SummarizationConfig(enabled=True, model_name="fallback-model")
    fallback_app_config.memory = MemoryConfig(enabled=False)

    from unittest.mock import MagicMock

    captured: dict[str, object] = {}
    fake_model = MagicMock()
    fake_model.with_config.return_value = fake_model

    def _fake_create_chat_model(*, name=None, thinking_enabled, reasoning_effort=None, app_config=None, attach_tracing=True):
        captured["app_config"] = app_config
        return fake_model

    monkeypatch.setattr(lead_agent_module, "get_app_config", lambda: fallback_app_config)
    monkeypatch.setattr(lead_agent_module, "create_chat_model", _fake_create_chat_model)
    monkeypatch.setattr(lead_agent_module, "DeerFlowSummarizationMiddleware", lambda **kwargs: kwargs)

    lead_agent_module._create_summarization_middleware()

    assert captured["app_config"] is fallback_app_config


def test_memory_middleware_uses_explicit_memory_config_without_global_read(monkeypatch):
    from deerflow.agents.middlewares import memory_middleware as memory_middleware_module
    from deerflow.agents.middlewares.memory_middleware import MemoryMiddleware

    def _raise_get_memory_config():
        raise AssertionError("ambient get_memory_config() must not be used when memory_config is explicit")

    monkeypatch.setattr(memory_middleware_module, "get_memory_config", _raise_get_memory_config)

    middleware = MemoryMiddleware(memory_config=MemoryConfig(enabled=False))

    assert middleware.after_agent({"messages": []}, runtime=MagicMock(context={"thread_id": "thread-1"})) is None
