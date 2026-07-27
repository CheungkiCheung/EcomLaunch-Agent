from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT_DIR = REPO_ROOT / "agents" / "commerce-agent"
APP_CONFIG = REPO_ROOT / "config.yaml"


def test_builtin_commerce_agent_has_scoped_tools_and_skills():
    config = yaml.safe_load((AGENT_DIR / "config.yaml").read_text(encoding="utf-8"))

    assert config == {
        "name": "commerce-agent",
        "description": "中文 Chat-first 电商经营诊断与行动 Agent",
        "model": "deepseek-reasoner",
        "subagent_required": True,
        "subagent_complexity_tool_call_threshold": 2,
        "required_subagent_types": ["analyst", "verifier"],
        "subagent_requirement_recovery_mode": "force_dispatch",
        "max_subagent_requirement_recovery_attempts": 8,
        "max_concurrent_subagents": 3,
        "max_subagent_tasks_per_run": 6,
        "max_failed_subagent_tasks_per_run": 2,
        "max_parent_direct_tool_calls": 3,
        "max_parent_direct_tool_rounds": 2,
        "require_explicit_subagent_scope": True,
        "todo_list_enabled": False,
        "memory_enabled": False,
        "model_generated_title": False,
        "local_title_rules": [
            {
                "keywords": ["履约", "延迟", "晚到", "配送"],
                "title": "订单履约异常诊断",
            },
            {
                "keywords": ["评价", "评论", "评分"],
                "title": "商品评价体验诊断",
            },
            {
                "keywords": ["对标", "同类", "同行"],
                "title": "卖家同类对标分析",
            },
            {
                "keywords": ["数据", "字段", "能力"],
                "title": "电商数据能力检查",
            },
        ],
        "local_title_fallback": "电商经营数据诊断",
        "subagent_scope_rules": [
            {
                "name": "fulfillment-coverage",
                "subagent_type": "explore",
                "match_skills_all": ["fulfillment-investigation"],
                "enforced_skills": ["fulfillment-investigation"],
                "enforced_tools": [
                    "commerce_capabilities",
                    "commerce_list_entities",
                    "commerce_seller_coverage",
                ],
                "prompt_suffix": (
                    "实体解析合同：如果 Prompt 没有给出 seller_id，先用 "
                    "`commerce_list_entities` 查询 seller；只有一个候选时使用其 "
                    "`external_key`，不得向用户追问内部 ID。"
                    "`commerce_seller_coverage` 在 Dataset 恰好只有一个卖家时也允许"
                    "省略 seller_id 自动选择。"
                ),
                "max_tool_rounds": 3,
                "max_tool_calls": 3,
            },
            {
                "name": "fulfillment-geography",
                "subagent_type": "analyst",
                "match_skills_all": ["fulfillment-investigation"],
                "prompt_keywords_any": ["地域", "区域"],
                "enforced_skills": ["fulfillment-investigation"],
                "enforced_tools": [
                    "commerce_seller_coverage",
                    "commerce_geographic_segments",
                ],
                "prompt_suffix": (
                    "地域 Tool 合同：`commerce_geographic_segments` 每次只接受一个"
                    "半开区间的 `start` 和 `end`，不接受 `metric_names`、baseline/"
                    "current 复合参数。需要比较两个窗口时最多调用两次，并明确地域"
                    "分段只能描述集中现象，不能归因给承运商。用户没有要求地域定位"
                    "时，不得把本任务当作核心终答的前置条件。"
                ),
                "max_tool_rounds": 2,
                "max_tool_calls": 3,
            },
            {
                "name": "fulfillment-window",
                "subagent_type": "analyst",
                "match_skills_all": ["fulfillment-investigation"],
                "enforced_skills": ["fulfillment-investigation"],
                "enforced_tools": [
                    "commerce_capabilities",
                    "commerce_list_entities",
                    "commerce_seller_coverage",
                    "commerce_compare_windows",
                    "commerce_evidence_query",
                ],
                "prompt_suffix": (
                    "实体与时间窗口权威合同：如果 Prompt 没有给出 seller_id，先用 "
                    "`commerce_list_entities` 查询 seller；只有一个候选时使用其 "
                    "`external_key`，不得向用户追问内部 ID。"
                    "`commerce_seller_coverage` 在 Dataset 恰好只有一个卖家时也允许"
                    "省略 seller_id 自动选择。`commerce_compare_windows` 使用半开区间 "
                    "`[start, end)`，结束时间是排他边界。相邻窗口必须保持 "
                    "`baseline_end == current_start`。如果用户没有指定窗口，先调用"
                    "一次 `commerce_seller_coverage`，原样使用返回的 "
                    "`default_recent_windows`；不得心算、自造或移动边界，并在结果中"
                    "披露使用了默认近期窗口。"
                ),
                "max_tool_rounds": 4,
                "max_tool_calls": 5,
            },
            {
                "name": "fulfillment-verifier",
                "subagent_type": "verifier",
                "match_skills_all": ["fulfillment-investigation"],
                "enforced_skills": ["fulfillment-investigation"],
                "enforced_tools": ["commerce_evidence_query"],
                "inherit_source_tools": True,
                "prompt_suffix": (
                    "时间窗口权威合同：`commerce_compare_windows` 使用半开区间 "
                    "`[start, end)`，结束时间是排他边界。本合同覆盖任务和 source "
                    "snapshot 中“含两端”等冲突措辞。相邻窗口必须保持 "
                    "`baseline_end == current_start`；必须按 source_refs 对应任务的"
                    "原始 ISO-8601 边界独立重算，不得继承其边界调整，也不得减一天、"
                    "加一天、改成当天 `23:59:59` 或自行移动边界。"
                ),
                "max_tool_rounds": 3,
                "max_tool_calls": 4,
            },
        ],
        "final_answer_forbidden_phrases": [
            "根因是",
            "主因",
            "导致",
            "造成",
            "压垮",
            "完全排除",
            "唯一主要驱动",
            "责任区间",
        ],
        "max_final_answer_repairs": 1,
        "tool_groups": ["commerce", "file:read"],
        "skills": [
            "fulfillment-investigation",
            "seller-peer-analysis",
            "review-experience-diagnosis",
            "commerce-diagnostic-synthesis",
        ],
    }


