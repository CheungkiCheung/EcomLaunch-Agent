import threading
from types import SimpleNamespace
from typing import cast

import anyio

from deerflow.agents.lead_agent import prompt as prompt_module
from deerflow.config.app_config import AppConfig
from deerflow.config.subagents_config import CustomSubagentConfig, SubagentsAppConfig
from deerflow.skills.types import Skill, SkillCategory


def _set_skills_cache_state(*, skills=None, active=False, version=0):
    prompt_module._get_cached_skills_prompt_section.cache_clear()
    with prompt_module._enabled_skills_lock:
        prompt_module._enabled_skills_cache = skills
        prompt_module._enabled_skills_by_config_cache.clear()
        prompt_module._enabled_skills_refresh_active = active
        prompt_module._enabled_skills_refresh_version = version
        prompt_module._enabled_skills_refresh_event.clear()


def test_build_self_update_section_empty_for_default_agent():
    assert prompt_module._build_self_update_section(None) == ""


def test_build_self_update_section_present_for_custom_agent():
    section = prompt_module._build_self_update_section("my-agent")

    assert "<self_update>" in section
    assert "my-agent" in section
    assert "update_agent" in section
    assert '"null"' in section


def test_apply_prompt_template_can_omit_self_update_for_read_only_agent(monkeypatch):
    monkeypatch.setattr(prompt_module, "get_agent_soul", lambda agent_name: "")
    monkeypatch.setattr(prompt_module, "get_skills_prompt_section", lambda *args, **kwargs: "")
    monkeypatch.setattr(prompt_module, "get_deferred_tools_prompt_section", lambda *args, **kwargs: "")
    monkeypatch.setattr(prompt_module, "_build_acp_section", lambda *args, **kwargs: "")
    monkeypatch.setattr(prompt_module, "_build_custom_mounts_section", lambda *args, **kwargs: "")

    prompt = prompt_module.apply_prompt_template(
        agent_name="ecom-launch",
        self_update_enabled=False,
    )

    assert "ecom-launch" in prompt
    assert "<self_update>" not in prompt
    assert "update_agent" not in prompt


def test_build_custom_mounts_section_returns_empty_when_no_mounts(monkeypatch):
    config = SimpleNamespace(sandbox=SimpleNamespace(mounts=[]))
    monkeypatch.setattr("deerflow.config.get_app_config", lambda: config)

    assert prompt_module._build_custom_mounts_section() == ""


def test_build_custom_mounts_section_lists_configured_mounts(monkeypatch):
    mounts = [
        SimpleNamespace(container_path="/home/user/shared", read_only=False),
        SimpleNamespace(container_path="/mnt/reference", read_only=True),
    ]
    config = SimpleNamespace(sandbox=SimpleNamespace(mounts=mounts))
    monkeypatch.setattr("deerflow.config.get_app_config", lambda: config)

    section = prompt_module._build_custom_mounts_section()

    assert "**Custom Mounted Directories:**" in section
    assert "`/home/user/shared`" in section
    assert "read-write" in section
    assert "`/mnt/reference`" in section
    assert "read-only" in section


def test_build_custom_mounts_section_uses_explicit_app_config_without_global_read(monkeypatch):
    mounts = [SimpleNamespace(container_path="/home/user/shared", read_only=False)]
    config = SimpleNamespace(sandbox=SimpleNamespace(mounts=mounts))

    def fail_get_app_config():
        raise AssertionError("ambient get_app_config() must not be used when app_config is explicit")

    monkeypatch.setattr("deerflow.config.get_app_config", fail_get_app_config)

    section = prompt_module._build_custom_mounts_section(app_config=config)

    assert "`/home/user/shared`" in section
    assert "read-write" in section


def test_apply_prompt_template_includes_custom_mounts(monkeypatch):
    mounts = [SimpleNamespace(container_path="/home/user/shared", read_only=False)]
    config = SimpleNamespace(
        sandbox=SimpleNamespace(mounts=mounts),
        skills=SimpleNamespace(container_path="/mnt/skills"),
    )
    monkeypatch.setattr("deerflow.config.get_app_config", lambda: config)
    monkeypatch.setattr(prompt_module, "_get_enabled_skills", lambda: [])
    monkeypatch.setattr(prompt_module, "get_deferred_tools_prompt_section", lambda **kwargs: "")
    monkeypatch.setattr(prompt_module, "_build_acp_section", lambda **kwargs: "")
    monkeypatch.setattr(prompt_module, "_get_memory_context", lambda agent_name=None, **kwargs: "")
    monkeypatch.setattr(prompt_module, "get_agent_soul", lambda agent_name=None: "")

    prompt = prompt_module.apply_prompt_template()

    assert "`/home/user/shared`" in prompt
    assert "Custom Mounted Directories" in prompt


