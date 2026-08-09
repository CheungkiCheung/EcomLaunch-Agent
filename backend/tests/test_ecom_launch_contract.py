import hashlib
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PM_SKILLS_ROOT = REPO_ROOT / "skills" / "custom" / "pm-skills"
UPSTREAM_COMMIT = "18468a95b427e70e258b51389796367c6f684e7d"

EXPECTED_SUBAGENTS = {
    "market-voc-researcher": {
        "tools": ["web_search", "web_fetch", "image_search", "read_file"],
        "skills": [
            "competitor-analysis",
            "market-segments",
            "sentiment-analysis",
        ],
        "max_model_calls": 4,
        "max_total_tokens": 45000,
        "model": "deepseek-chat",
        "max_output_tokens": 1200,
    },
    "offer-architect": {
        "tools": ["read_file"],
        "skills": [
            "beachhead-segment",
            "value-proposition",
            "pricing-strategy",
            "identify-assumptions-new",
            "prioritize-assumptions",
            "brainstorm-experiments-new",
        ],
        "max_model_calls": 2,
        "max_total_tokens": 30000,
        "model": "deepseek-chat",
        "max_output_tokens": 1000,
    },
    "asset-studio": {
        "tools": ["read_file"],
        "skills": [
            "positioning-ideas",
            "value-prop-statements",
            "marketing-ideas",
        ],
        "max_model_calls": 2,
        "max_total_tokens": 30000,
        "model": "deepseek-chat",
        "max_output_tokens": 900,
    },
    "evidence-checker": {
        "tools": ["read_file", "grep", "web_fetch"],
        "skills": ["strategy-red-team", "pre-mortem", "test-scenarios"],
        "max_model_calls": 4,
        "max_total_tokens": 55000,
        "model": "inherit",
        "max_output_tokens": None,
    },
}

UPSTREAM_PM_SKILL_SHA256 = {
    "beachhead-segment": "a3f94e98c05315938ad80d5e2103eab70096abfa40881dfb2c22a731d923ea5f",
    "brainstorm-experiments-new": "fe66d9ba76cf6b0e156298c88f752d8e1e62549fe77a7c01c0a74d8679da9334",
    "competitor-analysis": "8e627fc7fba96f223ad9f8fd23c6033a429cc28f9e9ce2d672854c6851810c2b",
    "customer-journey-map": "656c0e16318b3b24870065a8eabb8a116b72e47c167472836ce76ea97ec5c75e",
    "gtm-motions": "b26db17f9eee4f04aa3d53bf3c393da0574a3fa54d59eb7427e0cf5edf2377c3",
    "gtm-strategy": "fcc7c24dda6b4fec94d1d847e0ba2b42cff38b5ec6215bb1749a65d8b885f91e",
    "ideal-customer-profile": "8d434df786db2290efb575f1d219c7e19650e7a7e3df9a5f4b82b0bd0d2ce298",
    "identify-assumptions-new": "962b1e0c01e45ceb930e4d806c0ffb05e36cf25dcfef5497e7828d89d6ae474b",
    "market-segments": "f8425da0486d844a661fe18f809de1e055d7125c74ed423ee750cf2be74a2319",
    "market-sizing": "96d1250ba0ab7e5b64c9be8278f63f9661b510237e423b42ef70ab914184faf8",
    "marketing-ideas": "83242a3a8f5feae768820fee5ae8f4b6b4f7eaf12c8a450c49b134995bd76a89",
    "positioning-ideas": "8864f284e66c8bb106c46dc5e51656a47ae4792e39091eb3a49f63cde00c3850",
    "pre-mortem": "4e5cf10a46ac1d1cdde6aa009ba2b860c532f55c0c3d9ec53a82082cad073052",
    "pricing-strategy": "09321c5984f3654077bd58921ec4b7235f47e00caf44445bd2e5a5ed13bcb895",
    "prioritize-assumptions": "18160a0138c788790c9dd22995ffdcfac485c1f0599c170d8668678e59766073",
    "product-name": "16d715bbe6ab07b024a63a1a38f3616a3d9602bf4ca9425e1bb33496becce0b3",
    "sentiment-analysis": "516357ba8366845d13c4ee17acf96884571ad0fc8d3d48a2809c5cb84c95a01c",
    "strategy-red-team": "3758fcf6f2f2653721c9d58586f7816e17d47d4723b54a5d3457a6641d2663fc",
    "test-scenarios": "2dc10ebb6359604275f26234d3c66c9ccc952e501ad5b685c23a5c0f34f634d4",
    "user-segmentation": "d91f745c9520e6a31c07e37c14bfa01e7982570e30a398be71cf324ac93be9c8",
    "value-prop-statements": "5f4e89542439b16d18af608d91d0a319c0e66a6d89257da38d6652a655aae5bc",
    "value-proposition": "b07cc0399582fc178be31b513b313d2420c7941dd568b52a0bf6cfb0ab6c4ec7",
}


