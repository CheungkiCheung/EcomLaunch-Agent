import hashlib
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

UPSTREAM_PM_SKILL_SHA256 = {
    # phuryn/pm-skills commit 18468a95b427e70e258b51389796367c6f684e7d
    "sql-queries": "18da062d5171607dcaa31eb277be420560e061bdcb0c960201e86c7067e2e59a",
    "cohort-analysis": "bd721a429e58c71a1a488ac1e89ba2bcbb9e179cb9c0b5eac44a3c3b3e9fdb15",
    "ab-test-analysis": "9956966671d6d19d42acb6150307fd7954d16d1d150e8fd8277f99eec9a949e0",
}

_DEERFLOW_SKILL_METADATA = re.compile(
    r"^license: MIT; copied from phuryn/pm-skills, Copyright \(c\) 2026 "
    r"Pawel Huryn\. See LICENSE\.txt\.\n"
    r"allowed-tools:\n(?:  - [^\n]+\n)+",
    re.MULTILINE,
)


def test_data_inspector_agent_uses_native_deerflow_configuration(monkeypatch) -> None:
    monkeypatch.setenv("DEER_FLOW_PROJECT_ROOT", str(REPO_ROOT))

    from deerflow.config.agents_config import is_builtin_agent, list_custom_agents, load_agent_config, load_agent_soul

    config = load_agent_config("data-inspector", user_id="contract-user")
    soul = load_agent_soul("data-inspector", user_id="contract-user")

    assert config is not None
    assert is_builtin_agent("data-inspector", user_id="contract-user") is True
    assert "data-inspector" in {agent.name for agent in list_custom_agents(user_id="contract-user")}
    assert config.name == "data-inspector"
    assert config.tool_groups == ["data", "file:read"]
    assert config.skills == ["sql-queries", "cohort-analysis", "ab-test-analysis"]
    assert config.memory_enabled is True
    assert soul is not None
    assert soul.startswith("# Growth Analyst")
    assert "长期增长引擎" in soul
    assert "跨会话记忆" in soul
    assert "inspect_data" in soul
    assert "query_data" in soul
    assert "分析一下" in soul
    assert "为什么" in soul
    assert "怎么改进" in soul
    assert len(soul.splitlines()) <= 18


def test_data_inspector_exposes_only_analysis_tools(monkeypatch) -> None:
    monkeypatch.setenv("DEER_FLOW_PROJECT_ROOT", str(REPO_ROOT))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "validation-placeholder")

    from deerflow.agents.lead_agent.agent import _load_enabled_skills_for_tool_policy
    from deerflow.config.agents_config import load_agent_config
    from deerflow.config.app_config import AppConfig
    from deerflow.skills.tool_policy import filter_tools_by_skill_allowed_tools
    from deerflow.tools import get_available_tools

    app_config = AppConfig.from_file(REPO_ROOT / "config.yaml")
    agent_config = load_agent_config("data-inspector", user_id="contract-user")
    assert agent_config is not None

    skills = _load_enabled_skills_for_tool_policy(set(agent_config.skills or []), app_config=app_config)
    assert {skill.name for skill in skills} == {"sql-queries", "cohort-analysis", "ab-test-analysis"}
    raw_tools = get_available_tools(
        groups=agent_config.tool_groups,
        include_mcp=False,
        subagent_enabled=False,
        app_config=app_config,
    )
    final_tools = filter_tools_by_skill_allowed_tools(raw_tools, skills)
    tools_by_name = {tool.name: tool for tool in final_tools}

    assert set(tools_by_name) == {
        "analyze_ab_test",
        "ask_clarification",
        "inspect_data",
        "query_data",
        "read_file",
    }
    assert set(tools_by_name["inspect_data"].args) == {"filenames", "include_text_samples", "sample_rows"}
    assert set(tools_by_name["query_data"].args) == {"filenames", "max_rows", "sql"}
    assert set(tools_by_name["analyze_ab_test"].args) == {
        "confidence_level",
        "control_conversions",
        "control_visitors",
        "expected_control_share",
        "variant_conversions",
        "variant_visitors",
    }


def test_data_inspector_uses_upstream_pm_data_skills() -> None:
    skills = {name: (REPO_ROOT / "skills" / "custom" / name / "SKILL.md").read_text(encoding="utf-8") for name in ("sql-queries", "cohort-analysis", "ab-test-analysis")}

    assert "Generate SQL queries from natural language" in skills["sql-queries"]
    assert "Perform cohort analysis on user engagement data" in skills["cohort-analysis"]
    assert "Analyze A/B test results with statistical significance" in skills["ab-test-analysis"]
    for skill_name, skill in skills.items():
        assert f"name: {skill_name}" in skill
        assert "phuryn/pm-skills" in skill
        assert "license: MIT" in skill
        assert "write_file" not in skill
        assert "present_files" not in skill
        license_text = (REPO_ROOT / "skills" / "custom" / skill_name / "LICENSE.txt").read_text(encoding="utf-8")
        assert "Copyright (c) 2026 Pawel Huryn" in license_text
        assert "Permission is hereby granted" in license_text


def test_data_inspector_pm_skill_content_matches_pinned_upstream() -> None:
    """Keep the vendored PM skills generic instead of tuning them to one dataset."""

    for skill_name, expected_sha256 in UPSTREAM_PM_SKILL_SHA256.items():
        skill_text = (REPO_ROOT / "skills" / "custom" / skill_name / "SKILL.md").read_text(encoding="utf-8")
        upstream_compatible_text, substitutions = _DEERFLOW_SKILL_METADATA.subn("", skill_text, count=1)

        assert substitutions == 1, f"{skill_name} must only add the DeerFlow license/tool metadata block"
        actual_sha256 = hashlib.sha256(upstream_compatible_text.encode()).hexdigest()
        assert actual_sha256 == expected_sha256, (
            f"{skill_name} diverged from the pinned phuryn/pm-skills source; "
            "update the upstream pin deliberately instead of adding dataset-specific instructions"
        )


def test_project_configs_register_data_tool_group_and_tools() -> None:
    for filename in ("config.yaml", "config.example.yaml"):
        config = yaml.safe_load((REPO_ROOT / filename).read_text(encoding="utf-8"))
        groups = {group["name"] for group in config["tool_groups"]}
        tools = {tool["name"]: tool for tool in config["tools"]}

        assert "data" in groups
        assert tools["inspect_data"] == {
            "name": "inspect_data",
            "group": "data",
            "use": "app.data_inspector.tools:inspect_data_tool",
        }
        assert tools["query_data"] == {
            "name": "query_data",
            "group": "data",
            "use": "app.data_inspector.tools:query_data_tool",
        }
        assert tools["analyze_ab_test"] == {
            "name": "analyze_ab_test",
            "group": "data",
            "use": "app.data_inspector.tools:analyze_ab_test_tool",
        }
        assert "validate_data_answer" not in tools