def test_apply_prompt_template_includes_relative_path_guidance(monkeypatch):
    config = SimpleNamespace(
        sandbox=SimpleNamespace(mounts=[]),
        skills=SimpleNamespace(container_path="/mnt/skills"),
    )
    monkeypatch.setattr("deerflow.config.get_app_config", lambda: config)
    monkeypatch.setattr(prompt_module, "_get_enabled_skills", lambda: [])
    monkeypatch.setattr(prompt_module, "get_deferred_tools_prompt_section", lambda **kwargs: "")
    monkeypatch.setattr(prompt_module, "_build_acp_section", lambda **kwargs: "")
    monkeypatch.setattr(prompt_module, "_get_memory_context", lambda agent_name=None, **kwargs: "")
    monkeypatch.setattr(prompt_module, "get_agent_soul", lambda agent_name=None: "")

    prompt = prompt_module.apply_prompt_template()

    assert "Treat `/mnt/user-data/workspace` as your default current working directory" in prompt
    assert "`hello.txt`, `../uploads/data.csv`, and `../outputs/report.md`" in prompt


def test_apply_prompt_template_threads_explicit_app_config_without_global_config(monkeypatch):
    mounts = [SimpleNamespace(container_path="/home/user/shared", read_only=False)]
    explicit_config = SimpleNamespace(
        sandbox=SimpleNamespace(mounts=mounts),
        skills=SimpleNamespace(container_path="/mnt/explicit-skills"),
        skill_evolution=SimpleNamespace(enabled=False),
        tool_search=SimpleNamespace(enabled=False),
        memory=SimpleNamespace(enabled=False, injection_enabled=True, max_injection_tokens=2000),
        acp_agents={},
    )

    def fail_get_app_config():
        raise AssertionError("ambient get_app_config() must not be used when app_config is explicit")

    def fail_get_memory_config():
        raise AssertionError("ambient get_memory_config() must not be used when app_config is explicit")

    monkeypatch.setattr("deerflow.config.get_app_config", fail_get_app_config)
    monkeypatch.setattr("deerflow.config.memory_config.get_memory_config", fail_get_memory_config)
    monkeypatch.setattr(prompt_module, "get_or_new_skill_storage", lambda app_config=None: SimpleNamespace(load_skills=lambda enabled_only=True: []))
    monkeypatch.setattr(prompt_module, "get_agent_soul", lambda agent_name=None: "")

    prompt = prompt_module.apply_prompt_template(app_config=explicit_config)

    assert "`/home/user/shared`" in prompt
    assert "Custom Mounted Directories" in prompt


def test_apply_prompt_template_threads_explicit_app_config_to_subagents_without_global_config(monkeypatch):
    explicit_config = SimpleNamespace(
        sandbox=SimpleNamespace(
            use="deerflow.sandbox.local:LocalSandboxProvider",
            allow_host_bash=False,
            mounts=[],
        ),
        subagents=SubagentsAppConfig(
            custom_agents={
                "researcher": CustomSubagentConfig(
                    description="Research agent\nwith details",
                    system_prompt="You research.",
                    max_tool_rounds=3,
                    max_tool_calls=5,
                )
            }
        ),
        skills=SimpleNamespace(container_path="/mnt/skills"),
        skill_evolution=SimpleNamespace(enabled=False),
        tool_search=SimpleNamespace(enabled=False),
        memory=SimpleNamespace(enabled=False, injection_enabled=True, max_injection_tokens=2000),
        acp_agents={},
    )

    def fail_get_app_config():
        raise AssertionError("ambient get_app_config() must not be used when app_config is explicit")

    def fail_get_subagents_app_config():
        raise AssertionError("ambient get_subagents_app_config() must not be used when app_config is explicit")

    monkeypatch.setattr("deerflow.config.get_app_config", fail_get_app_config)
    monkeypatch.setattr("deerflow.config.subagents_config.get_subagents_app_config", fail_get_subagents_app_config)
    monkeypatch.setattr(prompt_module, "get_or_new_skill_storage", lambda app_config=None: SimpleNamespace(load_skills=lambda enabled_only=True: []))
    monkeypatch.setattr(prompt_module, "get_agent_soul", lambda agent_name=None: "")

    prompt = prompt_module.apply_prompt_template(subagent_enabled=True, app_config=explicit_config)

    assert "**researcher**: Research agent" in prompt
    assert "max_tool_rounds=3" in prompt
    assert "max_tool_calls=5" in prompt
    assert "显式传入只能收窄" in prompt
    assert "通常省略预算参数" in prompt
    assert "**bash**" not in prompt