def test_ecom_launch_retains_four_bounded_specialist_definitions() -> None:
    config = yaml.safe_load((REPO_ROOT / "config.yaml").read_text(encoding="utf-8"))
    custom_agents = config["subagents"]["custom_agents"]

    assert set(custom_agents) == set(EXPECTED_SUBAGENTS)
    assert "growth-analyst" not in custom_agents

    for name, expected in EXPECTED_SUBAGENTS.items():
        assert custom_agents[name]["tools"] == expected["tools"]
        assert custom_agents[name]["skills"] == expected["skills"]
        assert custom_agents[name]["model"] == expected["model"]
        assert custom_agents[name]["max_turns"] == 50
        assert custom_agents[name]["timeout_seconds"] <= 150
        assert custom_agents[name]["max_model_calls"] == expected["max_model_calls"]
        assert custom_agents[name]["max_total_tokens"] == expected["max_total_tokens"]
        assert custom_agents[name].get("max_output_tokens") == expected["max_output_tokens"]

    researcher_prompt = custom_agents["market-voc-researcher"]["system_prompt"]
    assert "at most 2 web_search" in researcher_prompt
    assert "at most two tool rounds" in researcher_prompt
    assert "under 1200 Chinese characters" in researcher_prompt
    assert "do not repeat similar queries" in researcher_prompt
    assert "last30days" not in researcher_prompt
    assert "exact source URL" in researcher_prompt
    assert "Search snippets and generic source names are discovery aids" in researcher_prompt
    assert "web_search" not in custom_agents["offer-architect"]["tools"]
    assert "web_search" not in custom_agents["asset-studio"]["tools"]
    assert "first-person usage history" in custom_agents["asset-studio"]["system_prompt"]
    assert "consumer copy may state only the category, target price, user problem, and validation question" in custom_agents["asset-studio"]["system_prompt"]
    assert custom_agents["evidence-checker"]["tools"] == ["read_file", "grep", "web_fetch"]
    assert "exact final files" in custom_agents["evidence-checker"]["system_prompt"]
    assert "observed_public entries without direct source URLs" in custom_agents["evidence-checker"]["system_prompt"]
    assert "one targeted web_fetch batch" in custom_agents["evidence-checker"]["system_prompt"]
    assert "reserve the next model response for the final verdict" in custom_agents["evidence-checker"]["system_prompt"]
    assert "never return conditional pass" in custom_agents["evidence-checker"]["system_prompt"]


def test_opensku_launch_soul_is_shallow_and_mode_agnostic() -> None:
    soul = (REPO_ROOT / "agents" / "ecom-launch" / "SOUL.md").read_text(encoding="utf-8")

    assert len(soul.splitlines()) <= 12
    assert "默认直接回答" in soul
    assert "OpenSKU Launch Team" in soul
    assert "DeerFlow" not in soul
    assert "growth-analyst" not in soul
    assert "launch-war-room.html" not in soul
    assert "Flash 用单智能体直接生成" in soul
    assert "不能停止交付" in soul


