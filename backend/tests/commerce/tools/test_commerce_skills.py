"""Commerce Skill discovery and deterministic Tool policy contracts."""

from __future__ import annotations

from pathlib import Path

from deerflow.config import get_app_config
from deerflow.skills.storage import get_or_new_skill_storage
from deerflow.skills.tool_policy import allowed_tool_names_for_skills

REPO_ROOT = Path(__file__).parents[4]

COMMERCE_SKILLS = {
    "fulfillment-investigation",
    "seller-peer-analysis",
    "review-experience-diagnosis",
    "commerce-diagnostic-synthesis",
}

COMMERCE_TOOLS = {
    "commerce_ingest_uploads",
    "commerce_list_datasets",
    "commerce_select_dataset",
    "commerce_dataset_profile",
    "commerce_capabilities",
    "commerce_list_entities",
    "commerce_metric_snapshot",
    "commerce_compare_windows",
    "commerce_peer_comparison",
    "commerce_geographic_segments",
    "commerce_evidence_query",
}


def test_commerce_skills_are_discovered_enabled_and_chinese_first():
    skills = get_or_new_skill_storage(app_config=get_app_config()).load_skills(enabled_only=True)
    by_name = {skill.name: skill for skill in skills}

    assert COMMERCE_SKILLS.issubset(by_name)
    for name in COMMERCE_SKILLS:
        skill = by_name[name]
        assert skill.allowed_tools is not None
        assert "commerce_" in skill.skill_file.read_text(encoding="utf-8")
        assert any("\u4e00" <= character <= "\u9fff" for character in skill.description)


def test_enabled_skill_policy_keeps_commerce_and_durable_subagent_tools_available():
    skills = get_or_new_skill_storage(app_config=get_app_config()).load_skills(enabled_only=True)
    allowed = allowed_tool_names_for_skills(skills)

    assert allowed is not None
    assert COMMERCE_TOOLS.issubset(allowed)
    assert {
        "spawn_task",
        "wait_task",
        "follow_up_task",
        "cancel_task",
        "resume_task",
    }.issubset(allowed)


def test_domain_skills_are_read_only_and_do_not_bypass_action_approval():
    skills = get_or_new_skill_storage(app_config=get_app_config()).load_skills(enabled_only=True)
    commerce = [skill for skill in skills if skill.name in COMMERCE_SKILLS]

    forbidden = {
        "bash",
        "write_file",
        "str_replace",
        "skill_manage",
        "write_opensku_artifact_bundle",
    }
    for skill in commerce:
        assert forbidden.isdisjoint(skill.allowed_tools or ())


def test_review_and_peer_skills_freeze_minimal_tool_round_plans():
    skill_root = REPO_ROOT / "skills" / "custom"
    review = (skill_root / "review-experience-diagnosis" / "SKILL.md").read_text(encoding="utf-8")
    peer = (skill_root / "seller-peer-analysis" / "SKILL.md").read_text(encoding="utf-8")

    assert "两轮以内" in review
    assert "一次 `commerce_compare_windows`" in review
    assert "一次 `commerce_evidence_query`" in review
    assert "不再用 `commerce_metric_snapshot` 重算" in review
    assert "ContextPacket" in review and "max_tool_rounds" in review

    assert "三轮以内" in peer
    assert "一次 `commerce_peer_comparison`" in peer
    assert "一次 `commerce_geographic_segments`" in peer
    assert "一次 `commerce_evidence_query`" in peer
    assert "不重复调用" in peer
    assert "ContextPacket" in peer and "max_tool_rounds" in peer
    assert "只表示当前响应的 Fact ID 预览被截断" in peer
    assert "不写“显著高于/显著差异”" in peer


def test_fulfillment_skill_freezes_minimal_metric_and_evidence_claims():
    skill = (REPO_ROOT / "skills" / "custom" / "fulfillment-investigation" / "SKILL.md").read_text(encoding="utf-8")

    assert "默认通过 `metric_names` 只请求以上四项" in skill
    assert "半开区间 `[start, end)`" in skill
    assert "`baseline_end == current_start`" in skill
    assert "不得减一天" in skill
    assert "不得改成当天 `23:59:59`" in skill
    assert "include_column_details=false" in skill
    assert "不能写成“排除了卖家处理流程/卖家自身原因”" in skill
    assert "不得从少量样本升级为“计算可靠”" in skill