def test_apply_prompt_template_includes_required_subagent_delivery_contract(monkeypatch):
    explicit_config = SimpleNamespace(
        sandbox=SimpleNamespace(
            use="deerflow.sandbox.local:LocalSandboxProvider",
            allow_host_bash=False,
            mounts=[],
        ),
        subagents=SubagentsAppConfig(
            custom_agents={
                "verifier": CustomSubagentConfig(
                    description="Independently verify evidence and counterevidence",
                    system_prompt="Verify conclusions from fresh context.",
                )
            }
        ),
        skills=SimpleNamespace(container_path="/mnt/skills"),
        skill_evolution=SimpleNamespace(enabled=False),
        tool_search=SimpleNamespace(enabled=False),
        memory=SimpleNamespace(enabled=False, injection_enabled=True, max_injection_tokens=2000),
        acp_agents={},
    )
    monkeypatch.setattr(
        prompt_module,
        "get_or_new_skill_storage",
        lambda app_config=None: SimpleNamespace(load_skills=lambda enabled_only=True: []),
    )
    monkeypatch.setattr(prompt_module, "get_agent_soul", lambda agent_name=None: "")

    prompt = prompt_module.apply_prompt_template(
        subagent_enabled=True,
        subagent_required=True,
        subagent_complexity_tool_call_threshold=2,
        required_subagent_types=("verifier",),
        app_config=explicit_config,
    )

    assert "强制交付策略" in prompt
    assert "2 个直接工作 Tool" in prompt
    assert "`verifier`" in prompt
    assert "`task:<task_id>`" in prompt
    assert "fail-closed" in prompt
    assert "不允许 Parent 完成全部分析后跳过 Durable Task" in prompt


def test_subagent_section_requires_explicit_scope_when_policy_enabled(monkeypatch):
    explicit_config = SimpleNamespace(
        sandbox=SimpleNamespace(
            use="deerflow.sandbox.local:LocalSandboxProvider",
            allow_host_bash=False,
            mounts=[],
        ),
        subagents=SubagentsAppConfig(
            custom_agents={
                "analyst": CustomSubagentConfig(
                    description="Analyze deterministic metrics",
                    system_prompt="Analyze.",
                    max_tool_rounds=4,
                    max_tool_calls=6,
                )
            }
        ),
    )

    prompt = prompt_module._build_subagent_section(
        3,
        app_config=explicit_config,
        require_explicit_subagent_scope=True,
    )

    assert "每次 spawn_task 都必须显式传入" in prompt
    assert "非空 skills" in prompt
    assert "非空 tools" in prompt
    assert "max_tool_rounds" in prompt
    assert "max_tool_calls" in prompt
    assert "通常省略预算参数" not in prompt
    assert 'skills=["<已启用 Skill 名称>"]' in prompt
    assert 'tools=["<完成目标所需的最小 Tool>"]' in prompt
    assert "max_tool_rounds=1" in prompt
    assert "max_tool_calls=1" in prompt


def test_subagent_section_prefers_exact_custom_specialist_types(monkeypatch):
    explicit_config = SimpleNamespace(
        sandbox=SimpleNamespace(
            use="deerflow.sandbox.local:LocalSandboxProvider",
            allow_host_bash=False,
            mounts=[],
        ),
        subagents=SubagentsAppConfig(
            custom_agents={
                "market-scout": CustomSubagentConfig(
                    description="Search public ecommerce market signals",
                    system_prompt="You scout markets.",
                ),
                "voc-miner": CustomSubagentConfig(
                    description="Mine public customer voice",
                    system_prompt="You mine VOC.",
                ),
                "offer-architect": CustomSubagentConfig(
                    description="Turn evidence into launch offers",
                    system_prompt="You design offers.",
                ),
            }
        ),
    )

    prompt = prompt_module._build_subagent_section(3, app_config=explicit_config)

    assert "**market-scout**: Search public ecommerce market signals" in prompt
    assert "use that exact role name as `subagent_type`" in prompt
    assert "Do NOT use `general-purpose` for work covered by a specialized subagent" in prompt
    assert 'subagent_type="market-scout"' in prompt
    assert 'subagent_type="voc-miner"' in prompt
    assert 'subagent_type="offer-architect"' in prompt
    assert "**general-purpose**: Fallback for non-trivial tasks" in prompt
    assert "spawn_task" in prompt
    assert "wait_task" in prompt
    assert "立即返回 task_id" in prompt
    assert "旧版阻塞兼容入口" in prompt
    assert "tool call will block" not in prompt