def test_ecom_launch_skill_uses_minimum_needed_workflow() -> None:
    skill = (REPO_ROOT / "skills" / "custom" / "ecom-launch" / "SKILL.md").read_text(encoding="utf-8")
    frontmatter = yaml.safe_load(skill.split("---", 2)[1])

    assert "Choose the smallest useful scope" in skill
    assert "Do not call all specialists by default" in skill
    assert "short prioritization question" in skill
    assert "Maximum useful concurrency is two" in skill
    assert frontmatter["allowed-tools"] == [
        "read_file",
        "grep",
        "write_file",
        "render_launch_pack",
        "str_replace",
        "present_files",
        "task",
        "ask_clarification",
    ]
    assert "The OpenSKU Launch Team itself must not repeat or extend that web research" in skill
    assert "complete Launch Validation Pack only when the user explicitly asks" in skill
    assert "call each specialist type at most once" in skill
    assert "minimum specialist sequence is mandatory" in skill
    assert "Never schedule dependent specialists in the same tool-call batch" in skill
    assert "10 KB or less" in skill
    assert "no more than two model turns" in skill
    assert "never silently switch geography" in skill
    assert "Do not create extra files outside the standard set" in skill
    assert "currently disabled for the OpenSKU Launch Team" in skill
    assert "Do not call it" in skill
    assert "未经过独立 Evidence Checker 审计" in skill
    assert "[待确认]" in skill
    assert "direct `source_urls` list" in skill
    assert "first-person usage story" in skill
    assert "URL checks validate only HTTP(S) syntax" in skill
    assert "fake listings" in skill
    assert "end with a question" in skill
    assert "stop" in skill.lower()
    assert "growth-analyst" not in skill
    assert "last30days" not in skill
    assert "No store dataset is a supported concept-validation input" in skill
    assert "If public search is also unavailable" in skill
    assert "Ultra" not in skill
    assert "calibrate-content" not in skill


def test_ecom_launch_agent_loads_only_its_router_skill() -> None:
    config = yaml.safe_load((REPO_ROOT / "agents" / "ecom-launch" / "config.yaml").read_text(encoding="utf-8"))

    assert config["name"] == "ecom-launch"
    assert config["skills"] == ["ecom-launch"]
    assert config["memory_enabled"] is False
    assert config["run_budget"] == {
        "max_lead_model_calls": 20,
        "max_subagent_calls": 3,
        "max_total_tokens": 500000,
        "max_execution_seconds": 270,
        "deduplicate_subagents": True,
        "allowed_subagent_types": [
            "market-voc-researcher",
            "offer-architect",
            "asset-studio",
        ],
        "subagent_dependencies": {
            "offer-architect": ["market-voc-researcher"],
            "asset-studio": ["offer-architect"],
        },
        "direct_answer_patterns": [
            "(?:最先|首先|第一步|优先).{0,32}(?:验证|假设|测试|检查|改进)",
            "(?:哪一个|哪个|什么).{0,32}(?:假设|风险|指标|问题).{0,16}(?:最先|优先|先)",
            "(?:what|which).{0,40}(?:first|priority|hypothesis|risk)",
        ],
        "direct_answer_exclude_patterns": ["公开信号|公开数据|公开信息|网页|搜索|调研|研究|竞品|来源|链接|最新|上传|文件|完整|Launch Validation Pack|报告"],
        "complete_workflow_patterns": [
            "Launch Validation Pack",
            "完整.{0,16}(?:验证包|上市包|七件套|7\\s*件)",
            "7\\s*天.{0,20}(?:验证包|Pack)",
        ],
        "required_completed_subagents": [
            "market-voc-researcher",
            "offer-architect",
            "asset-studio",
        ],
        "compact_write_file_history": True,
        "required_output_files": [
            "launch-war-room.html",
            "evidence-ledger.json",
            "competitor-table.csv",
            "positioning-brief.md",
            "listing-pack.md",
            "content-pack.md",
            "launch-calendar.csv",
        ],
        "auto_present_complete_pack": True,
        "require_evidence_checker": False,
        "validate_pack_before_evidence": False,
        "validate_pack_before_present": True,
    }
    assert "content-calibration" not in config["skills"]


def test_vendored_pm_skills_match_pinned_upstream() -> None:
    assert {skill_name for specialist in EXPECTED_SUBAGENTS.values() for skill_name in specialist["skills"]} <= set(UPSTREAM_PM_SKILL_SHA256)

    for skill_name, expected_sha256 in UPSTREAM_PM_SKILL_SHA256.items():
        skill_path = PM_SKILLS_ROOT / skill_name / "SKILL.md"
        license_path = PM_SKILLS_ROOT / skill_name / "LICENSE.txt"

        skill_text = skill_path.read_text(encoding="utf-8")
        actual_sha256 = hashlib.sha256(skill_text.encode()).hexdigest()
        license_text = license_path.read_text(encoding="utf-8")

        assert actual_sha256 == expected_sha256, f"{skill_name} diverged from phuryn/pm-skills commit {UPSTREAM_COMMIT}"
        assert f"name: {skill_name}" in skill_text
        assert "Copyright (c) 2026 Pawel Huryn" in license_text
        assert "Permission is hereby granted" in license_text