def test_builtin_commerce_agent_soul_freezes_product_and_evidence_boundaries():
    soul = (AGENT_DIR / "SOUL.md").read_text(encoding="utf-8")

    required_phrases = (
        "始终使用中文",
        "动态派遣 0–N 个 Subagent",
        "不使用固定 Crew",
        "确定性 Tool",
        "支持证据",
        "反证",
        "unknown",
        "相关性不能写成因果",
        "人工审批",
        "fresh-context Verifier",
        "Goal、Budget、Stop Condition",
        "GMV、CTR、CVR、ROI、利润、库存",
        "每次 `spawn_task` 都必须显式传入非空 `skills`、`tools`",
        "不要使用 `write_todos`",
        "不携带任何 Tool Call",
        "半开区间 `[start, end)`",
        "不得写“含两端”",
        "最近履约怎么了",
        "不要因为用户没有说“窗口、核验、重算”",
    )

    for phrase in required_phrases:
        assert phrase in soul


def test_commerce_subagent_profiles_have_enforced_tool_call_envelopes():
    config = yaml.safe_load(APP_CONFIG.read_text(encoding="utf-8"))
    profiles = config["subagents"]["custom_agents"]

    assert {
        name: {
            "max_tool_rounds": profiles[name]["max_tool_rounds"],
            "max_tool_calls": profiles[name]["max_tool_calls"],
        }
        for name in ("explore", "analyst", "verifier", "operator")
    } == {
        "explore": {"max_tool_rounds": 4, "max_tool_calls": 4},
        "analyst": {"max_tool_rounds": 4, "max_tool_calls": 6},
        "verifier": {"max_tool_rounds": 3, "max_tool_calls": 5},
        "operator": {"max_tool_rounds": 2, "max_tool_calls": 4},
    }

    for name in ("explore", "analyst", "verifier", "operator"):
        prompt = profiles[name]["system_prompt"]
        assert "ContextPacket.available_tools" in prompt
        assert "不得尝试未授权 Tool" in prompt
        assert "不要使用 Markdown 表格" in prompt
        assert "最终输出不超过" in prompt

    assert {name: profiles[name]["max_output_tokens"] for name in ("explore", "analyst", "verifier", "operator")} == {
        "explore": 3200,
        "analyst": 3600,
        "verifier": 3200,
        "operator": 1600,
    }


def test_fulfillment_skills_require_exact_coverage_and_scoped_dispatch():
    fulfillment = (REPO_ROOT / "skills" / "custom" / "fulfillment-investigation" / "SKILL.md").read_text(encoding="utf-8")
    synthesis = (REPO_ROOT / "skills" / "custom" / "commerce-diagnostic-synthesis" / "SKILL.md").read_text(encoding="utf-8")

    assert "commerce_seller_coverage" in fulfillment
    assert "default_recent_windows" in fulfillment
    assert "最近履约怎么了" in fulfillment
    assert "不得使用 evidence_query 抽样推断最早/最晚订单时间" in fulfillment
    assert "`baseline_end == current_start`" in fulfillment
    assert "commerce_seller_coverage" in synthesis
    assert 'skills=["fulfillment-investigation"]' in synthesis
    assert 'tools=["commerce_compare_windows"' in synthesis
    assert "read_file" in synthesis
    assert "必须在同一个模型响应中并行拆为 `explore` 和 `analyst`" in synthesis
    assert "Parent 不再直接调用覆盖或窗口计算 Tool" in synthesis


def test_commerce_scope_config_preserves_authoritative_prompt_suffix():
    from deerflow.config.agents_config import load_agent_config

    config = load_agent_config("commerce-agent")

    assert config is not None
    rules = {rule.name: rule for rule in config.subagent_scope_rules}
    assert "[start, end)" in rules["fulfillment-window"].prompt_suffix
    assert "baseline_end == current_start" in rules["fulfillment-verifier"].prompt_suffix
    assert rules["fulfillment-coverage"].prompt_keywords_any == []
    assert rules["fulfillment-geography"].prompt_keywords_any == ["地域", "区域"]
    assert rules["fulfillment-window"].prompt_keywords_any == []
    assert rules["fulfillment-verifier"].prompt_keywords_any == []


def test_runtime_title_prompt_requires_a_chinese_product_title():
    config = yaml.safe_load(APP_CONFIG.read_text(encoding="utf-8"))
    prompt = config["title"]["prompt_template"]

    assert "中文标题" in prompt
    assert "只返回标题" in prompt
    assert "不要使用英文句子" in prompt