def test_build_acp_section_uses_explicit_app_config_without_global_config(monkeypatch):
    explicit_config = SimpleNamespace(acp_agents={"codex": object()})

    def fail_get_acp_agents():
        raise AssertionError("ambient get_acp_agents() must not be used when app_config is explicit")

    monkeypatch.setattr("deerflow.config.acp_config.get_acp_agents", fail_get_acp_agents)

    section = prompt_module._build_acp_section(app_config=explicit_config)

    assert "ACP Agent Tasks" in section
    assert "/mnt/acp-workspace/" in section


def test_get_memory_context_uses_explicit_app_config_without_global_config(monkeypatch):
    explicit_config = SimpleNamespace(
        memory=SimpleNamespace(enabled=True, injection_enabled=True, max_injection_tokens=1234),
    )
    captured: dict[str, object] = {}

    def fail_get_memory_config():
        raise AssertionError("ambient get_memory_config() must not be used when app_config is explicit")

    def fake_get_memory_data(agent_name=None, *, user_id=None):
        captured["agent_name"] = agent_name
        captured["user_id"] = user_id
        return {"facts": []}

    def fake_format_memory_for_injection(memory_data, *, max_tokens):
        captured["memory_data"] = memory_data
        captured["max_tokens"] = max_tokens
        return "remember this"

    monkeypatch.setattr("deerflow.config.memory_config.get_memory_config", fail_get_memory_config)
    monkeypatch.setattr("deerflow.runtime.user_context.get_effective_user_id", lambda: "user-1")
    monkeypatch.setattr("deerflow.agents.memory.get_memory_data", fake_get_memory_data)
    monkeypatch.setattr("deerflow.agents.memory.format_memory_for_injection", fake_format_memory_for_injection)

    context = prompt_module._get_memory_context("agent-a", app_config=explicit_config)

    assert "<memory>" in context
    assert "remember this" in context
    assert captured == {
        "agent_name": "agent-a",
        "user_id": "user-1",
        "memory_data": {"facts": []},
        "max_tokens": 1234,
    }


def test_refresh_skills_system_prompt_cache_async_reloads_immediately(monkeypatch, tmp_path):
    def make_skill(name: str) -> Skill:
        skill_dir = tmp_path / name
        return Skill(
            name=name,
            description=f"Description for {name}",
            license="MIT",
            skill_dir=skill_dir,
            skill_file=skill_dir / "SKILL.md",
            relative_path=skill_dir.relative_to(tmp_path),
            category=SkillCategory.CUSTOM,
            enabled=True,
        )

    state = {"skills": [make_skill("first-skill")]}
    monkeypatch.setattr(prompt_module, "get_or_new_skill_storage", lambda **kwargs: __import__("types").SimpleNamespace(load_skills=lambda *, enabled_only: list(state["skills"])))
    _set_skills_cache_state()

    try:
        prompt_module.warm_enabled_skills_cache()
        assert [skill.name for skill in prompt_module._get_enabled_skills()] == ["first-skill"]

        state["skills"] = [make_skill("second-skill")]
        anyio.run(prompt_module.refresh_skills_system_prompt_cache_async)

        assert [skill.name for skill in prompt_module._get_enabled_skills()] == ["second-skill"]
    finally:
        _set_skills_cache_state()


def test_explicit_config_enabled_skills_are_cached_by_config_identity(monkeypatch, tmp_path):
    def make_skill(name: str) -> Skill:
        skill_dir = tmp_path / name
        return Skill(
            name=name,
            description=f"Description for {name}",
            license="MIT",
            skill_dir=skill_dir,
            skill_file=skill_dir / "SKILL.md",
            relative_path=skill_dir.relative_to(tmp_path),
            category=SkillCategory.CUSTOM,
            enabled=True,
        )

    config = cast(
        AppConfig,
        cast(
            object,
            SimpleNamespace(
                skills=SimpleNamespace(container_path="/mnt/skills"),
                skill_evolution=SimpleNamespace(enabled=False),
            ),
        ),
    )
    load_count = 0

    def fake_get_or_new_skill_storage(**kwargs):
        nonlocal load_count
        assert kwargs == {"app_config": config}

        def load_skills(*, enabled_only):
            nonlocal load_count
            load_count += 1
            assert enabled_only is True
            return [make_skill("cached-skill")]

        return SimpleNamespace(load_skills=load_skills)

    monkeypatch.setattr(prompt_module, "get_or_new_skill_storage", fake_get_or_new_skill_storage)
    _set_skills_cache_state()

    try:
        first = prompt_module.get_skills_prompt_section(app_config=config)
        second = prompt_module.get_skills_prompt_section(app_config=config)

        assert "cached-skill" in first
        assert "cached-skill" in second
        assert load_count == 1
    finally:
        _set_skills_cache_state()