def test_example_and_documented_subagent_configs_match_the_four_role_contract() -> None:
    example_text = (REPO_ROOT / "config.example.yaml").read_text(encoding="utf-8")
    documented = yaml.safe_load((REPO_ROOT / "docs" / "opensku-launch" / "subagents.ecom-launch.yaml").read_text(encoding="utf-8"))

    for name in EXPECTED_SUBAGENTS:
        assert name in example_text

    assert "growth-analyst" not in example_text
    assert set(documented["subagents"]["custom_agents"]) == set(EXPECTED_SUBAGENTS)


# ── flash_skills / openskufast contracts ──────────────────────────


def test_ecom_launch_has_flash_skills() -> None:
    config = yaml.safe_load((REPO_ROOT / "agents" / "ecom-launch" / "config.yaml").read_text(encoding="utf-8"))
    assert config["flash_skills"] is not None
    assert len(config["flash_skills"]) == 5


def test_flash_skills_match_pm_skills_dir() -> None:
    config = yaml.safe_load((REPO_ROOT / "agents" / "ecom-launch" / "config.yaml").read_text(encoding="utf-8"))
    existing = {d.name for d in PM_SKILLS_ROOT.iterdir() if d.is_dir()}
    assert set(config["flash_skills"]).issubset(existing)


def test_openskufast_agent_config_loads() -> None:
    openskufast_dir = REPO_ROOT / "agents" / "openskufast"
    cfg_file = openskufast_dir / "config.yaml"
    assert cfg_file.is_file()
    cfg = yaml.safe_load(cfg_file.read_text(encoding="utf-8"))
    assert cfg["name"] == "openskufast"
    assert cfg["tool_groups"] == ["web", "file:read", "file:write"]
    assert len(cfg["skills"]) == 22
    assert set(cfg["skills"]) == {d.name for d in PM_SKILLS_ROOT.iterdir() if d.is_dir()}
    rb = cfg["run_budget"]
    assert rb["max_lead_model_calls"] == 16
    assert rb["max_total_tokens"] == 250000
    assert rb["complete_pack_initial_research_calls"] == 2
    assert rb["compact_write_file_history"] is True


def test_flash_and_ultra_share_short_question_routing_contract() -> None:
    launch = yaml.safe_load((REPO_ROOT / "agents" / "ecom-launch" / "config.yaml").read_text(encoding="utf-8"))
    flash = yaml.safe_load((REPO_ROOT / "agents" / "openskufast" / "config.yaml").read_text(encoding="utf-8"))

    assert flash["run_budget"]["direct_answer_patterns"] == launch["run_budget"]["direct_answer_patterns"]
    assert flash["run_budget"]["direct_answer_exclude_patterns"] == launch["run_budget"]["direct_answer_exclude_patterns"]


def test_openskufast_soul_exists() -> None:
    soul = (REPO_ROOT / "agents" / "openskufast" / "SOUL.md").read_text(encoding="utf-8")
    assert len(soul) > 50
    assert "OpenSKU" in soul


def test_flash_skills_runtime_swap() -> None:
    from deerflow.agents.lead_agent.agent import _available_skill_names
    from deerflow.config.agents_config import AgentConfig

    cfg = AgentConfig(
        name="ecom-launch",
        skills=["ecom-launch"],
        flash_skills=["beachhead-segment", "competitor-analysis"],
    )
    assert cfg.flash_skills is not None
    # The runtime swap is tested via _available_skill_names in agent.py;
    # here we verify the config carries both fields.
    assert cfg.skills == ["ecom-launch"]
    assert cfg.flash_skills == ["beachhead-segment", "competitor-analysis"]
    assert _available_skill_names(cfg, False, runtime_config={"mode": "flash"}) == {
        "ecom-launch",
        "beachhead-segment",
        "competitor-analysis",
    }