def test_clear_cache_does_not_spawn_parallel_refresh_workers(monkeypatch, tmp_path):
    started = threading.Event()
    release = threading.Event()
    active_loads = 0
    max_active_loads = 0
    call_count = 0
    lock = threading.Lock()

    def make_skill(name: str) -> Skill:
        skill_dir = tmp_path / name
        return Skill(
            name=name,
            description=f"Description for {name}",
            license="MIT",
            skill_dir=skill_dir,
            skill_file=skill_dir / "SKILL.md",
            relative_path=skill_dir.relative_to(tmp_path),
            category=SkillCategory.CUSTOM,
            enabled=True,
        )

    def fake_load_skills(enabled_only=True):
        nonlocal active_loads, max_active_loads, call_count
        with lock:
            active_loads += 1
            max_active_loads = max(max_active_loads, active_loads)
            call_count += 1
            current_call = call_count

        started.set()
        if current_call == 1:
            release.wait(timeout=5)

        with lock:
            active_loads -= 1

        return [make_skill(f"skill-{current_call}")]

    monkeypatch.setattr(prompt_module, "get_or_new_skill_storage", lambda **kwargs: __import__("types").SimpleNamespace(load_skills=lambda *, enabled_only: fake_load_skills(enabled_only=enabled_only)))
    _set_skills_cache_state()

    try:
        prompt_module.clear_skills_system_prompt_cache()
        assert started.wait(timeout=5)

        prompt_module.clear_skills_system_prompt_cache()
        release.set()
        prompt_module.warm_enabled_skills_cache()

        assert max_active_loads == 1
        assert [skill.name for skill in prompt_module._get_enabled_skills()] == ["skill-2"]
    finally:
        release.set()
        _set_skills_cache_state()


def test_warm_enabled_skills_cache_logs_on_timeout(monkeypatch, caplog):
    event = threading.Event()
    monkeypatch.setattr(prompt_module, "_ensure_enabled_skills_cache", lambda: event)

    with caplog.at_level("WARNING"):
        warmed = prompt_module.warm_enabled_skills_cache(timeout_seconds=0.01)

    assert warmed is False
    assert "Timed out waiting" in caplog.text


def test_system_prompt_template_contains_file_editing_workflow_rule():
    """The File Editing Workflow rule must remain in the system prompt
    template so the planner picks the right tool (str_replace for edits,
    write_file + append=True for long new content) and avoids mid-stream
    chunk-gap timeouts on oversized single-shot writes. See issue #3189
    / PR #3195.

    We deliberately do NOT assert on any specific byte / word threshold
    here — that would re-introduce the docstring-lock-in pattern the
    reviewers flagged. The numeric cap lives in the server-side guard
    (see test_write_file_tool_size_guard.py), which is where it belongs.
    """
    template = prompt_module.SYSTEM_PROMPT_TEMPLATE
    # Section anchor — keeps the rule discoverable in the assembled prompt.
    assert "File Editing Workflow" in template
    # Behavioural anchors — if either of these disappears, the model will
    # silently regress to single-shot write_file calls for long content.
    assert "str_replace" in template
    assert "append=True" in template


def test_system_prompt_template_preserves_placeholders():
    """Ensure the chunking-rule edit didn't drop any f-string placeholder
    consumed by apply_prompt_template(). A missing placeholder would
    crash prompt rendering at runtime.
    """
    template = prompt_module.SYSTEM_PROMPT_TEMPLATE
    for ph in (
        "{agent_name}",
        "{soul}",
        "{self_update_section}",
        "{subagent_thinking}",
        "{skills_section}",
        "{deferred_tools_section}",
        "{subagent_section}",
        "{acp_section}",
        "{subagent_reminder}",
    ):
        assert ph in template, f"placeholder {ph} accidentally removed"
